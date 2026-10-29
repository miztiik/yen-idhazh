/** Which body-free facts explain one parsed candidate that lost a selection? */
import { z } from "zod";
import { DropReasonSchema, REASON_STAGES, RetainedRejectionReasonSchema } from "./rejection.schema";
import { RecordedInstantSchema } from "./recorded-instant.schema";
import {
  DateStampSchema, PositiveCountSchema, RejectionStageSchema, RunIdSchema,
  Sha256Schema, SlugSchema, reject,
} from "./primitives";

export const REJECTED_ARTICLE_VERSION = "2026-10-29";
export const REJECTED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS = ["2026-10-27", "2026-10-29"] as const;
export const RejectedArticleRowSchema = z.strictObject({
  run_id: RunIdSchema, attempt: PositiveCountSchema, date: DateStampSchema,
  candidate_id: Sha256Schema, url_key: Sha256Schema, feed_id: SlugSchema,
  stage: RejectionStageSchema, reason_code: RetainedRejectionReasonSchema,
  freshness_cutoff_at: RecordedInstantSchema.nullable(),
}).superRefine((row, ctx) => {
  if (!row.run_id.startsWith(`${row.date}-`)) reject(ctx, "rejected date must match its selection run");
  if (row.stage === "harvest-feeds") reject(ctx, "only parsed candidates have selection rejection rows", ["stage"]);
  const currentReason = DropReasonSchema.safeParse(row.reason_code);
  if (currentReason.success && !REASON_STAGES[currentReason.data].includes(row.stage)) {
    reject(ctx, "reason does not belong to its rejection stage", ["reason_code"]);
  }
}).meta({
  version: REJECTED_ARTICLE_VERSION,
  changelog: [
    { version: REJECTED_ARTICLE_VERSION, change: "Accept bounded retained reason strings without rewriting ledger rows." },
    { version: "2026-10-27", change: "Declare terminal selection rejections without article text or titles." },
  ],
});
export type RejectedArticleRow = z.infer<typeof RejectedArticleRowSchema>;
export const RejectedArticleRowContract = {
  schema: RejectedArticleRowSchema, schemaVersion: REJECTED_ARTICLE_VERSION,
  acceptedSchemaVersions: REJECTED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS,
} as const;
