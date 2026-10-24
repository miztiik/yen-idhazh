/** Which articles pass screening and ranking within one saved parse batch? */
import type { ParsedFeedBatch } from "@idhazh/common-contracts";
import type { PlanInputs } from "./load-plan-inputs";
import { screenArticleCandidates } from "./screen-article-candidates/triage-gates";
import type { ScreeningResult } from "./screen-article-candidates/triage-gates";
import { curateArticles, persistPortfolio } from "./curate-article-portfolio/editorial-selection";
import { resolveOperationalHistory } from "./curate-article-portfolio/portfolio-input";
import { resolvePlanRequest } from "./api/plan-request";
import { resolvePlanningInputs } from "./resolve-planning-inputs";

export async function selectArticles(
  batch: ParsedFeedBatch, inputs: PlanInputs, onScreened?: (result: ScreeningResult) => void,
) {
  const request = resolvePlanRequest(batch.request, inputs.harvest.config);
  const planning = resolvePlanningInputs(inputs, request);
  const overrides = request.freshness_hours === undefined ? {} : { freshness_hours: request.freshness_hours };
  const screening = await screenArticleCandidates({
    candidates: batch.candidates, observations: batch.observations,
    seen: batch.seen, planning, clock_config: inputs.clock_config,
    run: { now: batch.context.now, run_id: batch.context.run_id,
      correlation_id: batch.context.correlation_id, overrides },
  }, {
    outputRoot: inputs.outputRoot, registryEntry: inputs.registrations.rejections,
    ledgerSettings: inputs.ledgerSettings, writerContext: batch.context.writer,
  });
  onScreened?.(screening);
  const curation = curateArticles({
    articles: screening.admitted.map(article => {
      const supplied = batch.evidence[article.candidate.candidate_id] ?? {
        publisher: null, parent_domain: null, operational: null, primary_evidence: null,
        estimated_work: article.candidate.word_count,
      };
      return { ...article, evidence: {
        ...supplied,
        operational: resolveOperationalHistory(article.candidate.source_id, supplied.operational,
          batch.operational_history[article.candidate.source_id] ?? null),
      } };
    }),
    planning, observed_at: batch.context.now,
    reliability_floor: inputs.clock_config.collect.reliability_floor,
    opportunity: batch.opportunity,
  });
  const portfolio = await persistPortfolio(curation, {
    outputRoot: inputs.outputRoot, writerContext: batch.context.writer,
    ledgerSettings: inputs.ledgerSettings, registrations: inputs.registrations, date: batch.context.date,
  });
  return { screening, curation, portfolio };
}
