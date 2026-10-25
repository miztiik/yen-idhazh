/** Which source outcomes prove one planning attempt is complete? */
import { z } from "zod";
import { LifecycleStatusSchema, SourceSnapshotSchema } from "./source.schema";
import { DropReasonSchema } from "./rejection.schema";
import { CountSchema, DateStampSchema, FiniteSchema, NonEmptySchema, PositiveCountSchema, RejectionStageSchema, RunIdSchema, Sha256Schema, SlugSchema, TimestampSchema, reject } from "./primitives";
import { SOURCE_RUN_VERSION } from "../version";
import { SchemaVersionSchema } from "./primitives";

export const FetchStatusSchema = z.enum(["not_requested", "success", "http_failure", "network_failure", "timeout"]);
export const ParseStatusSchema = z.enum(["not_attempted", "success", "empty", "failure"]);
export const DropReasonCountSchema = z.strictObject({
  subject: z.enum(["feed", "article"]), stage: RejectionStageSchema,
  reason: DropReasonSchema, count: PositiveCountSchema,
});
export const CompletedFileSchema = z.strictObject({
  file_id: z.string().uuid(), content_sha256: Sha256Schema, row_count: PositiveCountSchema,
}).superRefine((value, ctx) => {
  if (value.file_id[14] !== "8") reject(ctx, "file_id must be a version 8 UUID");
});
export const CompletionLedgerSchema = z.enum([
  "article-assessments", "diversity", "article-selection-diversity",
  "editorial-selections", "dispatches", "article-dispatches",
  "rejections", "ingest-rejections",
]);
export const PreviousCompletionLedgerSchema = z.enum([
  "article-assessments", "diversity", "editorial-selections", "dispatches", "rejections",
]);
const CompletionLedgerGroups = [
  ["article-assessments"],
  ["diversity", "article-selection-diversity"],
  ["editorial-selections"],
  ["dispatches", "article-dispatches"],
  ["rejections", "ingest-rejections"],
] as const;
export const LogicalLedgerCommitmentSchema = z.strictObject({
  version: z.literal("2026-10-22").default("2026-10-22"),
  row_schema_version: SchemaVersionSchema, row_count: CountSchema, content_sha256: Sha256Schema,
});
export const LedgerCompletionEvidenceSchema = z.strictObject({
  ledger: CompletionLedgerSchema, row_count: CountSchema, files: z.array(CompletedFileSchema),
  logical: LogicalLedgerCommitmentSchema.nullable().default(null),
}).superRefine((value, ctx) => {
  if (value.files.reduce((total, file) => total + file.row_count, 0) !== value.row_count) reject(ctx, "ledger row_count must equal the sum of its file row counts");
  if ((value.row_count === 0) !== (value.files.length === 0)) reject(ctx, "an empty ledger has no files; a nonempty ledger has file evidence");
  if (new Set(value.files.map(file => file.file_id)).size !== value.files.length) reject(ctx, "ledger file identities must be distinct");
  if (value.logical !== null && value.logical.row_count > value.row_count) reject(ctx, "unique logical rows cannot exceed written rows");
});
export const PreviousLedgerCompletionEvidenceSchema = z.strictObject({
  ...LedgerCompletionEvidenceSchema.shape,
  ledger: PreviousCompletionLedgerSchema,
});
export const PreviousCompletionEvidenceSchema = z.array(PreviousLedgerCompletionEvidenceSchema).nullable();
export const SourceRunRecordSchema = z.strictObject({
  version: z.literal(SOURCE_RUN_VERSION).default(SOURCE_RUN_VERSION), date: DateStampSchema, correlation_id: NonEmptySchema,
  run_id: RunIdSchema, attempt: PositiveCountSchema, source_id: SlugSchema,
  source: SourceSnapshotSchema, status: LifecycleStatusSchema,
  fetch_status: FetchStatusSchema, parse_status: ParseStatusSchema,
  parsed_count: CountSchema.nullable(), harvested_count: CountSchema.nullable(),
  fresh_count: CountSchema.nullable(), duplicate_count: CountSchema.nullable(),
  eligible_count: CountSchema.nullable(), normalized_count: CountSchema.nullable(),
  selected_count: CountSchema.nullable(), published_count: CountSchema.nullable(),
  lead_count: CountSchema.nullable(), drop_reasons: z.array(DropReasonCountSchema),
  fetch_duration_ms: CountSchema.nullable(), parse_duration_ms: CountSchema.nullable(),
  last_failure_at: TimestampSchema.nullable(), last_failure_reason: DropReasonSchema.nullable(),
  history_success_fraction: FiniteSchema.min(0).max(1).nullable(),
  history_success_attempts: CountSchema.nullable(), history_window_days: PositiveCountSchema.nullable(),
  observation_phase: z.enum(["plan_complete", "publication_complete"]), observed_at: TimestampSchema,
  expected_source_count: CountSchema.nullable().default(null),
  completion_evidence: z.array(LedgerCompletionEvidenceSchema).nullable().default(null),
}).superRefine((value, ctx) => {
  if (value.source_id !== value.source.source_id) reject(ctx, "source_id must match the recorded source snapshot");
  if (value.status !== value.source.status) reject(ctx, "status must match the recorded source lifecycle");
  if (value.date !== value.run_id.slice(0, 10)) reject(ctx, "date must match the original run UTC day");
  if (value.fetch_status === "not_requested") {
    if (value.fetch_duration_ms !== null) reject(ctx, "an unrequested fetch has no fetch duration");
  } else if (value.fetch_duration_ms === null) reject(ctx, "an attempted fetch records its duration");
  if (value.fetch_status !== "success" && value.parse_status !== "not_attempted") reject(ctx, "only a successful fetch can be parsed");
  if (value.parse_status === "not_attempted") {
    if (value.parse_duration_ms !== null || value.parsed_count !== null) reject(ctx, "an unattempted parse has no duration or parsed count");
  } else if (value.parse_duration_ms === null) reject(ctx, "an attempted parse records its duration");
  if ((value.parse_status === "success" || value.parse_status === "empty") && value.parsed_count === null) reject(ctx, "a successful parse records its parsed count");
  if (value.parse_status === "empty" && value.parsed_count !== 0) reject(ctx, "an empty feed has a known parsed count of zero");
  if (value.parse_status === "success" && value.parsed_count === 0) reject(ctx, "a successful nonempty parse has at least one parsed entry");
  if ((value.last_failure_at === null) !== (value.last_failure_reason === null)) reject(ctx, "last failure time and reason must be available together");
  const history = [value.history_success_fraction, value.history_success_attempts, value.history_window_days];
  if (history.some(v => v !== null) && history.some(v => v === null)) reject(ctx, "success fraction, its attempts, and its window are recorded together");
  if (value.history_success_attempts === 0 && value.history_success_fraction !== null) reject(ctx, "a success fraction needs at least one measured attempt");
  const dropKeys = value.drop_reasons.map(drop => JSON.stringify([drop.subject, drop.stage, drop.reason]));
  if (new Set(dropKeys).size !== dropKeys.length) reject(ctx, "drop reason counts must have distinct subject/stage/reason keys");
  if (value.observation_phase === "plan_complete" && (value.published_count !== null || value.lead_count !== null)) reject(ctx, "a plan-complete observation has no publication counts");
  if (value.observation_phase === "publication_complete" && (value.published_count === null || value.lead_count === null)) reject(ctx, "a publication-complete observation records publication counts");
  if (value.expected_source_count === null || value.completion_evidence === null) reject(ctx, "a complete observation records expected sources and file evidence");
  if (value.published_count !== null && value.lead_count !== null && value.lead_count > value.published_count) reject(ctx, "lead_count is a subset of published_count");
  if (value.completion_evidence !== null) {
    const ledgers = value.completion_evidence.map(evidence => evidence.ledger);
    if (new Set(ledgers).size !== ledgers.length) reject(ctx, "completion evidence has one entry per ledger");
    if (CompletionLedgerGroups.some(group => group.filter(ledger => ledgers.includes(ledger)).length !== 1)) {
      reject(ctx, "completion evidence covers each required planning ledger once");
    }
  }
});
export type SourceRunRecord = z.infer<typeof SourceRunRecordSchema>;
export type CompletedFile = z.infer<typeof CompletedFileSchema>;
export type LedgerCompletionEvidence = z.infer<typeof LedgerCompletionEvidenceSchema>;
export type DropReasonCount = z.infer<typeof DropReasonCountSchema>;
