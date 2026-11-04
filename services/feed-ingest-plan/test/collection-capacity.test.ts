/** Keep a collection's full offered population and live references beyond the stage-slot count. */
import { expect, test } from "bun:test";
import {
  createRootContext, FeedHealthStateUpdateResponseSchema, ParsedFeedBatchSchema, PLANNER_API_PREFIX, writeTraceContext,
} from "@idhazh/common-contracts";
import { recordedPlan } from "./plan-recordings";
import { createPlanTestServer } from "./plan-test-server";
import { FetchResponseSchema, ParseResponseSchema } from "../src/api/document-response.schema";
import { CancelledCollectionSchema, CompletedCollectionSchema } from "../src/api/collection-contracts";
import { getCollection, collectionForRun } from "../src/api/collection-operation";
import { stageStore } from "../src/api/stage-store";
import { operationLink } from "../src/api/operation-context";
import type { OperationLink, ParsedFeedBatch } from "@idhazh/common-contracts";
import { runFeedPlan, summarizePlan } from "../src/run-feed-plan";

async function recordedPopulation() {
  const fixture = await recordedPlan();
  const capacity = fixture.inputs.settings.listener.max_stage_batches;
  const count = capacity + 1;
  const source = fixture.inputs.harvest.sources[0]!;
  const entries = Array.from({ length: count }, (_, index) => {
    const url = `https://news.example/capacity/${index}`;
    fixture.transport.recordings.responses[url] = [{ status: 200, fixture: "article" }];
    return `<item><title>Recorded science article ${index}</title><link>${url}</link><pubDate>Wed, 21 Oct 2026 23:00:00 GMT</pubDate></item>`;
  });
  fixture.transport.recordings.responses[source.url] = [{
    status: 200, body: `<rss version="2.0"><channel><title>Recorded science</title>${entries.join("")}</channel></rss>`,
  }];
  return { fixture, capacity, count, source };
}

test("one active collection crosses the configured stage capacity without losing parsed references", async () => {
  const { fixture, capacity, count, source } = await recordedPopulation();
  for (const index of [1, 2]) fixture.transport.recordings.responses[`https://news.example/capacity/${index}`] = [{
    status: 200, body: "<html><body></body></html>",
  }];
  const app = createPlanTestServer(fixture.inputs, fixture.runtime);
  const caller = createRootContext();
  const post = async (path: string, body: unknown) => {
    const response = await app.request(`${PLANNER_API_PREFIX}/${path}`, {
      method: "POST", headers: { "content-type": "application/json", ...writeTraceContext(caller) },
      body: JSON.stringify(body),
    });
    const result: unknown = await response.json();
    expect(response.status, `${path}: ${JSON.stringify(result)}`).toBe(200);
    return result;
  };
  let first: OperationLink | undefined;
  let firstSnapshot: ParsedFeedBatch | undefined;
  let rejected: OperationLink | undefined;
  let rejectedSnapshot: ParsedFeedBatch | undefined;
  try {
    await post("collections", { request: { article_limit: 100, shards: 4, partition_strategy: "bin-pack" } });
    const collection = getCollection(fixture.inputs, caller.traceId);
    const fetched = FetchResponseSchema.parse(await post("fetch", {
      traceId: caller.traceId, feed_id: source.id, fetch_item_type: "feed",
    }));
    const feed = ParseResponseSchema.parse(await post("parse", { links: [operationLink(fetched)] }));
    if (feed.fetch_item_type !== "feed") throw new Error("The generated RSS must return its actual feed offers");
    expect(feed.offers).toHaveLength(count);
    const feedSnapshot = stageStore(fixture.inputs).read("parsed", feed, ParsedFeedBatchSchema);
    for (const [index, offer] of feed.offers.entries()) {
      const article = FetchResponseSchema.parse(await post("fetch", {
        fetch_item_type: "article", links: [operationLink(feed)], offer_id: offer.offer_id,
      }));
      const parsed = ParseResponseSchema.parse(await post("parse", { links: [operationLink(article)] }));
      first ??= operationLink(parsed);
      firstSnapshot ??= stageStore(fixture.inputs).read("parsed", first, ParsedFeedBatchSchema);
      if (index === 1 || index === 2) {
        expect(parsed.failure).not.toBeNull();
        rejected ??= operationLink(parsed);
        rejectedSnapshot ??= stageStore(fixture.inputs).read("parsed", rejected, ParsedFeedBatchSchema);
      } else expect(parsed.failure).toBeNull();
    }
    if (first === undefined || firstSnapshot === undefined) throw new Error("The generated collection must parse its articles");
    const original = stageStore(fixture.inputs).read("parsed", first, ParsedFeedBatchSchema);
    expect(original).toEqual(firstSnapshot);
    expect(stageStore(fixture.inputs).read("parsed", feed, ParsedFeedBatchSchema)).toEqual(feedSnapshot);
    if (rejected === undefined || rejectedSnapshot === undefined) throw new Error("Generated empty articles must retain their failure snapshots");
    expect(stageStore(fixture.inputs).read("parsed", rejected, ParsedFeedBatchSchema)).toEqual(rejectedSnapshot);
    expect(original.candidates).toHaveLength(1);
    expect(original.candidates[0]!.canonical_url).toBe("https://news.example/capacity/0");
    expect((await app.request(`${PLANNER_API_PREFIX}/select-articles`, {
      method: "POST", headers: { "content-type": "application/json", ...writeTraceContext(caller) },
      body: JSON.stringify({ links: [first] }),
    })).status).toBe(409);
    const completed = CompletedCollectionSchema.parse(await post("collections/complete", { traceId: caller.traceId }));
    const batch = stageStore(fixture.inputs).read("parsed", completed, ParsedFeedBatchSchema);
    expect(batch.candidates).toHaveLength(count - 2);
    expect(batch.offers).toHaveLength(count);
    expect(batch.offers.filter(offer => offer.state === "rejected")).toHaveLength(2);
    expect(collection.results.size).toBe(count - 2);
    expect(collection.request).toMatchObject({ article_limit: 100, shards: 4, partition_strategy: "bin-pack" });
    expect(fixture.inputs.settings.listener.max_stage_batches).toBe(capacity);
    expect(batch.input_complete).toBe(true);
    const articleRequests = fixture.transport.requests.filter(request => request.url.pathname.startsWith("/capacity/")).length;
    expect(articleRequests).toBeGreaterThanOrEqual(count);
    expect(batch.work_rows.reduce((sum, row) => sum + (row.article_requests ?? 0), 0)).toBe(articleRequests);
    expect(fixture.transport.requests).toHaveLength(articleRequests + 1);
    for (const action of ["record", "summarize"] as const) {
      const health = FeedHealthStateUpdateResponseSchema.parse(await post("feed-health-state", { links: [first], action }));
      expect(health.rows.reduce((sum, row) => sum + (row.article_requests ?? 0), 0)).toBe(articleRequests);
      expect(stageStore(fixture.inputs).read("parsed", first, ParsedFeedBatchSchema)).toEqual(firstSnapshot);
    }
    const cancelled = CancelledCollectionSchema.parse(await post("collections/cancel", { traceId: caller.traceId }));
    const partial = stageStore(fixture.inputs).read("parsed", cancelled, ParsedFeedBatchSchema);
    expect(partial.candidates).toHaveLength(count - 2);
    expect(partial.input_complete).toBe(false);
    expect(stageStore(fixture.inputs).read("parsed", completed, ParsedFeedBatchSchema)).toEqual(batch);
    expect(collection.operations.size).toBe(0);
    await post("collections/finalize", {
      traceId: caller.traceId, failure_code: "PLANNER_EXECUTION_FAILED",
      collection_timing: { duration_ms: 0, status: "failed" },
    });
    expect(await post("collections/release", {
      run_id: collection.context.run_id, attempt: collection.context.writer.attempt,
    })).toMatchObject({ released: true });
    expect(stageStore(fixture.inputs).isRunActive(collection.context.run_id)).toBe(false);
    expect(stageStore(fixture.inputs).read("parsed", first, ParsedFeedBatchSchema)).toEqual(firstSnapshot);
  } finally { await app.close(); await fixture.close(); }
}, 120000);

test("full-stage admission and expiry preserve another run's outstanding fetched input", async () => {
  const fixture = await recordedPlan();
  fixture.inputs.settings.listener.max_stage_batches = 2;
  const { run_number: _run, ...runtime } = fixture.runtime;
  const app = createPlanTestServer(fixture.inputs, runtime);
  const caller = createRootContext();
  const external = createRootContext();
  const next = createRootContext();
  const post = (path: string, body: unknown, context = caller) => app.request(`${PLANNER_API_PREFIX}/${path}`, {
    method: "POST", headers: { "content-type": "application/json", ...writeTraceContext(context) },
    body: JSON.stringify(body),
  });
  const finish = async (id: string, context = caller) => {
    const collection = getCollection(fixture.inputs, id);
    expect((await post("collections/cancel", { traceId: id }, context)).status).toBe(200);
    expect((await post("collections/finalize", {
      traceId: id, failure_code: "PLANNER_EXECUTION_FAILED",
      collection_timing: { duration_ms: 0, status: "failed" },
    }, context)).status).toBe(200);
    expect(await (await post("collections/release", {
      run_id: collection.context.run_id, attempt: collection.context.writer.attempt,
    }, context)).json()).toMatchObject({ released: true });
  };
  try {
    const source = fixture.inputs.harvest.sources[0]!;
    fixture.transport.recordings.responses[source.url] = [
      { status: 200, fixture: "rss" }, { status: 200, fixture: "rss" },
    ];
    expect((await post("collections", { request: {} })).status).toBe(200);
    const firstFetch = FetchResponseSchema.parse(await (await post("fetch", {
      traceId: caller.traceId, feed_id: source.id, fetch_item_type: "feed",
    })).json());
    const firstParse = ParseResponseSchema.parse(await (await post("parse", { links: [operationLink(firstFetch)] })).json());
    const firstSnapshot = stageStore(fixture.inputs).read("parsed", firstParse, ParsedFeedBatchSchema);
    const feedFetch = FetchResponseSchema.parse(await (await post("fetch", {
      feed_id: source.id, fetch_item_type: "feed",
    }, external)).json());
    const feed = ParseResponseSchema.parse(await (await post("parse", { links: [operationLink(feedFetch)] }, external)).json());
    if (feed.fetch_item_type !== "feed") throw new Error("Recorded source must produce its actual feed offers");
    const article = FetchResponseSchema.parse(await (await post("fetch", {
      fetch_item_type: "article", links: [operationLink(feed)], offer_id: feed.offers[0]!.offer_id,
    }, external)).json());
    const held = stageStore(fixture.inputs).fetchedDocument(article);
    expect(held?.document.body).not.toBeNull();
    expect(held).toBeDefined();
    const refused = await post("collections", { request: {} }, next);
    expect(refused.status).toBe(409);
    expect(await refused.json()).toMatchObject({ code: "REQUEST_BUSY" });
    expect(stageStore(fixture.inputs).read("parsed", firstParse, ParsedFeedBatchSchema)).toEqual(firstSnapshot);
    expect(stageStore(fixture.inputs).fetchedDocument(article)).toEqual(held);
    await finish(caller.traceId);
    expect((await post("collections", { request: {} }, next)).status).toBe(200);
    expect(stageStore(fixture.inputs).has(firstParse)).toBe(false);
    expect((await post("feed-health-state", {
      links: [operationLink(firstParse)], action: "summarize",
    })).status).toBe(404);
    expect(stageStore(fixture.inputs).fetchedDocument(article)).toEqual(held);
    expect(stageStore(fixture.inputs).has(feed)).toBe(true);
    await finish(next.traceId, next);
    const parsed = ParseResponseSchema.parse(await (await post("parse", { links: [operationLink(article)] }, external)).json());
    expect(parsed.failure).toBeNull();
    expect(parsed.traceId).toBe(external.traceId);
    expect(parsed.run_id).not.toBe(firstSnapshot.context.run_id);
    expect(stageStore(fixture.inputs).fetchedDocument(article)).toBeUndefined();
  } finally { await app.close(); await fixture.close(); }
}, 120000);

test("ordinary planning completes selection and persistence beyond retained-stage capacity", async () => {
  const { fixture, capacity, count } = await recordedPopulation();
  try {
    const result = await runFeedPlan({ article_limit: 100, shards: 4, partition_strategy: "bin-pack" },
      fixture.inputs, fixture.runtime);
    expect(result.row.status).toBe("completed");
    expect(result.row.failure_code).toBeNull();
    expect(result.row.selection_started_at_utc).not.toBeNull();
    expect(result.row.selected_count).toBe(100);
    expect(result.row.dispatch_count).toBe(4);
    expect(result.row.strategy).toBe("bin-pack");
    expect(result.files.plan_runs?.status).toBe("written");
    expect(result.files.selected_articles?.status).toBe("written");
    if (result.health?.status !== "summarized") throw new Error("Completed planning must retain its actual health summary");
    expect(result.health.rows.reduce((sum, row) => sum + (row.article_requests ?? 0), 0)).toBe(count);
    expect(summarizePlan(result).planning_complete).toBe(true);
    expect(fixture.transport.requests).toHaveLength(count + 1);
    expect(fixture.transport.active).toBe(0);
    expect(fixture.inputs.settings.listener.max_stage_batches).toBe(capacity);
    expect(stageStore(fixture.inputs).isRunActive(result.context.run_id)).toBe(false);
    expect(collectionForRun(fixture.inputs, result.context.run_id)).toBeUndefined();
  } finally { await fixture.close(); }
}, 120000);
