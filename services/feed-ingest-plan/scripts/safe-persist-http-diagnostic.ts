/** Which native delivery facts and receiving operation can cross the diagnostic relay? */
import { z } from "zod";
import {
  CloudEventSchema, createCloudEvent, OperationMetadataSchema, PlannerErrorResponseSchema, readCloudEvent, writeTraceContext,
} from "@idhazh/common-contracts";
import type { OperationMetadata } from "@idhazh/common-contracts";
import { DELIVERY_EVENT_SOURCE } from "../src/declare-event-source";
import { MetadataDeliveryResultSchema, SafePersistHttpRequestSchema } from "./feed-ingest-plan-delivery-result";

export const SafePersistHttpDiagnosticSchema = z.strictObject({
  event: z.literal("safe_persist_http_completed"),
  run_number: SafePersistHttpRequestSchema.shape.runNumber,
  attempt: SafePersistHttpRequestSchema.shape.attempt,
  status: MetadataDeliveryResultSchema.shape.status,
  commit: MetadataDeliveryResultSchema.shape.commit,
  files: MetadataDeliveryResultSchema.shape.files,
  context: OperationMetadataSchema,
}).meta({
  version: "2026-11-05",
  readCompatibility: "current_only; completion diagnostics require the actual receiving operation",
  changelog: [
    { version: "2026-11-05", change: "Retain native delivery facts and complete receiving-operation metadata." },
  ],
});
export type SafePersistHttpDiagnostic = z.infer<typeof SafePersistHttpDiagnosticSchema>;

export const DeliveryCompletionDiagnosticSchema = z.strictObject({
  server_name: z.literal("hono-server"),
  severity: z.enum(["info", "warning", "error"]),
  duration_ms: z.number().finite().nonnegative().nullable(),
  exit_code: z.int().nullable(),
  code: z.string().regex(/^[A-Z][A-Z0-9_]*$/).nullable(),
  group: z.literal("delivery"),
  run_id: SafePersistHttpRequestSchema.shape.runNumber,
  attempt: SafePersistHttpRequestSchema.shape.attempt,
  phase: z.literal("operation_completed"),
  status: MetadataDeliveryResultSchema.shape.status,
  commit: MetadataDeliveryResultSchema.shape.commit,
  files: MetadataDeliveryResultSchema.shape.files,
  context: OperationMetadataSchema,
}).meta({
  version: "2026-11-05",
  readCompatibility: "current_only; completion payloads are separate from server lifecycle payloads",
  changelog: [
    { version: "2026-11-05", change: "Preserve native delivery facts and the complete request context in completion events." },
  ],
});

type Completion = z.infer<typeof DeliveryCompletionDiagnosticSchema>;
type CompletionAncillary = Partial<Pick<Completion, "severity" | "duration_ms" | "exit_code" | "code">>;

export function createDeliveryCompletionEvent(input: {
  source: string; runNumber: z.infer<typeof SafePersistHttpRequestSchema>["runNumber"];
} & Pick<Completion, "attempt" | "status" | "commit" | "files" | "context"> & CompletionAncillary) {
  return CompletionEventSchema.parse(createCloudEvent({
    source: input.source, type: "safe_persist_http_completed", context: input.context,
    data: {
      server_name: "hono-server", group: "delivery", phase: "operation_completed",
      run_id: input.runNumber, attempt: input.attempt,
      status: input.status, commit: input.commit, files: input.files, context: input.context,
      severity: input.severity ?? "info", duration_ms: input.duration_ms ?? null,
      exit_code: input.exit_code ?? null, code: input.code ?? null,
    },
    parseData: value => DeliveryCompletionDiagnosticSchema.parse(value),
  }));
}

const diagnosticContract = {
  version: "2026-11-05",
  readCompatibility: "current_only; diagnostic readers and writers change together",
  changelog: [
    { version: "2026-11-05", change: "Declare native delivery events and require the receiving-operation carrier." },
  ],
};
// Native optional operation fields retain their own model and the complete shared JSON checks.
const CompletionEventSchema = z.strictObject({
  ...CloudEventSchema.shape,
  type: z.literal("safe_persist_http_completed"), data: DeliveryCompletionDiagnosticSchema,
}).refine(event => CloudEventSchema.safeParse(event).success, {
  message: "Delivery must match the shared CloudEvents JSON profile",
}).refine(event => {
  const operation = OperationMetadataSchema.safeParse(event.data.context);
  if (!operation.success) return false;
  const carrier = writeTraceContext(operation.data);
  return event.traceparent === carrier.traceparent && event.tracestate === carrier.tracestate;
}, { path: ["traceparent"], message: "Delivery carrier must match its receiving context" });
const FailureDataSchema = z.strictObject({
  code: PlannerErrorResponseSchema.shape.code,
}).meta(diagnosticContract);
const FailureEventSchema = CloudEventSchema.safeExtend({
  source: z.literal(DELIVERY_EVENT_SOURCE),
  type: z.literal("safe_persist_http_failed"), data: FailureDataSchema,
});
export const DeliveryEventSchema = z.union([CompletionEventSchema, FailureEventSchema]).meta(diagnosticContract);
export type DeliveryEvent = z.infer<typeof DeliveryEventSchema>;
export type DeliveryEventOutput = (event: DeliveryEvent) => void;

export function createDeliveryFailureEvent(input: {
  context: OperationMetadata; code: z.infer<typeof FailureDataSchema>["code"];
}) {
  return FailureEventSchema.parse(createCloudEvent({
    source: DELIVERY_EVENT_SOURCE, type: "safe_persist_http_failed", context: input.context,
    data: { code: input.code }, parseData: value => FailureDataSchema.parse(value),
  }));
}

export function readDeliveryEvent(raw: unknown): DeliveryEvent {
  return DeliveryEventSchema.parse(readCloudEvent(raw, value => value));
}
