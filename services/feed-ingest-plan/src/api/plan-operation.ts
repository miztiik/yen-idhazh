/** Replay a completed keyed plan, refusing to repeat an interrupted ledger-producing run. */
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime, FeedPlanResult } from "../run-feed-plan";
import { summarizePlan } from "../run-feed-plan";
import { PlanError, resolvePlanRequest } from "./plan-request";
import type { PlanRequest } from "./plan-request";
import { prepareOperation } from "./document-operations";
import { RequestIdSchema } from "./operation-contracts";
import { openOperationStore } from "./operation-store";

export type CapturedPlanIdentity = Pick<PlanRuntime, "clock" | "run_number" | "correlation_id" | "captured_at" | "signal" | "stage_origin">;
export async function executeKeyedPlan(
  key: string, request: PlanRequest, inputs: PlanInputs, runtime: PlanRuntime,
  execute: (request: PlanRequest, captured?: CapturedPlanIdentity) => Promise<FeedPlanResult>,
) {
  RequestIdSchema.parse(key);
  const effective = resolvePlanRequest(request, inputs.harvest.config);
  if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled by service settings", "enabled");
  const proposed = prepareOperation("plan", key, effective, runtime.correlation_id ?? key, inputs, runtime);
  const store = await openOperationStore(inputs.outputRoot);
  try {
    const record = await store.execute(proposed, async record => {
      const result = await execute(request, {
        clock: () => new Date(record.created_at), captured_at: record.created_at, correlation_id: record.correlation_id,
        run_number: record.run_id.slice(11),
      });
      return { response_json: JSON.stringify(summarizePlan(result)), artifact: null };
    });
    return record.response_json!;
  } finally { store.close(); }
}
