/** What did one configured feed actually return on one native pipeline run? */
import { z } from "zod";
import { DateStampSchema, RunIdSchema, SchemaVersionSchema, Sha256Schema, SlugSchema, TimestampSchema } from "./primitives";

// Native contracts/feed_health.py and feed_retirement.py own these wire shapes.
export const FeedHealthRowSchema = z.strictObject({
  version: SchemaVersionSchema.default("2026-09-02T20:00"), run_id: RunIdSchema, date: DateStampSchema,
  feed_id: SlugSchema, checked_at: TimestampSchema,
  outcome: z.enum(["ok", "robots_denied", "blocked", "permanent", "transient", "skipped"]),
  status: z.int().min(100).max(599).nullable().default(null), items: z.int().nonnegative().default(0),
  detail: z.string().max(200).nullable().default(null), endpoint_key: Sha256Schema.nullable().default(null),
  robots_outcome: z.enum(["allowed", "denied", "unreachable"]).nullable().default(null),
  robots_checked_at: TimestampSchema.nullable().default(null), robots_status: z.int().min(100).max(599).nullable().default(null),
  target_attempted: z.boolean().nullable().default(null),
});
const PreviousFeedHealthSchema = FeedHealthRowSchema.omit({
  endpoint_key: true, robots_outcome: true, robots_checked_at: true, robots_status: true, target_attempted: true,
});
export const FeedHealthContract = {
  schema: FeedHealthRowSchema, schemaVersion: "2026-09-02T20:00",
  legacyVersions: {
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
export const FeedRetirementRowSchema = z.strictObject({
  version: SchemaVersionSchema.default("2026-09-17"), feed_id: SlugSchema, endpoint_key: Sha256Schema,
  retired_on: DateStampSchema, decided_by_run: RunIdSchema,
  cause: z.enum(["http_410", "low_yield"]),
  evidence_run_ids: z.array(RunIdSchema).default([]), evidence_dates: z.array(DateStampSchema).default([]),
}).superRefine((row, ctx) => {
  const runs = row.evidence_run_ids.length;
  const dates = row.evidence_dates.length;
  if (row.cause === "http_410" ? !runs || dates : !dates || runs) {
    ctx.addIssue({ code: "custom", message: "Retirement evidence must match its cause" });
  }
  if (new Set(row.evidence_run_ids).size !== runs || new Set(row.evidence_dates).size !== dates) {
    ctx.addIssue({ code: "custom", message: "Retirement evidence must name distinct runs or days" });
  }
});
export const FeedRetirementContract = {
  schema: FeedRetirementRowSchema, schemaVersion: "2026-09-17",
  legacyVersions: {
    "2026-09-02T20:00": {
      schema: z.strictObject({
        ...z.strictObject(FeedRetirementRowSchema.shape).omit({ evidence_dates: true }).shape,
        cause: z.literal("http_410"),
      }),
      migrate: (row: object) => FeedRetirementRowSchema.parse(row),
    },
  },
};
export type FeedRetirementRow = z.infer<typeof FeedRetirementRowSchema>;
