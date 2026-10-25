/** Which per-source request estimate is saved for a derived state revision? */
import { z } from "zod";
import { FEED_OPERATIONAL_STATE_VERSION } from "../version";
import {
  CommitShaSchema, CountSchema, DateStampSchema, NonEmptySchema, NonNegativeSchema,
  PositiveCountSchema, SlugSchema, TimestampSchema, reject,
} from "./primitives";

export const FeedIngestOperationalStateRowSchema = z.strictObject({
  version: z.literal(FEED_OPERATIONAL_STATE_VERSION).default(FEED_OPERATIONAL_STATE_VERSION),
  date: DateStampSchema,
  state_revision: PositiveCountSchema, parent_revision: PositiveCountSchema.nullable(),
  written_at_utc: TimestampSchema, evidence_cutoff_utc: TimestampSchema,
  window_days: PositiveCountSchema, window_start: DateStampSchema, window_end: DateStampSchema,
  code_revision: CommitShaSchema, policy_version: NonEmptySchema, source_id: SlugSchema,
  evidence_start_utc: TimestampSchema.nullable(), evidence_end_utc: TimestampSchema.nullable(),
  measured_target_requests: CountSchema.nullable(), measured_source_wasted_requests: CountSchema.nullable(),
  observed_attempted_opportunities: CountSchema, observed_measured_opportunities: CountSchema,
  measured_coverage: NonNegativeSchema.max(1).nullable(),
  qualification_status: z.enum(["qualified", "insufficient_support", "unavailable"]),
  request_waste_ratio: NonNegativeSchema.max(1).nullable(),
  operational_penalty: NonNegativeSchema.max(1).nullable(),
}).superRefine((value, ctx) => {
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
});
export type FeedIngestOperationalStateRow = z.infer<typeof FeedIngestOperationalStateRowSchema>;

export const OperationalStateReadSchema = z.strictObject({
  status: z.enum(["current", "stale_fallback", "unavailable"]),
  state_revision: PositiveCountSchema.nullable(),
  notices: z.array(z.literal("restrictions_unverified")).default([]),
  lifecycle_window_days: PositiveCountSchema,
  lifecycle_window_start: DateStampSchema.nullable(),
  lifecycle_window_end: DateStampSchema.nullable(),
  request_window_days: PositiveCountSchema,
  request_window_start: DateStampSchema.nullable(),
  request_window_end: DateStampSchema.nullable(),
}).superRefine((value, ctx) => {
  const expectedNotices = value.status === "unavailable" ? ["restrictions_unverified"] : [];
  if (JSON.stringify(value.notices) !== JSON.stringify(expectedNotices)) {
    reject(ctx, "an unavailable state has the neutral restrictions warning only");
  }
  if (value.status === "unavailable") {
    if ([
      value.state_revision,
      value.lifecycle_window_start,
      value.lifecycle_window_end,
      value.request_window_start,
      value.request_window_end,
    ].some(item => item !== null)) {
      reject(ctx, "unavailable state has no saved revision or window");
    }
  } else if (value.state_revision === null || [
    value.lifecycle_window_start,
    value.lifecycle_window_end,
    value.request_window_start,
    value.request_window_end,
  ].some(item => item === null)) {
    reject(ctx, "a saved state reading retains its revision and original window");
  }
  const windows: [string | null, string | null][] = [
    [value.lifecycle_window_start, value.lifecycle_window_end],
    [value.request_window_start, value.request_window_end],
  ];
  for (const [start, end] of windows) {
    if (start !== null && end !== null && start > end) {
      reject(ctx, "operational state window starts after it ends");
    }
  }
});
export type OperationalStateRead = z.infer<typeof OperationalStateReadSchema>;

export const SelectionStateCaptureSchema = z.strictObject({
  capture_status: z.enum(["captured", "not_recorded"]),
  selection_started_at_utc: TimestampSchema.nullable().default(null),
  state: OperationalStateReadSchema.nullable().default(null),
}).superRefine((value, ctx) => {
  if (value.capture_status === "captured") {
    if (value.selection_started_at_utc === null || value.state === null) {
      reject(ctx, "a captured selection state records its clock and state");
    }
  } else if (value.selection_started_at_utc !== null || value.state !== null) {
    reject(ctx, "an unrecorded legacy selection has no captured clock or state");
  }
});
export type SelectionStateCapture = z.infer<typeof SelectionStateCaptureSchema>;
