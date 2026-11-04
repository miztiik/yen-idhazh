/** Execute one run through validated stage requests and retain honest failure output. */
import { z } from "zod";
import type { FeedIngestEvent, OperationLink, OperationMetadata, PlanApiTiming, PlanRunRow, PlannerArticleEvidence, PlannerFailure, PlannerHealthOutcome, SelectedArticleRow } from "@idhazh/common-contracts";
import { createRootContext, PLANNER_API_PREFIX, PlannerHealthOutcomeSchema, PlannerRunResponseSchema, writeTraceContext } from "@idhazh/common-contracts";
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
  FinalizeCollectionRequestSchema, FinalizedCollectionSchema, ReleasedCollectionSchema,
} from "./api/collection-contracts";
import { FetchResponseSchema, ParseResponseSchema } from "./api/document-response.schema";
import { SelectionResponseSchema, PartitionResponseSchema, PersistenceResponseSchema } from "./api/stage-response.schema";
import { FeedHealthStateUpdateResponseSchema } from "./api/feed-health-state.schema";
import { prepareCollectionContext, discardCollectionContext, ownsPreparedCollection } from "./api/collection-operation";
import { resolveRunContext } from "./resolve-run-context";
import { capturePlannerFailure, combinePlannerFailures, readPlannerResponseError, withPlannerFailure } from "./api/plan-failure";
import { plannerFailureOperation } from "./api/planner-failure-operation";
import { operationLink, operationMetadata, runtimeOperation } from "./api/operation-context";

const documentPools = new WeakMap<PlanInputs, ReturnType<typeof workPool>>();
export type PlanRuntime = Partial<OperationMetadata> & {
  git_sha: string; run_number?: string;
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
  files: Partial<Record<"discovered_articles" | "selected_articles" | "rejected_articles" | "feed_health_state" | "plan_runs", PersistLedgerResult>>;
  selected: SelectedArticleRow[];
  health: PlannerHealthOutcome;
  failure?: PlannerFailure | null;
};
export async function runFeedPlan(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime): Promise<FeedPlanResult> {
  const request = resolvePlanRequest(raw, inputs.harvest.config);
  if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled", "enabled");
  const context = resolveRunContext(inputs.settings, runtime.git_sha, runtime.clock?.() ?? new Date(),
    runtime.run_number, runtimeOperation(runtime) ?? createRootContext(), runtime.captured_at, runtime.attempt, runtime.producer);
  const capture = { operation: "plan" as const, execution: context, limits: inputs.settings.diagnostics.failure };
  const emit = createStageLogger(context, inputs.event_source, runtime.log);
  const cleanup: { execute: () => unknown | Promise<unknown> }[] = [];
  let result: FeedPlanResult | undefined;
  let primary: PlanError | undefined;
  emit("plan", "started");
  try {
    let stageOrigin = runtime.stage_origin;
    if (stageOrigin === undefined) {
      const app = createPlanApp(inputs, runtime);
      cleanup.push({ execute: () => app.close() });
      // Port zero asks the operating system for an unused loopback port for this invocation.
      const server = Bun.serve({ hostname: inputs.settings.listener.hostname, port: 0, idleTimeout: 0, fetch: app.fetch });
      cleanup.unshift({ execute: () => server.stop(true) });
      stageOrigin = `http://${server.hostname}:${server.port}`;
    }
    result = await runPlanStages(raw, request, inputs, { ...runtime, stage_origin: stageOrigin }, context);
  } catch (error) { primary = withPlannerFailure(error, capture); }
  let failure = result?.failure ?? primary?.failure ?? null;
  for (const step of cleanup) {
    try { await step.execute(); }
    catch (error) {
      const current = capturePlannerFailure(error, { ...capture, operation: "listener-close" });
      failure = failure === null ? current : combinePlannerFailures(failure, current, capture.limits);
    }
  }
  if (result === undefined) {
    emit("plan", "failed", { failure_code: primary?.code ?? "PLAN_FAILED", failure });
    throw new PlanError(primary?.code ?? "PLAN_FAILED", "Planner request did not produce an outcome",
      primary?.field, { cause: primary, failure });
  }
  result.failure = failure;
  emit("plan", result.row.status === "completed" && failure === null ? "completed" : "failed", {
    output_count: result.row.selected_count, duration_ms: result.row.duration_ms,
    ...(result.row.status === "completed" && failure === null ? {} : {
      failure_code: result.row.failure_code ?? "PLAN_FAILED", failure,
    }),
  });
  return result;
}
async function runPlanStages(
  raw: unknown, request: ReturnType<typeof resolvePlanRequest>, inputs: PlanInputs, runtime: PlanRuntime,
  context: import("./resolve-run-context").RunContext,
): Promise<FeedPlanResult> {
  const traceId = context.traceId;
  const started = performance.now();
  async function call<T>(path: string, body: unknown, schema: z.ZodType<T>, allowAborted = false): Promise<T> {
    const capture = { operation: plannerFailureOperation(path), execution: {
      traceId, spanId: null, run_id: context.run_id, attempt: context.writer.attempt, git_sha: context.writer.git_sha,
    }, limits: inputs.settings.diagnostics.failure };
    try {
      const response = await fetch(new Request(new URL(`${PLANNER_API_PREFIX}/${path}`, runtime.stage_origin), {
        method: "POST", headers: { "content-type": "application/json", ...writeTraceContext(operationMetadata(context)) },
        body: JSON.stringify(body),
        ...(runtime.signal === undefined || allowAborted ? {} : { signal: runtime.signal }),
      }));
      const value: unknown = await response.json();
      if (!response.ok) throw readPlannerResponseError(value, capture);
      return schema.parse(value);
    } catch (error) {
      throw withPlannerFailure(error, capture);
    }
  }
  let owned = false;
  let result: FeedPlanResult | undefined;
  let primary: PlanError | undefined;
  try {
    prepareCollectionContext(inputs, context);
    let begin: z.infer<typeof CollectionResponseSchema> | undefined;
    let startupFailure: PlanError | undefined;
    try {
      begin = await call("collections", { request: raw }, CollectionResponseSchema);
      if (begin.traceId !== traceId || begin.context.run_id !== context.run_id
        || begin.context.writer.attempt !== context.writer.attempt) {
        throw new PlanError("ARTIFACT_INVALID", "Collection startup differs from its captured execution");
      }
    } catch (error) {
      if (error instanceof PlanError && error.code === "REQUEST_CONFLICT") throw error;
      let existing: z.infer<typeof CollectionExistsResponseSchema> | undefined;
      let startupError = error;
      try {
        existing = await call("collections/exists", { traceId }, CollectionExistsResponseSchema, true);
        if (existing.traceId !== traceId) throw new PlanError("ARTIFACT_INVALID", "Collection lookup identity differs");
      } catch (lookupError) {
        startupError = new AggregateError([
          error, new PlanError("PLAN_FAILED", "Collection startup outcome could not be checked", null, { cause: lookupError }),
        ], "Collection startup and outcome lookup failed");
        if (!ownsPreparedCollection(inputs, context)) throw startupError;
      }
      if (ownsPreparedCollection(inputs, context)) {
        owned = true;
        startupFailure = withPlannerFailure(startupError, {
          operation: "collection-start", execution: context, limits: inputs.settings.diagnostics.failure,
        });
      } else if (existing?.exists) {
        throw new PlanError("REQUEST_CONFLICT", "Collection startup belongs to another invocation", "traceId", { cause: error });
      } else {
        const failureCode = startupError instanceof PlanError ? startupError.code : "PLANNER_EXECUTION_FAILED";
        const failure = capturePlannerFailure(startupError, {
          operation: "collection-start", execution: context, limits: inputs.settings.diagnostics.failure,
        });
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
        return result = { context, row: recorded.row, files: { plan_runs: recorded.files }, selected: [], health: null, failure };
      }
    }
    if (!ownsPreparedCollection(inputs, context)) {
      throw new PlanError("REQUEST_CONFLICT", "Collection startup belongs to another invocation", "traceId");
    }
    owned = true;
    const emit = createStageLogger(context, inputs.event_source, runtime.log);
    const files: Partial<Record<"discovered_articles" | "selected_articles" | "rejected_articles" | "feed_health_state" | "plan_runs", PersistLedgerResult>> = {};
    let selected: z.infer<typeof SelectionResponseSchema> | undefined;
    let completedInput: OperationLink | undefined;
    let selectionMetrics: PlanRunRow["selection_metrics"] = null;
    let partitioned: z.infer<typeof PartitionResponseSchema> | undefined;
    let artifact: string | null = null;
    let failureCode: string | null = null;
    let failure: PlannerFailure | null = null;
    const collectionStarted = performance.now();
    let collectionFinished = false;
    let collectionTiming: Pick<PlanApiTiming, "duration_ms" | "status"> | undefined;
    emit("fetch", "started", { scope: "plan" });
    try {
      if (startupFailure !== undefined) throw startupFailure;
      if (begin === undefined) throw new Error("Collection startup did not produce its result");
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
              feed_id: feedId, fetch_item_type: "feed", traceId,
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
            links: [operationLink(fetched)],
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
              fetch_item_type: "article", links: [operationLink(parsed)], offer_id: offer.offer_id,
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
            links: [operationLink(article)],
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
      const collected = await call("collections/complete", { traceId }, CompletedCollectionSchema);
      completedInput = operationLink(collected);
      collectionFinished = true;
      const collectionDuration = Math.round(performance.now() - collectionStarted);
      collectionTiming = { duration_ms: collectionDuration, status: "completed" };
      emit("fetch", "completed", { scope: "plan", duration_ms: collectionDuration });
      files.discovered_articles = collected.discovered_articles;
      files.rejected_articles = collected.rejected_articles;
      const selection = await call("select-articles", { links: [operationLink(collected)] }, SelectionResponseSchema);
      selected = selection;
      selectionMetrics = summarizeSelectionMetrics(selection.articles,
        inputs.harvest.config.curate_articles.website_grouping.include_private_suffixes);
      let output = operationLink(selected);
      if (inputs.harvest.config.partition.enabled) {
        const partition = await call("partition-articles", {
          links: [operationLink(selected)], strategy: request.partition_strategy, shards: request.shards,
        }, PartitionResponseSchema);
        partitioned = partition;
        output = operationLink(partition);
      }
      const outputs = await Promise.allSettled([
        call("feed-health-state", { links: [output], action: "record" }, FeedHealthStateUpdateResponseSchema),
        call("persist-selected-articles", { links: [output] }, PersistenceResponseSchema),
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
      // A failed collection is not eligible for selection, but completed work remains inspectable.
      let partial: OperationLink | undefined;
      let hasPartialWork = false;
      try {
        const cancelled = await call("collections/cancel", { traceId }, CancelledCollectionSchema, true);
        files.rejected_articles ??= cancelled.rejected_articles;
        partial = operationLink(cancelled);
        hasPartialWork = cancelled.has_work;
      } catch (error) {
        failure = combinePlannerFailures(failure, capturePlannerFailure(error, {
          operation: "collection-cancel", execution: context, limits: inputs.settings.diagnostics.failure,
        }), inputs.settings.diagnostics.failure);
      }
      if (partial !== undefined && hasPartialWork && files.feed_health_state === undefined) {
        try {
          const health = await call("feed-health-state", { links: [partial], action: "record" },
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
      traceId, failure_code: failureCode, failure, collection_timing: collectionTiming,
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
    if (outcome.traceId !== traceId) throw new PlanError("ARTIFACT_INVALID", "Final outcome belongs to another collection");
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
    let health: PlannerHealthOutcome = null;
    const reportInput = selected === undefined ? completedInput : operationLink(selected);
    if (reportInput !== undefined) {
      try {
        health = PlannerHealthOutcomeSchema.parse(await call("feed-health-state", {
          links: [reportInput], action: "summarize",
        }, FeedHealthStateUpdateResponseSchema, true));
      } catch (error) {
        const current = capturePlannerFailure(error, {
          operation: "feed-health-summary", execution: context, limits: inputs.settings.diagnostics.failure,
        });
        health = { status: "failed", failure: current };
        failure = failure === null ? current : combinePlannerFailures(failure, current, inputs.settings.diagnostics.failure);
      }
    }
    return result = { context, row: recorded.row, files, selected: partitioned?.articles ?? selected?.articles ?? [], health, failure };
  } catch (error) {
    primary = withPlannerFailure(error, { operation: "plan", execution: context, limits: inputs.settings.diagnostics.failure });
    throw primary;
  } finally {
    discardCollectionContext(inputs, context);
    if (owned && ownsPreparedCollection(inputs, context)) {
      try {
        const released = await call("collections/release", {
          run_id: context.run_id, attempt: context.writer.attempt,
        }, ReleasedCollectionSchema, true);
        if (released.run_id !== context.run_id || released.attempt !== context.writer.attempt) {
          throw new PlanError("ARTIFACT_INVALID", "Planner released a different collection execution");
        }
      } catch (error) {
        const capture = { operation: "collection-release" as const, execution: context, limits: inputs.settings.diagnostics.failure };
        if (result === undefined) {
          throw withPlannerFailure(primary === undefined ? error : new AggregateError([
            primary, error,
          ], "Planner execution and collection release failed"), capture);
        }
        const current = capturePlannerFailure(error, capture);
        result.failure = result.failure == null ? current : combinePlannerFailures(result.failure, current, capture.limits);
      }
    }
  }
}
export function summarizePlan(result: FeedPlanResult) {
  return PlannerRunResponseSchema.parse({
    ...result.row, planning_complete: result.row.status === "completed",
    failure: result.failure ?? null,
    health: result.health,
    traceId: result.context.traceId, files: result.files,
    selected_url_keys: result.selected.map(article => article.url_key),
    assignments: result.selected.map(article => ({
      url_key: article.url_key, editorial_rank: article.editorial_rank, worker_assignment: article.worker_assignment,
    })),
  });
}
