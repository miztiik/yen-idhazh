/** Which failed raw document may enter the optional private diagnostic artifact? */
import { z } from "zod";
import { NonEmptySchema } from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";
import { FetchedDocumentSchema, RequestIdSchema } from "./planner-operation.schema";

export const RAW_DOCUMENT_FAILURE_VERSION = "2026-10-31" as const;
export const RawDocumentFailureSchema = z.strictObject({
  schema_version: z.literal(RAW_DOCUMENT_FAILURE_VERSION).default(RAW_DOCUMENT_FAILURE_VERSION),
  document_kind: FetchedDocumentSchema.shape.fetch_item_type,
  request_id: RequestIdSchema,
  operation: z.enum(["fetch", "parse"]),
  failed_at: RecordedInstantSchema.describe("Actual recorded UTC failure instant."),
  failure_reason: NonEmptySchema,
  document: FetchedDocumentSchema,
}).refine(value => value.document_kind === value.document.fetch_item_type, {
  message: "Failure kind must match its raw document",
  path: ["document_kind"],
}).meta({
  version: RAW_DOCUMENT_FAILURE_VERSION,
  changelog: [
    { version: RAW_DOCUMENT_FAILURE_VERSION, change: "Declare failure-only raw document diagnostics." },
  ],
});
export type RawDocumentFailure = z.infer<typeof RawDocumentFailureSchema>;
