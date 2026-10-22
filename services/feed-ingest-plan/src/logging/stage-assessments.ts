/** Which factual article assessments describe the actual early-stage decisions? */
import { ArticleAssessmentRecordSchema } from "@idhazh/common-contracts";
import type {
  ArticleAssessmentRecord, CandidateRejectionRecord, FeedIngestCandidate, PolicyIdentity,
  PlanningRunOverrides, SourceSnapshot,
} from "@idhazh/common-contracts";
import type { HarvestObservation, HarvestResult } from "../harvest-feeds/harvest-types";
import { harvestPolicy, sourceSnapshot } from "../harvest-feeds/load-harvest-inputs";
import { calculateFreshness } from "../screen-article-candidates/freshness-decay";
import type { FreshnessEvidence } from "../screen-article-candidates/freshness-decay";
import type { ScreeningResult } from "../screen-article-candidates/triage-gates";
import { indexSeenEvidence } from "../screen-article-candidates/seen-evidence";
import type { SeenEvidence } from "../screen-article-candidates/seen-evidence";
import { resolvePolicy } from "../config/resolve-policy";
import type { ArticleEvidence } from "../curate-article-portfolio/portfolio-input";
import type { RunContext } from "../resolve-run-context";

function assess(input: {
  candidate: FeedIngestCandidate | null; rejection: CandidateRejectionRecord | null;
  observation: HarvestObservation; source: SourceSnapshot; policy: PolicyIdentity;
  context: RunContext; stage: "harvest-feeds" | "screen-article-candidates";
  freshness: FreshnessEvidence | null; evidence: ArticleEvidence | undefined;
}) {
  const { candidate, rejection, observation, source, policy, context, freshness, evidence, stage } = input;
  const extraction = observation.extraction === "success" && candidate !== null;
  const failed = observation.extraction === "failed" || observation.extraction === "empty";
  const suitability = candidate !== null && observation.paywall !== null;
  const measured = freshness !== null && freshness.timing_source !== "unknown";
  return ArticleAssessmentRecordSchema.parse({
    date: context.date, correlation_id: context.correlation_id,
    candidate_id: observation.candidate_id, source_id: source.source_id, source,
    labels: candidate?.labels ?? {
      assigned_desk: null, lenses: null, event_types: null, event_cluster_id: null,
      entities: null, origin: null, matcher_version: null,
    },
    canonical_url: candidate?.canonical_url ?? rejection?.canonical_url ?? null,
    url_key: candidate?.url_key ?? rejection?.url_key ?? null,
    stage, decision: rejection === null ? "admitted" : "rejected",
    reason: rejection?.drop_reason ?? null, observed_at: context.now, policy,
    timing_at: measured ? freshness.timing_at : null,
    timing_basis: measured ? freshness.timing_source : "unavailable",
    age_hours: measured ? freshness.age_hours : null,
    max_age_hours: measured ? policy.max_age_hours : null,
    extracted_word_count: extraction ? candidate!.word_count : null,
    source_form: source.form,
    extraction_outcome: extraction ? "success" : failed ? "failed"
      : observation.extraction === "not-attempted" ? "not_attempted" : "unavailable",
    word_threshold: extraction || failed
      ? source.form === "article" ? policy.min_words_article : policy.min_words_abstract : null,
    author_present: candidate === null ? null : candidate.author !== null,
    publisher_identity: candidate === null ? null : evidence?.publisher?.value ?? null,
    attribution_status: candidate === null ? "unavailable" : "available",
    paywall: suitability ? observation.paywall : null,
    categories: suitability ? candidate!.categories : null,
    required_fields_present: suitability ? true : null,
    suitability_status: suitability ? "available" : "unavailable",
    informative_verdict_status: "not_assessed", informative_verdict: null,
    informative_evaluator_version: null, suitability_verdict_status: "not_assessed",
    suitability_verdict: null, suitability_evaluator_version: null,
    score_evidence: null, score_evidence_status: "not_assessed",
    diagnostics: observation.diagnostics,
  });
}

export function harvestAssessments(input: {
  harvest: HarvestResult; context: RunContext; overrides: PlanningRunOverrides;
  evidence?: ReadonlyMap<string, ArticleEvidence> | undefined;
}): ArticleAssessmentRecord[] {
  const sources = new Map(input.harvest.inputs.sources.map(source => [
    source.id, sourceSnapshot(input.harvest.inputs, source),
  ]));
  return input.harvest.articles.map(article => {
    const source = sources.get((article.candidate ?? article.rejection)!.source_id);
    if (source === undefined) throw new Error("Harvest article has no configured source snapshot");
    return assess({
      ...article, source, policy: harvestPolicy(input.harvest.inputs, source.vertical, input.overrides),
      context: input.context, stage: "harvest-feeds", freshness: article.observation.preflight_freshness ?? null,
      evidence: input.evidence?.get(article.observation.candidate_id),
    });
  });
}

export function screeningAssessments(input: {
  harvest: HarvestResult; screening: ScreeningResult; context: RunContext;
  overrides: PlanningRunOverrides; seen: SeenEvidence; maxFutureHours: number;
  evidence?: ReadonlyMap<string, ArticleEvidence> | undefined;
}): ArticleAssessmentRecord[] {
  const admitted = new Map(input.screening.admitted.map(article => [article.candidate.candidate_id, article]));
  const rejections = new Map(input.screening.rejections.map(row => [row.candidate_id, row]));
  const seen = indexSeenEvidence(input.seen);
  return input.harvest.articles.flatMap(article => {
    if (article.candidate === null) return [];
    const candidate = article.candidate;
    const accepted = admitted.get(candidate.candidate_id);
    const rejection = rejections.get(candidate.candidate_id) ?? null;
    if ((accepted === undefined) === (rejection === null)) throw new Error("Screening has no single terminal decision for candidate");
    const policy = accepted?.policy ?? resolvePolicy(input.harvest.inputs, candidate.vertical, input.overrides);
    const freshness = accepted?.freshness ?? calculateFreshness(
      candidate, seen.get(candidate.url_key), input.context.now, input.maxFutureHours, policy,
    );
    return [assess({
      candidate, rejection, observation: article.observation, source: candidate.source,
      policy: harvestPolicy(input.harvest.inputs, candidate.vertical, input.overrides),
      context: input.context, stage: "screen-article-candidates", freshness,
      evidence: input.evidence?.get(candidate.candidate_id),
    })];
  });
}
