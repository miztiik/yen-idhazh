/** Execute one run through validated stage requests and retain honest failure output. */
import { randomUUID } from "node:crypto";
import { z } from "zod";
import type { FeedIngestEvent, PlannerArticleEvidence, SelectedFeedBatch } from "@idhazh/common-contracts";
import { SelectedFeedBatchSchema, PartitionedFeedBatchSchema } from "@idhazh/common-contracts";
import type { PersistLedgerResult } from "@idhazh/ledger-file-writer";
import type { harvestFeeds } from "./harvest-feeds/harvest-pool";
import { workPool } from "./harvest-feeds/harvest-pool";
import type { ArticleParserPool } from "./harvest-feeds/article-parser-pool";
import type { PlanInputs } from "./load-plan-inputs";
import type { ProgressRecord } from "./logging/progress-logger";
import { resolvePlanRequest, PlanError } from "./api/plan-request";
import { createStageLogger } from "./logging/structured-logger";
import { recordPlanRun } from "./record-plan-run";
import { createPlanApp } from "./api/server";
import { CollectionResponseSchema, CompletedCollectionSchema, CancelledCollectionSchema } from "./api/collection-contracts";
import { FetchResponseSchema, ParseResponseSchema } from "./api/document-response.schema";
import { SelectionResponseSchema, PartitionResponseSchema, PersistenceResponseSchema, StageErrorResponseSchema } from "./api/stage-response.schema";
import { FeedHealthStateUpdateResponseSchema } from "./api/feed-health-state.schema";
import { stageStore } from "./api/stage-store";
import { currentExecutionState } from "./api/document-state";
import { getCollection, collectionForRun, prepareCollectionContext, discardCollectionContext } from "./api/collection-operation";
import { resolveRunContext } from "./resolve-run-context";

export type PlanRuntime = {
  git_sha: string; run_number?: string; correlation_id?: string;
  attempt?: number; producer?: string; clock?: () => Date;
  selection_clock?: () => Date; captured_at?: string; observation_clock?: () => Date;
  boundary?: NonNullable<Parameters<typeof harvestFeeds>[2]>;
  log?: (event: FeedIngestEvent) => void; progress?: (record: ProgressRecord) => void;
  parser_pool?: ArticleParserPool; signal?: AbortSignal;
  evidence?: ReadonlyMap<string, PlannerArticleEvidence>;
  stage_fetch?: (request: Request) => Promise<Response>; stage_origin?: string;
};
export type FeedPlanResult = {
  context: import("./resolve-run-context").RunContext;
  row: import("@idhazh/common-contracts").PlanRunRow;
  batches: { parsed_batch_id?: string; selection_batch_id?: string; partition_batch_id?: string };
  files: Partial<Record<"discovered_articles" | "selected_articles" | "rejected_articles" | "feed_health_state" | "plan_runs", PersistLedgerResult>>;
  selected: SelectedFeedBatch["articles"];
};
export async function runFeedPlan(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime): Promise<FeedPlanResult> {
  const request = resolvePlanRequest(raw, inputs.harvest.config);
  if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled", "enabled");
  // Port zero asks the operating system for an unused loopback port for this invocation.
  if (runtime.stage_fetch === undefined) {
    const app = createPlanApp(inputs, { ...runtime, stage_fetch: request => fetch(request) });
    const server = Bun.serve({ hostname: inputs.settings.listener.hostname, port: 0, idleTimeout: 0, fetch: app.fetch });
    try { return await runFeedPlan(raw, inputs, { ...runtime, stage_fetch: request => fetch(request),
      stage_origin: `http://${server.hostname}:${server.port}` }); }
    finally { await server.stop(true); app.close(); }
  }
  const transport = runtime.stage_fetch;
  const collectionId = randomUUID();
  const started = performance.now();
  async function call<T>(path: string, body: unknown, schema: z.ZodType<T>, allowAborted = false): Promise<T> {
    const response = await transport(new Request(new URL(`/api/2026-10-20/${path}`, runtime.stage_origin ?? "http://localhost"), {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
      ...(runtime.signal === undefined || allowAborted ? {} : { signal: runtime.signal }),
    }));
    const value: unknown = await response.json();
    if (!response.ok) {
      const error = StageErrorResponseSchema.parse(value);
      throw new PlanError(error.code, error.issues.map(issue => issue.message).join("; "), error.issues[0]?.field);
    }
    return schema.parse(value);
  }
  const context = resolveRunContext(inputs.settings, runtime.git_sha, runtime.clock?.() ?? new Date(),
    runtime.run_number, runtime.correlation_id, runtime.captured_at, runtime.attempt, runtime.producer);
  prepareCollectionContext(inputs, collectionId, context);
  let begin: z.infer<typeof CollectionResponseSchema>;
  try { begin = await call("collections", { collection_id: collectionId, request: raw }, CollectionResponseSchema); }
  catch (error) {
    if (collectionForRun(inputs, context.run_id) !== undefined) throw error;
    const failureCode = error instanceof PlanError ? error.code : "PLANNER_EXECUTION_FAILED";
    createStageLogger(context, runtime.log)("plan", "failed", { failure_code: failureCode });
    const recorded = await recordPlanRun(inputs, context, {
      status: "failed", failure_code: failureCode, duration_ms: Math.round(performance.now() - started),
      selected_count: 0, dispatch_count: 0, strategy: request.partition_strategy,
      selected_articles_artifact: null, evaluated_at: context.now, selection_started_at_utc: null,
      api_timings: [{ operation: "feed-health-before-fetch",
        duration_ms: Math.round(performance.now() - started), status: "failed" }],
    });
    return { context, row: recorded.row, batches: {}, files: { plan_runs: recorded.files }, selected: [] };
  } finally { discardCollectionContext(inputs, collectionId); }
  const emit = createStageLogger(context, runtime.log);
  const files: Partial<Record<"discovered_articles" | "selected_articles" | "rejected_articles" | "feed_health_state" | "plan_runs", PersistLedgerResult>> = {};
  const batches: { parsed_batch_id?: string; selection_batch_id?: string; partition_batch_id?: string } = {};
  let selected: SelectedFeedBatch | undefined;
  let partitioned: z.infer<typeof PartitionedFeedBatchSchema> | undefined;
  let artifact: string | null = null;
  let failureCode: string | null = null;
  emit("plan", "started");
  try {
    const pool = workPool(inputs.harvest.config.harvest.concurrency);
    const processFeed = async (feedId: string) => {
      runtime.signal?.throwIfAborted();
      runtime.progress?.({ eventType: "FEED_FETCH_STARTED", feed_id: feedId, output_count: null });
      let fetched;
      try {
        fetched = await call("fetch", {
          request_id: randomUUID(), correlation_id: context.correlation_id,
          feed_id: feedId, fetch_item_type: "feed", collection_id: collectionId,
        }, FetchResponseSchema);
      } catch (error) {
        if (!(error instanceof PlanError) || !["FEED_RESTING", "FEED_RETIRED", "FEED_CHECK_BUSY"].includes(error.code)) throw error;
        emit("fetch", "completed", { feed_id: feedId, availability: error.code, output_count: 0 });
        runtime.progress?.({ eventType: "FEED_FETCH_COMPLETED", feed_id: feedId, output_count: 0 });
        return;
      }
      if (fetched.failure !== null) {
        runtime.progress?.({ eventType: "FEED_FETCH_COMPLETED", feed_id: feedId, output_count: 0 });
        return;
      }
      const parsed = await call("parse", {
        request_id: randomUUID(), fetch_request_id: fetched.fetch_request_id,
        article_id: fetched.article_id, correlation_id: context.correlation_id,
      }, ParseResponseSchema);
      if (parsed.fetch_item_type !== "feed") throw new PlanError("ARTIFACT_INVALID", "Feed parsing returned an article result");
      runtime.progress?.({ eventType: "FEED_FETCH_COMPLETED", feed_id: feedId, output_count: parsed.parsed_count });
      const articleOutcomes = await Promise.allSettled(parsed.offers.map(offer => pool(async () => {
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
        const parsedArticle = await call("parse", {
          request_id: randomUUID(), fetch_request_id: article.fetch_request_id,
          article_id: article.article_id, correlation_id: context.correlation_id,
        }, ParseResponseSchema);
        runtime.progress?.({ eventType: "ARTICLE_HARVEST_COMPLETED", feed_id: feedId, output_count: parsedArticle.parsed_count });
        if (parsedArticle.fetch_item_type === "article" && parsedArticle.warnings.length) {
          runtime.progress?.({ eventType: "ARTICLE_EXTRACTION_WARNING", feed_id: feedId, output_count: null });
        }
      })));
      const articleFailure = articleOutcomes.find(outcome => outcome.status === "rejected");
      if (articleFailure?.status === "rejected") throw articleFailure.reason;
    };
    // Settle all required work before selection or failure finalization.
    const outcomes = await Promise.allSettled(begin.feeds.map(feed => processFeed(feed)));
    const failed = outcomes.find(outcome => outcome.status === "rejected");
    if (failed?.status === "rejected") throw failed.reason;
    const collected = await call("collections/complete", { collection_id: collectionId }, CompletedCollectionSchema);
    files.discovered_articles = collected.discovered_articles;
    files.rejected_articles = collected.rejected_articles;
    batches.parsed_batch_id = collected.batch_id;
    const selection = await call("select-articles", { batch_id: collected.batch_id }, SelectionResponseSchema);
    batches.selection_batch_id = selection.batch_id;
    selected = stageStore(inputs).read("selected", selection.batch_id, SelectedFeedBatchSchema);
    let outputId = selected.batch_id;
    if (inputs.harvest.config.partition.enabled) {
      const partition = await call("partition-articles", {
        batch_id: selected.batch_id, strategy: request.partition_strategy, shards: request.shards,
      }, PartitionResponseSchema);
      batches.partition_batch_id = partition.batch_id;
      partitioned = stageStore(inputs).read("partitioned", partition.batch_id, PartitionedFeedBatchSchema);
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
    const outputFailure = outputs.find(outcome => outcome.status === "rejected");
    if (outputFailure?.status === "rejected") throw outputFailure.reason;
  } catch (error) {
    failureCode = error instanceof PlanError ? error.code : "PLANNER_EXECUTION_FAILED";
    emit("plan", "failed", { failure_code: failureCode });
    const collection = getCollection(inputs, collectionId);
    // A failed collection is not eligible for selection, but completed work remains inspectable.
    let partialBatchId: string | undefined;
    try {
      const cancelled = await call("collections/cancel", { collection_id: collectionId }, CancelledCollectionSchema, true);
      files.rejected_articles ??= cancelled.rejected_articles;
      partialBatchId = cancelled.batch_id;
    } catch {
      emit("plan", "failed", { failure_code: "COLLECTION_CANCEL_FAILED" });
    }
    if (partialBatchId !== undefined && files.feed_health_state === undefined
      && collection.state.work.rows().some(row => row.checked_at !== null)) {
      try {
        const health = await call("feed-health-state", { batch_id: partialBatchId, action: "record" },
          FeedHealthStateUpdateResponseSchema, true);
        if (health.files !== undefined) files.feed_health_state = health.files;
      } catch {
        emit("persist", "failed", { failure_code: "FEED_HEALTH_WRITE_FAILED" });
      }
    }
  }
  const state = await currentExecutionState(inputs, context.run_id);
  if (state?.kind === "document") {
    for (const family of ["discovered_articles", "rejected_articles"] as const) {
      const retained = [...(state.completed_files?.[family] ?? []), ...(files[family] === undefined ? [] : [files[family]])];
      const written = retained.flatMap(result => result.status === "written" ? result.files : []);
      if (written.length) files[family] = { status: "written", files: [...new Map(written.map(file => [file.path, file])).values()] };
      else if (retained.length) files[family] = { status: "empty", files: [] };
    }
  }
  const timings = state?.api_timings ?? [];
  const recorded = await recordPlanRun(inputs, context, {
    duration_ms: Math.round(performance.now() - started), status: failureCode === null ? "completed"
      : getCollection(inputs, collectionId).state.work.rows().some(row => row.checked_at !== null) ? "partial" : "failed",
    failure_code: failureCode, selected_count: selected?.articles.length ?? 0,
    strategy: partitioned?.strategy ?? (inputs.harvest.config.partition.enabled ? request.partition_strategy : "none"),
    dispatch_count: partitioned?.dispatch_count ?? 0,
    selected_articles_artifact: artifact, api_timings: timings,
    evaluated_at: selected?.evaluated_at ?? context.now,
    selection_started_at_utc: selected?.selection_started_at_utc ?? null,
  });
  files.plan_runs = recorded.files;
  if (failureCode === null) emit("plan", "completed", { output_count: recorded.row.selected_count, duration_ms: recorded.row.duration_ms });
  return { context, row: recorded.row, batches, files, selected: partitioned?.articles ?? selected?.articles ?? [] };
}
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
