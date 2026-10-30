/** Which authored limits and operator enrollment events govern durable feed availability? */
import { z } from "zod";
import { RelativePathSchema } from "../config/service-settings";

const RequestIdSchema = z.uuid({ version: "v4" });
const FeedIdSchema = z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/);
const PublishedStatePathSchema = RelativePathSchema.refine(
  value => value.startsWith("state/raw/planner/feed-availability/"),
  "must stay under state/raw/planner/feed-availability",
);

export const FeedAvailabilityConfigSchema = z.strictObject({
  state_path: PublishedStatePathSchema,
  enrollment_path: PublishedStatePathSchema,
  initial_enrollment: z.literal("all-active-configured-sources-once"),
  max_enrolled_feeds: z.number().int().positive(),
  max_state_bytes: z.number().int().positive(),
  consecutive_failed_checks_before_rest: z.number().int().positive(),
  rest_hours: z.number().finite().positive(),
  recovery_rest_hours: z.number().finite().min(24),
  failed_recovery_checks_before_retirement: z.number().int().positive(),
  retirement_minimum_age_hours: z.number().finite().positive(),
  max_cas_refresh_attempts: z.number().int().positive(),
  operator_enrollments: z.array(z.strictObject({
    feed_id: FeedIdSchema,
    enrollment_id: RequestIdSchema,
  })),
}).superRefine((config, context) => {
  if (config.state_path === config.enrollment_path) {
    context.addIssue({ code: "custom", path: ["enrollment_path"], message: "Must differ from state_path" });
  }
  const enrollments = config.operator_enrollments.map(value => value.feed_id);
  if (new Set(enrollments).size !== enrollments.length) {
    context.addIssue({ code: "custom", path: ["operator_enrollments"], message: "A feed may have one current enrollment event" });
  }
  const ids = config.operator_enrollments.map(value => value.enrollment_id);
  if (new Set(ids).size !== ids.length) {
    context.addIssue({ code: "custom", path: ["operator_enrollments"], message: "Enrollment event IDs must be unique" });
  }
});

export type FeedAvailabilityConfig = z.infer<typeof FeedAvailabilityConfigSchema>;
