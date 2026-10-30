/** Capture one operator request's run identity and effective configuration before work starts. */
import { PlannerOperationSchema } from "@idhazh/common-contracts";
import type { PlannerOperation } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { DEFAULT_PLANNER_PRODUCER, FIRST_RUN_ATTEMPT, resolveRunContext } from "../resolve-run-context";
import { sha256 } from "./operation-store";
import type { PreparedOperation } from "./operation-store";

function operationConfiguration(inputs: PlanInputs, runtime: PlanRuntime) {
  return {
    harvest: inputs.harvest.config_sha256, settings: inputs.settings, clock: inputs.clock_config,
    ledger: inputs.ledgerSettings, registrations: inputs.registrations,
    attempt: runtime.attempt ?? FIRST_RUN_ATTEMPT,
    producer: runtime.producer ?? DEFAULT_PLANNER_PRODUCER, git_sha: runtime.git_sha,
  };
}
export function operationConfigFingerprint(inputs: PlanInputs, runtime: PlanRuntime) {
  return sha256(JSON.stringify(operationConfiguration(inputs, runtime)));
}
function legacyOperationConfigFingerprint(inputs: PlanInputs, runtime: PlanRuntime) {
  const config = operationConfiguration(inputs, runtime);
  const { digest_root, ...originalInputs } = config.settings.inputs;
  return sha256(JSON.stringify({ ...config, settings: { ...config.settings, inputs: originalInputs } }));
}
export function proposedOperation(
  operation: PlannerOperation["operation"], request_id: string, request: unknown, correlation_id: string,
  inputs: PlanInputs, runtime: PlanRuntime,
) {
  const now = runtime.clock?.() ?? new Date();
  const runNumber = operation === "plan" ? runtime.run_number : BigInt(`0x${request_id.replaceAll("-", "")}`).toString();
  const context = resolveRunContext(
    inputs.settings, runtime.git_sha, now, runNumber, correlation_id, runtime.captured_at,
    runtime.attempt, runtime.producer,
  );
  return PlannerOperationSchema.parse({
    request_id, operation, input_sha256: sha256(JSON.stringify(request)), config_sha256: operationConfigFingerprint(inputs, runtime),
    run_id: context.run_id, correlation_id, created_at: context.captured_at, state: "started", response_json: null, artifact: null,
  });
}
export function prepareOperation(
  operation: PlannerOperation["operation"], request_id: string, request: unknown, correlation_id: string,
  inputs: PlanInputs, runtime: PlanRuntime, runId?: string,
): PreparedOperation {
  return {
    request_id, operation, input_sha256: sha256(JSON.stringify(request)), config_sha256: operationConfigFingerprint(inputs, runtime),
    legacy_config_sha256: legacyOperationConfigFingerprint(inputs, runtime),
    capture: () => {
      const record = proposedOperation(operation, request_id, request, correlation_id, inputs, runtime);
      return runId === undefined ? record : { ...record, run_id: runId };
    },
  };
}
