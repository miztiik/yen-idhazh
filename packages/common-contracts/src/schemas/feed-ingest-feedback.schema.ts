/** Which per-source request estimate is saved for a derived state revision? */
import { z } from "zod";
import { FEED_OPERATIONAL_STATE_VERSION } from "../version";
import {
  CommitShaSchema, CountSchema, DateStampSchema, NonEmptySchema, NonNegativeSchema,
  PositiveCountSchema, Sha256Schema, SlugSchema, TimestampSchema, reject,
} from "./primitives";

const operationalStateFields = {
  date: DateStampSchema,
  state_revision: PositiveCountSchema, parent_revision: PositiveCountSchema.nullable(),
  written_at_utc: TimestampSchema, evidence_cutoff_utc: TimestampSchema,
  window_days: PositiveCountSchema, window_start: DateStampSchema, window_end: DateStampSchema,
  code_revision: CommitShaSchema, policy_version: NonEmptySchema, source_id: SlugSchema,
  snapshot_source_ids: z.array(SlugSchema).nonempty().nullable().default(null),
  snapshot_sha256: Sha256Schema.nullable().default(null),
  evidence_start_utc: TimestampSchema.nullable(), evidence_end_utc: TimestampSchema.nullable(),
  measured_target_requests: CountSchema.nullable(), measured_source_wasted_requests: CountSchema.nullable(),
  observed_attempted_opportunities: CountSchema, observed_measured_opportunities: CountSchema,
  measured_coverage: NonNegativeSchema.max(1).nullable(),
  qualification_status: z.enum(["qualified", "insufficient_support", "unavailable"]),
  request_waste_ratio: NonNegativeSchema.max(1).nullable(),
  operational_penalty: NonNegativeSchema.max(1).nullable(),
};
function validateOperationalState(value: {
  parent_revision: number | null; state_revision: number; window_start: string; window_end: string;
  evidence_start_utc: string | null; evidence_end_utc: string | null;
  measured_target_requests: number | null; measured_source_wasted_requests: number | null;
  observed_measured_opportunities: number; observed_attempted_opportunities: number;
  qualification_status: "qualified" | "insufficient_support" | "unavailable";
  measured_coverage: number | null; request_waste_ratio: number | null; operational_penalty: number | null;
  snapshot_source_ids: string[] | null; snapshot_sha256: string | null;
}, ctx: z.RefinementCtx) {
  if ((value.snapshot_source_ids === null) !== (value.snapshot_sha256 === null)) {
    reject(ctx, "snapshot source roster and digest are available together");
  }
  if (value.snapshot_source_ids !== null
    && value.snapshot_source_ids.some((source, index) => index > 0 && source <= value.snapshot_source_ids![index - 1]!)) {
    reject(ctx, "snapshot source IDs must be unique and sorted");
  }
  if (value.parent_revision !== null && value.parent_revision >= value.state_revision) {
    reject(ctx, "parent revision must be older than the saved state");
  }
  if (value.window_start > value.window_end) reject(ctx, "operational evidence window starts after it ends");
  if (value.evidence_start_utc !== null && value.evidence_end_utc !== null
    && value.evidence_start_utc > value.evidence_end_utc) {
    reject(ctx, "observed evidence starts after it ends");
  }
  if ((value.measured_target_requests === null) !== (value.measured_source_wasted_requests === null)) {
    reject(ctx, "measured request totals and waste are available together");
  }
  if (value.measured_target_requests !== null
    && value.measured_source_wasted_requests! > value.measured_target_requests) {
    reject(ctx, "wasted requests cannot exceed total requests");
  }
  if (value.observed_measured_opportunities > value.observed_attempted_opportunities) {
    reject(ctx, "measured opportunities cannot exceed attempted opportunities");
  }
  if (value.qualification_status === "qualified") {
    if (value.measured_target_requests === null || value.measured_target_requests === 0
      || value.measured_coverage === null || value.request_waste_ratio === null
      || value.operational_penalty === null) {
      reject(ctx, "qualified state has positive measured requests and coverage");
    }
  } else if (value.request_waste_ratio !== null || value.operational_penalty !== null) {
    reject(ctx, "unqualified state has no request estimate or score adjustment");
  }
}

export const FeedIngestOperationalStateRowSchema = z.strictObject({
  version: z.literal(FEED_OPERATIONAL_STATE_VERSION).default(FEED_OPERATIONAL_STATE_VERSION),
  ...operationalStateFields,
}).superRefine(validateOperationalState);
export type FeedIngestOperationalStateRow = z.infer<typeof FeedIngestOperationalStateRowSchema>;

const {
  snapshot_source_ids: _snapshotSourceIds,
  snapshot_sha256: _snapshotSha256,
  ...legacyOperationalStateFields
} = operationalStateFields;
export const PreviousFeedIngestOperationalStateRowSchema = z.strictObject({
  version: z.literal("2026-10-25"),
  ...legacyOperationalStateFields,
}).superRefine((value, ctx) => validateOperationalState({
  ...value, snapshot_source_ids: null, snapshot_sha256: null,
}, ctx));

export const OperationalStateReadSchema = z.strictObject({
  status: z.enum(["current", "stale_fallback", "unavailable"]),
  state_revision: PositiveCountSchema.nullable(),
  window_days: PositiveCountSchema,
  window_start: DateStampSchema.nullable(), window_end: DateStampSchema.nullable(),
}).superRefine((value, ctx) => {
  if (value.status === "unavailable") {
    if ([value.state_revision, value.window_start, value.window_end].some(item => item !== null)) {
      reject(ctx, "unavailable state has no saved revision or window");
    }
  } else if (value.state_revision === null || value.window_start === null || value.window_end === null) {
    reject(ctx, "a saved state reading retains its revision and original window");
  }
  if (value.window_start !== null && value.window_end !== null && value.window_start > value.window_end) {
    reject(ctx, "operational state window starts after it ends");
  }
});
export type OperationalStateRead = z.infer<typeof OperationalStateReadSchema>;
