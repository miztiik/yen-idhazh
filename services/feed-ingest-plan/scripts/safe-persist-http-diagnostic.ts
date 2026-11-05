/** Which native delivery facts and receiving operation can cross the diagnostic relay? */
import { z } from "zod";
import { OperationMetadataSchema } from "@idhazh/common-contracts";
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
