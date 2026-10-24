/** Which measured article components contribute before set-dependent penalties? */
import { ArticleAssessmentRecordSchema } from "@idhazh/common-contracts";
import type { SourceReliabilityPenalty } from "@idhazh/common-contracts";
import type { PortfolioArticle, ReliabilityControls } from "./portfolio-input";

export function measureArticle(article: PortfolioArticle) {
  const { candidate, policy, freshness, evidence } = article;
  const recency = freshness.recency_bonus;
  const authority = policy.curate.source_authority_weight
    * candidate.source.weight * candidate.source.applied_tier_weight;
  return {
    operational: evidence.operational,
    article: {
      timing: freshness, word_count: candidate.word_count, form: candidate.source.form,
      author_present: candidate.author !== null, publisher: evidence.publisher,
      informative_verdict: null, suitability_verdict: null, evaluator_version: null,
      verdict_status: "not_assessed" as const, harvest_observation: article.observation,
    },
    components: { recency, authority },
    base_article_score: recency + authority,
  };
}

export function recordAssessment(article: PortfolioArticle, observedAt: string) {
  const { candidate, policy, freshness, evidence } = article;
  const measured = freshness.timing_source !== "unknown";
  const observedExtraction = article.observation?.extraction;
  const extraction = observedExtraction === "success";
  const failedExtraction = observedExtraction === "failed" || observedExtraction === "empty";
  const suitability = article.observation?.paywall !== null && article.observation !== null;
  const { mmr_weights, ...curate } = policy.curate;
  return ArticleAssessmentRecordSchema.parse({
    date: observedAt.slice(0, 10), diagnostics: article.observation?.diagnostics ?? null,
    correlation_id: candidate.correlation_id, candidate_id: candidate.candidate_id,
    source_id: candidate.source_id, source: candidate.source, labels: candidate.labels,
    canonical_url: candidate.canonical_url, url_key: candidate.url_key,
    stage: "curate-article-portfolio", decision: "selected", reason: null, observed_at: observedAt,
    policy: { ...candidate.policy, ...policy.triage, ...curate, ...mmr_weights },
    timing_at: measured ? freshness.timing_at : null,
    timing_basis: measured ? freshness.timing_source : "unavailable",
    age_hours: measured ? freshness.age_hours : null,
    max_age_hours: measured ? policy.triage.max_age_hours : null,
    extracted_word_count: extraction ? candidate.word_count : null, source_form: candidate.source.form,
    extraction_outcome: extraction ? "success" : failedExtraction ? "failed"
      : observedExtraction === "not-attempted" ? "not_attempted" : "unavailable",
    word_threshold: !extraction && !failedExtraction ? null : candidate.source.form === "article"
      ? policy.triage.min_words_article : policy.triage.min_words_abstract,
    author_present: candidate.author !== null, publisher_identity: evidence.publisher?.value ?? null,
    attribution_status: "available", paywall: suitability ? article.observation!.paywall : null,
    categories: suitability ? candidate.categories : null,
    required_fields_present: suitability ? true : null, suitability_status: suitability ? "available" : "unavailable",
    informative_verdict_status: "not_assessed", informative_verdict: null, informative_evaluator_version: null,
    suitability_verdict_status: "not_assessed", suitability_verdict: null, suitability_evaluator_version: null,
    score_evidence: null, score_evidence_status: "not_assessed",
  });
}

export function measurePriority(article: PortfolioArticle, controls: ReliabilityControls) {
  const measured = measureArticle(article);
  const history = article.evidence.operational;
  const factor = history === null ? null : Math.max(controls.reliability_floor, history.success_fraction);
  const reliability: SourceReliabilityPenalty = {
    ...controls, source_authority_score: measured.components.authority,
    history, production_factor: factor,
    value: factor === null ? null : controls.enabled ? measured.components.authority * (1 - factor) : 0,
  };
  return {
    base_article_score: measured.base_article_score, source_reliability: reliability,
    priority_score: measured.base_article_score - (reliability.value ?? 0),
  };
}

export function compareArticle(left: PortfolioArticle, right: PortfolioArticle, controls: ReliabilityControls): number {
  const difference = measurePriority(right, controls).priority_score - measurePriority(left, controls).priority_score;
  if (difference !== 0) return difference;
  return left.candidate.candidate_id < right.candidate.candidate_id ? -1
    : left.candidate.candidate_id > right.candidate.candidate_id ? 1 : 0;
}
