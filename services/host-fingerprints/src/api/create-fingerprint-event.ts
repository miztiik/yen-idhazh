/** Which safe native outcomes identify actual fingerprint work? */
import { z } from "zod";
import { CloudEventSchema, createCloudEvent, readCloudEvent } from "@idhazh/common-contracts";
import type { OperationMetadata } from "@idhazh/common-contracts";
import { HOST_FINGERPRINT_EVENT_SOURCE } from "../declare-event-source";

export const HOST_FINGERPRINT_EVENT_VERSION = "2026-11-05";
const diagnosticContract = {
  version: HOST_FINGERPRINT_EVENT_VERSION,
  readCompatibility: "current_only; diagnostic readers and writers change together",
  changelog: [
    { version: HOST_FINGERPRINT_EVENT_VERSION, change: "Declare safe native fingerprint outcomes and failures." },
  ],
};
const CompletionDataSchema = z.strictObject({
  status: z.enum(["written", "disabled"]),
}).meta(diagnosticContract);
const FailureDataSchema = z.strictObject({
  code: z.literal("HOST_FINGERPRINT_FAILED"),
}).meta(diagnosticContract);
const CompletionEventSchema = CloudEventSchema.safeExtend({
  source: z.literal(HOST_FINGERPRINT_EVENT_SOURCE),
  type: z.literal("host_fingerprint_completed"), data: CompletionDataSchema,
});
const FailureEventSchema = CloudEventSchema.safeExtend({
  source: z.literal(HOST_FINGERPRINT_EVENT_SOURCE),
  type: z.literal("host_fingerprint_failed"), data: FailureDataSchema,
});
export const FingerprintEventSchema = z.discriminatedUnion("type", [
  CompletionEventSchema, FailureEventSchema,
]).meta(diagnosticContract);
export type FingerprintEvent = z.infer<typeof FingerprintEventSchema>;
export type FingerprintDiagnosticData = FingerprintEvent["data"];
export type FingerprintEventOutput = (event: FingerprintEvent) => void;

export function createFingerprintCompletionEvent(input: {
  context: OperationMetadata; status: z.infer<typeof CompletionDataSchema>["status"];
}) {
  return CompletionEventSchema.parse(createCloudEvent({
    source: HOST_FINGERPRINT_EVENT_SOURCE, type: "host_fingerprint_completed", context: input.context,
    data: { status: input.status }, parseData: value => CompletionDataSchema.parse(value),
  }));
}

export function createFingerprintFailureEvent(input: { context: OperationMetadata }) {
  return FailureEventSchema.parse(createCloudEvent({
    source: HOST_FINGERPRINT_EVENT_SOURCE, type: "host_fingerprint_failed", context: input.context,
    data: { code: "HOST_FINGERPRINT_FAILED" }, parseData: value => FailureDataSchema.parse(value),
  }));
}

export function readFingerprintEvent(raw: unknown): FingerprintEvent {
  return FingerprintEventSchema.parse(readCloudEvent(raw, value => value));
}
