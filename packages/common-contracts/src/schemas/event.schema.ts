/** Which typed observation crosses a planning stage boundary? */
import { z } from "zod";
import { isDeepStrictEqual } from "node:util";
import { ArticleAssessmentContract, ArticleAssessmentRecordSchema, PreviousArticleAssessmentSchema, PreviousDiagnosticArticleAssessmentSchema, PreviousExclusionArticleAssessmentSchema, PreviousQualityArticleAssessmentSchema, PreviousReliableArticleAssessmentSchema } from "./article-assessment.schema";
import {
  ArticleLabelsSchema, PolicyIdentitySchema, PreviousScoreEvidenceSchema, PreviousSourceSnapshotSchema,
  ScoreEvidenceSchema, SourceSnapshotSchema,
} from "./source.schema";
import {
  DropReasonSchema, PreviousDiagnosticDropReasonSchema, PreviousPreDiagnosticsDropReasonSchema,
} from "./rejection.schema";
import { FetchStatusSchema, ParseStatusSchema } from "./source-run.schema";
import { CountSchema, DateStampSchema, PlanningStageSchema, PositiveCountSchema, RunIdSchema, Sha256Schema, SlugSchema, TimestampSchema, reject } from "./primitives";
import { EXTRACTION_QUALITY_VERSION, FEED_HISTORY_EVENT_VERSION, FEED_INGEST_EVENT_VERSION, HARVEST_DIAGNOSTICS_VERSION, PLANNER_EXCLUSIONS_VERSION, SOURCE_RELIABILITY_VERSION } from "../version";
import { HarvestDiagnosticsSchema, PreviousHarvestDiagnosticsSchema } from "./harvest-diagnostics.schema";

export const FeedOutcomePayloadSchema = z.strictObject({
  kind: z.literal("feed_outcome"), source: SourceSnapshotSchema,
  fetch_status: FetchStatusSchema, parse_status: ParseStatusSchema,
  parsed_count: CountSchema.nullable(), harvested_count: CountSchema.nullable(),
  fetch_duration_ms: CountSchema.nullable(), parse_duration_ms: CountSchema.nullable(),
  rejection_reason: DropReasonSchema.nullable(),
  diagnostics: HarvestDiagnosticsSchema.nullable().default(null),
  history: z.strictObject({
    lifecycle: z.enum(["eligible", "resting", "retired", "unknown"]),
    endpoint_key: Sha256Schema, strikes: CountSchema.nullable(), rested_runs: CountSchema.nullable(),
    reliability: z.strictObject({
      success_fraction: z.number().finite().min(0).max(1), productive: CountSchema,
      attempted: PositiveCountSchema, window_days: PositiveCountSchema,
      from_day: DateStampSchema.nullable(), through_day: DateStampSchema.nullable(),
      production_factor: z.number().finite().min(0).max(1),
    }).nullable(),
    daily_published: z.strictObject({
      day: DateStampSchema, observed_count: CountSchema,
      availability: z.enum(["available", "unavailable"]),
    }),
    health_coverage: z.enum(["available", "unavailable"]),
    reliability_coverage: z.enum(["available", "unavailable"]),
  }).nullable().default(null),
});
const PreviousFeedOutcomePayloadSchema = FeedOutcomePayloadSchema.extend({
  source: PreviousSourceSnapshotSchema,
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
  version: z.literal(FEED_INGEST_EVENT_VERSION).default(FEED_INGEST_EVENT_VERSION),
  event_id: z.uuid({ version: "v5" }), correlation_id: z.uuid({ version: "v4" }),
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
      if (value.correlation_id !== payload.assessment.correlation_id) reject(ctx, "candidate decision correlation must match the event");
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
}).meta({
  $id: "feed-ingest-event", version: FEED_INGEST_EVENT_VERSION,
  changelog: [{
    version: FEED_INGEST_EVENT_VERSION,
    change: "Record curated publisher identity in source snapshots.",
  }, {
    version: SOURCE_RELIABILITY_VERSION,
    change: "Record separate source-reliability penalties on portfolio decisions.",
  }, {
    version: FEED_HISTORY_EVENT_VERSION,
    change: "Record native feed rest, retirement, reliability and daily publication evidence.",
  }, {
    version: EXTRACTION_QUALITY_VERSION,
    change: "Retain measured extraction quality and implementation fingerprints.",
  }, {
    version: "2026-10-22T20:30",
    change: "Earlier changes are in git.",
  }],
});
export type FeedIngestEvent = z.infer<typeof FeedIngestEventSchema>;
export type EventPayload = z.infer<typeof EventPayloadSchema>;
export type FeedOutcomePayload = z.infer<typeof FeedOutcomePayloadSchema>;
export type CandidateDecisionPayload = z.infer<typeof CandidateDecisionPayloadSchema>;
export type PortfolioChoicePayload = z.infer<typeof PortfolioChoicePayloadSchema>;
export type StageCompletionPayload = z.infer<typeof StageCompletionPayloadSchema>;

const PreviousPortfolioChoicePayloadSchema = z.strictObject({
  ...PortfolioChoicePayloadSchema.shape, scores: PreviousScoreEvidenceSchema,
});
const PreviousEventSchema = z.strictObject({
  ...FeedIngestEventSchema.shape,
  version: z.literal("2026-10-22T12:20"),
  payload: z.discriminatedUnion("kind", [
    PreviousFeedOutcomePayloadSchema.omit({ diagnostics: true, history: true }).extend({
      rejection_reason: PreviousPreDiagnosticsDropReasonSchema.nullable(),
    }),
    CandidateDecisionPayloadSchema.extend({ assessment: PreviousArticleAssessmentSchema }),
    PreviousPortfolioChoicePayloadSchema, StageCompletionPayloadSchema,
  ]),
});
const PreviousDiagnosticEventSchema = z.strictObject({
  ...FeedIngestEventSchema.shape,
  version: z.literal(HARVEST_DIAGNOSTICS_VERSION),
  payload: z.discriminatedUnion("kind", [
    PreviousFeedOutcomePayloadSchema.omit({ history: true }).extend({
      rejection_reason: PreviousDiagnosticDropReasonSchema.nullable(),
      diagnostics: PreviousHarvestDiagnosticsSchema.nullable().default(null),
    }),
    CandidateDecisionPayloadSchema.extend({ assessment: PreviousDiagnosticArticleAssessmentSchema }),
    PreviousPortfolioChoicePayloadSchema, StageCompletionPayloadSchema,
  ]),
});
const PreviousExclusionEventSchema = z.strictObject({
  ...FeedIngestEventSchema.shape,
  version: z.literal(PLANNER_EXCLUSIONS_VERSION),
  payload: z.discriminatedUnion("kind", [
    PreviousFeedOutcomePayloadSchema.omit({ history: true }).extend({ diagnostics: PreviousHarvestDiagnosticsSchema.nullable().default(null) }),
    CandidateDecisionPayloadSchema.extend({ assessment: PreviousExclusionArticleAssessmentSchema }),
    PreviousPortfolioChoicePayloadSchema, StageCompletionPayloadSchema,
  ]),
});
const PreviousQualityEventSchema = z.strictObject({
  ...FeedIngestEventSchema.shape,
  version: z.literal(EXTRACTION_QUALITY_VERSION),
  payload: z.discriminatedUnion("kind", [
    PreviousFeedOutcomePayloadSchema.omit({ history: true }),
    CandidateDecisionPayloadSchema.extend({ assessment: PreviousQualityArticleAssessmentSchema }),
    PreviousPortfolioChoicePayloadSchema, StageCompletionPayloadSchema,
  ]),
});
const PreviousHistoryEventSchema = z.strictObject({
  ...FeedIngestEventSchema.shape, version: z.literal(FEED_HISTORY_EVENT_VERSION),
  payload: z.discriminatedUnion("kind", [
    PreviousFeedOutcomePayloadSchema,
    CandidateDecisionPayloadSchema.extend({ assessment: PreviousQualityArticleAssessmentSchema }),
    PreviousPortfolioChoicePayloadSchema, StageCompletionPayloadSchema,
  ]),
});
const PreviousReliableEventSchema = z.strictObject({
  ...FeedIngestEventSchema.shape, version: z.literal(SOURCE_RELIABILITY_VERSION),
  payload: z.discriminatedUnion("kind", [
    PreviousFeedOutcomePayloadSchema,
    CandidateDecisionPayloadSchema.extend({ assessment: PreviousReliableArticleAssessmentSchema }),
    PreviousPortfolioChoicePayloadSchema, StageCompletionPayloadSchema,
  ]),
});

export function readFeedIngestEvent(input: unknown): FeedIngestEvent {
  if (input && typeof input === "object" && "version" in input) {
    const schema = [
      PreviousEventSchema, PreviousDiagnosticEventSchema, PreviousExclusionEventSchema,
      PreviousQualityEventSchema, PreviousHistoryEventSchema, PreviousReliableEventSchema,
    ].find(schema => schema.shape.version.value === input.version);
    if (schema !== undefined) {
      const previous = schema.parse(input);
      const payload = previous.payload.kind === "candidate_decision" ? {
        ...previous.payload, assessment: { ...previous.payload.assessment, version: ArticleAssessmentContract.schemaVersion },
      } : previous.payload;
      return FeedIngestEventSchema.parse({ ...previous, payload, version: FEED_INGEST_EVENT_VERSION });
    }
  }
  return FeedIngestEventSchema.parse(input);
}
