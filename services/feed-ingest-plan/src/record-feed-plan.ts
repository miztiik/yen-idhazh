/** Record required planning evidence and any operator-supplied publication observation. */
import type { PlanInputs } from "./load-plan-inputs";
import type { FeedPlanResult, PlanRuntime, RecordedFeedPlanResult } from "./run-feed-plan";
import { recordPlanningMetrics, recordPublicationMetrics } from "./metrics/metrics-recorder";

export async function recordFeedPlan(
  plan: FeedPlanResult, inputs: PlanInputs, runtime: PlanRuntime,
): Promise<RecordedFeedPlanResult> {
  const metrics = await recordPlanningMetrics(plan, inputs);
  if (runtime.observe_publication === undefined) return { ...plan, metrics };
  const observation = await runtime.observe_publication(plan, metrics);
  if (observation.run_id !== plan.context.run_id || observation.correlation_id !== plan.context.correlation_id
    || observation.writer.attempt !== plan.context.writer.attempt) throw new Error("Operator publication input differs from this planning attempt");
  const publication = await recordPublicationMetrics(observation);
  return { ...plan, metrics, publication };
}
