/** Call an enabled planner listener and verify its retained output before returning commit paths. */
import { join } from "node:path";
import { writeAtomically } from "@idhazh/ledger-file-writer";
import { createRootContext, writeTraceContext } from "@idhazh/common-contracts";
import type { OperationMetadata, PlannerFailureOperation } from "@idhazh/common-contracts";
import type { PlanInputs } from "../src/load-plan-inputs";
import type { PlanRequest } from "../src/api/plan-request";
import { PlanResponseSchema } from "../src/api/plan-response.schema";
import { createExecutionOutputs } from "./feed-ingest-plan-outputs";
import { verifyPlanningCompletion } from "./feed-ingest-plan-verification";
import { describePlanError } from "../src/api/plan-request";
import { readPlannerResponseError, withPlannerFailure } from "../src/api/plan-failure";
import { retainFailureThroughCleanup } from "../src/api/retain-failure-through-cleanup";
import { retainWorkflowFailure } from "./retain-workflow-failure";

export async function requestPlannerHttp(
  base: string, inputs: PlanInputs, request: PlanRequest, directory: string, signal?: AbortSignal,
  caller: OperationMetadata = createRootContext(),
) {
  const healthResponse = await fetch(`${base}/health`, { signal: signal ?? null });
  const listener: unknown = await healthResponse.json();
  if (healthResponse.status !== 200 || typeof listener !== "object" || listener === null
    || !("planner_enabled" in listener) || listener.planner_enabled !== true) throw new Error("Planner listener is not enabled and responsive");
  const response = await fetch(`${base}/plan`, {
    method: "POST", headers: { "content-type": "application/json", ...writeTraceContext(caller) },
    body: JSON.stringify(request), timeout: false, signal: signal ?? null,
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
  const capture = { operation: "plan" as const, execution: {
    run_id: summary.run_id, attempt: summary.attempt, traceId: summary.traceId, spanId: caller.spanId,
    git_sha: summary.failure?.execution.git_sha ?? null,
  }, limits: inputs.settings.diagnostics.failure };
  const health = summary.health?.status === "summarized" ? summary.health : undefined;
  const outputs: { operation: PlannerFailureOperation; execute: () => Promise<unknown> }[] = [
    { operation: "record-run", execute: () => writeAtomically(join(directory, "response.json"), Buffer.from(JSON.stringify(summary), "utf8")) },
    { operation: "verify-output", execute: () => verifyPlanningCompletion(inputs.outputRoot, summary, inputs.registrations, inputs.root) },
  ];
  if (health !== undefined) outputs.push({
    operation: "write-report", execute: () => writeAtomically(join(directory, "health.json"), Buffer.from(JSON.stringify(health), "utf8")),
  });
  const settled = await Promise.allSettled(outputs.map(async output => {
    try { await output.execute(); }
    catch (error) { throw withPlannerFailure(error, { ...capture, operation: output.operation }); }
  }));
  const failures = settled.flatMap(outcome => outcome.status === "rejected" ? [outcome.reason] : []);
  if (failures.length) {
    const error = withPlannerFailure(failures.length === 1 ? failures[0]
      : new AggregateError(failures, "Planner output retention failed"), capture);
    throw await retainFailureThroughCleanup(error, capture, [{
      operation: "record-run", execute: () => retainWorkflowFailure({ directory, error, capture, response: summary }),
    }]);
  }
  return { summary, health, outputs: createExecutionOutputs(summary, inputs.registrations), http_status: response.status };
}
