/** Which measured audit files were written and read back without claiming unsupported completion? */
import { resolve } from "node:path";
import { z } from "zod";
import {
  ArticleAssessmentRecordSchema, CONTRACT_VERSION, DiversityMetricRowSchema,
  LedgerCompletionEvidenceSchema, WriterIdentitySchema, CandidateRejectionRecordSchema,
  EditorialSelectionRowSchema, FeedIngestDispatchSchema, SourceRunRecordSchema,
  RunIdSchema, NonEmptySchema, Sha256Schema, FeedMetricsConfigSchema,
} from "@idhazh/common-contracts";
import type { LedgerCompletionEvidence, WriterIdentity, RowIdentity } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, LedgerRowContract, PersistLedgerResult } from "@idhazh/ledger-file-writer";
import type { PlanInputs } from "../load-plan-inputs";
import type { FeedPlanResult } from "../run-feed-plan";
import { readLedgerParquet } from "../read-ledger-history/read-parquet";
import { preflightMeasurements, translateArticleAssessments } from "./article-assessments";
import { calculateDiversityMetrics } from "./diversity-metrics";
import { reconcileStageMembership, requireSame } from "./stage-membership";
import { deriveSourceRunSummaries } from "./source-run-summary";
import { loadHarvestInputs } from "../harvest-feeds/load-harvest-inputs";
import { UtcInstantSchema } from "../screen-article-candidates/seen-evidence";
import { readPlanningHistory, settlePlanningDay } from "./planning-populations";
import type { NamedPlanningHistory } from "./planning-populations";
import { completePublicationObservations, readPublicationDay } from "./publication-outcomes";
import type { NamedPublicationDay } from "./publication-outcomes";
import { buildHistoryWindow, requiredHistoryDays } from "./history-window";
import { calculatePublicationMetrics } from "./publication-metrics";
import { DigestEventItemSchema, RecordedEventPairSchema } from "./publication-evidence";
import type { RecordedEventPair } from "./publication-evidence";
import { selectCompleteAttempt } from "../read-ledger-history/complete-attempt";

const RegistrationSchema = z.strictObject({
  name: z.enum(["article-assessments", "diversity", "source-runs"]), family: z.literal("feed-ingest-plan"),
  grain: z.literal("raw-and-compact"), lifecycle_status: z.literal("active"),
  prefix: z.array(z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/)).min(2),
});
const SettingsSchema = z.object({
  format: z.literal("parquet"),
  compression_raw: z.enum(["snappy", "zstd", "none"]),
  compression_compact: z.enum(["snappy", "zstd", "none"]),
});
export type AuditRegistrations = Readonly<{ assessments: LedgerRegistration; diversity: LedgerRegistration }>;

function registration(raw: LedgerRegistration, name: "article-assessments" | "diversity" | "source-runs") {
  const entry = RegistrationSchema.parse(raw);
  requireSame(entry.name, name, `registrations.${name}.name`);
  requireSame([entry.prefix[0], entry.prefix.at(-1)], [entry.family, name], `registrations.${name}.prefix`);
  return entry;
}

async function readWritten<T extends object>(
  written: PersistLedgerResult, ledger: LedgerCompletionEvidence["ledger"],
  contract: LedgerRowContract<T>, expected: readonly T[], inputs: PlanInputs, result: FeedPlanResult,
): Promise<LedgerCompletionEvidence> {
  await verifyLedgerWrite(written, ledger, contract, expected, inputs.outputRoot, result.context.writer);
  return LedgerCompletionEvidenceSchema.parse({
    ledger, row_count: expected.length,
    files: written.files.map(({ file_id, content_sha256, row_count }) => ({ file_id, content_sha256, row_count })),
  });
}
async function verifyLedgerWrite<T extends object>(
  written: PersistLedgerResult, ledger: RowIdentity["ledger"], contract: LedgerRowContract<T>,
  expected: readonly T[], outputRoot: string, writer: WriterIdentity,
): Promise<void> {
  if (written.status === "skipped") throw new Error(`audit.${ledger}: required write was skipped`);
  if ((expected.length === 0) !== (written.status === "empty")) throw new Error(`audit.${ledger}: write status differs from expected rows`);
  const actual: T[] = [];
  for (const file of written.files) {
    const loaded = await readLedgerParquet(resolve(outputRoot, ...file.path.split("/")), ledger, contract);
    requireSame(loaded.envelope.identity, writer, `audit.${ledger}.writer`);
    requireSame([loaded.envelope.file_id, loaded.envelope.content_sha256, loaded.rows.length],
      [file.file_id, file.content_sha256, file.row_count], `audit.${ledger}.receipt`);
    actual.push(...loaded.rows.map(item => item.row));
  }
  requireSame(actual, expected, `audit.${ledger}.readback`);
}

export function preparePlanningMetrics(
  result: FeedPlanResult, inputs: PlanInputs, registrations: AuditRegistrations = inputs.registrations,
) {
  // Refuse the entire request before any Row 14 parse can erase exact timing.
  preflightMeasurements(result, inputs);
  const original = loadHarvestInputs({
    config: { ...inputs.harvest.config, curate: { ...inputs.harvest.config.curate, article_limit: result.request.article_limit } },
    taxonomy: { ...inputs.harvest.taxonomy, ...inputs.harvest.registry },
    sources: { feeds: inputs.harvest.sources }, extraction: { extract: inputs.harvest.extraction },
  });
  requireSame(result.evidence.harvest.inputs, original, "audit.harvest.inputs");
  requireSame(result.evidence.harvest.config, original.config, "audit.harvest.config");
  const membership = reconcileStageMembership(result);
  const settings = SettingsSchema.parse(inputs.ledgerSettings);
  const entries = {
    assessments: registration(registrations.assessments, "article-assessments"),
    diversity: registration(registrations.diversity, "diversity"),
  };
  WriterIdentitySchema.parse(result.context.writer);
  if (result.context.writer.shard !== 0) throw new Error("audit.writer.shard: planning audit is unsharded");
  if (!inputs.outputRoot || inputs.outputRoot.includes("\0")) throw new Error("audit.outputRoot: invalid output path");
  requireSame(settings.compression_raw, result.evidence.harvest.config.seal.compression, "audit.compression_raw");
  for (const [name, files] of Object.entries(result.files)) {
    if (files.status === "skipped") throw new Error(`audit.inputs.${name}: required stage write was skipped`);
  }
  const assessments = translateArticleAssessments(result, inputs).map(row => ArticleAssessmentRecordSchema.parse(row));
  const diversity = calculateDiversityMetrics(result, membership).map(row => DiversityMetricRowSchema.parse(row));
  const sources = deriveSourceRunSummaries(result, membership);
  return { assessments, diversity, sources, membership, settings, registrations: entries };
}

export async function recordPlanningMetrics(
  result: FeedPlanResult, inputs: PlanInputs, registrations: AuditRegistrations = inputs.registrations,
) {
  const batch = preparePlanningMetrics(result, inputs, registrations);
  // Named input files are verified before creating either audit ledger.
  const rejectionContract = { schema: CandidateRejectionRecordSchema, schemaVersion: CONTRACT_VERSION };
  await readWritten(result.files.harvest_rejections, "rejections", rejectionContract, result.evidence.harvest.rejections, inputs, result);
  await readWritten(result.files.screening_rejections, "rejections", rejectionContract, result.evidence.screening.rejections, inputs, result);
  await readWritten(result.files.curation_rejections, "rejections", rejectionContract, result.evidence.curation.rejections, inputs, result);
  await readWritten(result.files.selections, "editorial-selections", {
    schema: EditorialSelectionRowSchema, schemaVersion: CONTRACT_VERSION,
  }, result.evidence.curation.rows, inputs, result);
  await readWritten(result.files.dispatches, "dispatches", {
    schema: FeedIngestDispatchSchema, schemaVersion: CONTRACT_VERSION,
  }, result.evidence.partition.dispatches, inputs, result);
  const common = {
    outputRoot: inputs.outputRoot, writerContext: result.context.writer,
    ledgerSettings: batch.settings, period: { tier: "raw" as const, covers: result.context.date },
  };
  const assessmentContract = { schema: ArticleAssessmentRecordSchema, schemaVersion: CONTRACT_VERSION };
  const diversityContract = { schema: DiversityMetricRowSchema, schemaVersion: CONTRACT_VERSION };
  const assessments = await persistLedger({
    ...common, ledger: "article-assessments", registryEntry: batch.registrations.assessments,
    rowContract: assessmentContract, rows: batch.assessments,
  });
  const assessmentReceipt = await readWritten(assessments, "article-assessments", assessmentContract, batch.assessments, inputs, result);
  const diversity = await persistLedger({
    ...common, ledger: "diversity", registryEntry: batch.registrations.diversity,
    rowContract: diversityContract, rows: batch.diversity,
  });
  const diversityReceipt = await readWritten(diversity, "diversity", diversityContract, batch.diversity, inputs, result);
  return {
    status: "assessment_diversity_recorded_audit_pending" as const,
    audited_complete: false as const,
    receipts: { assessments: assessmentReceipt, diversity: diversityReceipt },
    files: { assessments, diversity },
    source_summaries: batch.sources,
    evidence: {
      carrier_groups: batch.membership.carrier_groups, normalization: batch.membership.normalization,
      trace: batch.membership.trace, quality: batch.membership.quality,
    },
    unavailable: {
      source_completion: "Timing/count contract decisions and packed completion proof remain unresolved",
      publication_stage_diversity: "No publication or lead membership was observed; no before/after values exist",
      rolling_metrics: "No complete historical source/publication membership window was supplied",
    },
  };
}
export type PlanningMetricsResult = Awaited<ReturnType<typeof recordPlanningMetrics>>;

export type PublicationRecorderInput = Readonly<{
  run_id: string; correlation_id: string; as_of: string; through?: string;
  config_sha256: string; config: Parameters<typeof FeedMetricsConfigSchema.parse>[0];
  outputRoot: string; writer: WriterIdentity;
  ledgerSettings: z.infer<typeof SettingsSchema>;
  registrations: Readonly<{ diversity: LedgerRegistration; sources: LedgerRegistration }>;
  publication_days: readonly NamedPublicationDay[];
  planning_days: readonly NamedPlanningHistory[];
  event_pairs?: readonly RecordedEventPair[];
}>;

export async function recordPublicationMetrics(input: PublicationRecorderInput) {
  const run = RunIdSchema.parse(input.run_id);
  NonEmptySchema.parse(input.correlation_id);
  Sha256Schema.parse(input.config_sha256);
  const asOf = UtcInstantSchema.parse(input.as_of);
  const config = FeedMetricsConfigSchema.parse(input.config);
  for (const k of config.top_source_counts) {
    if (k !== 1 && k !== 5 && k !== 10) throw new Error(`metrics.top_source_counts.${k}: unsupported top_k`);
  }
  const writer = WriterIdentitySchema.parse(input.writer);
  if (writer.run_id !== run || writer.shard !== 0) throw new Error("Publication observer requires its named unsharded run writer");
  if (!input.outputRoot || input.outputRoot.includes("\0")) throw new Error("Invalid publication metric output root");
  const settings = SettingsSchema.parse(input.ledgerSettings);
  const diversityEntry = registration(input.registrations.diversity, "diversity");
  const sourceEntry = registration(input.registrations.sources, "source-runs");
  const names = requiredHistoryDays(asOf, config, input.through);
  const checkDays = (days: readonly string[], field: string) => {
    if (new Set(days).size !== days.length || days.some(day => !names.includes(day))) throw new Error(`${field}: name distinct configured UTC days only`);
  };
  checkDays(input.publication_days.map(day => day.published.day), "publication_days");
  checkDays(input.planning_days.map(day => day.sources.day), "planning_days");
  const pairs = input.event_pairs === undefined ? undefined : input.event_pairs.map(pair => RecordedEventPairSchema.parse(pair));
  // Verify and settle original native files before attributing publications or creating output.
  const planningHistory = await Promise.all(input.planning_days.map(day => readPlanningHistory(day)));
  const planning = planningHistory.map(history => settlePlanningDay(history));
  const observed = await Promise.all(input.publication_days.map(day => readPublicationDay(day)));
  const history = buildHistoryWindow(asOf, config, observed.map(day => day.publication), input.through);
  const eventItems = observed.flatMap(day => day.digest?.items.flatMap(item => {
    if (item.title === undefined || item.source_name === undefined) return [];
    return [DigestEventItemSchema.parse(item)];
  }) ?? []);
  const current = observed.find(day => day.publication.day === run.slice(0, 10));
  const outcome = current?.outcomes.find(outcome => outcome.run_id === run);
  const metrics = calculatePublicationMetrics({
    run_id: run, correlation_id: input.correlation_id, config_sha256: input.config_sha256,
    config, history, planning, run_publication: outcome,
    ...(pairs === undefined ? {} : { event_evidence: { pairs, items: eventItems } }),
  });
  const original = planningHistory.find(day => day.sources.day === run.slice(0, 10));
  const resolution = original === undefined ? null : selectCompleteAttempt(original, run);
  const proven = resolution?.selected;
  let sourceReason: string | null = null;
  let sourceRows: ReturnType<typeof completePublicationObservations> = [];
  if (proven === undefined || proven === null) sourceReason = "No reproducible original complete source attempt";
  else if (input.correlation_id !== proven.correlation_id) throw new Error("Observer correlation differs from its complete source attempt");
  else if (proven.date !== asOf.slice(0, 10)) sourceReason = "The source observation contract cannot record this following-day observation without backdating";
  else if (outcome === undefined || outcome.availability !== "available") sourceReason = "No complete publication observation for the recorded run";
  else sourceRows = completePublicationObservations(proven.sources, outcome, asOf);
  const common = {
    outputRoot: input.outputRoot, writerContext: writer, ledgerSettings: settings,
    period: { tier: "raw" as const, covers: asOf.slice(0, 10) },
  };
  const diversityContract = { schema: DiversityMetricRowSchema, schemaVersion: CONTRACT_VERSION };
  const diversity = await persistLedger({
    ...common, ledger: "diversity", registryEntry: diversityEntry, rowContract: diversityContract, rows: metrics.rows,
  });
  await verifyLedgerWrite(diversity, "diversity", diversityContract, metrics.rows, input.outputRoot, writer);
  const sources = sourceReason !== null ? null : await persistLedger({
    ...common, ledger: "source-runs", registryEntry: sourceEntry,
    rowContract: { schema: SourceRunRecordSchema, schemaVersion: CONTRACT_VERSION }, rows: sourceRows,
  });
  if (sources !== null) await verifyLedgerWrite(sources, "source-runs",
    { schema: SourceRunRecordSchema, schemaVersion: CONTRACT_VERSION }, sourceRows, input.outputRoot, writer);
  return {
    status: "publication_metrics_recorded_audit_pending" as const, audited_complete: false as const,
    files: { diversity, sources }, rows: metrics.rows, source_observations: sourceRows,
    receipts: { diversity: LedgerCompletionEvidenceSchema.parse({
      ledger: "diversity", row_count: metrics.rows.length,
      files: diversity.files.map(({ file_id, content_sha256, row_count }) => ({ file_id, content_sha256, row_count })),
    }) },
    history: { start: history.start, end: history.end, coverage_days: history.coverage_days, required_days: history.required_days },
    unavailable: { stage_losses: metrics.unavailable, source_observations: sourceReason,
      planning_attempts: planning.flatMap(day => day.findings) },
  };
}
export type PublicationMetricsResult = Awaited<ReturnType<typeof recordPublicationMetrics>>;
