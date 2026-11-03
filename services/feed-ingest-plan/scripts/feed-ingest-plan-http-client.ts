/** Call an enabled planner listener and verify its retained output before returning commit paths. */
import { join } from "node:path";
import { writeAtomically } from "@idhazh/ledger-file-writer";
import type { PlanInputs } from "../src/load-plan-inputs";
import type { PlanRequest } from "../src/api/plan-request";
import { PlanResponseSchema } from "../src/api/plan-response.schema";
import { FeedHealthStateUpdateResponseSchema } from "../src/api/feed-health-state.schema";
import { createExecutionOutputs } from "./feed-ingest-plan-outputs";
import { verifyPlanningCompletion } from "./feed-ingest-plan-verification";
import { ReleaseCollectionRequestSchema, ReleasedCollectionSchema } from "../src/api/collection-contracts";
import { describePlanError } from "../src/api/plan-request";
import { readPlannerResponseError } from "../src/api/plan-failure";
import { retainFailureThroughCleanup } from "../src/api/retain-failure-through-cleanup";

export async function requestPlannerHttp(base: string, inputs: PlanInputs, request: PlanRequest, directory: string, signal?: AbortSignal) {
  const healthResponse = await fetch(`${base}/health`, { signal: signal ?? null });
  const listener: unknown = await healthResponse.json();
  if (healthResponse.status !== 200 || typeof listener !== "object" || listener === null
    || !("planner_enabled" in listener) || listener.planner_enabled !== true) throw new Error("Planner listener is not enabled and responsive");
  const response = await fetch(`${base}/plan`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(request), timeout: false, signal: signal ?? null,
  });
  const body: unknown = await response.json();
  const parsed = PlanResponseSchema.safeParse(body);
  if (!parsed.success && response.status !== 200) {
    const error = readPlannerResponseError(body, { operation: "plan", limits: inputs.settings.diagnostics.failure });
    throw await retainFailureThroughCleanup(error, { operation: "plan", limits: inputs.settings.diagnostics.failure }, [{
      operation: "record-run", execute: () => writeAtomically(join(directory, "response.json"),
        Buffer.from(JSON.stringify(describePlanError(error)), "utf8")),
    }]);
  }
  const summary = parsed.success ? parsed.data : PlanResponseSchema.parse(body);
  await writeAtomically(join(directory, "response.json"), Buffer.from(JSON.stringify(summary), "utf8"));
  await verifyPlanningCompletion(inputs.outputRoot, summary, inputs.registrations, inputs.root);
  let health: ReturnType<typeof FeedHealthStateUpdateResponseSchema.parse> | undefined;
  let healthFailure: unknown;
  let healthFailed = false;
  let releaseFailure: unknown;
  let releaseFailed = false;
  const batch = summary.batches.selection_batch_id ?? summary.batches.parsed_batch_id;
  const execution = { run_id: summary.run_id, attempt: summary.attempt, correlation_id: summary.correlation_id,
    git_sha: summary.failure?.execution.git_sha ?? null };
  try {
    if (batch !== undefined) {
      const result = await fetch(`${base}/feed-health-state`, {
        method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ batch_id: batch, action: "summarize" }),
        signal: signal ?? null, timeout: false,
      });
      if (result.status !== 200) throw readPlannerResponseError(await result.json(), {
        operation: "feed-health-summary", execution, limits: inputs.settings.diagnostics.failure,
      });
      health = FeedHealthStateUpdateResponseSchema.parse(await result.json());
      await writeAtomically(join(directory, "health.json"), Buffer.from(JSON.stringify(health), "utf8"));
    }
  } catch (error) { healthFailed = true; healthFailure = error; }
  finally {
    try {
      const releaseRequest = ReleaseCollectionRequestSchema.parse({ run_id: summary.run_id, attempt: summary.attempt });
      const released = await fetch(`${base}/collections/release`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify(releaseRequest), timeout: false,
      });
      if (!released.ok) throw readPlannerResponseError(await released.json(), {
        operation: "collection-release", execution, limits: inputs.settings.diagnostics.failure,
      });
      const releaseResult = ReleasedCollectionSchema.parse(await released.json());
      if (releaseResult.run_id !== summary.run_id || releaseResult.attempt !== summary.attempt) {
        throw new Error("Planner released a different collection execution");
      }
    } catch (error) { releaseFailed = true; releaseFailure = error; }
  }
  if (healthFailed && releaseFailed) {
    throw new AggregateError([healthFailure, releaseFailure], "Health summary and collection release failed");
  }
  if (healthFailed) throw healthFailure;
  if (releaseFailed) throw releaseFailure;
  return { summary, health, outputs: createExecutionOutputs(summary, inputs.registrations), http_status: response.status };
}
