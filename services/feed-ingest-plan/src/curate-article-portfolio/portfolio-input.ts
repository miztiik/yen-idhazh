/** Which screened articles and recorded evidence may enter portfolio selection? */
import { isDeepStrictEqual } from "node:util";
import {
  EffectiveFeedPolicySchema, FeedIngestCandidateSchema, FiniteSchema, NonEmptySchema,
  NonNegativeSchema, OperationalHistorySchema, SourceOperationalEvidenceSchema, TimestampSchema,
} from "@idhazh/common-contracts";
import type { OperationalHistory, SourceOperationalEvidence, SourceReliabilityPenalty } from "@idhazh/common-contracts";
import type { ScreenedCandidate } from "../screen-article-candidates/triage-gates";
import { resolvePolicy } from "../config/resolve-policy";
import type { PlanningConfig } from "../config/resolve-policy";

const millisecondsPerHour = 3_600_000;
export type RecordedIdentity = Readonly<{ value: string; origin: string }>;
export type OperationalEvidence = Readonly<OperationalHistory>;
export type ReliabilityControls = Readonly<Pick<SourceReliabilityPenalty, "enabled" | "reliability_floor">>;
export type ArticleEvidence = Readonly<{
  publisher: RecordedIdentity | null;
  parent_domain: RecordedIdentity | null;
  operational: OperationalEvidence | null;
  source_operational?: SourceOperationalEvidence | null;
  primary_evidence: Readonly<{ ids: readonly string[]; origin: string }> | null;
  estimated_work: number;
}>;
export type PortfolioArticle = ScreenedCandidate & Readonly<{ evidence: ArticleEvidence }>;
export type OpportunityEvidence = Readonly<{
  covered_event_clusters: readonly string[] | null;
  underrepresented_verticals: readonly string[] | null;
  origin: string | null;
}>;

export function resolveOperationalHistory(
  source: string, supplied: OperationalEvidence | null, native: OperationalEvidence | null,
): OperationalEvidence | null {
  const measured = native === null ? null : {
    success_fraction: native.success_fraction, attempted: native.attempted, window_days: native.window_days,
  };
  if (supplied !== null && measured !== null && !isDeepStrictEqual(supplied, measured)) {
    throw new Error(`source.${source}.operational_history: supplied and native evidence disagree`);
  }
  return measured ?? supplied;
}

function validateIdentity(identity: RecordedIdentity | null): void {
  if (identity !== null) {
    NonEmptySchema.parse(identity.value);
    NonEmptySchema.parse(identity.origin);
  }
}

export function validateOpportunity(opportunity: OpportunityEvidence): void {
  if (opportunity.covered_event_clusters !== null || opportunity.underrepresented_verticals !== null) {
    NonEmptySchema.parse(opportunity.origin);
  } else if (opportunity.origin !== null) {
    throw new Error("Opportunity origin requires recorded opportunity evidence");
  }
  for (const values of [opportunity.covered_event_clusters, opportunity.underrepresented_verticals]) {
    for (const value of values ?? []) NonEmptySchema.parse(value);
  }
}

export function validatePortfolioArticles(
  articles: readonly PortfolioArticle[], planning: PlanningConfig, observedAt: string,
): PortfolioArticle[] {
  TimestampSchema.parse(observedAt);
  const identities = new Set<string>();
  let run: string | undefined;
  let correlation: string | undefined;
  const sources = new Map<string, PortfolioArticle["candidate"]["source"]>();
  const operational = new Map<string, OperationalEvidence | null>();
  return articles.map(article => {
    const candidate = FeedIngestCandidateSchema.parse(article.candidate);
    if (identities.has(candidate.candidate_id)) throw new Error("Repeated candidate instance in portfolio input");
    identities.add(candidate.candidate_id);
    run ??= candidate.run_id;
    correlation ??= candidate.correlation_id;
    if (candidate.run_id !== run || candidate.correlation_id !== correlation) {
      throw new Error("Portfolio candidates must belong to one run and correlation");
    }
    const previousSource = sources.get(candidate.source_id);
    if (previousSource !== undefined && !isDeepStrictEqual(previousSource, candidate.source)) {
      throw new Error("One run has inconsistent snapshots for a source");
    }
    sources.set(candidate.source_id, candidate.source);
    const policy = EffectiveFeedPolicySchema.parse(article.policy);
    const expected = resolvePolicy(planning, candidate.vertical, { freshness_hours: policy.triage.max_age_hours });
    if (!isDeepStrictEqual(policy, expected)) {
      throw new Error("Screened policy differs from resolved original-vertical policy");
    }
    const wordThreshold = candidate.source.form === "article"
      ? policy.triage.min_words_article : policy.triage.min_words_abstract;
    if (candidate.source.status !== "active" || candidate.word_count < wordThreshold) {
      throw new Error("Screened article does not meet its declared viability threshold");
    }
    const freshness = article.freshness;
    NonNegativeSchema.parse(freshness.recency_bonus);
    if (freshness.age_hours !== null) {
      FiniteSchema.parse(freshness.age_hours);
      if (freshness.age_hours > policy.triage.max_age_hours) throw new Error("Screened article exceeds its effective age limit");
    }
    if (freshness.timing_source === "unknown") {
      if (freshness.age_hours !== null || freshness.timing_at !== null || freshness.recency_bonus !== 0) {
        throw new Error("Unknown screening timing carries no inferred recency");
      }
    } else {
      TimestampSchema.parse(freshness.timing_at);
      if (freshness.age_hours === null) throw new Error("Known screening timing requires measured age");
      const age = (Date.parse(observedAt) - Date.parse(freshness.timing_at!)) / millisecondsPerHour;
      const recency = policy.triage.recency_weight * 0.5 ** (Math.max(0, age) / policy.triage.recency_half_life_hours);
      if (freshness.age_hours !== age || freshness.recency_bonus !== recency) {
        throw new Error("Screened freshness does not match the fixed observation clock");
      }
    }
    if (article.observation !== null && (article.observation.candidate_id !== candidate.candidate_id
      || article.observation.paywall === true)) {
      throw new Error("Harvest observation contradicts screened viability");
    }
    const evidence = article.evidence;
    validateIdentity(evidence.publisher);
    validateIdentity(evidence.parent_domain);
    NonNegativeSchema.parse(evidence.estimated_work);
    if (evidence.operational !== null) OperationalHistorySchema.parse(evidence.operational);
    if (evidence.source_operational != null) SourceOperationalEvidenceSchema.parse(evidence.source_operational);
    if (operational.has(candidate.source_id)
      && !isDeepStrictEqual(operational.get(candidate.source_id), evidence.operational)) {
      throw new Error(`source.${candidate.source_id}.operational_history: inconsistent per-source evidence`);
    }
    operational.set(candidate.source_id, evidence.operational);
    if (evidence.primary_evidence !== null) {
      NonEmptySchema.parse(evidence.primary_evidence.origin);
      for (const id of evidence.primary_evidence.ids) NonEmptySchema.parse(id);
    }
    return structuredClone({ ...article, candidate, policy, evidence });
  });
}

export function compareIdentity(left: PortfolioArticle, right: PortfolioArticle): number {
  return left.candidate.candidate_id < right.candidate.candidate_id ? -1
    : left.candidate.candidate_id > right.candidate.candidate_id ? 1 : 0;
}
