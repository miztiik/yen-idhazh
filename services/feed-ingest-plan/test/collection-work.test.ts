/** Keep rejected offers out of HTTP work and assemble collection snapshots only at stage boundaries. */
import { expect, test } from "bun:test";
import { ParsedFeedBatchSchema } from "@idhazh/common-contracts";
import { stageStore } from "../src/api/stage-store";
import { collectionForRun } from "../src/api/collection-operation";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";
import { randomUUID } from "node:crypto";
import { getCollection } from "../src/api/collection-operation";
import { createPlanTestServer } from "./plan-test-server";
import { collectRecordedFeeds } from "./collection-recordings";
import { FetchResponseSchema, ParseResponseSchema } from "../src/api/document-response.schema";
import { CancelledCollectionSchema, FinalizedCollectionSchema } from "../src/api/collection-contracts";

test("large feeds retain every rejection without per-offer collection snapshots or rejected HTTP requests", async () => {
  const sources = [source(), source({ id: "second-feed", url: "https://news.example/second.xml" })];
  const fixture = await recordedPlan(sources);
  const admittedPerFeed = 1;
  const rejectedPerFeed = 16;
  for (const feed of sources) {
    const entries = Array.from({ length: admittedPerFeed + rejectedPerFeed }, (_, index) => {
      const url = `https://news.example/${feed.id}/${index}`;
      if (index < admittedPerFeed) fixture.transport.recordings.responses[url] = [{ status: 200, fixture: "article" }];
      const date = index < admittedPerFeed ? "Wed, 21 Oct 2026 23:00:00 GMT" : "Wed, 01 Jan 2020 00:00:00 GMT";
      return `<item><title>Recorded science article ${index}</title><link>${url}</link><pubDate>${date}</pubDate></item>`;
    });
    fixture.transport.recordings.responses[feed.url] = [{
      status: 200, body: `<rss version="2.0"><channel><title>Recorded science</title>${entries.join("")}</channel></rss>`,
    }];
  }
  let articleFetches = 0;
  let snapshotsDuringWork = 0;
  fixture.transport.on_request = request => {
      if (/\/\d+$/.test(request.url.pathname)) {
        articleFetches++;
        const collection = collectionForRun(fixture.inputs, "2026-10-21-700")!;
        const held = stageStore(fixture.inputs).read("parsed", collection.parsed_batch_id, ParsedFeedBatchSchema);
        if (held.candidates.length || held.offers.length || held.work_rows.some(row => row.article_requests)) snapshotsDuringWork++;
      }
  };
  try {
    const { batch: parsed } = await collectRecordedFeeds(fixture.inputs, fixture.runtime);
    expect(articleFetches).toBe(admittedPerFeed * sources.length);
    expect(snapshotsDuringWork).toBe(0);
    expect(parsed.candidates).toHaveLength(admittedPerFeed * sources.length);
    expect(parsed.offers.filter(offer => offer.state === "rejected")).toHaveLength(rejectedPerFeed * sources.length);
    expect(parsed.input_complete).toBe(true);
    expect(fixture.transport.requests.filter(request => /\/\d+$/.test(request.url.pathname)))
      .toHaveLength(admittedPerFeed * sources.length);
    expect(parsed.work_rows.reduce((sum, row) => sum + (row.article_requests ?? 0), 0))
      .toBe(admittedPerFeed * sources.length);
    expect(parsed.exclusions.reduce((sum, row) => sum + (row.reason_code === "REJECTED_AGE_EXCEEDS_MAX_TIER_ENVELOPE" ? row.count : 0), 0))
      .toBe(rejectedPerFeed * sources.length);
  } finally { await fixture.close(); }
}, 120000);

test("explicit health reads capture current collection work without allowing premature selection", async () => {
  const fixture = await recordedPlan();
  const app = createPlanTestServer(fixture.inputs, fixture.runtime);
  const id = randomUUID();
  const post = (path: string, body: unknown) => app.request(`/api/2026-10-31/${path}`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
  });
  try {
    expect((await post("collections", { collection_id: id, request: {} })).status).toBe(200);
    const collection = getCollection(fixture.inputs, id);
    const fetchedResponse = await post("fetch", {
      request_id: randomUUID(), collection_id: id, feed_id: "recorded-news",
      correlation_id: collection.context.correlation_id, fetch_item_type: "feed",
    });
    expect(fetchedResponse.status).toBe(200);
    const fetched = await fetchedResponse.json();
    expect((await post("parse", {
      request_id: randomUUID(), fetch_request_id: fetched.fetch_request_id,
      article_id: fetched.article_id, correlation_id: collection.context.correlation_id,
    })).status).toBe(200);
    const healthResponse = await post("feed-health-state", { batch_id: collection.parsed_batch_id, action: "summarize" });
    expect(healthResponse.status).toBe(200);
    const health = await healthResponse.json();
    expect(health.rows[0]).toMatchObject({ feed_requests: 1, article_requests: 0, items: 2, check_result: "valid-feed" });
    const captured = stageStore(fixture.inputs).read("parsed", collection.parsed_batch_id, ParsedFeedBatchSchema);
    expect(captured.offers).toHaveLength(2);
    expect(captured.input_complete).toBe(false);
    expect((await post("select-articles", { batch_id: captured.batch_id })).status).toBe(409);
    expect((await post("collections/cancel", { collection_id: id })).status).toBe(200);
    expect(collection.signal.signal.aborted).toBe(true);
    expect(fixture.transport.requests.filter(request => request.url.pathname !== "/robots.txt")).toHaveLength(1);
    expect(collection.state.work.rows().some(row => row.checked_at !== null)).toBe(true);
    const outcome = FinalizedCollectionSchema.parse(await (await post("collections/finalize", {
      collection_id: id, failure_code: "PLANNER_EXECUTION_FAILED",
      collection_timing: { duration_ms: 1, status: "failed" },
    })).json());
    expect(outcome.status).toBe("partial");
  } finally { await app.close(); await fixture.close(); }
}, 120000);

test("cancellation drains owned requests and retains partial accounting without selecting unfinished work", async () => {
  const fixture = await recordedPlan();
  let notify!: () => void;
  const fetching = new Promise<void>(resolve => { notify = resolve; });
  fixture.transport.on_request = request => {
    if (request.url.pathname === "/timeout") notify();
  };
  fixture.transport.recordings.bodies.rss = `<rss version="2.0"><channel><title>Recorded cancellation</title>
    <item><title>Pending article</title><link>https://news.example/timeout</link></item></channel></rss>`;
  const app = createPlanTestServer(fixture.inputs, fixture.runtime);
  const id = randomUUID();
  const post = (path: string, body: unknown) => app.request(`/api/2026-10-31/${path}`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
  });
  let pending: Promise<Response> | undefined;
  let operationSettled = false;
  try {
    expect((await post("collections", { collection_id: id, request: {} })).status).toBe(200);
    const collection = getCollection(fixture.inputs, id);
    const fetched = FetchResponseSchema.parse(await (await post("fetch", {
      request_id: randomUUID(), collection_id: id, feed_id: "recorded-news",
      correlation_id: collection.context.correlation_id, fetch_item_type: "feed",
    })).json());
    const parsed = ParseResponseSchema.parse(await (await post("parse", {
      request_id: randomUUID(), fetch_request_id: fetched.fetch_request_id,
      article_id: fetched.article_id, correlation_id: fetched.correlation_id,
    })).json());
    if (parsed.fetch_item_type !== "feed") throw new Error("Expected a recorded feed offer");
    pending = post("fetch", {
      request_id: randomUUID(), feed_id: "recorded-news", fetch_item_type: "article",
      batch_id: parsed.batch_id, offer_id: parsed.offers[0]!.offer_id, correlation_id: collection.context.correlation_id,
    }).then(response => { operationSettled = true; return response; });
    await fetching;
    const cancellation = await post("collections/cancel", { collection_id: id });
    expect(cancellation.status).toBe(200);
    expect(operationSettled).toBe(true);
    expect(CancelledCollectionSchema.parse(await cancellation.json()).has_work).toBe(true);
    const cancelled = await pending;
    expect(cancelled.status).toBe(200);
    const terminal = FetchResponseSchema.parse(await cancelled.json());
    expect(terminal.failure).not.toBeNull();
    expect(terminal.body_sha256).toBeNull();
    expect(fixture.transport.requests.find(request => request.url.pathname === "/timeout")!.signal.aborted).toBe(true);
    expect(fixture.transport.active).toBe(0);
    expect(collection.status).toBe("failed");
    expect(collection.signal.signal.aborted).toBe(true);
    const captured = stageStore(fixture.inputs).read("parsed", collection.parsed_batch_id, ParsedFeedBatchSchema);
    expect(captured.input_complete).toBe(false);
    expect(captured.work_rows.some(row => (row.feed_requests ?? 0) > 0)).toBe(true);
    expect(fixture.transport.peak).toBeLessThanOrEqual(fixture.inputs.harvest.config.harvest.concurrency);
    expect((await post("select-articles", { batch_id: captured.batch_id })).status).toBe(409);
    const outcome = FinalizedCollectionSchema.parse(await (await post("collections/finalize", {
      collection_id: id, failure_code: "PLANNER_EXECUTION_FAILED",
      collection_timing: { duration_ms: 3, status: "failed" },
    })).json());
    expect(outcome.status).toBe("partial");
    expect(outcome.api_timings.filter(timing => timing.operation === "fetch")).toEqual([
      { operation: "fetch", duration_ms: 3, status: "failed" },
    ]);
  } finally {
    try { await pending; }
    finally {
      try { await app.close(); }
      finally { await fixture.close(); }
    }
  }
}, 120000);
