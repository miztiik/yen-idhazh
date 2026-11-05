/** Which native delivery facts and receiving operation can cross the diagnostic relay? */
import { z } from "zod";
import { createCloudEvent, OperationMetadataSchema } from "@idhazh/common-contracts";
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
  return createCloudEvent({
    source: input.source, type: "safe_persist_http_completed", context: input.context,
    data: {
      server_name: "hono-server", group: "delivery", phase: "operation_completed",
      run_id: input.runNumber, attempt: input.attempt,
      status: input.status, commit: input.commit, files: input.files, context: input.context,
      severity: input.severity ?? "info", duration_ms: input.duration_ms ?? null,
      exit_code: input.exit_code ?? null, code: input.code ?? null,
    },
    parseData: value => DeliveryCompletionDiagnosticSchema.parse(value),
  });
}
