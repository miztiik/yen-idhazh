/** Record required planning evidence and any operator-supplied publication observation. */
import type { PlanInputs } from "./load-plan-inputs";
import type { FeedPlanResult, PlanRuntime, RecordedFeedPlanResult } from "./run-feed-plan";
import { recordPlanningMetrics, recordPublicationMetrics } from "./metrics/metrics-recorder";
import { createProgressLogger } from "./logging/progress-logger";

export async function recordFeedPlan(
  plan: FeedPlanResult, inputs: PlanInputs, runtime: PlanRuntime,
): Promise<RecordedFeedPlanResult> {
  const progress = createProgressLogger(plan.context.correlation_id, runtime.progress);
  progress("AUDIT_RECORDING_STARTED");
  const metrics = await recordPlanningMetrics(plan, inputs);
  progress("AUDIT_RECORDING_COMPLETED");
  if (runtime.observe_publication === undefined) return { ...plan, metrics };
  progress("PUBLICATION_OBSERVATION_STARTED");
  const observation = await runtime.observe_publication(plan, metrics);
  if (observation.run_id !== plan.context.run_id || observation.correlation_id !== plan.context.correlation_id
    || observation.writer.attempt !== plan.context.writer.attempt) throw new Error("Operator publication input differs from this planning attempt");
  const publication = await recordPublicationMetrics(observation);
  progress("PUBLICATION_OBSERVATION_COMPLETED");
  return { ...plan, metrics, publication };
}
