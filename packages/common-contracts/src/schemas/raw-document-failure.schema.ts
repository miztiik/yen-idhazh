/** Which body-free failed-document metadata may enter the optional diagnostic artifact? */
import { z } from "zod";
import { NonEmptySchema } from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";
import { checkDocumentCandidate, checkDocumentObservations, FetchedDocumentSchema } from "./planner-operation.schema";
import { OperationMetadataSchema } from "./operation-metadata.schema";

export const RAW_DOCUMENT_FAILURE_VERSION = "2026-11-05" as const;
const FailedObservationSchema = OperationMetadataSchema.safeExtend(
  z.strictObject(FetchedDocumentSchema.shape.observation.shape).omit({ run_id: true }).shape,
);
export const FailedDocumentMetadataSchema = z.strictObject(FetchedDocumentSchema.shape).omit({
  body: true, observation: true, attempt_observations: true, canonical_url: true,
}).extend({
  canonical_url: FetchedDocumentSchema.shape.canonical_url.nullable(),
  observation: FailedObservationSchema,
  attempt_observations: z.array(FailedObservationSchema),
}).superRefine(checkDocumentCandidate).superRefine(checkDocumentObservations).meta({
  version: RAW_DOCUMENT_FAILURE_VERSION,
  changelog: [
    { version: RAW_DOCUMENT_FAILURE_VERSION, change: "Validate generic document identities and their matching observations." },
    { version: "2026-11-04", change: "Require matching captured article candidates in failed-document metadata." },
    { version: "2026-11-03", change: "Keep native operation context in failed-document observations." },
    { version: "2026-11-02", change: "Remove robots fields from failed-document metadata." },
    { version: "2026-11-01", change: "Earlier changes are in Git history." },
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
    { version: RAW_DOCUMENT_FAILURE_VERSION, change: "Name the failed input's generic address key document_id." },
    { version: "2026-11-04", change: "Retain the captured article candidate in private failure records." },
    { version: "2026-11-03", change: "Identify the failed operation with native context and input links." },
    { version: "2026-11-02", change: "Retain target-only fetched metadata in failure artifacts." },
    { version: "2026-11-01", change: "Earlier changes are in Git history." },
  ],
});
export type RawDocumentFailure = z.infer<typeof RawDocumentFailureSchema>;
