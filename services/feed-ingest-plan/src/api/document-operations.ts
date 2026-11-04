/** Claim a live document, execute its HTTP stage and release the raw body after use. */
import { FetchRequestSchema, ParseRequestSchema } from "./operation-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import {
  captureDocumentContext, commandContext, operationKey, operationLink, operationMetadata, stageConfigFingerprint,
} from "./operation-context";
import { fetchDocument, resolveFetchParent } from "./fetch-operation";
import { parseFetchedDocument } from "./parse-operation";
import { appendDocumentTiming } from "./document-state";
import { PlanError } from "./plan-request";
import { FetchResponseSchema, ParseResponseSchema } from "./document-response.schema";
import { stageStore } from "./stage-store";
import {
  claimCollectionFeed, collectionForRun, getCollection, settleCollectionFeed,
  trackCollectionOperation,
} from "./collection-operation";
import type { Collection } from "./collection-operation";
import { dumpRawDocumentFailure } from "../dump-raw-document-failure";
import { utcTimestamp } from "../harvest-feeds/harvest-types";
import type { FetchedDocumentReference } from "./stage-store";
import type { z } from "zod";
import { withPlannerFailure } from "./plan-failure";
import { retainFailureThroughCleanup } from "./retain-failure-through-cleanup";
import type { RunContext } from "../resolve-run-context";

type DocumentRequest = z.infer<typeof FetchRequestSchema> | z.infer<typeof ParseRequestSchema>;

function collectionForRequest(request: DocumentRequest, inputs: PlanInputs, parent: ReturnType<typeof resolveFetchParent>) {
  if ("fetch_item_type" in request) {
    if ("traceId" in request && request.traceId !== undefined) {
      return getCollection(inputs, request.traceId);
    }
    return parent === null ? undefined : collectionForRun(inputs, parent.batch.context.run_id);
  }
  const fetched = stageStore(inputs).fetchedDocument(request.links[0]);
  return fetched === undefined ? undefined : collectionForRun(inputs, fetched.context.run_id);
}

async function recordFailure(operation: "fetch" | "parse", context: RunContext, failure: string,
  fetched: FetchedDocumentReference | undefined, inputs: PlanInputs, runtime: PlanRuntime) {
  if (fetched === undefined) return;
  await dumpRawDocumentFailure(inputs, context, {
    ...operationMetadata(context), operation, document_kind: fetched.document.fetch_item_type,
    failed_at: utcTimestamp(runtime.observation_clock), failure_reason: failure, document: fetched.document,
  });
}

export async function executeDocumentOperation(
  operation: "fetch" | "parse", raw: unknown, inputs: PlanInputs, runtime: PlanRuntime, signal?: AbortSignal,
) {
  const request = operation === "fetch" ? FetchRequestSchema.parse(raw) : ParseRequestSchema.parse(raw);
  if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled", "enabled");
  const parent = "fetch_item_type" in request ? resolveFetchParent(request, inputs, runtime) : null;
  const collection = collectionForRequest(request, inputs, parent);
  const execute = () => executeOwnedDocumentOperation(request, inputs, runtime, parent, collection, signal);
  return collection === undefined ? execute() : trackCollectionOperation(collection, execute);
}

async function executeOwnedDocumentOperation(
  request: DocumentRequest, inputs: PlanInputs, runtime: PlanRuntime,
  parent: ReturnType<typeof resolveFetchParent>, collection: Collection | undefined, signal?: AbortSignal,
) {
  const store = stageStore(inputs);
  if ("fetch_item_type" in request) {
    if (collection !== undefined && request.fetch_item_type === "feed") {
      claimCollectionFeed(inputs, collection.context.traceId, request.feed_id);
    }
    const business = collection?.context ?? parent?.batch.context;
    const operation = commandContext(runtime, collection?.context, parent === null ? [] : [parent.batch]);
    const record = captureDocumentContext(inputs, { ...runtime, ...operation },
      business === undefined ? undefined : { ...business, ...operation });
    store.beginFetch(record);
    const begin = performance.now();
    let retain = false;
    try {
      const owned = collectionForRun(inputs, record.context.run_id);
      const signals = [runtime.signal, signal, owned?.signal.signal].filter((value): value is AbortSignal => value !== undefined);
      const result = await fetchDocument(request, record, inputs, { ...runtime, signal: AbortSignal.any(signals) }, parent);
      const response = FetchResponseSchema.parse(JSON.parse(result.response_json));
      if (response.failure !== null) {
        await recordFailure("fetch", record.context, response.failure, store.fetchedDocument(record.context), inputs, runtime);
        if (request.fetch_item_type === "feed") settleCollectionFeed(inputs, record.context.run_id, request.feed_id, null);
      }
      await appendDocumentTiming(inputs, record.context.run_id, {
        operation: "fetch", duration_ms: Math.round(performance.now() - begin),
        status: response.failure === null ? "completed" : "failed",
      });
      retain = response.failure === null;
      return result.response_json;
    } catch (error) {
      const failure = withPlannerFailure(error, {
        operation: "fetch", execution: record.context, limits: inputs.settings.diagnostics.failure,
      });
      throw await retainFailureThroughCleanup(failure, {
        operation: "fetch", execution: record.context, limits: inputs.settings.diagnostics.failure,
      }, [
        { operation: "write-document-failures", execute: () => recordFailure("fetch", record.context,
          failure.code, store.fetchedDocument(record.context), inputs, runtime) },
        { operation: "collection-cancel", execute: () => {
          if (request.fetch_item_type === "feed" && ["FEED_RESTING", "FEED_RETIRED"].includes(failure.code)) {
            settleCollectionFeed(inputs, record.context.run_id, request.feed_id, null);
          }
        } },
        { operation: "record-run", execute: () => appendDocumentTiming(inputs, record.context.run_id, {
          operation: "fetch", duration_ms: Math.round(performance.now() - begin), status: "failed",
        }) },
      ]);
    } finally { store.finishFetch(record.context, retain); }
  }
  const input = request.links[0];
  const held = store.fetchedDocument(input);
  if (held === undefined) throw new PlanError("ARTIFACT_NOT_FOUND", "No current completed fetched document exists", "links");
  const context = { ...held.context, ...commandContext(runtime, collection?.context, [input]) };
  const fetched = store.claimDocument(input, context, stageConfigFingerprint(inputs, runtime));
  const key = operationKey(context);
  collection?.parses.set(key, undefined);
  const begin = performance.now();
  try {
    const signals = [runtime.signal, signal, collection?.signal.signal].filter((value): value is AbortSignal => value !== undefined);
    const result = await parseFetchedDocument(fetched, context, inputs, runtime, AbortSignal.any(signals));
    const response = ParseResponseSchema.parse(JSON.parse(result.response_json));
    collection?.parses.set(key, operationLink(response));
    if (response.failure !== null) await recordFailure("parse", context, response.failure, fetched, inputs, runtime);
    if (response.fetch_item_type === "feed") {
      settleCollectionFeed(inputs, fetched.context.run_id, fetched.document.feed_id, operationLink(response));
    }
    await appendDocumentTiming(inputs, fetched.context.run_id, {
      operation: "parse", duration_ms: Math.round(performance.now() - begin),
      status: response.failure === null ? "completed" : "failed",
    });
    return result.response_json;
  } catch (error) {
    const failure = withPlannerFailure(error, {
      operation: "parse", execution: context, limits: inputs.settings.diagnostics.failure,
    });
    throw await retainFailureThroughCleanup(failure, {
      operation: "parse", execution: context, limits: inputs.settings.diagnostics.failure,
    }, [
      { operation: "write-document-failures", execute: () =>
        recordFailure("parse", context, failure.code, fetched, inputs, runtime) },
      { operation: "record-run", execute: () => appendDocumentTiming(inputs, fetched.context.run_id, {
        operation: "parse", duration_ms: Math.round(performance.now() - begin), status: "failed",
      }) },
    ]);
  } finally {
    if (collection?.parses.get(key) === undefined) collection?.parses.delete(key);
    store.consumeDocument(input, context);
  }
}
