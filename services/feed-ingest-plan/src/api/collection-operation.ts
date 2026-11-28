/** Own one complete collection and refuse selection before all its work settles. */
import { createChildContext, PlanApiTimingSchema } from "@idhazh/common-contracts";
import type { OperationLink, PlannerFailureOperation, PlannerFeedOffer, RejectedArticleRow, SelectedFeedBatch } from "@idhazh/common-contracts";
import type { HarvestArticleResult } from "../harvest-feeds/harvest-types";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { resolveRunContext } from "../resolve-run-context";
import type { RunContext } from "../resolve-run-context";
import { resolvePlanRequest, PlanError } from "./plan-request";
import {
  BeginCollectionSchema, CollectionReferenceSchema, CollectionResponseSchema, FinalizeCollectionRequestSchema, FinalizedCollectionSchema,
  ReleaseCollectionRequestSchema,
} from "./collection-contracts";
import { captureDocumentContext, commandContext, operationLink, operationMetadata, stageContext } from "./operation-context";
import { documentState } from "./document-state";
import type { DocumentState } from "./document-state";
import { stageStore } from "./stage-store";
import type { ExecutionOwnership } from "./stage-store";
import { rememberDiscoveries } from "../read-ledger-history/read-discovered-evidence";
import { summarizeFeedAvailability } from "../availability/feed-availability-view";
import { utcTimestamp } from "../harvest-feeds/harvest-types";
import { recordHarvestFailures, sealCombinedRejections } from "../record-harvest-failures";
import { DEFERRED_REJECTIONS } from "./stage-response.schema";
import { CompletedCollectionSchema } from "./collection-contracts";
import type { z } from "zod";
import { snapshotCollectionBatch } from "./collection-batch";
import { finishRawDocumentFailures } from "../dump-raw-document-failure";
import { finishArticleEntities } from "../record-article-entities";
import { capturePlannerFailure, combinePlannerFailures } from "./plan-failure";
import { retainFailureThroughCleanup } from "./retain-failure-through-cleanup";

export type Collection = {
  config_sha256: string;
  context: RunContext; request: ReturnType<typeof resolvePlanRequest>;
  state: DocumentState; signal: AbortController; status: "collecting" | "complete" | "failed";
  closing: boolean; finalizing: boolean;
  feeds: Map<string, { state: "pending" | "fetching" | "parsing" | "terminal"; parse: OperationLink | null }>;
  complete?: Promise<z.infer<typeof CompletedCollectionSchema>>;
  operations: Set<Promise<unknown>>;
  finalization?: { request: string; result: z.infer<typeof FinalizedCollectionSchema> };
  rejections?: ReturnType<typeof recordHarvestFailures>;
  persistedRejections?: readonly RejectedArticleRow[];
  completed?: OperationLink;
  parses: Map<string, OperationLink | undefined>;
  offers: Map<string, PlannerFeedOffer>;
  results: Map<string, HarvestArticleResult>;
  pending_offers: number;
};
const collections = new WeakMap<PlanInputs, Map<string, Collection>>();
type CollectionOwner = { context: RunContext; signal: AbortSignal | undefined };
const pendingContexts = new WeakMap<PlanInputs, Map<string, CollectionOwner>>();
const collectionOwners = new WeakMap<Collection, CollectionOwner>();
const combinedSelectionClaims = new WeakSet<ExecutionOwnership>();
const preparedStarts = new WeakMap<PlanInputs, WeakMap<RunContext, Promise<z.infer<typeof CollectionResponseSchema>>>>();
const startingCollections = new WeakMap<PlanInputs, Set<string>>();
export function prepareCollectionContext(inputs: PlanInputs, context: RunContext, signal?: AbortSignal) {
  let pending = pendingContexts.get(inputs);
  if (pending === undefined) { pending = new Map(); pendingContexts.set(inputs, pending); }
  if (pending.has(context.traceId) || collections.get(inputs)?.has(context.traceId)
    || startingCollections.get(inputs)?.has(context.traceId)
    || [...pending.values()].some(value => value.context.run_id === context.run_id)
    || stageStore(inputs).isRunActive(context.run_id)) {
    throw new PlanError("REQUEST_CONFLICT", "Collection execution already belongs to live work", "traceId");
  }
  if (pending.size >= inputs.settings.listener.max_stage_batches) throw new PlanError("REQUEST_BUSY", "Collection startup capacity is occupied");
  pending.set(context.traceId, { context, signal });
}
export function discardCollectionContext(inputs: PlanInputs, context: RunContext) {
  const pending = pendingContexts.get(inputs);
  if (pending?.get(context.traceId)?.context === context) pending.delete(context.traceId);
  preparedStarts.get(inputs)?.delete(context);
}
export async function awaitCollectionStartup(inputs: PlanInputs, context: RunContext) {
  await preparedStarts.get(inputs)?.get(context);
}
export function ownsPreparedCollection(inputs: PlanInputs, context: RunContext) {
  const collection = collections.get(inputs)?.get(context.traceId);
  return collection !== undefined && collectionOwners.get(collection)?.context === context;
}
function held(inputs: PlanInputs) {
  let value = collections.get(inputs);
  if (value === undefined) { value = new Map(); collections.set(inputs, value); }
  return value;
}
function collectionCancelled(collection: Collection) {
  return collection.status === "failed" || collection.signal.signal.aborted;
}
export function getCollection(inputs: PlanInputs, id: string) {
  const collection = held(inputs).get(id);
  if (collection === undefined) throw new PlanError("ARTIFACT_NOT_FOUND", "Collection is missing or expired", "traceId");
  return collection;
}
export function collectionExists(raw: unknown, inputs: PlanInputs) {
  const request = CollectionReferenceSchema.parse(raw);
  return { traceId: request.traceId, exists: collections.get(inputs)?.has(request.traceId) ?? false };
}
export async function beginCollection(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime) {
  if (runtime.signal?.aborted) {
    throw runtime.signal.reason instanceof Error ? runtime.signal.reason
      : new DOMException("Collection startup was cancelled", "AbortError");
  }
  const request = BeginCollectionSchema.parse(raw);
  if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled", "enabled");
  const { include_selected_urls: _display, ...controls } = resolvePlanRequest(request.request, inputs.harvest.config);
  const owned = held(inputs);
  const operation = commandContext(runtime);
  let starting = startingCollections.get(inputs);
  if (starting === undefined) { starting = new Set(); startingCollections.set(inputs, starting); }
  if (owned.has(operation.traceId) || starting.has(operation.traceId)) {
    throw new PlanError("REQUEST_CONFLICT", "Collection execution already exists", "traceId");
  }
  const pending = pendingContexts.get(inputs);
  const prepared = pending?.get(operation.traceId);
  if (prepared !== undefined && operation.parentSpanId !== prepared.context.spanId) {
    throw new PlanError("REQUEST_CONFLICT", "Collection startup belongs to another operation", "traceId");
  }
  const context: RunContext = prepared === undefined
    ? resolveRunContext(inputs.settings, runtime.git_sha, runtime.clock?.() ?? new Date(),
      runtime.run_number, operation, runtime.captured_at, runtime.attempt, runtime.producer)
    : { ...stageContext(prepared.context), ...operation };
  const stages = stageStore(inputs);
  if ([...owned.values()].some(value => value.context.run_id === context.run_id)
    || stages.isRunActive(context.run_id)
    || [...(pending?.values() ?? [])].some(value => value !== prepared && value.context.run_id === context.run_id)) {
    throw new PlanError("REQUEST_CONFLICT", "Execution identity already belongs to live work", "traceId");
  }
  if (owned.size + starting.size >= inputs.settings.listener.max_stage_batches) {
    const finished = [...owned].find(([, value]) => value.status !== "collecting"
      && !stageStore(inputs).isRunActive(value.context.run_id));
    if (finished === undefined) throw new PlanError("REQUEST_BUSY", "Collection capacity is occupied by active work", "traceId");
    owned.delete(finished[0]);
  }
  const record = captureDocumentContext(inputs, runtime, context);
  if (prepared !== undefined) pending?.delete(operation.traceId);
  starting.add(operation.traceId);
  const startup = (async () => {
    try {
      stages.retainRun(context);
      const state = await documentState(record, inputs, runtime);
      state.plan_owned = true;
      const preflightAt = utcTimestamp(runtime.observation_clock);
      const availability = summarizeFeedAvailability(state.history.sources, preflightAt, inputs.harvest.sources);
      for (const source of inputs.harvest.sources.filter(source => source.status === "active")) {
        state.work.carryFeed(source.id, preflightAt);
      }
      const eligible = new Set(availability.eligible_feed_ids);
      const feeds = new Map(inputs.harvest.sources.filter(source => source.status === "active" && eligible.has(source.id))
        .map(source => [source.id, { state: "pending" as const, parse: null }]));
      const collection: Collection = { context, request: controls, state, feeds, parses: new Map(),
        offers: new Map(), results: new Map(), pending_offers: 0,
        config_sha256: record.config_sha256, signal: new AbortController(), status: "collecting",
        closing: false, finalizing: false, operations: new Set() };
      owned.set(operation.traceId, collection);
      if (prepared !== undefined) collectionOwners.set(collection, prepared);
      return { ...operationMetadata(context), context: stageContext(context), feeds: [...feeds.keys()] };
    } catch (error) {
      throw await retainFailureThroughCleanup(error, {
        operation: "feed-health-before-fetch", execution: context, limits: inputs.settings.diagnostics.failure,
      }, [{ operation: "collection-cancel", execute: () => stages.releaseRun(context.run_id) }]);
    } finally { starting.delete(operation.traceId); }
  })();
  if (prepared !== undefined) {
    let starts = preparedStarts.get(inputs);
    if (starts === undefined) { starts = new WeakMap(); preparedStarts.set(inputs, starts); }
    starts.set(prepared.context, startup);
  }
  return startup;
}
export function claimCollectionFeed(inputs: PlanInputs, id: string, feedId: string) {
  const collection = getCollection(inputs, id);
  const feed = collection.feeds.get(feedId);
  if (collection.status !== "collecting" || collection.closing || collection.signal.signal.aborted
    || feed?.state !== "pending") {
    throw new PlanError("REQUEST_CONFLICT", "Feed is not pending in this collection", "traceId");
  }
  feed.state = "fetching";
  return collection;
}
export function settleCollectionFeed(inputs: PlanInputs, runId: string, feedId: string, parse: OperationLink | null) {
  const collection = [...held(inputs).values()].find(value => value.context.run_id === runId);
  if (collection === undefined) return;
  const feed = collection.feeds.get(feedId);
  if (feed === undefined) throw new PlanError("ARTIFACT_INVALID", "Feed does not belong to this collection", "feed_id");
  feed.state = "terminal";
  feed.parse = parse === null ? null : operationLink(parse);
}
export function collectionForRun(inputs: PlanInputs, runId: string) {
  return [...held(inputs).values()].find(value => value.context.run_id === runId);
}
export function combinedCollectionForPersistence(
  inputs: PlanInputs, batch: Pick<SelectedFeedBatch, "traceId" | "context">, claim: ExecutionOwnership,
) {
  if (!combinedSelectionClaims.has(claim)) return undefined;
  const collection = getCollection(inputs, batch.traceId);
  if (!collectionOwners.has(collection) || collection.status !== "complete"
    || collection.context.run_id !== batch.context.run_id || collection.context.writer.attempt !== batch.context.writer.attempt) {
    throw new PlanError("REQUEST_CONFLICT", "Persistence requires its complete owned collection", "links");
  }
  return collection;
}
export async function completeCollection(inputs: PlanInputs, id: string) {
  const collection = getCollection(inputs, id);
  if (collection.complete !== undefined) return collection.complete;
  if (collectionCancelled(collection) || collection.finalizing) {
    throw new PlanError("REQUEST_INCOMPLETE", "Cancelled collection cannot be selected", "traceId");
  }
  const operation = createChildContext(operationMetadata(collection.context));
  collection.closing = true;
  collection.complete = (async () => {
    await drainCollectionOperations(collection);
    if (collectionCancelled(collection)) {
      throw new PlanError("REQUEST_INCOMPLETE", "Cancelled collection cannot be selected", "traceId");
    }
    if ([...collection.feeds.values()].some(feed => feed.state !== "terminal")) {
      throw new PlanError("BATCH_INCOMPLETE", "Every configured feed needs a terminal result", "traceId");
    }
    if (collection.pending_offers !== 0) {
      throw new PlanError("BATCH_INCOMPLETE", "Every offered article needs a terminal result", "traceId");
    }
    const saved = await rememberDiscoveries(collection.state.baseline.discovered.rows,
      collection.state.discovered_rows, collection.context, {
      outputRoot: inputs.outputRoot, registryEntry: inputs.registrations.discovered_articles, ledgerSettings: inputs.ledgerSettings,
    });
    const batch = snapshotCollectionBatch(inputs, collection, operation, true);
    const claim = stageStore(inputs).ownership(batch);
    claim.scope = "plan";
    const combined = collectionOwners.has(collection);
    const rejected = combined ? DEFERRED_REJECTIONS : await writeExplicitCollectionRejections(inputs, collection);
    if (collectionCancelled(collection)) {
      throw new PlanError("REQUEST_INCOMPLETE", "Cancelled collection cannot be selected", "traceId");
    }
    collection.status = "complete";
    collection.completed = operationLink(batch);
    if (combined) combinedSelectionClaims.add(claim);
    return { ...operationMetadata(batch), discovered_articles: saved.result, rejected_articles: rejected };
  })();
  try { return await collection.complete; }
  catch (error) {
    delete collection.complete;
    if (collection.status === "collecting") collection.closing = false;
    throw error;
  }
}
async function writeExplicitCollectionRejections(inputs: PlanInputs, collection: Collection) {
  collection.rejections ??= recordHarvestFailures(collection.state.harvest_rejections ?? [], collection.context, inputs);
  try { return await collection.rejections; }
  catch (error) { delete collection.rejections; throw error; }
}
export async function cancelCollection(inputs: PlanInputs, id: string) {
  const collection = getCollection(inputs, id);
  if (collection.finalizing || collection.finalization !== undefined) {
    throw new PlanError("REQUEST_CONFLICT", "Finalized collection cannot be cancelled", "traceId");
  }
  const operation = createChildContext(operationMetadata(collection.context));
  collection.status = "failed";
  collection.closing = true;
  collection.signal.abort();
  await drainCollectionOperations(collection);
  await collection.complete?.catch(() => undefined);
  await drainCollectionOperations(collection);
  const parsed = snapshotCollectionBatch(inputs, collection, operation, false);
  return { ...operationMetadata(parsed), status: "cancelled" as const,
    rejected_articles: collectionOwners.has(collection) ? DEFERRED_REJECTIONS : await writeExplicitCollectionRejections(inputs, collection),
    has_work: collection.state.work.rows().length > 0 };
}
export async function trackCollectionOperation<T>(collection: Collection, operation: () => Promise<T>) {
  if (collection.status !== "collecting" || collection.closing || collection.signal.signal.aborted) {
    throw new PlanError("REQUEST_INCOMPLETE", "Collection no longer accepts document work", "traceId");
  }
  const pending = Promise.resolve().then(operation);
  collection.operations.add(pending);
  try { return await pending; }
  finally { collection.operations.delete(pending); }
}
async function drainCollectionOperations(collection: Collection) {
  while (collection.operations.size) await Promise.allSettled([...collection.operations]);
}
export async function finalizeCollection(raw: unknown, inputs: PlanInputs) {
  const request = FinalizeCollectionRequestSchema.parse(raw);
  const collection = getCollection(inputs, request.traceId);
  const requestKey = JSON.stringify(request);
  if (collection.finalization !== undefined) {
    if (collection.finalization.request !== requestKey) {
      throw new PlanError("REQUEST_CONFLICT", "Collection already has a different final outcome", "traceId");
    }
    return collection.finalization.result;
  }
  if (collection.status === "collecting" || collection.finalizing) {
    throw new PlanError("REQUEST_INCOMPLETE", "Collection work must settle before final accounting", "traceId");
  }
  if (collection.status === "failed" && request.failure_code === null) {
    throw new PlanError("INVALID_REQUEST", "Cancelled collection requires a failure cause", "failure_code");
  }
  if (request.failure !== null && (request.failure.execution.run_id !== collection.context.run_id
    || request.failure.execution.attempt !== collection.context.writer.attempt)) {
    throw new PlanError("INVALID_REQUEST", "Failure evidence belongs to another execution", "failure");
  }
  const owner = collectionOwners.get(collection);
  if (owner !== undefined && request.failure_code === null && (request.failure !== null
    || request.collection_timing.status !== "completed" || collection.persistedRejections === undefined
    || !collection.state.health_written)) {
    throw new PlanError("REQUEST_INCOMPLETE", "Combined finalization requires completed collection, selection and health writes", "traceId");
  }
  collection.closing = true;
  collection.finalizing = true;
  try {
    await drainCollectionOperations(collection);
    const result = await settleCollectionOutcome(inputs, collection, request, owner);
    collection.finalization = { request: requestKey, result };
    return result;
  } finally { collection.finalizing = false; }
}
async function settleCollectionOutcome(
  inputs: PlanInputs, collection: Collection, request: z.infer<typeof FinalizeCollectionRequestSchema>,
  owner: CollectionOwner | undefined,
) {
  const timing = PlanApiTimingSchema.parse({
    operation: "fetch", duration_ms: request.collection_timing.duration_ms, status: request.collection_timing.status,
  });
  const insertion = collection.state.api_timings.findIndex(item =>
    item.operation !== "feed-health-before-fetch");
  collection.state.api_timings.splice(insertion < 0 ? collection.state.api_timings.length : insertion, 0, timing);
  let failureCode = request.failure_code;
  let failure = request.failure;
  function retainFailure(error: unknown, operation: PlannerFailureOperation, code: string, cancelled = false) {
    const current = capturePlannerFailure(error, {
      operation, execution: collection.context, limits: inputs.settings.diagnostics.failure, cancelled,
    });
    failure = failure === null ? current : combinePlannerFailures(failure, current, inputs.settings.diagnostics.failure);
    failureCode ??= code;
  }
  const diagnostics = await Promise.allSettled([
    finishRawDocumentFailures(inputs, collection.state.context), finishArticleEntities(inputs, collection.state.context),
  ]);
  for (const [index, result] of diagnostics.entries()) {
    if (result.status !== "rejected") continue;
    retainFailure(result.reason, index === 0 ? "write-document-failures" : "write-entities",
      index === 0 ? "RAW_DOCUMENT_OUTPUT_FAILED" : "ARTICLE_ENTITY_OUTPUT_FAILED");
  }
  let rejections: Awaited<ReturnType<typeof sealCombinedRejections>> | undefined;
  if (failureCode === null && owner !== undefined && collection.persistedRejections !== undefined) {
    try {
      owner.signal?.throwIfAborted();
      rejections = await sealCombinedRejections(collection.state.harvest_rejections ?? [],
        collection.persistedRejections, collection.context, inputs);
    } catch (error) {
      const cancelled = owner.signal?.aborted === true && owner.signal.reason === error;
      retainFailure(error, "collection-finalize", cancelled ? "PLAN_CANCELLED" : "REJECTION_OUTPUT_FAILED", cancelled);
    }
  }
  const status = failureCode === null ? "completed"
    : collection.state.work.rows().some(row => row.checked_at !== null) ? "partial" : "failed";
  return FinalizedCollectionSchema.parse({
    traceId: request.traceId, status, failure_code: failureCode, failure,
    api_timings: [...collection.state.api_timings],
    ...(rejections === undefined ? {} : { rejected_articles: rejections }),
  });
}
export function releaseCollection(raw: unknown, inputs: PlanInputs) {
  const request = ReleaseCollectionRequestSchema.parse(raw);
  const collection = [...held(inputs).values()].find(value =>
    value.context.run_id === request.run_id && value.context.writer.attempt === request.attempt);
  if (collection === undefined) return { ...request, released: false };
  if (collection.finalization === undefined || collection.finalizing || collection.operations.size) {
    throw new PlanError("REQUEST_INCOMPLETE", "Collection cannot be released before final accounting", "run_id");
  }
  held(inputs).delete(collection.context.traceId);
  stageStore(inputs).releaseRun(collection.context.run_id);
  return { ...request, released: true };
}
