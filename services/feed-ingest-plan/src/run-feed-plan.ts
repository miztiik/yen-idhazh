/** Execute one isolated planner run and finalize its five-ledger result even after later work fails. */
import { randomUUID } from "node:crypto";
import {
  DiscoveredArticleRowSchema, ParsedFeedBatchSchema, PlannerWorkEventSchema,
} from "@idhazh/common-contracts";
import type { FeedIngestEvent, PlannerArticleEvidence, DiscoveredArticleRow, PlanRunRow } from "@idhazh/common-contracts";
import type { PersistLedgerResult } from "@idhazh/ledger-file-writer";
import { harvestFeeds } from "./harvest-feeds/harvest-pool";
import { sourceSnapshot } from "./harvest-feeds/load-harvest-inputs";
import { ArticleParserPool } from "./harvest-feeds/article-parser-pool";
import { resolveRunContext } from "./resolve-run-context";
import { readDiscoveredEvidence, rememberDiscoveries, foldDiscoveryHistory } from "./read-ledger-history/read-discovered-evidence";
import { requiredUtcDays } from "./utc-instant";
import { resolveArticleEvidence } from "./website-group";
import { readExclusionEvidence } from "./read-ledger-history/read-exclusion-evidence";
import { resolvePlanRequest, PlanError } from "./api/plan-request";
import { createStageLogger } from "./logging/structured-logger";
import { stageStore } from "./api/stage-store";
import { operationConfigFingerprint } from "./api/document-operations";
import { executeSelection } from "./api/selection-operation";
import { executePartition } from "./api/partition-operation";
import { executePersistence } from "./api/persistence-operation";
import { prepareFeedHealthState, recordFeedHealthState } from "./api/feed-health-state-operation";
import type { PlanInputs } from "./load-plan-inputs";
import type { ProgressRecord } from "./logging/progress-logger";
import { createIngestObservations } from "./ingest-observations";
import { createRunHealth } from "./run-health";
import { plannerMemory } from "./planner-memory";
import { recordPlanRun } from "./record-plan-run";
import { registerStageExecution } from "./api/document-state";

export type PlanRuntime = {
  git_sha: string; run_number?: string; correlation_id?: string;
  attempt?: number; producer?: string; clock?: () => Date;
  selection_clock?: () => Date; captured_at?: string; observation_clock?: () => Date;
  boundary?: NonNullable<Parameters<typeof harvestFeeds>[2]>;
  log?: (event: FeedIngestEvent) => void; progress?: (record: ProgressRecord) => void;
  parser_pool?: ArticleParserPool;
  signal?: AbortSignal;
  evidence?: ReadonlyMap<string, PlannerArticleEvidence>;
};
export async function runFeedPlan(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime) {
  const request = resolvePlanRequest(raw, inputs.harvest.config);
  if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled", "enabled");
  const captured = runtime.clock?.() ?? new Date();
  const context = resolveRunContext(inputs.settings, runtime.git_sha, captured,
    runtime.run_number, runtime.correlation_id, runtime.captured_at, runtime.attempt, runtime.producer);
  const started = performance.now();
  registerStageExecution(inputs, context, "plan", started);
  const emit = createStageLogger(context, runtime.log);
  const timings: PlanRunRow["api_timings"] = [];
  const files: Partial<Record<"discovered_articles" | "selected_articles" | "rejected_articles" | "feed_health_state" | "plan_runs", PersistLedgerResult>> = {};
  const batches: { parsed_batch_id?: string; selection_batch_id?: string; partition_batch_id?: string } = {};
  let selected: Awaited<ReturnType<typeof executeSelection>>["batch"] | undefined;
  let partitioned: Awaited<ReturnType<typeof executePartition>>["batch"] | undefined;
  let artifact: string | null = null;
  let failureCode: string | null = null;
  let selectionStartedAt: string | null = null;
  let healthAttempted = false;
  const memory = plannerMemory(inputs);
  const sources = inputs.harvest.sources.map(source => sourceSnapshot(inputs.harvest, source));
  let parseStarted: number | undefined;
  let parseFinished: number | undefined;
  let parseFailed = false;
  const parserActivity = (phase: "started" | "completed" | "failed", duration_ms: number | null, feed_id: string | null = null) => {
    const now = performance.now();
    if (phase === "started") parseStarted ??= now;
    else parseFinished = now;
    if (phase === "failed") parseFailed = true;
    emit("parse", phase, { duration_ms, ...(feed_id === null ? {} : { feed_id }) });
  };
  const parserPool = runtime.parser_pool ?? new ArticleParserPool(inputs.settings.listener.parser_concurrency);
  let work: ReturnType<typeof createRunHealth> | undefined;
  let history: Awaited<ReturnType<typeof prepareFeedHealthState>> | undefined;
  let discovery: Awaited<ReturnType<typeof readDiscoveredEvidence>> | undefined;
  const sightings: DiscoveredArticleRow[] = [];
  async function phase<T>(operation: PlanRunRow["api_timings"][number]["operation"], execute: () => Promise<T>): Promise<T> {
    const begin = performance.now();
    emit(operation, "started");
    try {
      const result = await execute();
      const duration_ms = Math.round(performance.now() - begin);
      timings.push({ operation, duration_ms, status: "completed" });
      emit(operation, "completed", { duration_ms });
      return result;
    } catch (error) {
      const duration_ms = Math.round(performance.now() - begin);
      timings.push({ operation, duration_ms, status: "failed" });
      emit(operation, "failed", { duration_ms, failure_code: "PLANNER_PHASE_FAILED" });
      throw error;
    }
  }
  emit("plan", "started");
  try {
    const loaded = await Promise.all([
      phase("feed-health-before-fetch", () => prepareFeedHealthState(inputs, context.now)),
      readDiscoveredEvidence({
        root: inputs.root, discovered_files: inputs.settings.inputs.discovered_files, discovered_days: inputs.settings.inputs.discovered_days,
        registration: inputs.registrations.discovered_articles, now: context.now,
        lookback_days: inputs.harvest.config.discovered_articles.lookback_days, concurrency: inputs.harvest.config.harvest.concurrency,
        own_rows: memory.discoveries(),
      }),
      readExclusionEvidence({
        root: inputs.root, now: context.now, publishedWindowDays: inputs.clock_config.collect.published_window_days,
        settledFailureCodes: inputs.clock_config.collect.settled_failure_codes,
        publishedRegistration: inputs.registrations.published, itemHealthRegistration: inputs.registrations.item_health,
        publishedDays: inputs.settings.inputs.published_days, settledFailureDays: inputs.settings.inputs.settled_failure_days,
        concurrency: inputs.harvest.config.harvest.concurrency,
      }),
    ]);
    const initialHistory = loaded[0];
    history = initialHistory;
    discovery = loaded[1];
    // The measured initial capture already includes bounded in-memory evidence and its summary.
    // Selection performs a separate fresh capture; no membership/index cache crosses that boundary.
    const historyRows = initialHistory.rows;
    work = createRunHealth(context, sources, initialHistory.sources,
      { ...inputs.harvest.config.triage, clock: runtime.observation_clock ?? (() => new Date()) });
    const currentWork = work;
    const observations = createIngestObservations(currentWork.observe);
    const harvest = await phase("fetch", () => harvestFeeds(inputs.harvest, {
      writer: context.writer, correlation_id: context.correlation_id,
      max_future_hours: inputs.clock_config.collect.max_future_hours,
      exclusions: { ...loaded[2], published_window_days: inputs.clock_config.collect.published_window_days },
      feed_history: initialHistory.sources, observations, parser_pool: parserPool,
      parser_options: { activity: parserActivity, ...(runtime.signal === undefined ? {} : { signal: runtime.signal }) },
      overrides: request.freshness_hours === undefined ? {} : { freshness_hours: request.freshness_hours },
      clock: () => new Date(context.now), observation_clock: runtime.observation_clock ?? (() => new Date()),
      log: () => {},
      on_feed: (outcome, entries, checkedAt) => {
        currentWork.feed(outcome, entries, checkedAt);
        for (const entry of entries) {
          if (entry.link === null) continue;
          let identity;
          try { identity = canonicalizeUrl(entry.link); }
          catch { continue; }
          if (matchUrlExclusion(identity.canonical_url, inputs.harvest.config.harvest.url_exclusions) !== undefined) continue;
          sightings.push(DiscoveredArticleRowSchema.parse({
            url_key: identity.url_key, first_seen_at: checkedAt, date: checkedAt.slice(0, 10),
          }));
        }
      },
      on_article: currentWork.article,
      progress: (eventType, details) => runtime.progress?.({
        eventType, feed_id: details?.feed_id ?? null, output_count: details?.output_count ?? null,
      }),
    }, runtime.boundary));
    const discoveredRows = memory.rememberDiscoveries([...discovery.rows, ...sightings],
      requiredUtcDays(context.now, inputs.harvest.config.discovered_articles.lookback_days)[0]!);
    const saved = await rememberDiscoveries(discovery.rows, discoveredRows, context, {
      outputRoot: inputs.outputRoot, registryEntry: inputs.registrations.discovered_articles, ledgerSettings: inputs.ledgerSettings,
    });
    files.discovered_articles = saved.result;
    const parsed = stageStore(inputs).write("parsed", ParsedFeedBatchSchema, {
      batch_id: randomUUID(), config_sha256: operationConfigFingerprint(inputs, runtime), context,
      request: {
        ...(request.freshness_hours === undefined ? {} : { freshness_hours: request.freshness_hours }),
        ...(request.article_limit === null ? {} : { article_limit: request.article_limit }),
        shards: request.shards, partition_strategy: request.partition_strategy,
      },
      candidates: harvest.candidates,
      observations: Object.fromEntries(harvest.articles.filter(article => article.candidate !== null)
        .map(article => [article.candidate!.candidate_id, article.observation])),
      discovered: { availability: "available", rows: foldDiscoveryHistory([...discoveredRows, ...memory.discoveries()]) },
      evidence: Object.fromEntries(harvest.candidates.map(candidate => {
        const supplied = runtime.evidence?.get(candidate.candidate_id);
        return [candidate.candidate_id, resolveArticleEvidence(
          candidate, supplied, inputs.harvest.config.curate_articles.website_grouping.include_private_suffixes,
        )];
      })),
      history_rows: historyRows, history_days: history.days, work_rows: currentWork.rows(), exclusions: currentWork.exclusions(),
    });
    PlannerWorkEventSchema.parse({ stage: "parsed", payload: parsed });
    batches.parsed_batch_id = parsed.batch_id;
    selectionStartedAt = utcTimestamp(runtime.selection_clock ?? runtime.clock);
    const selectionClock = selectionStartedAt;
    const selection = await phase("select", () => executeSelection({ batch_id: parsed.batch_id }, inputs,
      { ...runtime, selection_clock: () => new Date(selectionClock) }, timing => { timings.push(timing); }));
    selected = selection.batch;
    PlannerWorkEventSchema.parse({ stage: "selected", payload: selected });
    batches.selection_batch_id = selected.batch_id;
    const chosen = selected;
    const settled = await Promise.allSettled([
      phase("partition", () => executePartition({
        batch_id: chosen.batch_id, strategy: request.partition_strategy, shards: request.shards,
      }, inputs, runtime)),
      (async () => {
        healthAttempted = true;
        files.feed_health_state = await recordFeedHealthState(chosen.health_rows, context, inputs);
        memory.rememberHealth(chosen.health_rows);
      })(),
    ]);
    const partitionResult = settled[0];
    if (partitionResult.status === "fulfilled") {
      partitioned = partitionResult.value.batch;
      PlannerWorkEventSchema.parse({ stage: "partitioned", payload: partitioned });
      batches.partition_batch_id = partitioned.batch_id;
    }
    if (partitioned !== undefined) {
      const persisted = await phase("persist", () => executePersistence({ batch_id: partitioned!.batch_id }, inputs, runtime));
      files.selected_articles = persisted.files;
      files.rejected_articles = persisted.rejected_files;
      artifact = persisted.artifact;
    }
    const rejected = settled.filter(result => result.status === "rejected");
    if (rejected.length) {
      failureCode = settled[1].status === "rejected" ? "FEED_HEALTH_WRITE_FAILED" : "PARTITION_FAILED";
      emit("plan", "failed", { failure_code: failureCode });
    }
  } catch (error) {
    failureCode = error instanceof PlanError ? error.code : "PLANNER_EXECUTION_FAILED";
    emit("plan", "failed", { failure_code: failureCode });
    if (work !== undefined && !healthAttempted) {
      healthAttempted = true;
      try {
        files.feed_health_state = await recordFeedHealthState(work.rows(), context, inputs);
        memory.rememberHealth(work.rows());
      } catch {
        failureCode = "FEED_HEALTH_WRITE_FAILED";
        emit("persist", "failed", { failure_code: failureCode });
      }
    }
    if (discovery !== undefined && files.discovered_articles === undefined) {
      try {
        const saved = await rememberDiscoveries(discovery.rows, sightings, context, {
          outputRoot: inputs.outputRoot, registryEntry: inputs.registrations.discovered_articles, ledgerSettings: inputs.ledgerSettings,
        });
        files.discovered_articles = saved.result;
      } catch {
        failureCode = "DISCOVERY_WRITE_FAILED";
        emit("persist", "failed", { failure_code: failureCode });
      }
    }
  } finally {
    if (runtime.parser_pool === undefined) parserPool.close();
    if (parseStarted !== undefined) timings.push({
      operation: "parse", duration_ms: Math.round((parseFinished ?? performance.now()) - parseStarted),
      status: parseFailed ? "failed" : "completed",
    });
  }
  const recorded = await recordPlanRun(inputs, context, {
    duration_ms: Math.round(performance.now() - started), status: failureCode === null ? "completed"
      : work !== undefined && work.rows().some(row => row.checked_at !== null) ? "partial" : "failed",
    failure_code: failureCode, selected_count: selected?.articles.length ?? 0,
    strategy: partitioned?.strategy ?? request.partition_strategy, dispatch_count: partitioned?.dispatch_count ?? 0,
    selected_articles_artifact: artifact, api_timings: timings,
    evaluated_at: selected?.evaluated_at ?? context.now,
    selection_started_at_utc: selectionStartedAt,
  });
  const row = recorded.row;
  files.plan_runs = recorded.files;
  if (failureCode === null) emit("plan", "completed", { output_count: row.selected_count, duration_ms: row.duration_ms });
  return { context, row, batches, files, selected: partitioned?.articles ?? selected?.articles ?? [] };
}
export type FeedPlanResult = Awaited<ReturnType<typeof runFeedPlan>>;
export function summarizePlan(result: FeedPlanResult) {
  return {
    ...result.row, planning_complete: result.row.status === "completed",
    correlation_id: result.context.correlation_id, batches: result.batches, files: result.files,
    selected_url_keys: result.selected.map(article => article.url_key),
    assignments: result.selected.map(article => ({
      url_key: article.url_key, editorial_rank: article.editorial_rank, worker_assignment: article.worker_assignment,
    })),
  };
}
import { canonicalizeUrl } from "./harvest-feeds/url-cleaner";
import { matchUrlExclusion } from "./harvest-feeds/url-exclusions";
import { utcTimestamp } from "./harvest-feeds/harvest-types";
