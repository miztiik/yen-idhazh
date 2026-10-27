/** What did one configured feed actually return on one native pipeline run? */
import { z } from "zod";
import { DateStampSchema, RunIdSchema, SchemaVersionSchema, Sha256Schema, SlugSchema, TimestampSchema } from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";
import { PUBLISHER_IDENTITY_VERSION } from "../version";

// Native contracts/feed_health.py owns this wire shape.
export const FeedHealthRowSchema = z.strictObject({
  version: SchemaVersionSchema.default(PUBLISHER_IDENTITY_VERSION), run_id: RunIdSchema, date: DateStampSchema,
  feed_id: SlugSchema, checked_at: RecordedInstantSchema,
  outcome: z.enum(["ok", "robots_denied", "blocked", "permanent", "transient", "skipped"]),
  status: z.int().min(100).max(599).nullable().default(null), items: z.int().nonnegative().default(0),
  detail: z.string().max(200).nullable().default(null), endpoint_key: Sha256Schema.nullable().default(null),
  robots_outcome: z.enum(["allowed", "denied", "unreachable"]).nullable().default(null),
  robots_checked_at: TimestampSchema.nullable().default(null), robots_status: z.int().min(100).max(599).nullable().default(null),
  target_attempted: z.boolean().nullable().default(null),
  publisher_id: SlugSchema.nullable().default(null),
});
export type FeedHealthRow = z.infer<typeof FeedHealthRowSchema>;
