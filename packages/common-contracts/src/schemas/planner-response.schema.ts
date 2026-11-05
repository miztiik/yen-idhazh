/** Which saved planner response retains outcomes without private batches or article bodies? */
import { z } from "zod";
import { CountSchema, NonEmptySchema, PositiveCountSchema, RelPathSchema, Sha256Schema, SlugSchema, UrlSchema, deriveUrlKey } from "./primitives";
import { OperationMetadataSchema, TraceIdSchema } from "./operation-metadata.schema";
import { PlanRunRowSchema } from "./plan-run.schema";
import { PlannerErrorResponseSchema, PlannerFailureReadSchema } from "./planner-failure.schema";
import { FeedHealthStateRowSchema, FeedLifecycleFieldsSchema } from "./feed-health-state.schema";
import { PlannerRequestReportSchema } from "./planner-request-report.schema";

export const PLANNER_RESPONSE_VERSION = "2026-11-05" as const;
export const PlannerLedgerWriteResultSchema = z.discriminatedUnion("status", [
  z.strictObject({ status: z.literal("written"), files: z.array(z.strictObject({
    path: RelPathSchema, file_id: z.uuid(), covers: NonEmptySchema,
    content_sha256: Sha256Schema, row_count: CountSchema,
  })).min(1) }),
  z.strictObject({ status: z.literal("empty"), files: z.tuple([]) }),
]);
export const FeedAvailabilityViewSchema = z.strictObject({
  feed_id: SlugSchema, endpoint_key: Sha256Schema, ...FeedLifecycleFieldsSchema.shape,
});
export const FeedAvailabilitySnapshotSchema = z.strictObject({
  feeds: z.array(FeedAvailabilityViewSchema),
  eligible_feed_ids: z.array(SlugSchema),
});
export const FeedHealthStateUpdateResponseSchema = OperationMetadataSchema.safeExtend({
  status: z.enum(["summarized", "recorded"]),
  rows: z.array(FeedHealthStateRowSchema), request_report: PlannerRequestReportSchema,
  reliability: z.strictObject({ window_days: PositiveCountSchema }),
  availability: FeedAvailabilitySnapshotSchema.optional(),
  files: PlannerLedgerWriteResultSchema.optional(),
}).superRefine((value, ctx) => {
  if ((value.status === "recorded") !== (value.files !== undefined)) {
    ctx.addIssue({ code: "custom", message: "Recorded health returns its actual file receipt; summary does not write" });
  }
});
export const PlannerHealthOutcomeSchema = z.union([
  FeedHealthStateUpdateResponseSchema.safeExtend({ status: z.literal("summarized"), files: z.never().optional() }),
  z.strictObject({ status: z.literal("failed"), failure: PlannerFailureReadSchema }),
]).nullable();
export type PlannerHealthOutcome = z.infer<typeof PlannerHealthOutcomeSchema>;
export const PlannerRunResponseSchema = PlanRunRowSchema.safeExtend({
  planning_complete: z.boolean(), traceId: TraceIdSchema,
  health: PlannerHealthOutcomeSchema,
  files: z.strictObject({
    discovered_articles: PlannerLedgerWriteResultSchema.optional(), selected_articles: PlannerLedgerWriteResultSchema.optional(),
    rejected_articles: PlannerLedgerWriteResultSchema.optional(),
    feed_health_state: PlannerLedgerWriteResultSchema.optional(), plan_runs: PlannerLedgerWriteResultSchema.optional(),
  }),
  include_selected_urls: z.boolean(),
  selected_article_ids: z.array(Sha256Schema),
  assignments: z.array(z.strictObject({
    article_id: Sha256Schema, editorial_rank: CountSchema.positive(), worker_assignment: CountSchema.nullable(),
    canonical_url: UrlSchema.optional(),
  })),
  failure: PlannerFailureReadSchema.nullable().default(null),
}).superRefine((value, ctx) => {
  if (value.planning_complete !== (value.status === "completed") || value.selected_article_ids.length !== value.selected_count
    || value.assignments.length !== value.selected_count || new Set(value.selected_article_ids).size !== value.selected_count) {
    ctx.addIssue({ code: "custom", message: "Run status, chosen identities and assignments must reconcile" });
  }
  if ((value.status === "completed") !== (value.failure_code === null)) {
    ctx.addIssue({ code: "custom", message: "Only an unsuccessful run has a failure cause" });
  }
  if (value.health?.status === "failed" && value.failure === null) {
    ctx.addIssue({ code: "custom", path: ["failure"], message: "A failed report requires a request failure" });
  }
  if (value.planning_complete && value.health === null) {
    ctx.addIssue({ code: "custom", path: ["health"], message: "Completed planning requires its report outcome" });
  }
  if (value.failure !== null && (value.failure.execution.run_id !== value.run_id
    || value.failure.execution.attempt !== value.attempt)) {
    ctx.addIssue({ code: "custom", message: "Execution failure must belong to the saved response" });
  }
  if (value.assignments.some((article, index) => article.article_id !== value.selected_article_ids[index]
    || article.editorial_rank !== index + 1 || (article.worker_assignment === null
      ? value.planning_complete && value.dispatch_count !== 0 : article.worker_assignment >= value.dispatch_count))) {
    ctx.addIssue({ code: "custom", message: "Selected order, ranks and worker assignments must match the run" });
  }
  for (const [index, article] of value.assignments.entries()) {
    const url = article.canonical_url;
    if (value.include_selected_urls
      ? url === undefined || url.includes("#") || deriveUrlKey(url) !== article.article_id
      : Object.hasOwn(article, "canonical_url")) {
      ctx.addIssue({ code: "custom", path: ["assignments", index, "canonical_url"],
        message: "Selected URLs must be present only when requested and match their article identities" });
    }
  }
}).meta({
  version: PLANNER_RESPONSE_VERSION,
  changelog: [
    { version: PLANNER_RESPONSE_VERSION, change: "Expose article identities and validated optional selected URLs in combined summaries." },
    { version: "2026-11-03", change: "Include required report outcomes and independent request failures without live references." },
    { version: "2026-11-02", change: "Retain optional execution failures." },
  ],
});
export const PlannerSavedResponseSchema = z.union([PlannerRunResponseSchema, PlannerErrorResponseSchema]).meta({
  version: PLANNER_RESPONSE_VERSION,
  changelog: [
    { version: PLANNER_RESPONSE_VERSION, change: "Save combined article identities and the effective selected-URL display option." },
    { version: "2026-11-03", change: "Use the existing response file for both saved outcomes and safe execution errors." },
  ],
});
export type PlannerRunResponse = z.infer<typeof PlannerRunResponseSchema>;
