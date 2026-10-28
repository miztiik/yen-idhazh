/** Keep one owned planner child alive through its HTTP calls and reap it on every exit path. */
import { randomUUID } from "node:crypto";
import { relative } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { PlannerReadySchema, PlannerStartupSchema, PlannerStartupFailureSchema } from "../src/config/planner-startup";
import type { PlannerStartup } from "../src/config/planner-startup";
import type { PlanInputs } from "../src/load-plan-inputs";
import { PlanError } from "../src/api/plan-request";
import type { PlanRequest } from "../src/api/plan-request";
import { requestPlannerHttp } from "./feed-ingest-plan-http-client";

export function createPlannerStartup(inputs: PlanInputs, runtime: PlannerStartup["runtime"]) {
  return PlannerStartupSchema.parse({
    nonce: randomUUID(), settings: inputs.settings,
    output_root: relative(inputs.root, inputs.outputRoot).replaceAll("\\", "/"), runtime,
  });
}

async function beforeDeadline<T>(operation: Promise<T>, milliseconds: number, code: string): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([operation, new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new PlanError(code, code)), milliseconds);
    })]);
  } finally { clearTimeout(timer); }
}

async function readReady(stream: ReadableStream<Uint8Array>, limit: number, signal: AbortSignal) {
  const reader = stream.getReader();
  const abort = () => { void reader.cancel(); };
  signal.addEventListener("abort", abort, { once: true });
  const decoder = new TextDecoder();
  let line = "";
  let bytes = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) throw new PlanError("PLANNER_READY_MISSING", "Planner child closed before readiness");
      bytes += value.byteLength;
      line += decoder.decode(value, { stream: true });
      if (bytes > limit) throw new PlanError("PLANNER_READY_INVALID", "Planner child readiness exceeded its byte limit");
      if (line.includes("\n")) {
        const message = z.union([PlannerReadySchema, PlannerStartupFailureSchema])
          .parse(JSON.parse(line.slice(0, line.indexOf("\n"))));
        if (message.event === "planner_startup_failed") throw new PlanError(message.code, message.message);
        return message;
      }
    }
  } finally { signal.removeEventListener("abort", abort); reader.releaseLock(); }
}

export async function invokePlannerHttp(
  inputs: PlanInputs, startup: PlannerStartup, request: PlanRequest, directory: string,
  options: { signal?: AbortSignal; serverEntry?: string } = {},
) {
  const controls = inputs.settings.supervision;
  const cancellation = new AbortController();
  const signal = AbortSignal.any([cancellation.signal, ...(options.signal === undefined ? [] : [options.signal])]);
  signal.throwIfAborted();
  const startupLine = `${JSON.stringify(PlannerStartupSchema.parse(startup))}\n`;
  const child = Bun.spawn([process.execPath, options.serverEntry
    ?? fileURLToPath(new URL("./feed-ingest-plan-server.ts", import.meta.url))], {
    cwd: inputs.root, stdin: "pipe", stdout: "pipe", stderr: "inherit",
  });
  const unexpectedExit = child.exited.then(code => {
    throw new PlanError("PLANNER_CHILD_EXIT", `Planner child exited unexpectedly with status ${code}`);
  });
  // A losing race must still have a rejection handler after normal shutdown.
  void unexpectedExit.catch(() => {});
  const aborted = new Promise<never>((_, reject) => {
    signal.addEventListener("abort", () => reject(signal.reason), { once: true });
  });
  let completed = false;
  try {
    const startupReady = (async () => {
      child.stdin.write(startupLine);
      await child.stdin.flush();
      const ready = await readReady(child.stdout, inputs.settings.listener.max_body_bytes, signal);
      if (ready.pid !== child.pid || ready.nonce !== startup.nonce
        || JSON.stringify(ready.runtime) !== JSON.stringify(startup.runtime)
        || ready.port !== inputs.settings.listener.port) {
        throw new PlanError("PLANNER_READY_IDENTITY", "Readiness does not match the owned child and invocation");
      }
      const hostname = inputs.settings.listener.hostname;
      const base = `http://${hostname === "::1" ? "[::1]" : hostname}:${ready.port}/api/2026-10-20`;
      await fetch(`${base}/health`, { signal }).then(async response => {
        const body = z.object({ identity: PlannerReadySchema, planner_enabled: z.boolean() }).parse(await response.json());
        if (response.status !== 200 || body.planner_enabled !== true
          || JSON.stringify(PlannerReadySchema.parse(body.identity)) !== JSON.stringify(ready)) {
          throw new PlanError("PLANNER_READY_IDENTITY", "HTTP readiness does not match the owned child");
        }
      });
      return base;
    })();
    const base = await beforeDeadline(Promise.race([startupReady, unexpectedExit, aborted]),
      controls.readiness_timeout_ms, "PLANNER_READY_TIMEOUT");
    const result = await Promise.race([
      requestPlannerHttp(base, inputs, request, directory, signal), unexpectedExit, aborted,
    ]);
    completed = true;
    return result;
  } finally {
    cancellation.abort(new Error("Planner supervisor stopped"));
    // EOF also closes the child if its supervisor dies without delivering a signal.
    let pipeFailure: unknown;
    const closingPipe = Promise.resolve().then(() => child.stdin.end()).catch(error => {
      if (!(error instanceof Error) || !("code" in error) || !["EPIPE", "ERR_STREAM_DESTROYED"].includes(String(error.code))) pipeFailure = error;
    });
    try {
      const [code] = await beforeDeadline(Promise.all([child.exited, closingPipe]),
        controls.shutdown_timeout_ms, "PLANNER_SHUTDOWN_TIMEOUT");
      if (completed && code !== 0) throw new PlanError("PLANNER_CHILD_EXIT", `Planner child shutdown failed with status ${code}`);
    } catch (error) {
      if (!(error instanceof PlanError) || error.code !== "PLANNER_SHUTDOWN_TIMEOUT") throw error;
      console.error(JSON.stringify({ event: "planner_child_forced", pid: child.pid }));
      child.kill("SIGKILL");
      await beforeDeadline(child.exited, controls.forced_exit_timeout_ms, "PLANNER_REAP_TIMEOUT");
      if (completed) throw error;
    } finally { await child.stdout.cancel(); }
    if (pipeFailure !== undefined) throw pipeFailure;
  }
}
