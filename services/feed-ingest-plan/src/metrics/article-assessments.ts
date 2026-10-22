/** Can every original measurement be represented without changing its meaning? */
import { ArticleAssessmentRecordSchema, FeedIngestConfigSchema, FiniteSchema } from "@idhazh/common-contracts";
import type { ArticleAssessmentRecord } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { FeedPlanResult } from "../run-feed-plan";
import { calculateFreshness } from "../screen-article-candidates/freshness-decay";
import { indexSeenEvidence } from "../screen-article-candidates/seen-evidence";
import { resolvePolicy } from "../config/resolve-policy";
import { requireSame } from "./stage-membership";
import { harvestPolicy } from "../harvest-feeds/load-harvest-inputs";

export function preflightMeasurements(result: FeedPlanResult, inputs: PlanInputs) {
  FeedIngestConfigSchema.parse(result.evidence.harvest.config);
  const maxFutureHours = FiniteSchema.min(0).parse(inputs.clock_config.collect.max_future_hours);
  const seen = indexSeenEvidence(result.evidence.seen.evidence);
  const overrides = result.request.freshness_hours === undefined ? {} : { freshness_hours: result.request.freshness_hours };
  const timing = new Map<string, ReturnType<typeof calculateFreshness>>();
  for (const candidate of result.evidence.harvest.candidates) {
    const policy = resolvePolicy(result.evidence.harvest.inputs, candidate.vertical, overrides);
    // Rejected candidates do not retain timing. Replay the same pure measurement on its original inputs.
    const measured = calculateFreshness(candidate, seen.get(candidate.url_key), result.context.now, maxFutureHours, policy);
    const field = `candidate.${candidate.candidate_id}`;
    const retained = result.evidence.screening.admitted.find(article => article.candidate.candidate_id === candidate.candidate_id);
    if (retained !== undefined) requireSame(retained.freshness, measured, `${field}.freshness`);
    timing.set(candidate.candidate_id, measured);
  }
  return timing;
}

export function translateArticleAssessments(result: FeedPlanResult, inputs: PlanInputs): ArticleAssessmentRecord[] {
  const timing = preflightMeasurements(result, inputs);
  const rows = result.events.flatMap(event => {
    if (event.payload.kind !== "candidate_decision") return [];
    const row = ArticleAssessmentRecordSchema.parse(event.payload.assessment);
    const original = result.evidence.harvest.articles.find(article => article.observation.candidate_id === row.candidate_id);
    if (original === undefined) throw new Error(`candidate.${row.candidate_id}: original harvest observation is missing`);
    const candidate = original.candidate;
    const overrides = result.request.freshness_hours === undefined ? {} : { freshness_hours: result.request.freshness_hours };
    const policy = harvestPolicy(result.evidence.harvest.inputs, row.source.vertical, overrides);
    requireSame(row.policy, policy, `candidate.${row.candidate_id}.policy`);
    if (candidate !== null) {
      requireSame([row.source, row.canonical_url, row.url_key, row.labels, row.author_present],
        [candidate.source, candidate.canonical_url, candidate.url_key, candidate.labels, candidate.author !== null],
        `candidate.${row.candidate_id}.article`);
      if (original.observation.extraction === "success") requireSame(
        [row.extracted_word_count, row.word_threshold, row.extraction_outcome],
        [candidate.word_count, candidate.source.form === "article" ? policy.min_words_article : policy.min_words_abstract, "success"],
        `candidate.${row.candidate_id}.substance`);
    }
    requireSame([
      row.informative_verdict_status, row.informative_verdict, row.informative_evaluator_version,
      row.suitability_verdict_status, row.suitability_verdict, row.suitability_evaluator_version,
    ], ["not_assessed", null, null, "not_assessed", null, null], `candidate.${row.candidate_id}.semantic_verdict`);
    if (row.stage !== "harvest-feeds") {
      const measured = timing.get(row.candidate_id);
      if (measured === undefined) throw new Error(`candidate.${row.candidate_id}.freshness: original measurement is missing`);
      requireSame([row.timing_basis, row.timing_at, row.age_hours],
        [measured.timing_source === "unknown" ? "unavailable" : measured.timing_source,
          measured.timing_at, measured.age_hours], `candidate.${row.candidate_id}.timing`);
      requireSame(row.max_age_hours, measured.age_hours === null ? null : policy.max_age_hours, `candidate.${row.candidate_id}.max_age_hours`);
    }
    if (row.stage === "curate-article-portfolio") {
      const actual = result.evidence.curation.assessments.find(item => item.candidate_id === row.candidate_id);
      requireSame(row, actual, `candidate.${row.candidate_id}.curation_assessment`);
    }
    return [row];
  });
  return rows;
}
