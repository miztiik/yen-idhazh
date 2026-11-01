/** Claim a live document, execute its HTTP stage and release the raw body after use. */
import { FetchRequestSchema, ParseRequestSchema } from "./operation-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { captureDocumentContext, stageConfigFingerprint } from "./operation-context";
import { fetchDocument, resolveFetchParent } from "./fetch-operation";
import { parseFetchedDocument } from "./parse-operation";
import { appendDocumentTiming } from "./document-state";
import { PlanError, describePlanError } from "./plan-request";
import { FetchResponseSchema, ParseResponseSchema } from "./document-response.schema";
import { stageStore } from "./stage-store";
import { claimCollectionFeed, collectionForRun, settleCollectionFeed } from "./collection-operation";
import { dumpRawDocumentFailure } from "../dump-raw-document-failure";
import { utcTimestamp } from "../harvest-feeds/harvest-types";
import type { FetchedDocumentReference } from "./stage-store";

async function recordFailure(operation: "fetch" | "parse", requestId: string, failure: string,
  fetched: FetchedDocumentReference | undefined, inputs: PlanInputs, runtime: PlanRuntime) {
  if (fetched === undefined) return;
  await dumpRawDocumentFailure(inputs, fetched.context, {
    request_id: requestId, operation, document_kind: fetched.document.fetch_item_type,
    failed_at: utcTimestamp(runtime.observation_clock), failure_reason: failure, document: fetched.document,
  });
}

export async function executeDocumentOperation(
  operation: "fetch" | "parse", raw: unknown, inputs: PlanInputs, runtime: PlanRuntime, signal?: AbortSignal,
) {
  const request = operation === "fetch" ? FetchRequestSchema.parse(raw) : ParseRequestSchema.parse(raw);
  if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled", "enabled");
  const store = stageStore(inputs);
  if ("feed_id" in request) {
    const collection = request.collection_id === undefined ? undefined
      : claimCollectionFeed(inputs, request.collection_id, request.feed_id, request.correlation_id);
    const parent = resolveFetchParent(request, inputs, runtime);
    const record = captureDocumentContext(request.request_id, request.correlation_id, inputs, runtime,
      collection?.context ?? parent?.batch.context);
    store.beginFetch(record);
    const begin = performance.now();
    let retain = false;
    try {
      const owned = collectionForRun(inputs, record.context.run_id);
      const signals = [runtime.signal, signal, owned?.signal.signal].filter((value): value is AbortSignal => value !== undefined);
      const result = await fetchDocument(request, record, inputs, { ...runtime, signal: AbortSignal.any(signals) }, parent);
      const response = FetchResponseSchema.parse(JSON.parse(result.response_json));
      if (response.failure !== null) {
        await recordFailure("fetch", request.request_id, response.failure, store.fetchedDocument(request.request_id), inputs, runtime);
        if (request.fetch_item_type === "feed") settleCollectionFeed(inputs, record.context.run_id, request.feed_id, null);
      }
      await appendDocumentTiming(inputs, record.context.run_id, {
        operation: "fetch", duration_ms: Math.round(performance.now() - begin),
        status: response.failure === null ? "completed" : "failed",
      });
      retain = response.failure === null;
      return result.response_json;
    } catch (error) {
      await recordFailure("fetch", request.request_id, describePlanError(error, inputs.root).code,
        store.fetchedDocument(request.request_id), inputs, runtime);
      if (request.fetch_item_type === "feed" && error instanceof PlanError && ["FEED_RESTING", "FEED_RETIRED"].includes(error.code)) {
        settleCollectionFeed(inputs, record.context.run_id, request.feed_id, null);
      }
      await appendDocumentTiming(inputs, record.context.run_id, {
        operation: "fetch", duration_ms: Math.round(performance.now() - begin), status: "failed",
      });
      throw error;
    } finally { store.finishFetch(request.request_id, retain); }
  }
  const fetched = store.claimDocument(request.fetch_request_id, request.request_id, request.article_id,
    request.correlation_id, stageConfigFingerprint(inputs, runtime));
  const begin = performance.now();
  try {
    const collection = collectionForRun(inputs, fetched.context.run_id);
    const signals = [runtime.signal, signal, collection?.signal.signal].filter((value): value is AbortSignal => value !== undefined);
    const result = await parseFetchedDocument(request, fetched, inputs, runtime, AbortSignal.any(signals));
    const response = ParseResponseSchema.parse(JSON.parse(result.response_json));
    if (response.failure !== null) await recordFailure("parse", request.request_id, response.failure, fetched, inputs, runtime);
    if (response.fetch_item_type === "feed") {
      settleCollectionFeed(inputs, fetched.context.run_id, fetched.document.feed_id, response.batch_id);
    }
    await appendDocumentTiming(inputs, fetched.context.run_id, {
      operation: "parse", duration_ms: Math.round(performance.now() - begin),
      status: response.failure === null ? "completed" : "failed",
    });
    return result.response_json;
  } catch (error) {
    await recordFailure("parse", request.request_id, describePlanError(error, inputs.root).code, fetched, inputs, runtime);
    await appendDocumentTiming(inputs, fetched.context.run_id, {
      operation: "parse", duration_ms: Math.round(performance.now() - begin), status: "failed",
    });
    throw error;
  } finally { store.consumeDocument(request.fetch_request_id, request.request_id); }
}
