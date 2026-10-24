/** How is one actual task wrapped without sampling a disabled or replayed call? */
import { Worker } from "node:worker_threads";
import type { ProbeConfig } from "../config";
import type { ProbeContext } from "../probe/proc-reader";
import { CollectorInputSchema, CollectorMessageSchema } from "./profile-schema";
import type { OwnedProcess, TaskIdentity, TaskOutcome, TaskProfile } from "./profile-schema";

export type TaskProfiling = {
  config: ProbeConfig;
  report: (profile: TaskProfile) => void | Promise<void>;
  server?: OwnedProcess;
  context?: ProbeContext;
};

export async function startTaskProfile(
  options: TaskProfiling, identity: TaskIdentity,
): Promise<{ close: (outcome: TaskOutcome) => Promise<TaskProfile> } | null> {
  if (!options.config.task_profile.enabled) return null;
  const input = CollectorInputSchema.parse({
    identity, config: options.config.task_profile, max_proc_bytes: options.config.max_proc_bytes,
    worker_pid: process.pid, server: options.server ?? null, context: options.context ?? {},
  });
  const worker = new Worker(new URL("./collector.worker.ts", import.meta.url), { workerData: input });
  let ready: () => void;
  let failedStart: (error: Error) => void;
  const started = new Promise<void>((resolve, reject) => { ready = resolve; failedStart = reject; });
  type Result = { profile: TaskProfile } | { error: Error };
  let finish: (result: Result) => void;
  const finished = new Promise<Result>(resolve => { finish = resolve; });
  let received = false;
  const fail = (error: Error) => {
    failedStart(error);
    finish({ error });
  };
  worker.on("message", (raw: unknown) => {
    const message = CollectorMessageSchema.safeParse(raw);
    if (!message.success) { fail(new Error("Task collector returned invalid metadata")); return; }
    if (message.data.type === "ready") ready();
    else { received = true; finish({ profile: message.data.profile }); }
  });
  worker.once("error", error => fail(new Error("Task profile collector failed", { cause: error })));
  worker.once("exit", () => {
    if (!received) fail(new Error("Task profile collector exited without a closing observation"));
  });
  const timeout = setTimeout(() => fail(new Error("Task profile collector startup timed out")), input.config.lifecycle_timeout_ms);
  try { await started; }
  catch (error) { await worker.terminate(); throw error; }
  finally { clearTimeout(timeout); }
  let closing: Promise<TaskProfile> | undefined;
  return {
    close(outcome) {
      closing ??= (async () => {
        const timeout = setTimeout(() => finish({ error: new Error("Task profile collector shutdown timed out") }),
          input.config.lifecycle_timeout_ms);
        try {
          worker.postMessage({ outcome });
          const result = await finished;
          if ("error" in result) throw result.error;
          await options.report(result.profile);
          return result.profile;
        } finally {
          clearTimeout(timeout);
          await worker.terminate();
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
  const watcher = await startTaskProfile(options, identity);
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
