/** Keep rejected offers out of HTTP work and assemble collection snapshots only at stage boundaries. */
import { expect, test } from "bun:test";
import { ParsedFeedBatchSchema } from "@idhazh/common-contracts";
import { createPlanApp } from "../src/api/server";
import { stageStore } from "../src/api/stage-store";
import { collectionForRun } from "../src/api/collection-operation";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";
import { randomUUID } from "node:crypto";
import { getCollection } from "../src/api/collection-operation";
import { createPlanTestServer } from "./plan-test-server";
import { runFeedPlan } from "../src/run-feed-plan";

test("large feeds retain every rejection without per-offer collection snapshots or rejected HTTP requests", async () => {
  const sources = [source(), source({ id: "second-feed", url: "https://news.example/second.xml" })];
  const fixture = await recordedPlan(sources);
  const admittedPerFeed = fixture.inputs.harvest.config.harvest.concurrency
    + fixture.inputs.settings.listener.parser_concurrency;
  const rejectedPerFeed = 512;
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
  let activeParses = 0;
  let peakParses = 0;
  const app = createPlanApp(fixture.inputs, fixture.runtime);
  let server: ReturnType<typeof Bun.serve>;
  server = Bun.serve({ hostname: "127.0.0.1", port: 0, idleTimeout: 0, async fetch(request) {
    const path = new URL(request.url).pathname;
    const parsing = path.endsWith("/parse");
    if (parsing) {
      activeParses++;
      peakParses = Math.max(peakParses, activeParses);
    }
    if (path.endsWith("/fetch")) {
      const body = await request.clone().json();
      if (body.fetch_item_type === "article") {
        articleFetches++;
        const collection = collectionForRun(fixture.inputs, "2026-10-21-700")!;
        const held = stageStore(fixture.inputs).read("parsed", collection.parsed_batch_id, ParsedFeedBatchSchema);
        if (held.candidates.length || held.offers.length || held.work_rows.some(row => row.article_requests)) snapshotsDuringWork++;
      }
    }
    try { return await app.fetch(request, { stage_origin: `http://127.0.0.1:${server.port}` }); }
    finally { if (parsing) activeParses--; }
  } });
  try {
    const response = await fetch(`http://127.0.0.1:${server.port}/api/2026-10-31/plan`, {
      method: "POST", headers: { "content-type": "application/json" }, body: "{}",
    });
    const result = await response.json();
    expect(response.status, JSON.stringify(result)).toBe(200);
    expect(result.planning_complete).toBe(true);
    expect(result.api_timings.filter((timing: { operation: string }) => timing.operation === "fetch")).toHaveLength(1);
    expect(result.api_timings.some((timing: { operation: string }) => timing.operation === "parse")).toBe(false);
    expect(articleFetches).toBe(admittedPerFeed * sources.length);
    expect(peakParses).toBeLessThanOrEqual(fixture.inputs.settings.listener.parser_concurrency);
    expect(snapshotsDuringWork).toBe(0);
    const parsed = stageStore(fixture.inputs).read("parsed", result.batches.parsed_batch_id, ParsedFeedBatchSchema);
    expect(parsed.candidates).toHaveLength(admittedPerFeed * sources.length);
    expect(parsed.offers.filter(offer => offer.state === "rejected")).toHaveLength(rejectedPerFeed * sources.length);
    expect(parsed.input_complete).toBe(true);
    expect(fixture.transport.requests.filter(request => /\/\d+$/.test(request.url.pathname)))
      .toHaveLength(admittedPerFeed * sources.length);
    expect(parsed.work_rows.reduce((sum, row) => sum + (row.article_requests ?? 0), 0))
      .toBe(admittedPerFeed * sources.length);
    expect(parsed.exclusions.reduce((sum, row) => sum + (row.reason_code === "REJECTED_AGE_EXCEEDS_MAX_TIER_ENVELOPE" ? row.count : 0), 0))
      .toBe(rejectedPerFeed * sources.length);
  } finally { await server.stop(true); await app.close(); await fixture.close(); }
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
  } finally { await app.close(); await fixture.close(); }
}, 120000);

test("cancellation drains owned requests and retains partial accounting without selecting unfinished work", async () => {
  const fixture = await recordedPlan();
  const cancellation = new AbortController();
  fixture.runtime.signal = cancellation.signal;
  fixture.transport.on_request = request => {
    if (request.url.pathname === "/story/") cancellation.abort(new Error("Recorded collection cancellation"));
  };
  try {
    const result = await runFeedPlan({}, fixture.inputs, fixture.runtime);
    expect(result.row.status).toBe("partial");
    expect(result.row.failure_code).not.toBeNull();
    expect(result.selected).toEqual([]);
    expect(result.batches.selection_batch_id).toBeUndefined();
    expect(result.files.feed_health_state?.status).toBe("written");
    expect(fixture.transport.active).toBe(0);
    const collection = collectionForRun(fixture.inputs, result.context.run_id)!;
    expect(collection.status).toBe("failed");
    expect(collection.signal.signal.aborted).toBe(true);
    const captured = stageStore(fixture.inputs).read("parsed", collection.parsed_batch_id, ParsedFeedBatchSchema);
    expect(captured.input_complete).toBe(false);
    expect(captured.work_rows.some(row => (row.feed_requests ?? 0) > 0)).toBe(true);
    expect(fixture.transport.peak).toBeLessThanOrEqual(fixture.inputs.harvest.config.harvest.concurrency);
  } finally { await fixture.close(); }
}, 120000);
