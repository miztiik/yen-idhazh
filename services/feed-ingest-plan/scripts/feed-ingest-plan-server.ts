/** Reconstruct one planner child from private startup data and close it when its supervisor leaves. */
import { createInterface } from "node:readline";
import { resolve } from "node:path";
import { PlannerReadySchema, PlannerStartupSchema, PlannerStartupFailureSchema } from "../src/config/planner-startup";
import type { PlannerStartup } from "../src/config/planner-startup";
import { loadPlanInputs } from "../src/load-plan-inputs";
import type { PlanInputs } from "../src/load-plan-inputs";
import type { PlanRuntime } from "../src/run-feed-plan";
import { servePlan } from "../src/api/server";
import { PlanError } from "../src/api/plan-request";

export async function restorePlannerStartup(startup: PlannerStartup, root = process.cwd()) {
  const inputs = await loadPlanInputs(root, undefined, startup.settings);
  inputs.harvest = { ...inputs.harvest, config: startup.planning };
  inputs.outputRoot = resolve(root, startup.output_root);
  const runtime: PlanRuntime = {
    ...startup.runtime, clock: () => new Date(startup.runtime.captured_at),
    selection_clock: () => new Date(),
  };
  return { inputs, runtime };
}

export async function runPlannerServer(
  restore: (startup: PlannerStartup) => Promise<{ inputs: PlanInputs; runtime: PlanRuntime }> = restorePlannerStartup,
) {
  const lines = createInterface({ input: process.stdin, crlfDelay: Infinity });
  const cancellation = new AbortController();
  let server: ReturnType<typeof servePlan> | undefined;
  let closing: Promise<void> | undefined;
  let shutdownMs: number | undefined;
  let forceTimer: ReturnType<typeof setTimeout> | undefined;
  let closed = false;
  const stop = () => {
    closed = true;
    cancellation.abort(new Error("Planner supervisor closed"));
    if (shutdownMs !== undefined) forceTimer ??= setTimeout(() => {
      console.error(JSON.stringify({ event: "planner_shutdown_forced" }));
      void server?.stop(true);
      process.exit(2);
    }, shutdownMs);
    if (server === undefined) { lines.close(); return; }
    closing ??= (async () => {
      try { await server!.stop(); }
      finally { lines.close(); }
    })();
  };
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
  lines.once("close", stop);
  try {
    const [line] = await new Promise<[string]>((resolveLine, reject) => {
      lines.once("line", value => resolveLine([value]));
      lines.once("close", () => reject(new PlanError("PLANNER_STARTUP_CLOSED", "Startup pipe closed before startup")));
    });
    const startup = PlannerStartupSchema.parse(JSON.parse(line));
    shutdownMs = startup.settings.supervision.shutdown_timeout_ms;
    const { inputs, runtime } = await restore(startup);
    if (closed) throw new PlanError("PLANNER_STARTUP_CLOSED", "Supervisor left before listener startup");
    const identity = PlannerReadySchema.parse({
      event: "planner_ready", nonce: startup.nonce, pid: process.pid,
      port: inputs.settings.listener.port, runtime: startup.runtime,
    });
    try { server = servePlan(inputs, { ...runtime, signal: cancellation.signal }, identity); }
    catch (error) {
      const code = error instanceof Error && "code" in error ? String(error.code) : "LISTEN_FAILED";
      throw new PlanError("PLANNER_BIND_FAILED", `Planner loopback listener could not bind: ${code}`);
    }
    console.log(JSON.stringify({ ...identity, port: server.port }));
    await new Promise<void>(resolveClosed => {
      if (closed) resolveClosed();
      else lines.once("close", resolveClosed);
    });
    await closing;
  } catch (error) {
    console.log(JSON.stringify(PlannerStartupFailureSchema.parse({
      event: "planner_startup_failed",
      code: error instanceof PlanError ? error.code : "PLANNER_STARTUP_FAILED",
      message: error instanceof PlanError ? error.message : "Planner startup could not load validated controls and named inputs",
    })));
    throw error;
  } finally {
    stop();
    await closing;
    clearTimeout(forceTimer);
    lines.close();
    process.off("SIGINT", stop);
    process.off("SIGTERM", stop);
  }
}

if (import.meta.main) {
  try { await runPlannerServer(); }
  catch (error) {
    console.error(JSON.stringify({
      event: "planner_server_failed",
      code: error instanceof PlanError ? error.code : "PLANNER_STARTUP_FAILED",
      ...(error instanceof PlanError ? { message: error.message } : {}),
    }));
    process.exitCode = 2;
  }
}
