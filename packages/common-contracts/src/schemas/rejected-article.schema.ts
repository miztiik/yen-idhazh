/** Which body-free facts explain one terminal harvest failure or parsed candidate selection loss? */
import { z } from "zod";
import { DropReasonSchema, HarvestArticleFailureReasonSchema, REASON_STAGES, RetainedRejectionReasonSchema } from "./rejection.schema";
import { ArticleFetchEvidenceSchema } from "./harvest-diagnostics.schema";
import { RecordedInstantSchema } from "./recorded-instant.schema";
import {
  CandidateIdSchema, DateStampSchema, PositiveCountSchema, RejectionStageSchema, RunIdSchema,
  Sha256Schema, SlugSchema, reject,
} from "./primitives";

export const REJECTED_ARTICLE_VERSION = "2026-11-04";
export const RejectedArticleRowSchema = z.strictObject({
  run_id: RunIdSchema, attempt: PositiveCountSchema, date: DateStampSchema,
  candidate_id: CandidateIdSchema, url_key: Sha256Schema, feed_id: SlugSchema,
  stage: RejectionStageSchema, reason_code: RetainedRejectionReasonSchema,
  freshness_cutoff_at: RecordedInstantSchema.nullable(),
  ...ArticleFetchEvidenceSchema.shape,
}).superRefine((row, ctx) => {
  if (!row.run_id.startsWith(`${row.date}-`)) reject(ctx, "rejected date must match its selection run");
  const harvestFailure = row.stage === "harvest-feeds"
    && HarvestArticleFailureReasonSchema.safeParse(row.reason_code).success;
  if (row.stage === "harvest-feeds" && !harvestFailure) reject(ctx, "only terminal article fetch or extraction failures belong to harvest rejection rows", ["stage"]);
  const currentReason = DropReasonSchema.safeParse(row.reason_code);
  if (currentReason.success && !REASON_STAGES[currentReason.data].includes(row.stage)) {
    reject(ctx, "reason does not belong to its rejection stage", ["reason_code"]);
  }
}).meta({
  version: REJECTED_ARTICLE_VERSION,
  changelog: [
    { version: REJECTED_ARTICLE_VERSION, change: "Require a non-null captured UUIDv4 for terminal article settlement." },
    { version: "2026-11-02", change: "Remove robots permission, status and failure columns." },
    { version: "2026-11-02", change: "Use current global age, duplicate-carrier and capacity loss causes." },
    { version: "2026-11-01", change: "Retain request pacing evidence in terminal fetch failures." },
    { version: "2026-10-29", change: "Earlier changes are in git." },
  ],
});
export type RejectedArticleRow = z.infer<typeof RejectedArticleRowSchema>;
export const RejectedArticleRowContract = {
  schema: RejectedArticleRowSchema, schemaVersion: REJECTED_ARTICLE_VERSION,
} as const;
