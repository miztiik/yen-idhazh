/** Which body-free failed-document metadata may enter the optional diagnostic artifact? */
import { z } from "zod";
import { NonEmptySchema } from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";
import { FetchedDocumentSchema, RequestIdSchema } from "./planner-operation.schema";

export const RAW_DOCUMENT_FAILURE_VERSION = "2026-11-01" as const;
export const FailedDocumentMetadataSchema = z.strictObject(FetchedDocumentSchema.shape).omit({
  body: true, observation: true, attempt_observations: true, canonical_url: true,
}).extend({
  canonical_url: FetchedDocumentSchema.shape.canonical_url.nullable(),
  observation: FetchedDocumentSchema.shape.observation.omit({ run_id: true }),
  attempt_observations: z.array(FetchedDocumentSchema.shape.observation.omit({ run_id: true })),
}).meta({
  version: RAW_DOCUMENT_FAILURE_VERSION,
  changelog: [{ version: RAW_DOCUMENT_FAILURE_VERSION, change: "Project failed input to body-free diagnostic metadata." }],
});
export const RawDocumentFailureSchema = z.strictObject({
  schema_version: z.literal(RAW_DOCUMENT_FAILURE_VERSION).default(RAW_DOCUMENT_FAILURE_VERSION),
  document_kind: FetchedDocumentSchema.shape.fetch_item_type,
  request_id: RequestIdSchema,
  operation: z.enum(["fetch", "parse"]),
  failed_at: RecordedInstantSchema.describe("Actual recorded UTC failure instant."),
  failure_reason: NonEmptySchema,
  document: FailedDocumentMetadataSchema,
}).refine(value => value.document_kind === value.document.fetch_item_type, {
  message: "Failure kind must match its document metadata",
  path: ["document_kind"],
}).meta({
  version: RAW_DOCUMENT_FAILURE_VERSION,
  changelog: [
    { version: RAW_DOCUMENT_FAILURE_VERSION, change: "Remove bodies and repeated run identity from failure diagnostics." },
  ],
});
export type RawDocumentFailure = z.infer<typeof RawDocumentFailureSchema>;
