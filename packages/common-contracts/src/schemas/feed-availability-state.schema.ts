/** What durable per-feed check and recovery state may a later planner run read? */
import { z } from "zod";
import { FEED_AVAILABILITY_STATE_VERSION } from "../version";
import {
  CountSchema, NonEmptySchema, PositiveCountSchema, RunIdSchema, Sha256Schema, SlugSchema, reject,
} from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";

const RequestIdSchema = z.uuid({ version: "v4" });

const AvailabilityChangelogSchema = z.array(z.strictObject({
  version: z.literal(FEED_AVAILABILITY_STATE_VERSION),
  change: NonEmptySchema,
})).min(1).max(5);

export const FeedAvailabilityEpisodeSchema = z.strictObject({
  first_confirmed_failure_at: RecordedInstantSchema,
  failed_recovery_checks: CountSchema,
});

export const FeedAvailabilityReservationSchema = z.strictObject({
  request_id: RequestIdSchema,
  run_id: RunIdSchema,
  attempt: PositiveCountSchema,
  reserved_at: RecordedInstantSchema,
  phase: z.enum(["fetch", "parse"]),
  status: z.enum(["reserved", "unknown"]),
});

export const FeedAvailabilityCompletionSchema = z.strictObject({
  request_id: RequestIdSchema,
  run_id: RunIdSchema,
  attempt: PositiveCountSchema,
  completed_at: RecordedInstantSchema,
  result: z.enum([
    "valid-feed", "confirmed-http-failure", "other-http-failure",
    "timeout", "robots", "transport-unknown", "local-failure",
  ]),
  http_status: z.int().min(100).max(599).nullable(),
});

export const FeedAvailabilityRecordSchema = z.strictObject({
  feed_id: SlugSchema,
  endpoint_key: Sha256Schema,
  consecutive_failed_checks: CountSchema,
  rest_until: RecordedInstantSchema.nullable(),
  retired_at: RecordedInstantSchema.nullable(),
  episode: FeedAvailabilityEpisodeSchema.nullable(),
  reservation: FeedAvailabilityReservationSchema.nullable(),
  last_completion: FeedAvailabilityCompletionSchema.nullable(),
  operator_enrollment_id: RequestIdSchema.nullable(),
}).superRefine((value, context) => {
  if (value.retired_at !== null && value.reservation !== null) {
    reject(context, "retired feeds cannot have an in-flight reservation", ["reservation"]);
  }
  if (value.retired_at !== null && value.rest_until !== null) {
    reject(context, "retired feeds cannot have a rest deadline", ["rest_until"]);
  }
});

export const FeedAvailabilityStateSchema = z.strictObject({
  version: z.literal(FEED_AVAILABILITY_STATE_VERSION),
  changelog: AvailabilityChangelogSchema,
  sequence: CountSchema,
  updated_at: RecordedInstantSchema,
  feeds: z.array(FeedAvailabilityRecordSchema),
}).superRefine((value, context) => {
  const ids = value.feeds.map(feed => feed.feed_id);
  if (new Set(ids).size !== ids.length) reject(context, "feed IDs must be unique", ["feeds"]);
  if ([...ids].sort().join("\n") !== ids.join("\n")) reject(context, "feeds must be sorted by feed ID", ["feeds"]);
});

export const FeedAvailabilityEnrollmentSchema = z.strictObject({
  version: z.literal(FEED_AVAILABILITY_STATE_VERSION),
  changelog: AvailabilityChangelogSchema,
  initialized_at: RecordedInstantSchema,
  initial_feed_ids: z.array(SlugSchema).min(1),
  catalog_sha256: Sha256Schema,
}).superRefine((value, context) => {
  if (new Set(value.initial_feed_ids).size !== value.initial_feed_ids.length) {
    reject(context, "initial feed IDs must be unique", ["initial_feed_ids"]);
  }
  if ([...value.initial_feed_ids].sort().join("\n") !== value.initial_feed_ids.join("\n")) {
    reject(context, "initial feed IDs must be sorted", ["initial_feed_ids"]);
  }
});

export type FeedAvailabilityEpisode = z.infer<typeof FeedAvailabilityEpisodeSchema>;
export type FeedAvailabilityReservation = z.infer<typeof FeedAvailabilityReservationSchema>;
export type FeedAvailabilityCompletion = z.infer<typeof FeedAvailabilityCompletionSchema>;
export type FeedAvailabilityRecord = z.infer<typeof FeedAvailabilityRecordSchema>;
export type FeedAvailabilityState = z.infer<typeof FeedAvailabilityStateSchema>;
export type FeedAvailabilityEnrollment = z.infer<typeof FeedAvailabilityEnrollmentSchema>;

export const FeedAvailabilityStateContract = {
  schema: FeedAvailabilityStateSchema, schemaVersion: FEED_AVAILABILITY_STATE_VERSION,
} as const;
export const FeedAvailabilityEnrollmentContract = {
  schema: FeedAvailabilityEnrollmentSchema, schemaVersion: FEED_AVAILABILITY_STATE_VERSION,
} as const;
