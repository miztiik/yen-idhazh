/** Does HTTP readiness identify the owned child and its captured native module controls? */
import { z } from "zod";
import { PLANNER_API_PREFIX, writeTraceContext } from "@idhazh/common-contracts";
import { PlanError } from "@idhazh/feed-ingest-plan/plan-request";
import { PlannerReadySchema } from "@idhazh/feed-ingest-plan/startup";
import { SafePersistHttpReadySchema } from "@idhazh/feed-ingest-plan/delivery-contracts";
import type { superviseHttpChild } from "@idhazh/feed-ingest-plan/http-child-lifetime";
import {
  API_HEALTH_PATH, ApiReadySchema, ApiStartupFailureSchema, enabledModules, startupNonce,
} from "./api-startup";
import type { ApiStartup } from "./api-startup";
import { apiOrigin } from "./load-settings";

export async function readApiReadiness(input: {
  message: unknown; pid: number; startup: ApiStartup;
  kind: Parameters<typeof superviseHttpChild>[0]["kind"]; signal: AbortSignal;
}): Promise<string> {
  const { startup, pid, signal, kind } = input;
  const failure = ApiStartupFailureSchema.safeParse(input.message);
  if (failure.success) throw new PlanError(failure.data.code, failure.data.message, null, { failure: failure.data.failure });
  const ready = ApiReadySchema.parse(input.message);
  const mismatch = () => new PlanError(`${kind}_READY_IDENTITY`, "Readiness does not match the owned child and captured module controls");
  if (ready.pid !== pid || ready.nonce !== startupNonce(startup) || ready.port !== startup.server.port
    || ready.group !== startup.group || ready.enabled !== true
    || JSON.stringify(ready.modules) !== JSON.stringify(enabledModules(startup.group))) throw mismatch();
  const origin = apiOrigin(startup.server);
  const headers = writeTraceContext(startup.run.context);
  const response = await fetch(new URL(API_HEALTH_PATH, origin), { signal, headers, redirect: "error" });
  const health = z.strictObject({ identity: ApiReadySchema }).parse(await response.json());
  if (response.status !== 200 || response.headers.get("cache-control") !== "no-store"
    || JSON.stringify(health.identity) !== JSON.stringify(ready)) throw mismatch();
  if (startup.group === "planning") {
    const response = await fetch(`${origin}${PLANNER_API_PREFIX}/health`, { signal, headers, redirect: "error" });
    const health = z.object({ identity: PlannerReadySchema, planner_enabled: z.boolean() }).parse(await response.json());
    const expected = PlannerReadySchema.parse({
      event: "planner_ready", nonce: startup.planner.nonce, pid, port: startup.server.port,
      runtime: startup.planner.runtime,
    });
    if (response.status !== 200 || !health.planner_enabled
      || JSON.stringify(health.identity) !== JSON.stringify(expected)) throw mismatch();
  } else if (startup.group === "delivery") {
    const response = await fetch(`${origin}${PLANNER_API_PREFIX}/health`, { signal, headers, redirect: "error" });
    const health = z.strictObject({ identity: SafePersistHttpReadySchema }).parse(await response.json());
    const expected = SafePersistHttpReadySchema.parse({
      event: "safe_persist_ready", nonce: startup.delivery.nonce, pid, port: startup.server.port,
    });
    if (response.status !== 200 || JSON.stringify(health.identity) !== JSON.stringify(expected)) throw mismatch();
  }
  return origin;
}
