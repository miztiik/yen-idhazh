/** Do unfinished collections refuse selection and prevent duplicate feed claims over real HTTP? */
import { expect, test } from "bun:test";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { createPlanTestServer } from "./plan-test-server";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";
import { getCollection } from "../src/api/collection-operation";
import {
  CancelledCollectionSchema, CollectionExistsResponseSchema, FinalizedCollectionSchema,
} from "../src/api/collection-contracts";
import { rawDocumentContentsPath } from "../src/selected-artifact-path";
import { FetchResponseSchema } from "../src/api/document-response.schema";
import { createRootContext, PLANNER_API_PATHS, PLANNER_API_PREFIX, writeTraceContext } from "@idhazh/common-contracts";
import { operationLink } from "../src/api/operation-context";

test("unfinished or cancelled collection cannot be selected and a feed cannot be claimed twice", async () => {
  const fixture = await recordedPlan();
  const app = createPlanTestServer(fixture.inputs, fixture.runtime);
  const caller = createRootContext();
  const post = (body: unknown) => ({ method: "POST", headers: { "content-type": "application/json", ...writeTraceContext(caller) }, body: JSON.stringify(body) });
  const prefix = PLANNER_API_PREFIX;
  const id = caller.traceId;
  try {
    const begun = await app.request(`${prefix}${PLANNER_API_PATHS.startCollection}`, post({ request: {} }));
    expect(begun.status).toBe(200);
    const collection = getCollection(fixture.inputs, id);
    expect((await app.request(`${prefix}${PLANNER_API_PATHS.completeCollection}`, post({ traceId: id }))).status).toBe(409);
    expect((await app.request(`${prefix}${PLANNER_API_PATHS.selectArticles}`, post({ links: [operationLink(collection.context)] }))).status).toBe(404);
    const body = { traceId: id, feed_id: "recorded-news", fetch_item_type: "feed" };
    const fetched = await app.request(`${prefix}${PLANNER_API_PATHS.fetch}`, post(body));
    expect(fetched.status, await fetched.clone().text()).toBe(200);
    expect((await app.request(`${prefix}${PLANNER_API_PATHS.fetch}`, post(body))).status).toBe(409);
    const cancellation = await app.request(`${prefix}${PLANNER_API_PATHS.cancelCollection}`, post({ traceId: id }));
    expect(cancellation.status).toBe(200);
    const cancelled = CancelledCollectionSchema.parse(await cancellation.json());
    expect((await app.request(`${prefix}${PLANNER_API_PATHS.selectArticles}`, post({ links: [operationLink(cancelled)] }))).status).toBe(409);
    expect(collection.signal.signal.aborted).toBe(true);
    expect((await app.request(`${prefix}${PLANNER_API_PATHS.completeCollection}`, post({ traceId: id }))).status).toBe(409);
  } finally { await app.close(); await fixture.close(); }
}, 120000);

test("standalone and collection fetches share their domain queue", async () => {
  const fixture = await recordedPlan([
    source({ id: "recorded-news", url: "https://news.example/feed.xml" }),
    source({ id: "recorded-second", url: "https://news.example/second-feed.xml" }),
  ]);
  fixture.inputs.harvest.config.harvest.request_pacing = {
    enabled: true, domain_delay_ms: 50, publisher_delay_ms: 0, jitter_ms: 0,
  };
  fixture.transport.recordings.responses["https://news.example/second-feed.xml"] = [{
    status: 200, fixture: "rss",
  }];
  const app = createPlanTestServer(fixture.inputs, fixture.runtime);
  const caller = createRootContext();
  const post = (body: unknown) => ({ method: "POST", headers: { "content-type": "application/json", ...writeTraceContext(caller) }, body: JSON.stringify(body) });
  const prefix = PLANNER_API_PREFIX;
  const collectionId = caller.traceId;
  const collection = await app.request(`${prefix}${PLANNER_API_PATHS.startCollection}`, post({ request: {} }));
  expect(collection.status).toBe(200);
  const starts: number[] = [];
  let resolveFirstDispatch!: () => void;
  const firstDispatch = new Promise<void>(resolve => { resolveFirstDispatch = resolve; });
  fixture.transport.on_request = () => {
    starts.push(performance.now());
    if (starts.length === 1) resolveFirstDispatch();
  };
  const pending: Promise<Response>[] = [];
  try {
    const standalone = app.request(`${prefix}${PLANNER_API_PATHS.fetch}`, post({
      feed_id: "recorded-news", fetch_item_type: "feed",
    }));
    pending.push(standalone);
    await Promise.race([firstDispatch, standalone.then(() => { throw new Error("Standalone fetch ended before dispatch"); })]);
    pending.push(app.request(`${prefix}${PLANNER_API_PATHS.fetch}`, post({
      traceId: collectionId, feed_id: "recorded-second", fetch_item_type: "feed",
    })));
    const responses = await Promise.all(pending);
    expect(responses.map(response => response.status)).toEqual([200, 200]);
    expect(fixture.transport.requests.map(request => request.url.href)).toEqual([
      "https://news.example/feed.xml", "https://news.example/second-feed.xml",
    ]);
    expect(fixture.transport.peak).toBe(1);
    expect(starts).toHaveLength(2);
    for (let index = 1; index < starts.length; index++) {
      expect(starts[index]! - starts[index - 1]!).toBeGreaterThanOrEqual(40);
    }
  } finally {
    await Promise.allSettled(pending);
    await app.request(`${prefix}${PLANNER_API_PATHS.cancelCollection}`, post({ traceId: collectionId }));
    await app.close();
    await fixture.close();
  }
}, 120000);

test("active execution input remains pinned and an expired result cannot reopen historical files", async () => {
  const fixture = await recordedPlan();
  fixture.inputs.settings.listener.max_stage_batches = 1;
  const { run_number: _run, ...runtime } = fixture.runtime;
  const app = createPlanTestServer(fixture.inputs, runtime);
  const caller = createRootContext();
  const nextCaller = createRootContext();
  const post = (body: unknown, context = caller) => ({ method: "POST",
    headers: { "content-type": "application/json", ...writeTraceContext(context) }, body: JSON.stringify(body) });
  const prefix = PLANNER_API_PREFIX;
  const first = caller.traceId;
  const second = nextCaller.traceId;
  try {
    expect((await app.request(`${prefix}${PLANNER_API_PATHS.startCollection}`, post({ request: {} }))).status).toBe(200);
    expect(CollectionExistsResponseSchema.parse(await (await app.request(
      `${prefix}${PLANNER_API_PATHS.checkCollection}`, post({ traceId: first }),
    )).json())).toMatchObject({ traceId: first, exists: true });
    const original = getCollection(fixture.inputs, first);
    const baseline = original.state.baseline;
    const blocked = await app.request(`${prefix}${PLANNER_API_PATHS.startCollection}`, post({ request: {} }, nextCaller));
    expect(blocked.ok).toBe(false);
    expect(await blocked.json()).toMatchObject({ code: "REQUEST_BUSY" });
    expect(original.state.baseline).toBe(baseline);
    const cancellation = await app.request(`${prefix}${PLANNER_API_PATHS.cancelCollection}`, post({ traceId: first }));
    expect(cancellation.status).toBe(200);
    const cancelled = CancelledCollectionSchema.parse(await cancellation.json());
    const outcome = await app.request(`${prefix}${PLANNER_API_PATHS.finalizeCollection}`, post({
      traceId: first, failure_code: "PLANNER_EXECUTION_FAILED",
      collection_timing: { duration_ms: 0, status: "failed" },
    }));
    expect(FinalizedCollectionSchema.parse(await outcome.json()).status).toBe("failed");
    const released = await app.request(`${prefix}${PLANNER_API_PATHS.releaseCollection}`, post({
      run_id: original.context.run_id, attempt: original.context.writer.attempt,
    }));
    expect(await released.json()).toMatchObject({ released: true });
    expect(CollectionExistsResponseSchema.parse(await (await app.request(
      `${prefix}${PLANNER_API_PATHS.checkCollection}`, post({ traceId: first }),
    )).json())).toMatchObject({ traceId: first, exists: false });
    expect((await app.request(`${prefix}${PLANNER_API_PATHS.startCollection}`, post({ request: {} }, nextCaller))).status).toBe(200);
    expect((await app.request(`${prefix}${PLANNER_API_PATHS.cancelCollection}`, post({ traceId: second }))).status).toBe(200);
    const expired = await app.request(`${prefix}${PLANNER_API_PATHS.selectArticles}`, post({ links: [operationLink(cancelled)] }));
    expect(expired.status).toBe(404);
    expect(await expired.json()).toMatchObject({ code: "ARTIFACT_NOT_FOUND" });
    expect(fixture.transport.requests).toEqual([]);
  } finally { await app.close(); await fixture.close(); }
});

test("final status uses checked work, not carry rows, and raw finish errors keep the earlier cause", async () => {
  const fixture = await recordedPlan();
  const app = createPlanTestServer(fixture.inputs, fixture.runtime);
  const caller = createRootContext();
  const post = (body: unknown, context = caller) => ({ method: "POST",
    headers: { "content-type": "application/json", ...writeTraceContext(context) }, body: JSON.stringify(body) });
  const prefix = PLANNER_API_PREFIX;
  const id = caller.traceId;
  try {
    expect((await app.request(`${prefix}${PLANNER_API_PATHS.startCollection}`, post({ request: {} }))).status).toBe(200);
    const collection = getCollection(fixture.inputs, id);
    const cancelled = CancelledCollectionSchema.parse(await (await app.request(
      `${prefix}${PLANNER_API_PATHS.cancelCollection}`, post({ traceId: id }),
    )).json());
    expect(cancelled.has_work).toBe(true);
    expect(collection.state.work.rows().every(row => row.checked_at === null)).toBe(true);
    const invalid = await app.request(`${prefix}${PLANNER_API_PATHS.finalizeCollection}`, post({
      traceId: id, failure_code: "PLANNER_EXECUTION_FAILED",
      collection_timing: { duration_ms: "0", status: "failed" },
    }));
    expect(invalid.status).toBe(400);
    const outcome = FinalizedCollectionSchema.parse(await (await app.request(`${prefix}${PLANNER_API_PATHS.finalizeCollection}`, post({
      traceId: id, failure_code: "PLANNER_EXECUTION_FAILED",
      collection_timing: { duration_ms: 0, status: "failed" },
    }))).json());
    expect(outcome).toMatchObject({ status: "failed", failure_code: "PLANNER_EXECUTION_FAILED" });
    expect(outcome.api_timings.filter(timing => timing.operation === "fetch")).toEqual([
      { operation: "fetch", duration_ms: 0, status: "failed" },
    ]);
    await app.request(`${prefix}${PLANNER_API_PATHS.releaseCollection}`, post({
      run_id: collection.context.run_id, attempt: collection.context.writer.attempt,
    }));

    fixture.inputs.settings.dump_raw_document_contents = true;
    fixture.runtime.run_number = "701";
    const feed = fixture.inputs.harvest.sources[0]!;
    fixture.transport.recordings.responses[feed.url] = [{ status: 503, body: "recorded failure" }];
    const nextCaller = createRootContext();
    const secondId = nextCaller.traceId;
    expect((await app.request(`${prefix}${PLANNER_API_PATHS.startCollection}`, post({ request: {} }, nextCaller))).status).toBe(200);
    const second = getCollection(fixture.inputs, secondId);
    expect(second.context.run_id).not.toBe(collection.context.run_id);
    const rawPath = rawDocumentContentsPath(fixture.inputs.settings.inputs.artifact_root, second.state.context);
    await mkdir(join(fixture.inputs.root, ...rawPath.split("/")), { recursive: true });
    const fetched = FetchResponseSchema.parse(await (await app.request(`${prefix}${PLANNER_API_PATHS.fetch}`, post({
      traceId: secondId, feed_id: feed.id, fetch_item_type: "feed",
    }))).json());
    expect(fetched.failure).not.toBeNull();
    await app.request(`${prefix}${PLANNER_API_PATHS.cancelCollection}`, post({ traceId: secondId }));
    const priorCause = FinalizedCollectionSchema.parse(await (await app.request(`${prefix}${PLANNER_API_PATHS.finalizeCollection}`, post({
      traceId: secondId, failure_code: "EARLIER_FETCH_FAILURE",
      collection_timing: { duration_ms: 1, status: "failed" },
    }))).json());
    expect(priorCause.failure_code).toBe("EARLIER_FETCH_FAILURE");
  } finally { await app.close(); await fixture.close(); }
}, 120000);
