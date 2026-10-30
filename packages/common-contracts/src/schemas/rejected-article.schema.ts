/** Which body-free facts explain one terminal harvest failure or parsed candidate selection loss? */
import { z } from "zod";
import { DropReasonSchema, HarvestArticleFailureReasonSchema, REASON_STAGES, RetainedRejectionReasonSchema } from "./rejection.schema";
import { ArticleFetchEvidenceSchema } from "./harvest-diagnostics.schema";
import { RecordedInstantSchema } from "./recorded-instant.schema";
import {
  DateStampSchema, PositiveCountSchema, RejectionStageSchema, RunIdSchema,
  Sha256Schema, SlugSchema, reject,
} from "./primitives";

export const REJECTED_ARTICLE_VERSION = "2026-10-29T20:15";
export const REJECTED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS = ["2026-10-27", "2026-10-29", REJECTED_ARTICLE_VERSION] as const;
export const LegacyRejectedArticleRowSchema = z.strictObject({
  run_id: RunIdSchema, attempt: PositiveCountSchema, date: DateStampSchema,
  candidate_id: Sha256Schema, url_key: Sha256Schema, feed_id: SlugSchema,
  stage: RejectionStageSchema, reason_code: RetainedRejectionReasonSchema,
  freshness_cutoff_at: RecordedInstantSchema.nullable(),
});
export const RejectedArticleRowSchema = LegacyRejectedArticleRowSchema.extend({
  candidate_id: Sha256Schema.nullable(), ...ArticleFetchEvidenceSchema.shape,
}).superRefine((row, ctx) => {
  if (!row.run_id.startsWith(`${row.date}-`)) reject(ctx, "rejected date must match its selection run");
  const harvestFailure = row.stage === "harvest-feeds"
    && HarvestArticleFailureReasonSchema.safeParse(row.reason_code).success;
  if (row.stage === "harvest-feeds" && !harvestFailure) reject(ctx, "only terminal article fetch or extraction failures belong to harvest rejection rows", ["stage"]);
  if (row.candidate_id === null && !harvestFailure) reject(ctx, "only harvest article failures may omit a candidate identity", ["candidate_id"]);
  const currentReason = DropReasonSchema.safeParse(row.reason_code);
  if (currentReason.success && !REASON_STAGES[currentReason.data].includes(row.stage)) {
    reject(ctx, "reason does not belong to its rejection stage", ["reason_code"]);
  }
}).meta({
  version: REJECTED_ARTICLE_VERSION,
  changelog: [
    { version: REJECTED_ARTICLE_VERSION, change: "Retain terminal article fetch evidence and harvest failures without parsed candidate identities." },
    { version: "2026-10-29", change: "Accept bounded retained reason strings without rewriting ledger rows." },
    { version: "2026-10-27", change: "Declare terminal selection rejections without article text or titles." },
  ],
});
export type RejectedArticleRow = z.infer<typeof RejectedArticleRowSchema>;
export const RejectedArticleRowContract = {
  schema: RejectedArticleRowSchema, schemaVersion: REJECTED_ARTICLE_VERSION,
  acceptedSchemaVersions: REJECTED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS,
  historicalSchemas: {
    "2026-10-27": LegacyRejectedArticleRowSchema,
    "2026-10-29": LegacyRejectedArticleRowSchema,
  },
} as const;
