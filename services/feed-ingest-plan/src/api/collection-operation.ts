/** Own one complete collection and refuse selection before all its work settles. */
import { randomUUID } from "node:crypto";
import {
  ParsedFeedBatchSchema, PlannerOperationSchema,
} from "@idhazh/common-contracts";
import type { PlannerStageContext, DiscoveredArticleRow } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { resolveRunContext } from "../resolve-run-context";
import { resolvePlanRequest, PlanError } from "./plan-request";
import { BeginCollectionSchema } from "./collection-contracts";
import { operationConfigFingerprint } from "./operation-context";
import { sha256, openOperationStore } from "./operation-store";
import { documentState } from "./document-state";
import type { DocumentState } from "./document-state";
import { stageStore } from "./stage-store";
import { plannerMemory } from "../planner-memory";
import { rememberDiscoveries } from "../read-ledger-history/read-discovered-evidence";
import { readFeedAvailability } from "../availability/feed-availability";
import { recordHarvestFailures } from "../record-harvest-failures";
import { CompletedCollectionSchema } from "./collection-contracts";
import type { z } from "zod";

type Collection = {
  config_sha256: string;
  parsed_batch_id: string; feed_requests: Map<string, string>;
  context: PlannerStageContext; request: ReturnType<typeof resolvePlanRequest>;
  state: DocumentState; signal: AbortController; status: "collecting" | "complete" | "failed";
  feeds: Map<string, { state: "pending" | "fetching" | "parsing" | "terminal"; batch_id: string | null }>;
  complete?: Promise<z.infer<typeof CompletedCollectionSchema>>;
  rejections?: ReturnType<typeof recordHarvestFailures>;
  completed_batch_id?: string;
  discovery_baseline?: DiscoveredArticleRow[];
};
const collections = new WeakMap<PlanInputs, Map<string, Collection>>();
const pendingContexts = new WeakMap<PlanInputs, Map<string, PlannerStageContext>>();
export function prepareCollectionContext(inputs: PlanInputs, id: string, context: PlannerStageContext) {
  let pending = pendingContexts.get(inputs);
  if (pending === undefined) { pending = new Map(); pendingContexts.set(inputs, pending); }
  if (pending.size >= inputs.settings.listener.max_stage_batches) throw new PlanError("REQUEST_BUSY", "Collection startup capacity is occupied");
  pending.set(id, context);
}
export function discardCollectionContext(inputs: PlanInputs, id: string) {
  pendingContexts.get(inputs)?.delete(id);
}
function held(inputs: PlanInputs) {
  let value = collections.get(inputs);
  if (value === undefined) { value = new Map(); collections.set(inputs, value); }
  return value;
}
export function getCollection(inputs: PlanInputs, id: string) {
  const collection = held(inputs).get(id);
  if (collection === undefined) throw new PlanError("ARTIFACT_NOT_FOUND", "Collection is missing or expired", "collection_id");
  return collection;
}
export async function beginCollection(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime) {
  const request = BeginCollectionSchema.parse(raw);
  if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled", "enabled");
  const controls = resolvePlanRequest(request.request, inputs.harvest.config);
  const owned = held(inputs);
  if (owned.has(request.collection_id)) throw new PlanError("REQUEST_CONFLICT", "Collection identity already exists", "collection_id");
  if (owned.size >= inputs.settings.listener.max_stage_batches) {
    const finished = [...owned].find(([, value]) => value.status !== "collecting");
    if (finished === undefined) throw new PlanError("REQUEST_BUSY", "Collection capacity is occupied by active work", "collection_id");
    owned.delete(finished[0]);
  }
  const context = pendingContexts.get(inputs)?.get(request.collection_id) ?? resolveRunContext(inputs.settings, runtime.git_sha, runtime.clock?.() ?? new Date(),
    runtime.run_number, runtime.correlation_id ?? request.collection_id, runtime.captured_at, runtime.attempt, runtime.producer);
  pendingContexts.get(inputs)?.delete(request.collection_id);
  if ([...owned.values()].some(value => value.context.run_id === context.run_id)) {
    throw new PlanError("REQUEST_CONFLICT", "Execution identity already belongs to a collection", "collection_id");
  }
  const record = PlannerOperationSchema.parse({
    request_id: request.collection_id, operation: "fetch", run_id: context.run_id,
    correlation_id: context.correlation_id, created_at: context.captured_at,
    input_sha256: sha256(JSON.stringify(request)), config_sha256: operationConfigFingerprint(inputs, runtime),
    state: "started", response_json: null, artifact: null,
  });
  const store = await openOperationStore(inputs.outputRoot);
  let state: DocumentState;
  try { state = await documentState(record, inputs, runtime, store); }
  finally { store.close(); }
  state.plan_owned = true;
  const availability = await readFeedAvailability(inputs, new Date().toISOString());
  const eligible = new Set(availability.eligible_feed_ids);
  const feeds = new Map(inputs.harvest.sources.filter(source => source.status === "active" && eligible.has(source.id))
    .map(source => [source.id, { state: "pending" as const, batch_id: null }]));
  const parsed = stageStore(inputs).write("parsed", ParsedFeedBatchSchema, {
    batch_id: randomUUID(), context, config_sha256: operationConfigFingerprint(inputs, runtime), request: controls,
    candidates: [], observations: {}, evidence: {}, offers: [], input_complete: false,
    discovered: { availability: "available", rows: [] }, history_rows: [], history_days: state.history.days,
    work_rows: state.work.rows(), exclusions: state.work.exclusions(),
  });
  owned.set(request.collection_id, { context, request: controls, state, feeds,
    parsed_batch_id: parsed.batch_id, feed_requests: new Map(),
    config_sha256: operationConfigFingerprint(inputs, runtime), signal: new AbortController(), status: "collecting" });
  return { collection_id: request.collection_id, context, feeds: [...feeds.keys()] };
}
export function claimCollectionFeed(inputs: PlanInputs, id: string, feedId: string, correlationId: string) {
  const collection = getCollection(inputs, id);
  const feed = collection.feeds.get(feedId);
  if (collection.status !== "collecting" || collection.signal.signal.aborted
    || collection.context.correlation_id !== correlationId || feed?.state !== "pending") {
    throw new PlanError("REQUEST_CONFLICT", "Feed is not pending in this collection", "collection_id");
  }
  feed.state = "fetching";
  return collection;
}
export function settleCollectionFeed(inputs: PlanInputs, runId: string, feedId: string, batchId: string | null) {
  const collection = [...held(inputs).values()].find(value => value.context.run_id === runId);
  if (collection === undefined) return;
  const feed = collection.feeds.get(feedId);
  if (feed === undefined) throw new PlanError("ARTIFACT_INVALID", "Feed does not belong to this collection", "feed_id");
  feed.state = "terminal";
  feed.batch_id = batchId;
}
export function collectionForRun(inputs: PlanInputs, runId: string) {
  return [...held(inputs).values()].find(value => value.context.run_id === runId);
}
export function collectionFeedRequest(inputs: PlanInputs, runId: string, feedId: string) {
  return collectionForRun(inputs, runId)?.feed_requests.get(feedId);
}
export async function completeCollection(inputs: PlanInputs, id: string) {
  const collection = getCollection(inputs, id);
  if (collection.status === "failed" || collection.signal.signal.aborted) {
    throw new PlanError("REQUEST_INCOMPLETE", "Cancelled collection cannot be selected", "collection_id");
  }
  if ([...collection.feeds.values()].some(feed => feed.state !== "terminal")) {
    throw new PlanError("BATCH_INCOMPLETE", "Every configured feed needs a terminal result", "collection_id");
  }
  collection.complete ??= (async () => {
    const current = stageStore(inputs).read("parsed", collection.parsed_batch_id, ParsedFeedBatchSchema);
    if (current.offers.some(offer => offer.state !== "parsed" && offer.state !== "rejected")) {
      throw new PlanError("BATCH_INCOMPLETE", "Every offered article needs a terminal result", "collection_id");
    }
    const discoveries = plannerMemory(inputs).discoveries();
    const saved = await rememberDiscoveries(collection.discovery_baseline ?? [], discoveries, collection.context, {
      outputRoot: inputs.outputRoot, registryEntry: inputs.registrations.discovered_articles, ledgerSettings: inputs.ledgerSettings,
    });
    const batch = stageStore(inputs).replace("parsed", ParsedFeedBatchSchema, {
      ...current, input_complete: true,
      discovered: { availability: "available", rows: discoveries },
      history_rows: [], history_days: collection.state.history.days,
      work_rows: collection.state.work.rows(), exclusions: collection.state.work.exclusions(),
    });
    stageStore(inputs).ownership(batch.batch_id).scope = "plan";
    const rejected = await finalizeCollectionRejections(inputs, collection);
    collection.status = "complete";
    collection.completed_batch_id = batch.batch_id;
    return { collection_id: id, batch_id: batch.batch_id, discovered_articles: saved.result, rejected_articles: rejected };
  })();
  try { return await collection.complete; }
  catch (error) { delete collection.complete; throw error; }
}
async function finalizeCollectionRejections(inputs: PlanInputs, collection: Collection) {
  collection.rejections ??= recordHarvestFailures(collection.state.harvest_rejections ?? [], collection.context, inputs);
  try { return await collection.rejections; }
  catch (error) { delete collection.rejections; throw error; }
}
export async function cancelCollection(inputs: PlanInputs, id: string) {
  const collection = getCollection(inputs, id);
  collection.status = "failed";
  collection.signal.abort();
  const parsed = stageStore(inputs).read("parsed", collection.parsed_batch_id, ParsedFeedBatchSchema);
  stageStore(inputs).replace("parsed", ParsedFeedBatchSchema, {
    ...parsed, work_rows: collection.state.work.rows(), exclusions: collection.state.work.exclusions(),
  });
  return { collection_id: id, status: "cancelled" as const, batch_id: parsed.batch_id,
    rejected_articles: await finalizeCollectionRejections(inputs, collection) };
}
