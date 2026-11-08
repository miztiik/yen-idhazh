/** Keep one private-pipe HTTP child alive and close and reap only that owned process. */
import type { HttpChildFailure, HttpChildFailurePolicy, HttpChildKind } from "./http-child-failure";
import type { SupervisionSettings } from "./load-settings";
import type { ApiReady, ApiReadiness } from "./api-startup";
export type HttpChildObservation = {
  phase: "started" | "ready" | "startup_failed" | "stopping" | "stopped" | "forced" | "cleanup_failed";
  pid: number;
  exit_code?: number;
  identity?: ApiReady;
};

async function forwardDiagnostics(stream: ReadableStream<Uint8Array>, write: (line: string) => void) {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let pending = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      pending += done ? decoder.decode() : decoder.decode(value, { stream: true });
      let newline: number;
      while ((newline = pending.indexOf("\n")) !== -1) {
        write(pending.slice(0, newline));
        pending = pending.slice(newline + 1);
      }
      if (done) { if (pending !== "") write(pending); return; }
    }
  } finally { reader.releaseLock(); }
}

async function beforeDeadline<T>(operation: Promise<T>, milliseconds: number, error: () => Error): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([operation, new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(error()), milliseconds);
    })]);
  } finally { clearTimeout(timer); }
}

async function readReady(
  stream: ReadableStream<Uint8Array>, limit: number, signal: AbortSignal,
  kind: HttpChildKind, failure: Pick<HttpChildFailurePolicy, "create">,
) {
  const reader = stream.getReader();
  const abort = () => { void reader.cancel(); };
  signal.addEventListener("abort", abort, { once: true });
  const decoder = new TextDecoder();
  let line = "";
  let bytes = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) throw failure.create(`${kind}_READY_MISSING`, "HTTP child closed before readiness");
      bytes += value.byteLength;
      line += decoder.decode(value, { stream: true });
      if (bytes > limit) throw failure.create(`${kind}_READY_INVALID`, "HTTP child readiness exceeded its byte limit");
      if (line.includes("\n")) {
        const message: unknown = JSON.parse(line.slice(0, line.indexOf("\n")));
        return message;
      }
    }
  } finally { signal.removeEventListener("abort", abort); reader.releaseLock(); }
}

export async function superviseHttpChild<T, Failure extends HttpChildFailure>(input: {
  root: string; serverEntry: string; startup: object; kind: HttpChildKind;
  supervision: SupervisionSettings; maxControlBytes: number;
  failure: HttpChildFailurePolicy<Failure>;
  signal?: AbortSignal;
  diagnostics?: (line: string) => void;
  observe?: (event: HttpChildObservation) => void;
  ready: (message: unknown, pid: number, signal: AbortSignal) => Promise<ApiReadiness>;
  request: (base: string, signal: AbortSignal, identity: ApiReady) => Promise<T>;
}) {
  const controls = input.supervision;
  const cancellation = new AbortController();
  const signal = AbortSignal.any([cancellation.signal, ...(input.signal === undefined ? [] : [input.signal])]);
  if (signal.aborted) throw input.failure.capture(signal.reason, true);
  const child = Bun.spawn([process.execPath, input.serverEntry], {
    cwd: input.root, stdin: "pipe", stdout: "pipe", stderr: input.diagnostics === undefined ? "inherit" : "pipe",
  });
  const diagnostics = input.diagnostics !== undefined && child.stderr !== undefined && child.stderr !== null && typeof child.stderr !== "number"
    ? forwardDiagnostics(child.stderr, input.diagnostics) : Promise.resolve();
  void diagnostics.catch(() => {});
  const unexpectedExit = child.exited.then(code => {
    throw input.failure.create(`${input.kind}_CHILD_EXIT`, `HTTP child exited unexpectedly with status ${code}`);
  });
  // A losing race must still have a rejection handler after normal shutdown.
  void unexpectedExit.catch(() => {});
  const aborted = new Promise<never>((_, reject) => {
    signal.addEventListener("abort", () => reject(signal.reason), { once: true });
  });
  let completed = false;
  let ready = false;
  let original: Failure | undefined;
  const deadlineError = (code: string) => () => input.failure.create(code, code);
  try {
    input.observe?.({ phase: "started", pid: child.pid });
    const startupReady = (async () => {
      child.stdin.write(`${JSON.stringify(input.startup)}\n`);
      await child.stdin.flush();
      return input.ready(await readReady(child.stdout, input.maxControlBytes, signal, input.kind, input.failure), child.pid, signal);
    })();
    const base = await beforeDeadline(Promise.race([startupReady, unexpectedExit, aborted]),
      controls.readiness_timeout_ms, deadlineError(`${input.kind}_READY_TIMEOUT`));
    input.observe?.({ phase: "ready", pid: child.pid, identity: base.identity });
    ready = true;
    const result = await Promise.race([input.request(base.origin, signal, base.identity), unexpectedExit, aborted]);
    completed = true;
    return result;
  } catch (error) {
    if (!ready) input.observe?.({ phase: "startup_failed", pid: child.pid });
    original = input.failure.capture(error, signal.aborted && error === signal.reason);
    throw original;
  } finally {
    const close = async () => {
      input.observe?.({ phase: "stopping", pid: child.pid });
      const wasRunning = child.exitCode === null;
      cancellation.abort(new Error("HTTP child supervisor stopped"));
      let pipeFailure: unknown;
      // EOF also closes the child if its supervisor disappears.
      const closingPipe = Promise.resolve().then(() => child.stdin.end()).catch(error => {
        if (!(error instanceof Error) || !("code" in error) || !["EPIPE", "ERR_STREAM_DESTROYED"].includes(String(error.code))) pipeFailure = error;
      });
      let cleanupFailure: unknown;
      try {
        const [code] = await beforeDeadline(Promise.all([child.exited, closingPipe]),
          controls.shutdown_timeout_ms, deadlineError(`${input.kind}_SHUTDOWN_TIMEOUT`));
        input.observe?.({ phase: "stopped", pid: child.pid, exit_code: code });
        if (code !== 0 && (completed || (ready && wasRunning))) {
          throw input.failure.create(`${input.kind}_CHILD_EXIT`, `HTTP child shutdown failed with status ${code}`);
        }
      } catch (error) {
        cleanupFailure = error;
        if (error instanceof Error && "code" in error && error.code === `${input.kind}_SHUTDOWN_TIMEOUT`) {
          if (input.observe === undefined) console.error(JSON.stringify({ event: `${input.kind.toLowerCase()}_child_forced`, pid: child.pid }));
          input.observe?.({ phase: "forced", pid: child.pid });
          child.kill("SIGKILL");
          try {
            const code = await beforeDeadline(child.exited, controls.forced_exit_timeout_ms, deadlineError(`${input.kind}_REAP_TIMEOUT`));
            input.observe?.({ phase: "stopped", pid: child.pid, exit_code: code });
          }
          catch (reapError) { cleanupFailure = new AggregateError([error, reapError], "HTTP child could not be reaped"); }
        }
      }
      try { await beforeDeadline(diagnostics, controls.forced_exit_timeout_ms, deadlineError(`${input.kind}_DIAGNOSTICS_TIMEOUT`)); }
      catch (error) {
        cleanupFailure = cleanupFailure === undefined ? error
          : new AggregateError([cleanupFailure, error], "HTTP child diagnostics and cleanup failed");
      }
      try { await child.stdout.cancel(); }
      catch (error) {
        cleanupFailure = cleanupFailure === undefined ? error
          : new AggregateError([cleanupFailure, error], "HTTP child drain and stream cleanup failed");
      }
      if (cleanupFailure !== undefined || pipeFailure !== undefined) input.observe?.({ phase: "cleanup_failed", pid: child.pid });
      if (cleanupFailure !== undefined && pipeFailure !== undefined) {
        throw new AggregateError([cleanupFailure, pipeFailure], "HTTP child cleanup failed");
      }
      if (cleanupFailure !== undefined) throw cleanupFailure;
      if (pipeFailure !== undefined) throw pipeFailure;
    };
    if (original !== undefined) {
      throw await input.failure.retainCleanup(original, close);
    }
    await close();
  }
}
