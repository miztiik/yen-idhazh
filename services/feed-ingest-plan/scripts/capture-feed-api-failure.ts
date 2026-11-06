/** Preserve planner lifecycle codes, safe frames and execution identity through shared hosting. */
import type { HttpChildFailurePolicy } from "@idhazh/serve-pipeline-apis/child-failure";
import { PlanError } from "../src/api/plan-request";
import { describePlanError, withPlannerFailure } from "../src/api/plan-failure";
import type { FailureCaptureOptions } from "../src/api/plan-failure";
import { retainFailureThroughCleanup } from "../src/api/retain-failure-through-cleanup";

export function captureFeedApiFailure(capture: FailureCaptureOptions): HttpChildFailurePolicy<PlanError> {
  return {
    create: (code, message, cause) => new PlanError(code, message, null, cause === undefined ? undefined : { cause }),
    capture: (error, cancelled) => withPlannerFailure(error, {
      ...capture, ...(cancelled === undefined ? {} : { cancelled }),
    }),
    retainCleanup: (error, close) => retainFailureThroughCleanup(error, capture, [
      { operation: "listener-close", execute: close },
    ]),
    startup(error, kind) {
      const captured = withPlannerFailure(error, capture);
      const original = new PlanError(error instanceof PlanError ? error.code : `${kind}_STARTUP_FAILED`,
        "HTTP child operation did not complete", null, { cause: error, failure: captured.failure });
      return { error: original, packet: {
        event: `${kind.toLowerCase()}_startup_failed`, code: original.code,
        message: `${original.code}: HTTP child operation did not complete`, failure: original.failure,
      } };
    },
    describe: error => describePlanError(error, undefined, capture),
  };
}
