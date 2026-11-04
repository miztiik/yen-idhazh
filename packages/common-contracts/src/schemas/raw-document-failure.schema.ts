/** Which body-free failed-document metadata may enter the optional diagnostic artifact? */
import { z } from "zod";
import { NonEmptySchema } from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";
import { FetchedDocumentSchema } from "./planner-operation.schema";
import { OperationMetadataSchema } from "./operation-metadata.schema";

export const RAW_DOCUMENT_FAILURE_VERSION = "2026-11-03" as const;
const FailedObservationSchema = OperationMetadataSchema.safeExtend(
  z.strictObject(FetchedDocumentSchema.shape.observation.shape).omit({ run_id: true }).shape,
);
export const FailedDocumentMetadataSchema = z.strictObject(FetchedDocumentSchema.shape).omit({
  body: true, observation: true, attempt_observations: true, canonical_url: true,
}).extend({
  canonical_url: FetchedDocumentSchema.shape.canonical_url.nullable(),
  observation: FailedObservationSchema,
  attempt_observations: z.array(FailedObservationSchema),
}).meta({
  version: RAW_DOCUMENT_FAILURE_VERSION,
  changelog: [
    { version: RAW_DOCUMENT_FAILURE_VERSION, change: "Keep native operation context in failed-document observations." },
    { version: "2026-11-02", change: "Remove robots fields from failed-document metadata." },
    { version: "2026-11-01", change: "Retain request pacing measurements and effective settings." },
    { version: "2026-11-01", change: "Project failed input to body-free diagnostic metadata." },
  ],
});
export const RawDocumentFailureSchema = OperationMetadataSchema.safeExtend({
  schema_version: z.literal(RAW_DOCUMENT_FAILURE_VERSION).default(RAW_DOCUMENT_FAILURE_VERSION),
  document_kind: FetchedDocumentSchema.shape.fetch_item_type,
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
    { version: RAW_DOCUMENT_FAILURE_VERSION, change: "Identify the failed operation with native context and input links." },
    { version: "2026-11-02", change: "Retain target-only fetched metadata in failure artifacts." },
    { version: "2026-11-01", change: "Preserve request pacing evidence in body-free failures." },
    { version: "2026-11-01", change: "Remove bodies and repeated run identity from failure diagnostics." },
  ],
});
export type RawDocumentFailure = z.infer<typeof RawDocumentFailureSchema>;
