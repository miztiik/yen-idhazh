/** Capture one live document's run identity and effective stage configuration. */
import {
  createChildContext, createRootContext, OperationLinkSchema, OperationMetadataSchema,
  PlannerStageContextSchema, readTraceContext,
} from "@idhazh/common-contracts";
import type { OperationLink, OperationMetadata, PlannerStageContext } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { DEFAULT_PLANNER_PRODUCER, FIRST_RUN_ATTEMPT, resolveRunContext } from "../resolve-run-context";
import type { RunContext } from "../resolve-run-context";
import { hashText } from "../hash-text";

export type DocumentOperationContext = {
  context: RunContext;
  config_sha256: string;
};

export function operationMetadata(value: OperationMetadata): OperationMetadata {
  return OperationMetadataSchema.parse({
    traceId: value.traceId, spanId: value.spanId, links: value.links,
    ...(value.parentSpanId === undefined ? {} : { parentSpanId: value.parentSpanId }),
    ...(value.traceState === undefined ? {} : { traceState: value.traceState }),
  });
}
export function operationLink(value: OperationLink): OperationLink {
  return OperationLinkSchema.parse({ traceId: value.traceId, spanId: value.spanId });
}
export function operationKey(value: OperationLink) {
  const reference = operationLink(value);
  return `${reference.traceId}:${reference.spanId}`;
}
export function stageContext(value: PlannerStageContext): PlannerStageContext {
  return PlannerStageContextSchema.parse({
    now: value.now, captured_at: value.captured_at, date: value.date,
    run_id: value.run_id, writer: value.writer,
  });
}
export function operationRunContext(value: OperationMetadata & { context: PlannerStageContext }): RunContext {
  return { ...stageContext(value.context), ...operationMetadata(value) };
}
export function runtimeOperation(runtime: PlanRuntime): OperationMetadata | undefined {
  if (runtime.traceId === undefined && runtime.spanId === undefined) return undefined;
  return OperationMetadataSchema.parse({
    traceId: runtime.traceId, spanId: runtime.spanId, links: runtime.links,
    ...(runtime.parentSpanId === undefined ? {} : { parentSpanId: runtime.parentSpanId }),
    ...(runtime.traceState === undefined ? {} : { traceState: runtime.traceState }),
  });
}
export function captureRequestRuntime(runtime: PlanRuntime, headers: Headers): PlanRuntime {
  const {
    traceId: _traceId, spanId: _spanId, parentSpanId: _parentSpanId, links: _links, traceState: _traceState,
    ...controls
  } = runtime;
  const incoming = readTraceContext({
    traceparent: headers.get("traceparent") ?? undefined, tracestate: headers.get("tracestate") ?? undefined,
  });
  return { ...controls, ...(incoming === undefined ? createRootContext() : createChildContext(incoming)) };
}
export function commandContext(runtime: PlanRuntime, parent?: RunContext, links: readonly OperationLink[] = []) {
  const inputs = links.map(operationLink);
  return parent === undefined
    ? { ...(runtimeOperation(runtime) ?? createRootContext()), links: inputs }
    : createChildContext(operationMetadata(parent), { links: inputs });
}

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
  inputs: PlanInputs, runtime: PlanRuntime, context?: RunContext,
): DocumentOperationContext {
  // Independent documents must not inherit a listener run and its cancellation or candidate identities.
  return {
    context: context ?? resolveRunContext(inputs.settings, runtime.git_sha, runtime.clock?.() ?? new Date(),
      undefined, runtimeOperation(runtime) ?? createRootContext(), runtime.captured_at,
      runtime.attempt, runtime.producer),
    config_sha256: stageConfigFingerprint(inputs, runtime),
  };
}
