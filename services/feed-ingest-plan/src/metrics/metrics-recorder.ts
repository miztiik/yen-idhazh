/** Which assessment and diversity files were really written, without sealing this attempt? */
import { resolve } from "node:path";
import { z } from "zod";
import {
  ArticleAssessmentRecordSchema, CONTRACT_VERSION, DiversityMetricRowSchema,
  LedgerCompletionEvidenceSchema, WriterIdentitySchema, CandidateRejectionRecordSchema,
  EditorialSelectionRowSchema, FeedIngestDispatchSchema,
} from "@idhazh/common-contracts";
import type { LedgerCompletionEvidence } from "@idhazh/common-contracts";
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

const RegistrationSchema = z.strictObject({
  name: z.enum(["article-assessments", "diversity"]), family: z.literal("feed-ingest-plan"),
  grain: z.literal("raw-and-compact"), lifecycle_status: z.literal("active"),
  prefix: z.array(z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/)).min(2),
});
const SettingsSchema = z.object({
  format: z.literal("parquet"),
  compression_raw: z.enum(["snappy", "zstd", "none"]),
  compression_compact: z.enum(["snappy", "zstd", "none"]),
});
export type AuditRegistrations = Readonly<{ assessments: LedgerRegistration; diversity: LedgerRegistration }>;

function registration(raw: LedgerRegistration, name: "article-assessments" | "diversity") {
  const entry = RegistrationSchema.parse(raw);
  requireSame(entry.name, name, `registrations.${name}.name`);
  requireSame([entry.prefix[0], entry.prefix.at(-1)], [entry.family, name], `registrations.${name}.prefix`);
  return entry;
}

async function readWritten<T extends object>(
  written: PersistLedgerResult, ledger: LedgerCompletionEvidence["ledger"],
  contract: LedgerRowContract<T>, expected: readonly T[], inputs: PlanInputs, result: FeedPlanResult,
): Promise<LedgerCompletionEvidence> {
  if (written.status === "skipped") throw new Error(`audit.${ledger}: required write was skipped`);
  if ((expected.length === 0) !== (written.status === "empty")) throw new Error(`audit.${ledger}: write status differs from expected rows`);
  const actual: T[] = [];
  for (const file of written.files) {
    const loaded = await readLedgerParquet(resolve(inputs.outputRoot, ...file.path.split("/")), ledger, contract);
    requireSame(loaded.envelope.identity, result.context.writer, `audit.${ledger}.writer`);
    requireSame([loaded.envelope.file_id, loaded.envelope.content_sha256, loaded.rows.length],
      [file.file_id, file.content_sha256, file.row_count], `audit.${ledger}.receipt`);
    actual.push(...loaded.rows.map(item => item.row));
  }
  requireSame(actual, expected, `audit.${ledger}.readback`);
  return LedgerCompletionEvidenceSchema.parse({
    ledger, row_count: expected.length,
    files: written.files.map(({ file_id, content_sha256, row_count }) => ({ file_id, content_sha256, row_count })),
  });
}

export function preparePlanningMetrics(result: FeedPlanResult, inputs: PlanInputs, registrations: AuditRegistrations) {
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

export async function recordPlanningMetrics(result: FeedPlanResult, inputs: PlanInputs, registrations: AuditRegistrations) {
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
