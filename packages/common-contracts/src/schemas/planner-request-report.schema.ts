/** Which request totals are known, and which records or UTC days remain unknown? */
import { z } from "zod";
import { CountSchema, DateStampSchema, SlugSchema, reject } from "./primitives";

export const PlannerRequestCounterCoverageSchema = z.strictObject({
  status: z.enum(["complete", "partial", "none"]),
  known_records: CountSchema, unknown_records: CountSchema,
  recorded_days: z.array(DateStampSchema), complete_days: z.array(DateStampSchema),
});
const coverage = PlannerRequestCounterCoverageSchema;
export const PlannerRequestReportSchema = z.strictObject({
  from_day: DateStampSchema, through_day: DateStampSchema, complete: z.boolean(),
  missing_days: z.array(DateStampSchema), unattributed_days: z.array(DateStampSchema),
  input_complete: z.boolean(),
  feeds: z.array(z.strictObject({
    feed_id: SlugSchema, feed_requests: CountSchema.nullable(),
    article_requests: CountSchema.nullable(), robots_requests: CountSchema.nullable(),
    counts_complete: z.boolean(),
    coverage: z.strictObject({ feed_requests: coverage, article_requests: coverage, robots_requests: coverage }),
  })),
}).superRefine((value, ctx) => {
  const validDays = (days: string[]) => new Set(days).size === days.length
    && days.every(day => day >= value.from_day && day <= value.through_day);
  if (value.from_day > value.through_day || !validDays(value.missing_days) || !validDays(value.unattributed_days)) {
    reject(ctx, "request coverage days must be distinct and inside the closed UTC window");
  }
  const dayCount = (Date.parse(value.through_day) - Date.parse(value.from_day)) / 86_400_000 + 1;
  for (const feed of value.feeds) {
    for (const field of ["feed_requests", "article_requests", "robots_requests"] as const) {
      const cell = feed.coverage[field];
      const complete = value.input_complete && value.missing_days.length === 0
        && value.unattributed_days.length === 0 && cell.unknown_records === 0 && cell.complete_days.length === dayCount;
      if (!validDays(cell.recorded_days) || !validDays(cell.complete_days)
        || cell.complete_days.some(day => value.missing_days.includes(day) || value.unattributed_days.includes(day))
        || (cell.known_records === 0) !== (cell.recorded_days.length === 0)
        || cell.recorded_days.length > cell.known_records
        || (cell.status === "complete") !== complete
        || (cell.status === "none") !== (!complete && cell.known_records === 0)
        || (cell.status === "none") !== (feed[field] === null)
        || (cell.status === "partial" && cell.known_records === 0)
        || (cell.known_records === 0 && feed[field] !== null && feed[field] !== 0)) {
        reject(ctx, "request totals must agree with their per-counter coverage", ["feeds", feed.feed_id, field]);
      }
    }
    if (feed.counts_complete !== Object.values(feed.coverage).every(cell => cell.status === "complete")) {
      reject(ctx, "feed accounting must agree with every request counter");
    }
  }
  if (new Set(value.feeds.map(feed => feed.feed_id)).size !== value.feeds.length
    || value.complete !== (value.input_complete && value.missing_days.length === 0
      && value.unattributed_days.length === 0 && value.feeds.every(feed => feed.counts_complete))) {
    reject(ctx, "report completeness must include missing files, staged inputs and counter coverage");
  }
}).meta({
  version: "2026-10-29",
  changelog: [{ version: "2026-10-29", change: "Declare independent request totals and their record and closed-day coverage." }],
});
export type PlannerRequestReport = z.infer<typeof PlannerRequestReportSchema>;
