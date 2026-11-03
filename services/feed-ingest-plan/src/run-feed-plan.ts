/** Execute one run through validated stage requests and retain honest failure output. */
import { randomUUID } from "node:crypto";
import { z } from "zod";
import type { FeedIngestEvent, PlanApiTiming, PlanRunRow, PlannerArticleEvidence, PlannerFailure, SelectedArticleRow } from "@idhazh/common-contracts";
import { PLANNER_API_PREFIX } from "@idhazh/common-contracts";
import type { PersistLedgerResult } from "@idhazh/ledger-file-writer";
import type { harvestFeeds } from "./harvest-feeds/harvest-pool";
import { workPool } from "./harvest-feeds/harvest-pool";
import type { ArticleParserPool } from "./harvest-feeds/article-parser-pool";
import type { PlanInputs } from "./load-plan-inputs";
import type { ProgressRecord } from "./logging/progress-logger";
import { resolvePlanRequest, PlanError } from "./api/plan-request";
import { createStageLogger } from "./logging/structured-logger";
import { recordPlanRun } from "./record-plan-run";
import { summarizeSelectionMetrics } from "./summarize-selection-metrics";
import { createPlanApp } from "./api/server";
import {
  CollectionExistsResponseSchema, CollectionResponseSchema, CompletedCollectionSchema, CancelledCollectionSchema,
  FinalizeCollectionRequestSchema, FinalizedCollectionSchema,
} from "./api/collection-contracts";
import { FetchResponseSchema, ParseResponseSchema } from "./api/document-response.schema";
import { SelectionResponseSchema, PartitionResponseSchema, PersistenceResponseSchema } from "./api/stage-response.schema";
import { FeedHealthStateUpdateResponseSchema } from "./api/feed-health-state.schema";
import { prepareCollectionContext, discardCollectionContext } from "./api/collection-operation";
import { resolveRunContext } from "./resolve-run-context";
import { capturePlannerFailure, combinePlannerFailures, readPlannerResponseError, withPlannerFailure } from "./api/plan-failure";
import { plannerFailureOperation } from "./api/planner-failure-operation";
import { retainFailureThroughCleanup } from "./api/retain-failure-through-cleanup";

const documentPools = new WeakMap<PlanInputs, ReturnType<typeof workPool>>();
export type PlanRuntime = {
  git_sha: string; run_number?: string; correlation_id?: string;
  attempt?: number; producer?: string; clock?: () => Date;
  selection_clock?: () => Date; captured_at?: string; observation_clock?: () => Date;
  boundary?: NonNullable<Parameters<typeof harvestFeeds>[2]>;
  log?: (event: FeedIngestEvent) => void; progress?: (record: ProgressRecord) => void;
  parser_pool?: ArticleParserPool; signal?: AbortSignal;
  evidence?: ReadonlyMap<string, PlannerArticleEvidence>;
  stage_origin?: string;
};
export type FeedPlanResult = {
  context: import("./resolve-run-context").RunContext;
  row: import("@idhazh/common-contracts").PlanRunRow;
  batches: { parsed_batch_id?: string; selection_batch_id?: string; partition_batch_id?: string };
  files: Partial<Record<"discovered_articles" | "selected_articles" | "rejected_articles" | "feed_health_state" | "plan_runs", PersistLedgerResult>>;
  selected: SelectedArticleRow[];
  failure?: PlannerFailure | null;
};
export async function runFeedPlan(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime): Promise<FeedPlanResult> {
  const request = resolvePlanRequest(raw, inputs.harvest.config);
  if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled", "enabled");
  // Port zero asks the operating system for an unused loopback port for this invocation.
  if (runtime.stage_origin === undefined) {
    const app = createPlanApp(inputs, runtime);
    const server = Bun.serve({ hostname: inputs.settings.listener.hostname, port: 0, idleTimeout: 0, fetch: app.fetch });
    let result: FeedPlanResult | undefined;
    try {
      result = await runFeedPlan(raw, inputs, { ...runtime,
        stage_origin: `http://${server.hostname}:${server.port}` });
      await server.stop(true);
      await app.close();
      return result;
    } catch (error) {
      const original = result?.failure == null ? error : new AggregateError([
        new PlanError(result.row.failure_code ?? "PLAN_FAILED", "Planner execution failed", null, { failure: result.failure }),
        withPlannerFailure(error, { operation: "listener-close", execution: result.context, limits: inputs.settings.diagnostics.failure }),
      ], "Planner execution and listener cleanup failed");
      throw await retainFailureThroughCleanup(original, {
        operation: "plan", limits: inputs.settings.diagnostics.failure,
        ...(result === undefined ? {} : { execution: result.context }),
      }, [
        { operation: "listener-close", execute: () => server.stop(true) },
        { operation: "listener-close", execute: () => app.close() },
      ]);
    }
  }
  const collectionId = randomUUID();
  const started = performance.now();
  async function call<T>(path: string, body: unknown, schema: z.ZodType<T>, allowAborted = false): Promise<T> {
    const capture = { operation: plannerFailureOperation(path), execution: context, limits: inputs.settings.diagnostics.failure };
    try {
      const response = await fetch(new Request(new URL(`${PLANNER_API_PREFIX}/${path}`, runtime.stage_origin), {
        method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
        ...(runtime.signal === undefined || allowAborted ? {} : { signal: runtime.signal }),
      }));
      const value: unknown = await response.json();
      if (!response.ok) throw readPlannerResponseError(value, capture);
      return schema.parse(value);
    } catch (error) {
      throw withPlannerFailure(error, capture);
    }
  }
  const context = resolveRunContext(inputs.settings, runtime.git_sha, runtime.clock?.() ?? new Date(),
    runtime.run_number, runtime.correlation_id, runtime.captured_at, runtime.attempt, runtime.producer);
  prepareCollectionContext(inputs, collectionId, context);
  let begin: z.infer<typeof CollectionResponseSchema>;
  try { begin = await call("collections", { collection_id: collectionId, request: raw }, CollectionResponseSchema); }
  catch (error) {
    let existing: z.infer<typeof CollectionExistsResponseSchema>;
    try {
      existing = await call("collections/exists", { collection_id: collectionId }, CollectionExistsResponseSchema, true);
    } catch (lookupError) {
      throw new AggregateError([error, lookupError], "Collection startup outcome could not be checked");
    }
    if (existing.collection_id !== collectionId) throw new PlanError("ARTIFACT_INVALID", "Collection lookup identity differs");
    if (existing.exists) throw error;
    const failureCode = error instanceof PlanError ? error.code : "PLANNER_EXECUTION_FAILED";
    const failure = capturePlannerFailure(error, {
      operation: "collection-start", execution: context, limits: inputs.settings.diagnostics.failure,
    });
    createStageLogger(context, runtime.log)("plan", "failed", { failure_code: failureCode, failure });
    let recorded: Awaited<ReturnType<typeof recordPlanRun>>;
    try { recorded = await recordPlanRun(inputs, context, {
      status: "failed", failure_code: failureCode, duration_ms: Math.round(performance.now() - started),
      selected_count: 0, selection_metrics: null, dispatch_count: 0, strategy: request.partition_strategy,
      selected_articles_artifact: null, evaluated_at: context.now, selection_started_at_utc: null,
      api_timings: [{ operation: "feed-health-before-fetch",
        duration_ms: Math.round(performance.now() - started), status: "failed" }],
    }); } catch (recordingError) {
      throw withPlannerFailure(new AggregateError([
        new PlanError(failureCode, "Collection startup failed", null, { failure }),
        withPlannerFailure(recordingError, { operation: "record-run", execution: context, limits: inputs.settings.diagnostics.failure }),
      ], "Collection startup and outcome recording failed"), { operation: "collection-start", execution: context });
    }
    return { context, row: recorded.row, batches: {}, files: { plan_runs: recorded.files }, selected: [], failure };
  } finally { discardCollectionContext(inputs, collectionId); }
  {
    const emit = createStageLogger(context, runtime.log);
    const files: Partial<Record<"discovered_articles" | "selected_articles" | "rejected_articles" | "feed_health_state" | "plan_runs", PersistLedgerResult>> = {};
    const batches: { parsed_batch_id?: string; selection_batch_id?: string; partition_batch_id?: string } = {};
    let selected: z.infer<typeof SelectionResponseSchema> | undefined;
    let selectionMetrics: PlanRunRow["selection_metrics"] = null;
    let partitioned: z.infer<typeof PartitionResponseSchema> | undefined;
    let artifact: string | null = null;
    let failureCode: string | null = null;
    let failure: PlannerFailure | null = null;
    const collectionStarted = performance.now();
    let collectionFinished = false;
    let collectionTiming: Pick<PlanApiTiming, "duration_ms" | "status"> | undefined;
    emit("plan", "started");
    emit("fetch", "started", { scope: "plan" });
    try {
      const feedPool = workPool(inputs.harvest.config.harvest.concurrency);
      const articlePool = workPool(inputs.harvest.config.harvest.concurrency + inputs.settings.listener.parser_concurrency);
      const parsePool = workPool(inputs.settings.listener.parser_concurrency);
      let documentPool = documentPools.get(inputs);
      if (documentPool === undefined) {
        documentPool = workPool(inputs.settings.listener.max_stage_batches);
        documentPools.set(inputs, documentPool);
      }
      const boundedDocuments = documentPool;
      const processFeed = async (feedId: string) => {
        runtime.signal?.throwIfAborted();
        runtime.progress?.({ eventType: "FEED_FETCH_STARTED", feed_id: feedId, output_count: null });
        const parsed = await boundedDocuments(async () => {
          let fetched;
          try {
            fetched = await call("fetch", {
              request_id: randomUUID(), correlation_id: context.correlation_id,
              feed_id: feedId, fetch_item_type: "feed", collection_id: collectionId,
            }, FetchResponseSchema);
          } catch (error) {
            if (!(error instanceof PlanError) || !["FEED_RESTING", "FEED_RETIRED"].includes(error.code)) throw error;
            emit("fetch", "completed", { feed_id: feedId, availability: error.code, output_count: 0 });
            return null;
          }
          if (fetched.failure !== null) {
            return null;
          }
          return parsePool(() => call("parse", {
            request_id: randomUUID(), fetch_request_id: fetched.fetch_request_id,
            article_id: fetched.article_id, correlation_id: context.correlation_id,
          }, ParseResponseSchema));
        });
        if (parsed === null) {
          runtime.progress?.({ eventType: "FEED_FETCH_COMPLETED", feed_id: feedId, output_count: 0 });
          return;
        }
        if (parsed.fetch_item_type !== "feed") throw new PlanError("ARTIFACT_INVALID", "Feed parsing returned an article result");
        runtime.progress?.({ eventType: "FEED_FETCH_COMPLETED", feed_id: feedId, output_count: parsed.parsed_count });
        const articleOutcomes = await Promise.allSettled(parsed.offers.map(offer => articlePool(() => boundedDocuments(async () => {
          runtime.signal?.throwIfAborted();
          runtime.progress?.({ eventType: "ARTICLE_HARVEST_STARTED", feed_id: feedId, output_count: null });
          let article;
          try {
            article = await call("fetch", {
              request_id: randomUUID(), correlation_id: context.correlation_id,
              feed_id: feedId, fetch_item_type: "article", batch_id: parsed.batch_id, offer_id: offer.offer_id,
            }, FetchResponseSchema);
          } catch (error) {
            if (error instanceof PlanError && error.code === "ARTICLE_EXCLUDED") {
              runtime.progress?.({ eventType: "ARTICLE_HARVEST_COMPLETED", feed_id: feedId, output_count: 0 });
              return;
            }
            throw error;
          }
          if (article.failure !== null) {
            runtime.progress?.({ eventType: "ARTICLE_HARVEST_COMPLETED", feed_id: feedId, output_count: 0 });
            return;
          }
          const parsedArticle = await parsePool(() => call("parse", {
            request_id: randomUUID(), fetch_request_id: article.fetch_request_id,
            article_id: article.article_id, correlation_id: context.correlation_id,
          }, ParseResponseSchema));
          runtime.progress?.({ eventType: "ARTICLE_HARVEST_COMPLETED", feed_id: feedId, output_count: parsedArticle.parsed_count });
          if (parsedArticle.fetch_item_type === "article" && parsedArticle.warnings.length) {
            runtime.progress?.({ eventType: "ARTICLE_EXTRACTION_WARNING", feed_id: feedId, output_count: null });
          }
        }))));
        const articleFailure = articleOutcomes.find(outcome => outcome.status === "rejected");
        if (articleFailure?.status === "rejected") throw articleFailure.reason;
      };
      // Settle all required work before selection or failure finalization.
      const outcomes = await Promise.allSettled(begin.feeds.map(feed => feedPool(() => processFeed(feed))));
      const failed = outcomes.find(outcome => outcome.status === "rejected");
      if (failed?.status === "rejected") throw failed.reason;
      const collected = await call("collections/complete", { collection_id: collectionId }, CompletedCollectionSchema);
      collectionFinished = true;
      const collectionDuration = Math.round(performance.now() - collectionStarted);
      collectionTiming = { duration_ms: collectionDuration, status: "completed" };
      emit("fetch", "completed", { scope: "plan", duration_ms: collectionDuration });
      files.discovered_articles = collected.discovered_articles;
      files.rejected_articles = collected.rejected_articles;
      batches.parsed_batch_id = collected.batch_id;
      const selection = await call("select-articles", { batch_id: collected.batch_id }, SelectionResponseSchema);
      batches.selection_batch_id = selection.batch_id;
      selected = selection;
      selectionMetrics = summarizeSelectionMetrics(selection.articles,
        inputs.harvest.config.curate_articles.website_grouping.include_private_suffixes);
      let outputId = selected.batch_id;
      if (inputs.harvest.config.partition.enabled) {
        const partition = await call("partition-articles", {
          batch_id: selected.batch_id, strategy: request.partition_strategy, shards: request.shards,
        }, PartitionResponseSchema);
        batches.partition_batch_id = partition.batch_id;
        partitioned = partition;
        outputId = partition.batch_id;
      }
      const outputs = await Promise.allSettled([
        call("feed-health-state", { batch_id: outputId, action: "record" }, FeedHealthStateUpdateResponseSchema),
        call("persist-selected-articles", { batch_id: outputId }, PersistenceResponseSchema),
      ]);
      if (outputs[0].status === "fulfilled" && outputs[0].value.files !== undefined) files.feed_health_state = outputs[0].value.files;
      if (outputs[1].status === "fulfilled") {
        files.selected_articles = outputs[1].value.files;
        const harvested = files.rejected_articles.files;
        const rejected = [...harvested, ...outputs[1].value.rejected_files.files];
        files.rejected_articles = rejected.length ? { status: "written", files: rejected } : { status: "empty", files: [] };
        artifact = outputs[1].value.artifact;
      }
      const outputFailures = outputs.flatMap(outcome => outcome.status === "rejected" ? [outcome.reason] : []);
      if (outputFailures.length) throw outputFailures.length === 1 ? outputFailures[0]
        : new AggregateError(outputFailures, "Health and selected output failed");
    } catch (error) {
      failureCode = error instanceof PlanError ? error.code : "PLANNER_EXECUTION_FAILED";
      failure = capturePlannerFailure(error, { operation: "plan", execution: context, limits: inputs.settings.diagnostics.failure });
      if (!collectionFinished) {
        const collectionDuration = Math.round(performance.now() - collectionStarted);
        collectionTiming = { duration_ms: collectionDuration, status: "failed" };
        emit("fetch", "failed", { scope: "plan", duration_ms: collectionDuration, failure_code: failureCode, failure });
      }
      emit("plan", "failed", { failure_code: failureCode, failure });
      // A failed collection is not eligible for selection, but completed work remains inspectable.
      let partialBatchId: string | undefined;
      let hasPartialWork = false;
      try {
        const cancelled = await call("collections/cancel", { collection_id: collectionId }, CancelledCollectionSchema, true);
        files.rejected_articles ??= cancelled.rejected_articles;
        partialBatchId = cancelled.batch_id;
        hasPartialWork = cancelled.has_work;
      } catch (error) {
        failure = combinePlannerFailures(failure, capturePlannerFailure(error, {
          operation: "collection-cancel", execution: context, limits: inputs.settings.diagnostics.failure,
        }), inputs.settings.diagnostics.failure);
        emit("plan", "failed", { failure_code: "COLLECTION_CANCEL_FAILED", failure });
      }
      if (partialBatchId !== undefined && hasPartialWork && files.feed_health_state === undefined) {
        try {
          const health = await call("feed-health-state", { batch_id: partialBatchId, action: "record" },
            FeedHealthStateUpdateResponseSchema, true);
          if (health.files !== undefined) files.feed_health_state = health.files;
        } catch (error) {
          failure = combinePlannerFailures(failure, capturePlannerFailure(error, {
            operation: "feed-health-state", execution: context, limits: inputs.settings.diagnostics.failure,
          }), inputs.settings.diagnostics.failure);
          emit("persist", "failed", { failure_code: "FEED_HEALTH_WRITE_FAILED", failure });
        }
      }
    }
    if (collectionTiming === undefined) throw new Error("Collection execution did not produce its measured timing");
    const finalization = FinalizeCollectionRequestSchema.parse({
      collection_id: collectionId, failure_code: failureCode, failure, collection_timing: collectionTiming,
    });
    let outcome: z.infer<typeof FinalizedCollectionSchema>;
    try { outcome = await call("collections/finalize", finalization, FinalizedCollectionSchema, true); }
    catch (error) {
      throw withPlannerFailure(failure === null ? error : new AggregateError([
        new PlanError(failureCode ?? "PLAN_FAILED", "Planner execution failed", null, { failure }), error,
      ], "Planner execution and final accounting failed"), {
        operation: "collection-finalize", execution: context, limits: inputs.settings.diagnostics.failure,
      });
    }
    if (outcome.collection_id !== collectionId) throw new PlanError("ARTIFACT_INVALID", "Final outcome belongs to another collection");
    if (failureCode === null && outcome.failure_code !== null) {
      emit("plan", "failed", { failure_code: outcome.failure_code, failure: outcome.failure });
    }
    failureCode = outcome.failure_code;
    failure = outcome.failure ?? failure;
    let recorded: Awaited<ReturnType<typeof recordPlanRun>>;
    try { recorded = await recordPlanRun(inputs, context, {
      duration_ms: Math.round(performance.now() - started), status: outcome.status,
      failure_code: failureCode, selected_count: selected?.articles.length ?? 0,
      selection_metrics: selectionMetrics,
      strategy: partitioned?.strategy ?? (inputs.harvest.config.partition.enabled ? request.partition_strategy : "none"),
      dispatch_count: partitioned?.dispatch_count ?? 0,
      selected_articles_artifact: artifact, api_timings: outcome.api_timings,
      evaluated_at: selected?.evaluated_at ?? context.now,
      selection_started_at_utc: selected?.selection_started_at_utc ?? null,
    }); } catch (error) {
      throw withPlannerFailure(failure === null ? error : new AggregateError([
        new PlanError(failureCode ?? "PLAN_FAILED", "Planner execution failed", null, { failure }),
        withPlannerFailure(error, { operation: "record-run", execution: context, limits: inputs.settings.diagnostics.failure }),
      ], "Planner execution and outcome recording failed"), {
        operation: "record-run", execution: context, limits: inputs.settings.diagnostics.failure,
      });
    }
    files.plan_runs = recorded.files;
    if (failureCode === null) emit("plan", "completed", { output_count: recorded.row.selected_count, duration_ms: recorded.row.duration_ms });
    return { context, row: recorded.row, batches, files, selected: partitioned?.articles ?? selected?.articles ?? [], failure };
  }
}
export function summarizePlan(result: FeedPlanResult) {
  return {
    ...result.row, planning_complete: result.row.status === "completed",
    failure: result.failure ?? null,
    correlation_id: result.context.correlation_id, batches: result.batches, files: result.files,
    selected_url_keys: result.selected.map(article => article.url_key),
    assignments: result.selected.map(article => ({
      url_key: article.url_key, editorial_rank: article.editorial_rank, worker_assignment: article.worker_assignment,
    })),
  };
}
