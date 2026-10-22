/** Which typed observation crosses a planning stage boundary? */
import { z } from "zod";
import { isDeepStrictEqual } from "node:util";
import { ArticleAssessmentRecordSchema } from "./article-assessment.schema";
import { ArticleLabelsSchema, PolicyIdentitySchema, ScoreEvidenceSchema, SourceSnapshotSchema } from "./source.schema";
import { DropReasonSchema } from "./rejection.schema";
import { FetchStatusSchema, ParseStatusSchema } from "./source-run.schema";
import { CountSchema, NonEmptySchema, PlanningStageSchema, PositiveCountSchema, RunIdSchema, Sha256Schema, SlugSchema, TimestampSchema, reject } from "./primitives";
import { FEED_INGEST_AUDIT_VERSION } from "../version";

export const FeedOutcomePayloadSchema = z.strictObject({
  kind: z.literal("feed_outcome"), source: SourceSnapshotSchema,
  fetch_status: FetchStatusSchema, parse_status: ParseStatusSchema,
  parsed_count: CountSchema.nullable(), harvested_count: CountSchema.nullable(),
  fetch_duration_ms: CountSchema.nullable(), parse_duration_ms: CountSchema.nullable(),
  rejection_reason: DropReasonSchema.nullable(),
});
export const CandidateDecisionPayloadSchema = z.strictObject({
  kind: z.literal("candidate_decision"), assessment: ArticleAssessmentRecordSchema,
});
export const PortfolioChoicePayloadSchema = z.strictObject({
  kind: z.literal("portfolio_choice"), candidate_id: Sha256Schema, url_key: Sha256Schema,
  editorial_rank: PositiveCountSchema, scores: ScoreEvidenceSchema, labels: ArticleLabelsSchema,
  replaced_candidate_id: Sha256Schema.nullable(), replacement_reason: z.enum(["carrier", "cap_relaxation", "none"]),
}).superRefine((value, ctx) => {
  if ((value.replaced_candidate_id === null) !== (value.replacement_reason === "none")) reject(ctx, "replacement identity and reason must agree");
});
export const StageCompletionPayloadSchema = z.strictObject({
  kind: z.literal("stage_completion"), stage: PlanningStageSchema,
  input_count: CountSchema, output_count: CountSchema, terminal_rejection_count: CountSchema,
  source_count: CountSchema.nullable(),
});
export const AuditEventTypeSchema = z.enum(["feed_outcome", "candidate_decision", "portfolio_choice", "stage_completion"]);
export const EventPayloadSchema = z.discriminatedUnion("kind", [
  FeedOutcomePayloadSchema, CandidateDecisionPayloadSchema,
  PortfolioChoicePayloadSchema, StageCompletionPayloadSchema,
]);
export const FeedIngestEventSchema = z.strictObject({
  version: z.literal(FEED_INGEST_AUDIT_VERSION).default(FEED_INGEST_AUDIT_VERSION), event_id: Sha256Schema, correlation_id: NonEmptySchema,
  run_id: RunIdSchema, attempt: PositiveCountSchema, sequence: CountSchema,
  occurred_at: TimestampSchema, stage: PlanningStageSchema, audit_event_type: AuditEventTypeSchema,
  source_id: SlugSchema.nullable(), candidate_id: Sha256Schema.nullable(),
  elapsed_ms: CountSchema, step_elapsed_ms: CountSchema,
  policy: PolicyIdentitySchema, payload: EventPayloadSchema,
}).superRefine((value, ctx) => {
  const payload = value.payload;
  if (value.audit_event_type !== payload.kind) reject(ctx, "audit_event_type must match the typed payload discriminator");
  switch (payload.kind) {
    case "feed_outcome":
      if (value.source_id !== payload.source.source_id || value.candidate_id !== null) reject(ctx, "feed outcome events identify only their source");
      break;
    case "candidate_decision":
      if (value.candidate_id !== payload.assessment.candidate_id || value.source_id !== payload.assessment.source_id) reject(ctx, "candidate decision events identify source and candidate");
      if (value.stage !== payload.assessment.stage) reject(ctx, "candidate decision stage must match the event stage");
      if (!isDeepStrictEqual(value.policy, payload.assessment.policy)) reject(ctx, "candidate decision policy must match the event policy");
      break;
    case "portfolio_choice":
      if (value.candidate_id !== payload.candidate_id || value.source_id === null) reject(ctx, "portfolio choice events identify source and candidate");
      if (value.stage !== "curate-article-portfolio") reject(ctx, "portfolio choices belong to the portfolio stage");
      break;
    case "stage_completion":
      if (value.candidate_id !== null) reject(ctx, "stage completion events do not identify a candidate");
      if (value.stage !== payload.stage) reject(ctx, "stage completion payload must match the event stage");
      break;
  }
});
export type FeedIngestEvent = z.infer<typeof FeedIngestEventSchema>;
export type EventPayload = z.infer<typeof EventPayloadSchema>;
export type FeedOutcomePayload = z.infer<typeof FeedOutcomePayloadSchema>;
export type CandidateDecisionPayload = z.infer<typeof CandidateDecisionPayloadSchema>;
export type PortfolioChoicePayload = z.infer<typeof PortfolioChoicePayloadSchema>;
export type StageCompletionPayload = z.infer<typeof StageCompletionPayloadSchema>;
