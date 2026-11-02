/** Keep one private-pipe HTTP child alive and close and reap only that owned process. */
import { createInterface } from "node:readline";
import { PlanError } from "../src/api/plan-request";
import type { ServiceSettings } from "../src/config/service-settings";
import { writeJsonLine } from "../src/logging/structured-logger";
import { describePlanError } from "../src/api/plan-request";
import { withPlannerFailure } from "../src/api/plan-failure";
import type { FailureCaptureOptions } from "../src/api/plan-failure";
import { retainFailureThroughCleanup } from "../src/api/retain-failure-through-cleanup";

type ChildKind = "PLANNER" | "SAFE_PERSIST";
type HttpServer = { stop(force?: boolean): Promise<void> };

async function beforeDeadline<T>(operation: Promise<T>, milliseconds: number, code: string): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([operation, new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new PlanError(code, code)), milliseconds);
    })]);
  } finally { clearTimeout(timer); }
}

async function readReady(stream: ReadableStream<Uint8Array>, limit: number, signal: AbortSignal, kind: ChildKind) {
  const reader = stream.getReader();
  const abort = () => { void reader.cancel(); };
  signal.addEventListener("abort", abort, { once: true });
  const decoder = new TextDecoder();
  let line = "";
  let bytes = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) throw new PlanError(`${kind}_READY_MISSING`, "HTTP child closed before readiness");
      bytes += value.byteLength;
      line += decoder.decode(value, { stream: true });
      if (bytes > limit) throw new PlanError(`${kind}_READY_INVALID`, "HTTP child readiness exceeded its byte limit");
      if (line.includes("\n")) {
        const message: unknown = JSON.parse(line.slice(0, line.indexOf("\n")));
        return message;
      }
    }
  } finally { signal.removeEventListener("abort", abort); reader.releaseLock(); }
}

export async function superviseHttpChild<T>(input: {
  root: string; serverEntry: string; startup: object; kind: ChildKind;
  settings: Pick<ServiceSettings, "listener" | "supervision">; signal?: AbortSignal;
  capture?: FailureCaptureOptions;
  ready: (message: unknown, pid: number, signal: AbortSignal) => Promise<string>;
  request: (base: string, signal: AbortSignal) => Promise<T>;
}) {
  const controls = input.settings.supervision;
  const cancellation = new AbortController();
  const signal = AbortSignal.any([cancellation.signal, ...(input.signal === undefined ? [] : [input.signal])]);
  signal.throwIfAborted();
  const child = Bun.spawn([process.execPath, input.serverEntry], {
    cwd: input.root, stdin: "pipe", stdout: "pipe", stderr: "inherit",
  });
  const unexpectedExit = child.exited.then(code => {
    throw new PlanError(`${input.kind}_CHILD_EXIT`, `HTTP child exited unexpectedly with status ${code}`);
  });
  // A losing race must still have a rejection handler after normal shutdown.
  void unexpectedExit.catch(() => {});
  const aborted = new Promise<never>((_, reject) => {
    signal.addEventListener("abort", () => reject(signal.reason), { once: true });
  });
  let completed = false;
  let original: PlanError | undefined;
  try {
    const startupReady = (async () => {
      child.stdin.write(`${JSON.stringify(input.startup)}\n`);
      await child.stdin.flush();
      return input.ready(await readReady(child.stdout, input.settings.listener.max_body_bytes, signal, input.kind), child.pid, signal);
    })();
    const base = await beforeDeadline(Promise.race([startupReady, unexpectedExit, aborted]),
      controls.readiness_timeout_ms, `${input.kind}_READY_TIMEOUT`);
    const result = await Promise.race([input.request(base, signal), unexpectedExit, aborted]);
    completed = true;
    return result;
  } catch (error) {
    original = withPlannerFailure(error, input.capture ?? { operation: "workflow" });
    throw original;
  } finally {
    const close = async () => {
      cancellation.abort(new Error("HTTP child supervisor stopped"));
      let pipeFailure: unknown;
      // EOF also closes the child if its supervisor disappears.
      const closingPipe = Promise.resolve().then(() => child.stdin.end()).catch(error => {
        if (!(error instanceof Error) || !("code" in error) || !["EPIPE", "ERR_STREAM_DESTROYED"].includes(String(error.code))) pipeFailure = error;
      });
      let cleanupFailure: unknown;
      try {
        const [code] = await beforeDeadline(Promise.all([child.exited, closingPipe]),
          controls.shutdown_timeout_ms, `${input.kind}_SHUTDOWN_TIMEOUT`);
        if (completed && code !== 0) throw new PlanError(`${input.kind}_CHILD_EXIT`, `HTTP child shutdown failed with status ${code}`);
      } catch (error) {
        cleanupFailure = error;
        if (error instanceof PlanError && error.code === `${input.kind}_SHUTDOWN_TIMEOUT`) {
          writeJsonLine({ event: `${input.kind.toLowerCase()}_child_forced`, pid: child.pid });
          child.kill("SIGKILL");
          try { await beforeDeadline(child.exited, controls.forced_exit_timeout_ms, `${input.kind}_REAP_TIMEOUT`); }
          catch (reapError) { cleanupFailure = new AggregateError([error, reapError], "HTTP child could not be reaped"); }
        }
      }
      try { await child.stdout.cancel(); }
      catch (error) {
        cleanupFailure = cleanupFailure === undefined ? error
          : new AggregateError([cleanupFailure, error], "HTTP child drain and stream cleanup failed");
      }
      if (cleanupFailure !== undefined && pipeFailure !== undefined) {
        throw new AggregateError([cleanupFailure, pipeFailure], "HTTP child cleanup failed");
      }
      if (cleanupFailure !== undefined) throw cleanupFailure;
      if (pipeFailure !== undefined) throw pipeFailure;
    };
    if (original !== undefined) {
      throw await retainFailureThroughCleanup(original, input.capture ?? { operation: "workflow" }, [
        { operation: "listener-close", execute: close },
      ]);
    }
    await close();
  }
}

export async function runHttpChild(
  kind: ChildKind,
  prepare: (message: unknown) => {
    shutdownTimeoutMs: number;
    capture?: FailureCaptureOptions;
    start: (signal: AbortSignal) => Promise<{ server: HttpServer; ready: object }>;
  },
) {
  const lines = createInterface({ input: process.stdin, crlfDelay: Infinity });
  const cancellation = new AbortController();
  let server: HttpServer | undefined;
  let closing: Promise<void> | undefined;
  let shutdownMs: number | undefined;
  let forceTimer: ReturnType<typeof setTimeout> | undefined;
  let closed = false;
  let capture: FailureCaptureOptions = { operation: "listener-start" };
  let original: PlanError | undefined;
  const stop = () => {
    closed = true;
    cancellation.abort(new Error("HTTP child supervisor closed"));
    if (shutdownMs !== undefined) forceTimer ??= setTimeout(() => {
      writeJsonLine({ event: `${kind.toLowerCase()}_shutdown_forced` });
      void server?.stop(true).catch(error => writeJsonLine({
        event: `${kind.toLowerCase()}_forced_close_failed`, ...describePlanError(error, undefined, capture),
      }));
      process.exit(2);
    }, shutdownMs);
    const current = server;
    if (current === undefined) { lines.close(); return; }
    closing ??= (async () => {
      try { await current.stop(); }
      finally { lines.close(); }
    })();
    void closing.catch(() => {});
  };
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
  lines.once("close", stop);
  try {
    const line = await new Promise<string>((resolveLine, reject) => {
      lines.once("line", resolveLine);
      lines.once("close", () => reject(new PlanError(`${kind}_STARTUP_CLOSED`, "Startup pipe closed before startup")));
    });
    const message: unknown = JSON.parse(line);
    const prepared = prepare(message);
    capture = prepared.capture ?? capture;
    shutdownMs = prepared.shutdownTimeoutMs;
    if (closed) throw new PlanError(`${kind}_STARTUP_CLOSED`, "Supervisor left before listener startup");
    const started = await prepared.start(cancellation.signal);
    server = started.server;
    if (closed) {
      stop();
      throw new PlanError(`${kind}_STARTUP_CLOSED`, "Supervisor left before listener startup");
    }
    console.log(JSON.stringify(started.ready));
    await new Promise<void>(resolveClosed => {
      if (closed) resolveClosed();
      else lines.once("close", resolveClosed);
    });
    await closing;
  } catch (error) {
    original = withPlannerFailure(error, capture);
    console.log(JSON.stringify({
      event: `${kind.toLowerCase()}_startup_failed`,
      code: original.code,
      message: "HTTP child operation did not complete",
      failure: original.failure,
    }));
    throw original;
  } finally {
    try {
      const close = () => { stop(); return closing; };
      if (original !== undefined) throw await retainFailureThroughCleanup(original, capture, [
        { operation: "listener-close", execute: close },
      ]);
      await close();
    } finally {
      clearTimeout(forceTimer);
      lines.close();
      process.off("SIGINT", stop);
      process.off("SIGTERM", stop);
    }
  }
}
