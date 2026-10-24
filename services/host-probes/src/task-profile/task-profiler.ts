/** How is one actual task wrapped without sampling a disabled or replayed call? */
import { Worker } from "node:worker_threads";
import type { ProbeConfig } from "../config";
import type { ProbeContext } from "../probe/proc-reader";
import { CollectorInputSchema, CollectorMessageSchema } from "./profile-schema";
import type { OwnedProcess, TaskEndReason, TaskIdentity, TaskOutcome, TaskProfile } from "./profile-schema";
import { resolveClockTicks } from "./clock-ticks";
import { ProcessPinError, verifyProcessPin } from "./process-stat";

export type TaskProfiling = {
  config: ProbeConfig;
  report: (profile: TaskProfile) => void | Promise<void>;
  target?: OwnedProcess;
  server?: OwnedProcess;
  context?: ProbeContext;
};

export type TaskProfileResult = { profile: TaskProfile } | { error: Error };
export type TaskProfileSession = {
  target: OwnedProcess | null;
  expires_at: string | null;
  settled: Promise<TaskProfileResult>;
  close: (outcome: TaskOutcome, reason?: TaskEndReason) => Promise<TaskProfile>;
};

async function withinDeadline<T>(work: Promise<T>, deadline: number, message: string): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      work,
      new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(new Error(message)), Math.max(0, deadline - performance.now()));
      }),
    ]);
  } finally { clearTimeout(timer); }
}

export async function startTaskProfile(
  options: TaskProfiling, identity: TaskIdentity,
  controls: { signal?: AbortSignal; expiresAfterMs?: number } = {},
): Promise<TaskProfileSession | null> {
  if (!options.config.task_profile.enabled) return null;
  controls.signal?.throwIfAborted();
  if (options.target !== undefined) verifyProcessPin(options.target, options.config.max_proc_bytes, options.context ?? {});
  const clock_ticks_per_second = await resolveClockTicks(options.config);
  controls.signal?.throwIfAborted();
  const input = CollectorInputSchema.parse({
    identity, config: options.config.task_profile, max_proc_bytes: options.config.max_proc_bytes,
    worker_pid: options.target?.pid ?? process.pid, target: options.target ?? null,
    clock_ticks_per_second, expires_after_ms: controls.expiresAfterMs ?? null,
    server: options.server ?? null, context: options.context ?? {},
  });
  const worker = new Worker(new URL("./collector.worker.ts", import.meta.url), { workerData: input });
  let terminating: ReturnType<Worker["terminate"]> | undefined;
  const terminate = () => terminating ??= worker.terminate();
  type Ready = Pick<TaskProfileSession, "target" | "expires_at">;
  let ready: (value: Ready) => void;
  let failedStart: (error: Error) => void;
  const started = new Promise<Ready>((resolve, reject) => { ready = resolve; failedStart = reject; });
  let resolveFinished: (result: TaskProfileResult) => void;
  const finished = new Promise<TaskProfileResult>(resolve => { resolveFinished = resolve; });
  let completionDeadline: number | undefined;
  const finish = (result: TaskProfileResult) => {
    completionDeadline ??= performance.now() + input.config.lifecycle_timeout_ms;
    resolveFinished(result);
  };
  let received = false;
  const fail = (error: Error) => {
    received = true;
    failedStart(error);
    finish({ error });
  };
  worker.on("message", (raw: unknown) => {
    const message = CollectorMessageSchema.safeParse(raw);
    if (!message.success) { fail(new Error("Task collector returned invalid metadata")); return; }
    if (message.data.type === "ready") ready({ target: message.data.target, expires_at: message.data.expires_at });
    else if (message.data.type === "rejected") fail(new ProcessPinError(message.data.reason));
    else { received = true; finish({ profile: message.data.profile }); }
  });
  worker.once("error", error => fail(new Error("Task profile collector failed", { cause: error })));
  worker.once("exit", () => {
    if (!received) fail(new Error("Task profile collector exited without a closing observation"));
  });
  const timeout = setTimeout(() => fail(new Error("Task profile collector startup timed out")), input.config.lifecycle_timeout_ms);
  const abort = () => fail(new Error("Task profile start aborted", { cause: controls.signal?.reason }));
  controls.signal?.addEventListener("abort", abort, { once: true });
  if (controls.signal?.aborted) abort();
  let details: Ready;
  try { details = await started; }
  catch (error) {
    try {
      await withinDeadline(terminate(), performance.now() + input.config.lifecycle_timeout_ms,
        "Task profile startup cleanup timed out");
    } catch (cleanup) {
      throw new AggregateError([error, cleanup], "Task profile startup and cleanup failed");
    }
    throw error;
  }
  finally { clearTimeout(timeout); controls.signal?.removeEventListener("abort", abort); }
  const settled = (async (): Promise<TaskProfileResult> => {
    let result = await finished;
    const deadline = completionDeadline ??= performance.now() + input.config.lifecycle_timeout_ms;
    try { await withinDeadline(terminate(), deadline, "Task profile collector cleanup timed out"); }
    catch (error) {
      result = { error: new AggregateError("error" in result ? [result.error, error] : [error], "Task collector cleanup failed") };
    }
    if ("profile" in result) {
      const profile = result.profile;
      try {
        await withinDeadline(Promise.resolve().then(() => options.report(profile)), deadline, "Task profile reporting timed out");
      } catch (error) {
        result = { error: error instanceof Error ? error : new Error("Task profile reporting failed", { cause: error }) };
      }
    }
    return result;
  })();
  let closing: Promise<TaskProfile> | undefined;
  return {
    ...details, settled,
    close(outcome, end_reason = "task_settled") {
      closing ??= (async () => {
        completionDeadline ??= performance.now() + input.config.lifecycle_timeout_ms;
        const timeout = setTimeout(() => fail(new Error("Task profile collector shutdown timed out")),
          Math.max(0, completionDeadline - performance.now()));
        try {
          if (!received) {
            try { worker.postMessage({ outcome, end_reason }); }
            catch (error) { fail(new Error("Task profile close command failed", { cause: error })); }
          }
          const result = await settled;
          if ("error" in result) throw result.error;
          return result.profile;
        } finally {
          clearTimeout(timeout);
        }
      })();
      return closing;
    },
  };
}

export async function profileTask<T>(
  options: TaskProfiling | undefined, identity: TaskIdentity, work: () => T | Promise<T>,
  controls: { signal?: AbortSignal; outcome?: (value: T) => TaskOutcome } = {},
): Promise<T> {
  if (options === undefined || !options.config.task_profile.enabled) return work();
  controls.signal?.throwIfAborted();
  const watcher = await startTaskProfile(options, identity, controls.signal === undefined ? {} : { signal: controls.signal });
  let outcome: TaskOutcome = "error";
  let failure: { error: unknown } | undefined;
  try {
    controls.signal?.throwIfAborted();
    const value = await work();
    outcome = controls.outcome?.(value) ?? "success";
    return value;
  } catch (error) {
    failure = { error };
    throw error;
  } finally {
    try { await watcher?.close(controls.signal?.aborted ? "cancelled" : outcome); }
    catch (error) {
      if (failure) throw new AggregateError([failure.error, error], "Task and resource collection failed");
      throw error;
    }
  }
}
