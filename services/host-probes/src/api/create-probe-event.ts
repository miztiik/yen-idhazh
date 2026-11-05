/** Which safe native outcomes describe handled probe commands and owned failures? */
import { z } from "zod";
import { CloudEventSchema, createCloudEvent, readCloudEvent } from "@idhazh/common-contracts";
import type { OperationMetadata } from "@idhazh/common-contracts";
import { HOST_PROBE_EVENT_SOURCE } from "../declare-event-source";

export const HOST_PROBE_EVENT_VERSION = "2026-11-05";
const diagnosticContract = {
  version: HOST_PROBE_EVENT_VERSION,
  readCompatibility: "current_only; diagnostic readers and writers change together",
  changelog: [
    { version: HOST_PROBE_EVENT_VERSION, change: "Declare safe native probe command outcomes and failures." },
  ],
};
const NativeEnvelopeSchema = CloudEventSchema.safeExtend({ source: z.literal(HOST_PROBE_EVENT_SOURCE) });
const CompletionDataSchema = z.strictObject({
  operation: z.enum(["sample", "start-task-profile", "stop-task-profile", "cache-latency"]),
  outcome: z.enum(["handled", "disabled"]),
}).meta(diagnosticContract);
const CompletionEventSchema = NativeEnvelopeSchema.safeExtend({
  type: z.literal("host_probe_completed"), data: CompletionDataSchema,
});

// These type/code pairs are the native diagnostic protocol, not operator settings.
const PROBE_FAILURE_CODES = {
  host_probe_failed: "HOST_PROBE_FAILED",
  host_probe_cleanup_failed: "HOST_PROBE_CLEANUP_FAILED",
  host_probe_body_cleanup_failed: "HOST_PROBE_BODY_CLEANUP_FAILED",
  task_profile_failed: "TASK_PROFILE_FAILED",
} as const;
export type ProbeFailureType = keyof typeof PROBE_FAILURE_CODES;
const FailureEventSchema = z.discriminatedUnion("type", [
  NativeEnvelopeSchema.safeExtend({
    type: z.literal("host_probe_failed"),
    data: z.strictObject({ code: z.literal(PROBE_FAILURE_CODES.host_probe_failed) }).meta(diagnosticContract),
  }),
  NativeEnvelopeSchema.safeExtend({
    type: z.literal("host_probe_cleanup_failed"),
    data: z.strictObject({ code: z.literal(PROBE_FAILURE_CODES.host_probe_cleanup_failed) }).meta(diagnosticContract),
  }),
  NativeEnvelopeSchema.safeExtend({
    type: z.literal("host_probe_body_cleanup_failed"),
    data: z.strictObject({ code: z.literal(PROBE_FAILURE_CODES.host_probe_body_cleanup_failed) }).meta(diagnosticContract),
  }),
  NativeEnvelopeSchema.safeExtend({
    type: z.literal("task_profile_failed"),
    data: z.strictObject({ code: z.literal(PROBE_FAILURE_CODES.task_profile_failed) }).meta(diagnosticContract),
  }),
]);
export const ProbeEventSchema = z.union([CompletionEventSchema, FailureEventSchema]).meta(diagnosticContract);
export type ProbeEvent = z.infer<typeof ProbeEventSchema>;
export type ProbeDiagnosticData = ProbeEvent["data"];
export type ProbeEventOutput = (event: ProbeEvent) => void;
export type ProbeOperation = z.infer<typeof CompletionDataSchema>["operation"];

export function createProbeCompletionEvent(input: {
  context: OperationMetadata; operation: ProbeOperation; outcome: z.infer<typeof CompletionDataSchema>["outcome"];
}) {
  return CompletionEventSchema.parse(createCloudEvent({
    source: HOST_PROBE_EVENT_SOURCE, type: "host_probe_completed", context: input.context,
    data: { operation: input.operation, outcome: input.outcome },
    parseData: value => CompletionDataSchema.parse(value),
  }));
}

export function createProbeFailureEvent(input: { context: OperationMetadata; type: ProbeFailureType }) {
  const code = PROBE_FAILURE_CODES[input.type];
  return FailureEventSchema.parse(createCloudEvent({
    source: HOST_PROBE_EVENT_SOURCE, type: input.type, context: input.context,
    data: { code }, parseData: value => z.strictObject({ code: z.literal(code) }).parse(value),
  }));
}

export function readProbeEvent(raw: unknown): ProbeEvent {
  return ProbeEventSchema.parse(readCloudEvent(raw, value => value));
}
