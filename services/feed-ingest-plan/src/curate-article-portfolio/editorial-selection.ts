/** Which unsharded selection and terminal losses does one screened run produce? */
import {
  ArticleAssessmentRecordSchema, CandidateRejectionContract,
  EditorialSelectionContract, EditorialSelectionRowSchema, NonNegativeSchema,
} from "@idhazh/common-contracts";
import type { CandidateRejectionRecord, ScoreEvidence, WriterIdentity } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, LedgerSettings, PersistLedgerResult } from "@idhazh/ledger-file-writer";
import type { PlanningConfig } from "../config/resolve-policy";
import { validateOpportunity, validatePortfolioArticles } from "./portfolio-input";
import type { OpportunityEvidence, PortfolioArticle } from "./portfolio-input";
import { groupCarriers } from "./carrier-cluster";
import { normalizeOpportunity } from "./quota-normalizer";
import { choosePortfolio } from "./mmr-portfolio";
import { measureArticle, recordAssessment } from "./quality-decoupler";
import { recordRejection } from "./record-rejection";

export function curateArticles(input: Readonly<{
  articles: readonly PortfolioArticle[];
  planning: PlanningConfig;
  opportunity: OpportunityEvidence;
  observed_at: string;
  reliability_floor: number;
}>) {
  validateOpportunity(input.opportunity);
  const articles = validatePortfolioArticles(input.articles, input.planning, input.observed_at);
  const controls = {
    enabled: input.planning.config.curate.source_reliability_penalty_enabled,
    reliability_floor: NonNegativeSchema.max(1).parse(input.reliability_floor),
  };
  const carriers = groupCarriers(articles, controls);
  const normalization = normalizeOpportunity(carriers.representatives, input.opportunity, controls, articles);
  const portfolio = choosePortfolio(
    normalization.admitted, input.planning.config.curate, normalization.allowances,
    carriers.groups, input.opportunity, controls,
  );
  const rejections: CandidateRejectionRecord[] = [
    ...carriers.suppressed.map(suppression => recordRejection(
      suppression.article, input.observed_at, suppression.reason,
      { matched_url_key: suppression.representative.candidate.url_key },
    )),
    ...normalization.rejected.map(rejection => recordRejection(
      rejection.article, input.observed_at, "SOURCE_QUOTA_EXCEEDED",
      { observed_value: rejection.position, limit: rejection.allowance.allowance },
    )),
    ...portfolio.cutoffs.map(cutoff => recordRejection(
      cutoff.article, input.observed_at, "MMR_PORTFOLIO_CUTOFF",
      { observed_value: cutoff.controls[0]!.observed_value, limit: cutoff.controls[0]!.limit },
    )),
  ];
  const choices = new Map(portfolio.choices.map(choice => [choice.candidate_id, choice]));
  const rows = portfolio.selected.map(article => {
    const candidate = article.candidate;
    const choice = choices.get(candidate.candidate_id)!;
    return EditorialSelectionRowSchema.parse({
      date: input.observed_at.slice(0, 10),
      correlation_id: candidate.correlation_id, candidate_id: candidate.candidate_id,
      source_id: candidate.source_id, vertical: candidate.vertical, source: candidate.source,
      canonical_url: candidate.canonical_url, url_key: candidate.url_key,
      labels: candidate.labels, editorial_rank: choice.editorial_rank,
      estimated_work: article.evidence.estimated_work, ratings: choice.scores,
      policy: recordAssessment(article, input.observed_at).policy,
    });
  });
  const reasons = new Map(rejections.map(rejection => [rejection.candidate_id, rejection.drop_reason]));
  const scores = new Map<string, ScoreEvidence>();
  for (const step of portfolio.trace) {
    for (const entry of step.evaluated) scores.set(entry.candidate_id, entry.scores);
  }
  const assessments = articles.map(article => {
    const id = article.candidate.candidate_id;
    const reason = reasons.get(id) ?? null;
    const score = choices.get(id)?.scores ?? scores.get(id) ?? null;
    return ArticleAssessmentRecordSchema.parse({
      ...recordAssessment(article, input.observed_at),
      decision: reason === null ? "selected" : "rejected", reason,
      score_evidence: score, score_evidence_status: score === null ? "not_assessed" : "assessed",
    });
  });
  if (articles.length !== rows.length + rejections.length) throw new Error("Curation terminal decisions do not reconcile");
  return {
    input: articles, opportunity: structuredClone(input.opportunity), reliability_controls: controls,
    selected: portfolio.selected, rows, rejections, assessments, cutoffs: portfolio.cutoffs,
    choices: portfolio.choices, trace: portfolio.trace,
    carriers, normalization, quality: articles.map(article => ({
      candidate_id: article.candidate.candidate_id, ...measureArticle(article),
    })),
  };
}

export type CurationResult = ReturnType<typeof curateArticles>;
export type CurationPersistence = Readonly<{
  outputRoot: string; writerContext: WriterIdentity; ledgerSettings: LedgerSettings;
  registrations: Readonly<{ selections: LedgerRegistration; rejections: LedgerRegistration }>;
  date: string;
}>;

function requireDurable(result: PersistLedgerResult): PersistLedgerResult {
  if (result.status === "skipped") throw new Error(`Curation ledger unavailable: ${result.warning.ledger}`);
  return result;
}

export async function persistPortfolio(result: CurationResult, context: CurationPersistence) {
  if (context.ledgerSettings.format !== "parquet") throw new Error("Curation requires Parquet ledger storage");
  if (context.writerContext.shard !== 0) throw new Error("Unsharded curation requires writer provenance shard 0");
  if (context.registrations.selections.name !== "editorial-selections"
    || context.registrations.rejections.name !== "rejections") throw new Error("Wrong curation ledger registration");
  for (const article of result.input) {
    if (article.candidate.run_id !== context.writerContext.run_id) throw new Error("Writer run differs from curated candidate run");
  }
  if ([...result.rows, ...result.rejections].some(row => row.date !== context.date)) throw new Error("Writer day differs from curation day");
  const common = {
    outputRoot: context.outputRoot, writerContext: context.writerContext,
    ledgerSettings: context.ledgerSettings, period: { tier: "raw" as const, covers: context.date },
  };
  const rejections = requireDurable(await persistLedger({
    ...common, ledger: "rejections", registryEntry: context.registrations.rejections,
    rowContract: CandidateRejectionContract,
    rows: result.rejections,
  }));
  const selections = requireDurable(await persistLedger({
    ...common, ledger: "editorial-selections", registryEntry: context.registrations.selections,
    rowContract: EditorialSelectionContract,
    rows: result.rows,
  }));
  return { selections, rejections };
}
