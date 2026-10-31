/** Capture one live document's run identity and effective stage configuration. */
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { DEFAULT_PLANNER_PRODUCER, FIRST_RUN_ATTEMPT, resolveRunContext } from "../resolve-run-context";
import type { RunContext } from "../resolve-run-context";
import { hashText } from "../hash-text";

export type DocumentOperationContext = {
  request_id: string;
  context: RunContext;
  config_sha256: string;
};

export function stageConfigFingerprint(inputs: PlanInputs, runtime: PlanRuntime) {
  return hashText(JSON.stringify({
    harvest: inputs.harvest.config_sha256, policy: inputs.harvest.config,
    settings: inputs.settings, clock: inputs.clock_config,
    ledger: inputs.ledgerSettings, registrations: inputs.registrations,
    attempt: runtime.attempt ?? FIRST_RUN_ATTEMPT,
    producer: runtime.producer ?? DEFAULT_PLANNER_PRODUCER, git_sha: runtime.git_sha,
  }));
}

export function captureDocumentContext(
  requestId: string, correlationId: string, inputs: PlanInputs, runtime: PlanRuntime, context?: RunContext,
): DocumentOperationContext {
  return {
    request_id: requestId,
    context: context ?? resolveRunContext(inputs.settings, runtime.git_sha, runtime.clock?.() ?? new Date(),
      BigInt(`0x${requestId.replaceAll("-", "")}`).toString(), correlationId, runtime.captured_at,
      runtime.attempt, runtime.producer),
    config_sha256: stageConfigFingerprint(inputs, runtime),
  };
}
