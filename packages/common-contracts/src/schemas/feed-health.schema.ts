/** What did one configured feed actually return on one native pipeline run? */
import { z } from "zod";
import { DateStampSchema, RunIdSchema, SchemaVersionSchema, Sha256Schema, SlugSchema, TimestampSchema } from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";

// Native contracts/feed_health.py owns this wire shape.
export const FeedHealthRowSchema = z.strictObject({
  version: SchemaVersionSchema.default("2026-10-23T18:50"), run_id: RunIdSchema, date: DateStampSchema,
  feed_id: SlugSchema, checked_at: RecordedInstantSchema,
  outcome: z.enum(["ok", "robots_denied", "blocked", "permanent", "transient", "skipped"]),
  status: z.int().min(100).max(599).nullable().default(null), items: z.int().nonnegative().default(0),
  detail: z.string().max(200).nullable().default(null), endpoint_key: Sha256Schema.nullable().default(null),
  robots_outcome: z.enum(["allowed", "denied", "unreachable"]).nullable().default(null),
  robots_checked_at: TimestampSchema.nullable().default(null), robots_status: z.int().min(100).max(599).nullable().default(null),
  target_attempted: z.boolean().nullable().default(null),
}).superRefine((row, ctx) => {
  if (row.checked_at.includes(".") && row.version < "2026-10-23T18:50") {
    ctx.addIssue({ code: "custom", message: "legacy feed health records use whole-second checked_at" });
  }
});
const LegacyEndpointHealthSchema = z.strictObject(FeedHealthRowSchema.shape).extend({
  version: SchemaVersionSchema.default("2026-09-02T20:00"), checked_at: TimestampSchema,
});
const PreviousFeedHealthSchema = LegacyEndpointHealthSchema.omit({
  endpoint_key: true, robots_outcome: true, robots_checked_at: true, robots_status: true, target_attempted: true,
});
export const FeedHealthContract = {
  schema: FeedHealthRowSchema, schemaVersion: "2026-10-23T18:50",
  legacyVersions: {
    "2026-09-02T20:00": {
      schema: LegacyEndpointHealthSchema,
      migrate: (row: object) => FeedHealthRowSchema.parse(row),
    },
    "2026-08-23": {
      schema: PreviousFeedHealthSchema,
      migrate: (row: object) => FeedHealthRowSchema.parse(row),
    },
    "2026-08-23T12:00": {
      schema: PreviousFeedHealthSchema,
      migrate: (row: object) => FeedHealthRowSchema.parse(row),
    },
  },
};
export type FeedHealthRow = z.infer<typeof FeedHealthRowSchema>;
