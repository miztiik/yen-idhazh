/** Attempt required cleanup without replacing the failure that made it necessary. */
import { PlanError } from "./plan-error";
import { capturePlannerFailure, combinePlannerFailures, withPlannerFailure } from "./plan-failure";
import type { FailureCaptureOptions } from "./plan-failure";
import type { PlannerFailureOperation } from "@idhazh/common-contracts";

export async function retainFailureThroughCleanup(error: unknown, capture: FailureCaptureOptions,
  steps: readonly { operation: PlannerFailureOperation; execute: () => unknown | Promise<unknown> }[]): Promise<PlanError> {
  let retained = withPlannerFailure(error, capture);
  for (const step of steps) {
    try { await step.execute(); }
    catch (failure) {
      const original = retained.failure;
      if (original === null) throw new Error("Cleanup requires captured original failure evidence");
      retained = new PlanError(retained.code, retained.message, retained.field, {
        cause: new AggregateError([retained, failure], "Execution and cleanup failed"),
        failure: combinePlannerFailures(original, capturePlannerFailure(failure, {
          ...capture, operation: step.operation,
        }), capture.limits),
      });
    }
  }
  return retained;
}
