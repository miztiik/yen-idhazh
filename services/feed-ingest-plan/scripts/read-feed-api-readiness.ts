/** Does the owned feed listener also identify its captured planner runtime or delivery controls? */
import { z } from "zod";
import { DELIVERY_API_PATHS, PLANNER_API_PATHS, PLANNER_API_PREFIX, writeTraceContext } from "@idhazh/common-contracts";
import { readApiReadiness } from "@idhazh/serve-pipeline-apis/readiness";
import type { ApiReadiness } from "@idhazh/serve-pipeline-apis/startup";
import { PlanError } from "../src/api/plan-request";
import { PlannerReadySchema } from "../src/config/planner-startup";
import { SafePersistHttpReadySchema } from "./feed-ingest-plan-delivery-result";
import { FeedApiStartupFailureSchema, readFeedApiIdentity } from "./read-feed-api-startup";
import type { FeedApiStartup } from "./read-feed-api-startup";
import type { HttpChildFailurePolicy, HttpChildKind } from "@idhazh/serve-pipeline-apis/child-failure";

export async function readFeedApiReadiness(input: {
  message: unknown; pid: number; startup: FeedApiStartup; kind: HttpChildKind;
  signal: AbortSignal; failure: HttpChildFailurePolicy<PlanError>;
}): Promise<ApiReadiness> {
  const { startup, pid, signal, kind } = input;
  const failed = FeedApiStartupFailureSchema.safeParse(input.message);
  if (failed.success) throw new PlanError(failed.data.code, failed.data.message, null, { failure: failed.data.failure });
  const ready = await readApiReadiness({
    ...input, expected: readFeedApiIdentity(startup, pid), server: startup.server, context: startup.run.context,
  });
  const mismatch = () => input.failure.create(`${kind}_READY_IDENTITY`, "Readiness does not match the owned child and captured module controls");
  const healthPath = startup.group === "planning" ? PLANNER_API_PATHS.health : DELIVERY_API_PATHS.health;
  const response = await fetch(`${ready.origin}${PLANNER_API_PREFIX}${healthPath}`, {
    signal, headers: writeTraceContext(startup.run.context), redirect: "error",
  });
  if (startup.group === "planning") {
    const health = z.object({ identity: PlannerReadySchema, planner_enabled: z.boolean() }).parse(await response.json());
    const expected = PlannerReadySchema.parse({
      event: "planner_ready", nonce: startup.planner.nonce, pid, port: startup.server.port,
      runtime: startup.planner.runtime,
    });
    if (response.status !== 200 || !health.planner_enabled
      || JSON.stringify(health.identity) !== JSON.stringify(expected)) throw mismatch();
  } else {
    const health = z.strictObject({ identity: SafePersistHttpReadySchema }).parse(await response.json());
    const expected = SafePersistHttpReadySchema.parse({
      event: "safe_persist_ready", nonce: startup.delivery.nonce, pid, port: startup.server.port,
    });
    if (response.status !== 200 || JSON.stringify(health.identity) !== JSON.stringify(expected)) throw mismatch();
  }
  return ready;
}
