/** Which real stages produce dispatches and pending audit evidence for one run? */
import type { FeedIngestEvent } from "@idhazh/common-contracts";
import { harvestFeeds } from "./harvest-feeds/harvest-pool";
import { harvestPolicy, loadHarvestInputs } from "./harvest-feeds/load-harvest-inputs";
import { screenArticleCandidates } from "./screen-article-candidates/triage-gates";
import { curateArticles, persistPortfolio } from "./curate-article-portfolio/editorial-selection";
import type { ArticleEvidence, OpportunityEvidence } from "./curate-article-portfolio/portfolio-input";
import { resolveRunContext } from "./resolve-run-context";
import { readSeenEvidence } from "./read-ledger-history/read-seen-evidence";
import { resolvePlanRequest, PlanError } from "./api/plan-request";
import { createStageLogger, writeJsonLine } from "./logging/structured-logger";
import { harvestAssessments, screeningAssessments } from "./logging/stage-assessments";
import { prepareDispatches, sealDispatches } from "./seal-article-ledger/plan-sealer";
import type { PlanInputs } from "./load-plan-inputs";

export type PlanRuntime = {
  git_sha: string;
  run_number?: string;
  clock?: () => Date;
  boundary?: NonNullable<Parameters<typeof harvestFeeds>[3]>;
  log?: (event: FeedIngestEvent) => void;
  evidence?: ReadonlyMap<string, ArticleEvidence>;
  opportunity?: OpportunityEvidence;
};

export async function runFeedPlan(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime) {
  const captured = runtime.clock?.() ?? new Date();
  const request = resolvePlanRequest(raw, inputs.harvest.config);
  const context = resolveRunContext(inputs.settings, runtime.git_sha, captured, runtime.run_number);
  if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled by service settings", "enabled");
  for (const entry of Object.values(inputs.registrations)) {
    if (entry.lifecycle_status !== "active") throw new PlanError("LEDGER_INACTIVE", `Required ledger ${entry.name} is not active`, entry.name);
  }
  // Recompute the effective input fingerprint instead of changing a harvested policy later.
  const harvestInputs = loadHarvestInputs({
    config: { ...inputs.harvest.config, curate: { ...inputs.harvest.config.curate, article_limit: request.article_limit } },
    taxonomy: { ...inputs.harvest.taxonomy, ...inputs.harvest.registry },
    sources: { feeds: inputs.harvest.sources }, extraction: { extract: inputs.harvest.extraction },
  });
  const overrides = request.freshness_hours === undefined ? {} : { freshness_hours: request.freshness_hours };
  const fallbackPolicy = harvestPolicy(harvestInputs, harvestInputs.taxonomy.verticals[0]!.id, overrides);
  for (const source of harvestInputs.sources) harvestPolicy(harvestInputs, source.vertical, overrides);
  const logger = createStageLogger(context, runtime.log ?? writeJsonLine);
  const complete = (stage: FeedIngestEvent["stage"], input_count: number, output_count: number,
    terminal_rejection_count: number, source_count: number | null = null) => logger.emit(stage, {
    kind: "stage_completion", stage, input_count, output_count, terminal_rejection_count, source_count,
  }, fallbackPolicy);
  const seen = await readSeenEvidence(inputs.root, inputs.settings.inputs.seen_files);
  logger.startStep();
  const harvest = await harvestFeeds(harvestInputs, {
    writer: context.writer, correlation_id: context.correlation_id,
    overrides, clock: () => new Date(context.now),
  }, {
    outputRoot: inputs.outputRoot, registryEntry: inputs.registrations.rejections,
    ledgerSettings: inputs.ledgerSettings,
  }, runtime.boundary);
  for (const outcome of harvest.feed_outcomes) {
    logger.emit("harvest-feeds", outcome, harvestPolicy(harvestInputs, outcome.source.vertical, overrides), outcome.source.source_id);
  }
  for (const assessment of harvestAssessments({ harvest, context, overrides, evidence: runtime.evidence })) logger.emit(
    "harvest-feeds", { kind: "candidate_decision", assessment },
    assessment.policy, assessment.source_id, assessment.candidate_id,
  );
  complete("harvest-feeds", harvest.candidates.length + harvest.rejections.length, harvest.candidates.length,
    harvest.rejections.length, harvest.feed_outcomes.length);
  logger.startStep();
  const screening = await screenArticleCandidates({
    candidates: harvest.candidates,
    observations: Object.fromEntries(harvest.articles.filter(article => article.candidate !== null)
      .map(article => [article.observation.candidate_id, article.observation])),
    seen: seen.evidence, planning: harvestInputs, clock_config: inputs.clock_config,
    run: { now: context.now, run_id: context.run_id, correlation_id: context.correlation_id, overrides },
  }, {
    outputRoot: inputs.outputRoot, registryEntry: inputs.registrations.rejections,
    ledgerSettings: inputs.ledgerSettings, writerContext: context.writer,
  });
  for (const assessment of screeningAssessments({
    harvest, screening, context, overrides, seen: seen.evidence,
    maxFutureHours: inputs.clock_config.collect.max_future_hours, evidence: runtime.evidence,
  })) logger.emit(
    "screen-article-candidates", { kind: "candidate_decision", assessment },
    assessment.policy, assessment.source_id, assessment.candidate_id,
  );
  complete("screen-article-candidates", harvest.candidates.length, screening.admitted.length, screening.rejections.length);
  logger.startStep();
  const curation = curateArticles({
    articles: screening.admitted.map(article => ({
      ...article, evidence: runtime.evidence?.get(article.candidate.candidate_id) ?? {
        publisher: null, parent_domain: null, operational: null, primary_evidence: null,
        estimated_work: article.candidate.word_count,
      },
    })),
    planning: harvestInputs, observed_at: context.now,
    opportunity: runtime.opportunity ?? {
      covered_event_clusters: null, underrepresented_verticals: null, origin: null,
    },
  });
  for (const assessment of curation.assessments) logger.emit(
    "curate-article-portfolio", { kind: "candidate_decision", assessment },
    assessment.policy, assessment.source_id, assessment.candidate_id,
  );
  for (const step of curation.trace) {
    if (step.choice === null) continue;
    const article = curation.selected.find(article => article.candidate.candidate_id === step.choice!.candidate_id)!;
    logger.emit("curate-article-portfolio", step.choice, article.candidate.policy,
      article.candidate.source_id, article.candidate.candidate_id);
  }
  const portfolio = await persistPortfolio(curation, {
    outputRoot: inputs.outputRoot, writerContext: context.writer, ledgerSettings: inputs.ledgerSettings,
    registrations: inputs.registrations, date: context.date,
  });
  complete("curate-article-portfolio", screening.admitted.length, curation.rows.length, curation.rejections.length);
  logger.startStep();
  const partition = await prepareDispatches(curation, portfolio, harvest.candidates, inputs, context, request);
  complete("partition-article-shards", curation.rows.length, partition.dispatches.length, 0);
  logger.startStep();
  const dispatches = await sealDispatches(partition, inputs, context);
  complete("seal-article-ledger", partition.dispatches.length, partition.dispatches.length, 0);
  return {
    status: "dispatches_persisted_audit_pending" as const,
    context, request, events: logger.events,
    files: {
      harvest_rejections: harvest.rejection_files,
      screening_rejections: screening.sealing,
      selections: portfolio.selections, curation_rejections: portfolio.rejections,
      dispatches,
    },
    evidence: { harvest, screening, curation, seen, partition },
  };
}
export type FeedPlanResult = Awaited<ReturnType<typeof runFeedPlan>>;

export function summarizePlan(result: FeedPlanResult) {
  return {
    status: result.status, audited_complete: false,
    run_id: result.context.run_id, correlation_id: result.context.correlation_id,
    date: result.context.date, observed_at: result.context.now, request: result.request,
    strategy: result.evidence.partition.strategy, dispatch_count: result.evidence.partition.dispatch_count,
    selected_candidate_ids: result.evidence.curation.rows.map(row => row.candidate_id),
    assignments: result.evidence.partition.dispatches.map(dispatch => ({
      candidate_id: dispatch.content.candidate_id, partition: dispatch.partition,
    })),
    files: result.files,
    audit: { status: "unavailable", reason: "Required audit writes and complete-attempt verification are not integrated" },
  };
}
