/** Which stored health fields does each independent history use require? */
import { z } from "zod";
import { FeedHealthStateRowSchema } from "./feed-health-state.schema";
import { reject } from "./primitives";

export const FeedHealthIdentitySchema = z.object(FeedHealthStateRowSchema.shape).pick({
  date: true, run_id: true, attempt: true, feed_id: true, endpoint_key: true,
});
const identity = FeedHealthIdentitySchema.shape;
const health = FeedHealthStateRowSchema.shape;
const rejection = health.rejection_counts.element.shape;

export const FeedHealthRequestFieldsSchema = z.object({
  ...identity, feed_requests: health.feed_requests,
  article_requests: health.article_requests, robots_requests: health.robots_requests,
});

function checkWorkDay(value: { date: string; checked_at: string | null }, ctx: z.RefinementCtx) {
  if (value.checked_at !== null && value.date !== value.checked_at.slice(0, 10)) {
    reject(ctx, "health date must name the actual UTC work day", ["checked_at"]);
  }
}
const readFields = {
  ...identity, checked_at: health.checked_at, outcome: health.outcome, items: health.items,
};
export const FeedHealthRestFieldsSchema = z.object(readFields).superRefine(checkWorkDay);
export const FeedHealthReliabilityFieldsSchema = z.object(readFields).superRefine(checkWorkDay);
export const FeedHealthAdmissionFieldsSchema = z.object({
  ...identity, article_candidates: health.article_candidates,
  counts_complete: health.counts_complete,
  rejection_counts: z.array(z.object({
    reason_code: rejection.reason_code, count: rejection.count,
    subject: rejection.subject, attribution: rejection.attribution,
  })),
});
export const FeedHealthFieldUseSchema = z.enum(["request_totals", "feed_rest", "feed_reliability", "article_admission"]);
export type FeedHealthFieldUse = z.infer<typeof FeedHealthFieldUseSchema>;
export type FeedHealthIdentity = z.infer<typeof FeedHealthIdentitySchema>;
export type FeedHealthRequestFields = z.infer<typeof FeedHealthRequestFieldsSchema>;
export type FeedHealthRestFields = z.infer<typeof FeedHealthRestFieldsSchema>;
export type FeedHealthReliabilityFields = z.infer<typeof FeedHealthReliabilityFieldsSchema>;
export type FeedHealthAdmissionFields = z.infer<typeof FeedHealthAdmissionFieldsSchema>;
