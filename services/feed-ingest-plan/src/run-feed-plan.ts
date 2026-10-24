/** Which real stages produce dispatches and pending audit evidence for one run? */
import { ParsedFeedBatchSchema } from "@idhazh/common-contracts";
import type { FeedIngestEvent } from "@idhazh/common-contracts";
import { randomUUID } from "node:crypto";
import type { PersistedLedgerFile } from "@idhazh/ledger-file-writer";
import { harvestFeeds } from "./harvest-feeds/harvest-pool";
import { harvestPolicy, sourceSnapshot } from "./harvest-feeds/load-harvest-inputs";
import type { ArticleEvidence, OpportunityEvidence } from "./curate-article-portfolio/portfolio-input";
import { resolveOperationalHistory } from "./curate-article-portfolio/portfolio-input";
import { resolveRunContext } from "./resolve-run-context";
import { readSeenEvidence, rememberFirstSight } from "./read-ledger-history/read-seen-evidence";
import { readExclusionEvidence } from "./read-ledger-history/read-exclusion-evidence";
import { readFeedHistory, observeFeedReliability } from "./read-ledger-history/read-feed-history";
import { readDailyPublication } from "./read-ledger-history/read-daily-publication";
import { recordFeedHealth } from "./read-ledger-history/record-feed-health";
import type { OwnFeedReceipt, FeedWriteReceipt } from "./read-ledger-history/own-feed-receipts";
import type { OwnSeenReceipt } from "./read-ledger-history/read-seen-evidence";
import { resolvePlanRequest, PlanError } from "./api/plan-request";
import { createStageLogger, resolveRunPolicy, writeAuditEvent } from "./logging/structured-logger";
import { harvestAssessments, screeningAssessments } from "./logging/stage-assessments";
import { readCurrentSelections } from "./partition-article-shards/read-editorial-selection";
import { resolvePlanningInputs } from "./resolve-planning-inputs";
import { writeStageBatch } from "./api/stage-store";
import { operationConfigFingerprint } from "./api/document-operations";
import { executeSelection } from "./api/selection-operation";
import { executePartition } from "./api/partition-operation";
import { executePersistence } from "./api/persistence-operation";
import type { PlanInputs } from "./load-plan-inputs";
import type { PlanningMetricsResult, PublicationMetricsResult, PublicationRecorderInput } from "./metrics/metrics-recorder";
import { createProgressLogger } from "./logging/progress-logger";
import type { ProgressRecord } from "./logging/progress-logger";
import type { TaskProfiling } from "../../host-probes/src/task-profile/task-profiler";

export type PlanRuntime = {
  git_sha: string;
  run_number?: string;
  correlation_id?: string;
  clock?: () => Date;
  captured_at?: string;
  boundary?: NonNullable<Parameters<typeof harvestFeeds>[3]>;
  log?: (event: FeedIngestEvent) => void;
  progress?: (record: ProgressRecord) => void;
  task_profiling?: TaskProfiling;
  evidence?: ReadonlyMap<string, ArticleEvidence>;
  opportunity?: OpportunityEvidence;
  seen_receipts?: readonly OwnSeenReceipt[];
  seen_days?: PlanInputs["settings"]["inputs"]["seen_days"];
  feed_history_receipts?: readonly OwnFeedReceipt[];
  on_feed_history_persisted?: (receipt: FeedWriteReceipt) => void;
  on_seen_persisted?: (receipt: { day: string; files: readonly PersistedLedgerFile[] }) => void;
  observe_publication?: (plan: FeedPlanResult, metrics: PlanningMetricsResult) => Promise<PublicationRecorderInput>;
};

export async function runFeedPlan(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime) {
  const captured = runtime.clock?.() ?? new Date();
  const request = resolvePlanRequest(raw, inputs.harvest.config);
  const context = resolveRunContext(inputs.settings, runtime.git_sha, captured,
    runtime.run_number, runtime.correlation_id, runtime.captured_at);
  if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled by service settings", "enabled");
  for (const entry of [
    inputs.registrations.rejections, inputs.registrations.selections,
    inputs.registrations.dispatches, inputs.registrations.seen,
    inputs.registrations.published, inputs.registrations.item_health,
    inputs.registrations.feed_health,
  ]) {
    if (entry.lifecycle_status !== "active") throw new PlanError("LEDGER_INACTIVE", `Required ledger ${entry.name} is not active`, entry.name);
  }
  // Recompute the effective input fingerprint instead of changing a harvested policy later.
  const harvestInputs = resolvePlanningInputs(inputs, request);
  const overrides = request.freshness_hours === undefined ? {} : { freshness_hours: request.freshness_hours };
  const fallbackPolicy = resolveRunPolicy(harvestInputs, request.freshness_hours);
  for (const source of harvestInputs.sources) {
    if (source.status !== "retired") harvestPolicy(harvestInputs, source.vertical, overrides);
  }
  const logger = createStageLogger(context, runtime.log ?? writeAuditEvent);
  const progress = createProgressLogger(context.correlation_id, runtime.progress);
  progress("PIPELINE_STARTED");
  const complete = (stage: FeedIngestEvent["stage"], input_count: number, output_count: number,
    terminal_rejection_count: number, source_count: number | null = null) => {
    progress("STAGE_COMPLETED", { stage, input_count, output_count, rejection_count: terminal_rejection_count });
    return logger.emit(stage, {
      kind: "stage_completion", stage, input_count, output_count, terminal_rejection_count, source_count,
    }, fallbackPolicy);
  };
  progress("HISTORY_READ_STARTED");
  const history = await readSeenEvidence(inputs.root, inputs.settings.inputs.seen_files, {
    now: context.now, lookback_days: inputs.clock_config.collect.seen_window_days,
    days: runtime.seen_days ?? inputs.settings.inputs.seen_days,
    receipt_root: inputs.outputRoot,
    ...(runtime.seen_receipts === undefined ? {} : { own_receipts: runtime.seen_receipts }),
  });
  const exclusionEvidence = {
    ...await readExclusionEvidence({
    root: inputs.root, now: context.now,
    publishedWindowDays: inputs.clock_config.collect.published_window_days,
    settledFailureCodes: inputs.clock_config.collect.settled_failure_codes,
    publishedRegistration: inputs.registrations.published, itemHealthRegistration: inputs.registrations.item_health,
    publishedDays: inputs.settings.inputs.published_days,
    settledFailureDays: inputs.settings.inputs.settled_failure_days,
    }),
    published_window_days: inputs.clock_config.collect.published_window_days,
  };
  const feedHistory = await readFeedHistory({
    root: inputs.root, now: context.captured_at, run_id: context.run_id,
    sources: harvestInputs.sources.map(source => sourceSnapshot(harvestInputs, source)),
    policy: inputs.clock_config.collect,
    health: inputs.registrations.feed_health,
    health_days: inputs.settings.inputs.feed_health_days,
    own_receipts: runtime.feed_history_receipts ?? [], receipt_root: inputs.outputRoot,
  });
  const dailyPublication = await readDailyPublication({
    root: inputs.root, day: context.date, registration: inputs.registrations.item_health,
    days: inputs.settings.inputs.settled_failure_days,
  });
  progress("HISTORY_READ_COMPLETED");
  logger.startStep();
  const harvest = await harvestFeeds(harvestInputs, {
    writer: context.writer, correlation_id: context.correlation_id,
    max_future_hours: inputs.clock_config.collect.max_future_hours,
    exclusions: exclusionEvidence,
    feed_history: feedHistory.sources,
    overrides, clock: () => new Date(context.now), progress,
    log: record => progress(record.subject === "feed" ? "FEED_REJECTED" : "ARTICLE_REJECTED", {
      source_id: record.source_id, ...(record.candidate_id === null ? {} : { candidate_id: record.candidate_id }),
      drop_reason: record.drop_reason,
      diagnostics: record.details.diagnostics,
    }),
  }, {
    outputRoot: inputs.outputRoot, registryEntry: inputs.registrations.rejections,
    ledgerSettings: inputs.ledgerSettings,
  }, runtime.boundary);
  const feedFiles = await recordFeedHealth({
    outcomes: harvest.feed_outcomes, articles: harvest.articles, history: feedHistory, now: context.captured_at,
    writer: context.writer, outputRoot: inputs.outputRoot, settings: inputs.ledgerSettings,
    health: inputs.registrations.feed_health,
    ...(runtime.on_feed_history_persisted === undefined ? {} : { on_persisted: runtime.on_feed_history_persisted }),
  });
  observeFeedReliability(feedHistory, feedFiles.rows, inputs.clock_config.collect);
  const seen = await rememberFirstSight(history, harvest.first_sight_candidates, context, {
    outputRoot: inputs.outputRoot, registryEntry: inputs.registrations.seen, ledgerSettings: inputs.ledgerSettings,
  });
  if (seen.sealing.files.length > 0) runtime.on_seen_persisted?.({ day: context.date, files: seen.sealing.files });
  for (const outcome of harvest.feed_outcomes) {
    const sourceHistory = feedHistory.sources.get(outcome.source.source_id)!;
    outcome.history = {
      ...sourceHistory,
      daily_published: {
        day: context.date, observed_count: dailyPublication.counts.get(outcome.source.source_id) ?? 0,
        availability: dailyPublication.history.availability,
      },
      health_coverage: feedHistory.history.health.availability,
      reliability_coverage: feedHistory.history.reliability.availability,
    };
    logger.emit("harvest-feeds", outcome, outcome.source.status === "active"
      ? harvestPolicy(harvestInputs, outcome.source.vertical, overrides) : fallbackPolicy, outcome.source.source_id);
  }
  for (const assessment of harvestAssessments({ harvest, context, overrides, evidence: runtime.evidence })) logger.emit(
    "harvest-feeds", { kind: "candidate_decision", assessment },
    assessment.policy, assessment.source_id, assessment.candidate_id,
  );
  complete("harvest-feeds", harvest.candidates.length + harvest.rejections.length, harvest.candidates.length,
    harvest.rejections.length, harvest.feed_outcomes.length);
  logger.startStep();
  const parsedBatch = await writeStageBatch(inputs.outputRoot, "parsed", ParsedFeedBatchSchema, {
    batch_id: randomUUID(), config_sha256: operationConfigFingerprint(inputs, runtime),
    context, request,
    candidates: harvest.candidates,
    observations: Object.fromEntries(harvest.articles.filter(article => article.candidate !== null)
      .map(article => [article.observation.candidate_id, article.observation])),
    seen: seen.evidence, rejections: harvest.rejections,
    evidence: Object.fromEntries(runtime.evidence ?? []),
    operational_history: Object.fromEntries([...feedHistory.sources].map(([id, history]) =>
      [id, resolveOperationalHistory(id, null, history.reliability)])),
    opportunity: runtime.opportunity ?? {
      covered_event_clusters: null, underrepresented_verticals: null, origin: null,
    },
  });
  const selection = await executeSelection({ batch_id: parsedBatch.batch_id }, inputs, runtime, screening => {
    for (const assessment of screeningAssessments({
      harvest, screening, context, overrides, seen: seen.evidence,
      maxFutureHours: inputs.clock_config.collect.max_future_hours, evidence: runtime.evidence,
    })) logger.emit(
      "screen-article-candidates", { kind: "candidate_decision", assessment },
      assessment.policy, assessment.source_id, assessment.candidate_id,
    );
    complete("screen-article-candidates", harvest.candidates.length, screening.admitted.length, screening.rejections.length);
    logger.startStep();
  });
  const { screening, curation, portfolio } = selection;
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
  complete("curate-article-portfolio", screening.admitted.length, curation.rows.length, curation.rejections.length);
  logger.startStep();
  await readCurrentSelections({
    curation, persisted: portfolio.selections, candidates: harvest.candidates,
    writer: context.writer, outputRoot: inputs.outputRoot, context,
  });
  const partitioned = await executePartition({
    batch_id: selection.batch.batch_id, strategy: request.partition_strategy, shards: request.shards,
  }, inputs, runtime);
  const { partition } = partitioned;
  complete("partition-article-shards", curation.rows.length, partition.dispatches.length, 0);
  logger.startStep();
  const dispatches = await executePersistence({ batch_id: partitioned.batch.batch_id }, inputs, runtime);
  complete("seal-article-ledger", partition.dispatches.length, partition.dispatches.length, 0);
  progress("PLANNING_STAGES_COMPLETED", { output_count: partition.dispatches.length });
  return {
    status: "dispatches_persisted_audit_pending" as const,
    context, request, events: logger.events,
    batches: {
      parsed_batch_id: parsedBatch.batch_id,
      selection_batch_id: selection.batch.batch_id,
      partition_batch_id: partitioned.batch.batch_id,
    },
    files: {
      harvest_rejections: harvest.rejection_files,
      screening_rejections: screening.sealing,
      selections: portfolio.selections, curation_rejections: portfolio.rejections,
      dispatches,
      seen: seen.sealing,
      feed_health: feedFiles.health,
    },
    evidence: { harvest, screening, curation, seen, exclusions: exclusionEvidence, partition,
      feed_history: feedHistory, daily_publication: dailyPublication,
      publisher_publication: selection.publisher_publication },
  };
}
export type FeedPlanResult = Awaited<ReturnType<typeof runFeedPlan>>;
export type RecordedFeedPlanResult = FeedPlanResult & { metrics: PlanningMetricsResult; publication?: PublicationMetricsResult };

export function summarizePlan(result: FeedPlanResult & { metrics?: PlanningMetricsResult; publication?: PublicationMetricsResult }) {
  const planningCompletion = result.metrics?.planning_completion ?? null;
  const planningComplete = planningCompletion?.status === "complete";
  const publication = result.publication ?? null;
  const auditedComplete = planningComplete && publication?.audited_complete === true;
  if (publication !== null && (publication.run_id !== result.context.run_id
    || publication.attempt !== result.context.writer.attempt || publication.correlation_id !== result.context.correlation_id)) {
    throw new Error("Publication audit differs from this planning attempt");
  }
  return {
    status: auditedComplete ? "audit_complete" as const : planningComplete ? "planning_complete_audit_pending" as const : result.status,
    planning_complete: planningComplete, audited_complete: auditedComplete, publication,
    planning_completion: planningCompletion,
    source_records: result.metrics?.source_records ?? null,
    run_id: result.context.run_id, correlation_id: result.context.correlation_id,
    date: result.context.date, observed_at: result.context.now, request: result.request,
    batches: result.batches,
    strategy: result.evidence.partition.strategy, dispatch_count: result.evidence.partition.dispatch_count,
    selected_candidate_ids: result.evidence.curation.rows.map(row => row.candidate_id),
    assignments: result.evidence.partition.dispatches.map(dispatch => ({
      candidate_id: dispatch.content.candidate_id, partition: dispatch.partition,
    })),
    files: { ...result.files, ...(result.metrics === undefined ? {} : { source_runs: result.metrics.files.source_runs }) },
    metrics: result.metrics,
    first_sight: {
      absence_proof: result.evidence.seen.absence_proof,
      global_absence: result.evidence.seen.global_absence,
      window: result.evidence.seen.window,
      own_receipts: result.evidence.seen.own_receipts,
      created_count: result.evidence.seen.new_rows.length,
    },
    exclusions: {
      already_published: result.evidence.harvest.rejections.filter(row => row.drop_reason === "ALREADY_PUBLISHED").length,
      settled_failure: result.evidence.harvest.rejections.filter(row => row.drop_reason === "SETTLED_FAILURE").length,
      blocked_url_marker: result.evidence.harvest.rejections.filter(row => row.drop_reason === "BLOCKED_URL_MARKER").length,
      history: result.evidence.exclusions.history,
    },
    feed_history: {
      ...result.evidence.feed_history.history,
      daily_publication: result.evidence.daily_publication.history,
      publisher_publication: {
        day: result.evidence.publisher_publication.day,
        availability: result.evidence.publisher_publication.availability,
        gaps: result.evidence.publisher_publication.gaps,
        history: result.evidence.publisher_publication.history,
      },
    },
    editorial_inputs: {
      headline_consumer: "existing_mmr_lens_entity_penalties",
      bonus_consumer: null,
      unavailable_consumers: ["salience_vote", "watchlist_bonus", "lens_weight_bonus"],
      salience: result.evidence.harvest.salience,
      candidates: result.evidence.harvest.candidates.map(candidate => ({
        candidate_id: candidate.candidate_id, url_key: candidate.url_key, labels: candidate.labels,
        planning_observations: candidate.planning_observations,
      })),
    },
    audit: {
      status: auditedComplete ? "complete" : result.metrics === undefined ? "unavailable" : "assessment_diversity_recorded_audit_pending",
      reason: auditedComplete ? null : planningComplete
        ? "Current planning is verified; publication and complete historical audit remain outside this result"
        : "Current planning completion has not been verified",
    },
  };
}
