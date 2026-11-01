/** Do unfinished collections refuse selection and prevent duplicate feed claims over real HTTP? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { createPlanTestServer } from "./plan-test-server";
import { recordedPlan } from "./plan-recordings";
import { getCollection } from "../src/api/collection-operation";
import {
  CancelledCollectionSchema, CollectionExistsResponseSchema, FinalizedCollectionSchema,
} from "../src/api/collection-contracts";
import { rawDocumentContentsPath } from "../src/selected-artifact-path";
import { FetchResponseSchema } from "../src/api/document-response.schema";

test("unfinished or cancelled collection cannot be selected and a feed cannot be claimed twice", async () => {
  const fixture = await recordedPlan();
  const app = createPlanTestServer(fixture.inputs, fixture.runtime);
  const post = (body: unknown) => ({ method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  const prefix = "/api/2026-10-31";
  const id = randomUUID();
  try {
    const begun = await app.request(`${prefix}/collections`, post({ collection_id: id, request: {} }));
    expect(begun.status).toBe(200);
    const collection = getCollection(fixture.inputs, id);
    expect((await app.request(`${prefix}/collections/complete`, post({ collection_id: id }))).status).toBe(409);
    expect((await app.request(`${prefix}/select-articles`, post({ batch_id: collection.parsed_batch_id }))).status).toBe(409);
    const body = { request_id: randomUUID(), collection_id: id, feed_id: "recorded-news",
      correlation_id: collection.context.correlation_id, fetch_item_type: "feed" };
    const fetched = await app.request(`${prefix}/fetch`, post(body));
    expect(fetched.status, await fetched.clone().text()).toBe(200);
    expect((await app.request(`${prefix}/fetch`, post({ ...body, request_id: randomUUID() }))).status).toBe(409);
    expect((await app.request(`${prefix}/collections/cancel`, post({ collection_id: id }))).status).toBe(200);
    expect(collection.signal.signal.aborted).toBe(true);
    expect((await app.request(`${prefix}/collections/complete`, post({ collection_id: id }))).status).toBe(409);
  } finally { await app.close(); await fixture.close(); }
}, 120000);

test("active execution input remains pinned and an expired batch cannot reopen historical files", async () => {
  const fixture = await recordedPlan();
  fixture.inputs.settings.listener.max_stage_batches = 1;
  const { run_number: _run, ...runtime } = fixture.runtime;
  const app = createPlanTestServer(fixture.inputs, runtime);
  const post = (body: unknown) => ({ method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  const prefix = "/api/2026-10-31";
  const first = randomUUID();
  const second = randomUUID();
  try {
    expect((await app.request(`${prefix}/collections`, post({ collection_id: first, request: {} }))).status).toBe(200);
    expect(CollectionExistsResponseSchema.parse(await (await app.request(
      `${prefix}/collections/exists`, post({ collection_id: first }),
    )).json())).toMatchObject({ collection_id: first, exists: true });
    const original = getCollection(fixture.inputs, first);
    const baseline = original.state.baseline;
    const blocked = await app.request(`${prefix}/collections`, post({ collection_id: second, request: {} }));
    expect(blocked.ok).toBe(false);
    expect(await blocked.json()).toMatchObject({ code: "REQUEST_BUSY" });
    expect(original.state.baseline).toBe(baseline);
    expect((await app.request(`${prefix}/collections/cancel`, post({ collection_id: first }))).status).toBe(200);
    const outcome = await app.request(`${prefix}/collections/finalize`, post({
      collection_id: first, failure_code: "PLANNER_EXECUTION_FAILED",
      collection_timing: { duration_ms: 0, status: "failed" },
    }));
    expect(FinalizedCollectionSchema.parse(await outcome.json()).status).toBe("failed");
    const released = await app.request(`${prefix}/collections/release`, post({
      run_id: original.context.run_id, attempt: original.context.writer.attempt,
    }));
    expect(await released.json()).toMatchObject({ released: true });
    expect(CollectionExistsResponseSchema.parse(await (await app.request(
      `${prefix}/collections/exists`, post({ collection_id: first }),
    )).json())).toMatchObject({ collection_id: first, exists: false });
    expect((await app.request(`${prefix}/collections`, post({ collection_id: second, request: {} }))).status).toBe(200);
    const expired = await app.request(`${prefix}/select-articles`, post({ batch_id: original.parsed_batch_id }));
    expect(expired.status).toBe(404);
    expect(await expired.json()).toMatchObject({ code: "ARTIFACT_NOT_FOUND" });
    expect(fixture.transport.requests).toEqual([]);
  } finally { await app.close(); await fixture.close(); }
});

test("final status uses checked work, not carry rows, and raw finish errors keep the earlier cause", async () => {
  const fixture = await recordedPlan();
  const app = createPlanTestServer(fixture.inputs, fixture.runtime);
  const post = (body: unknown) => ({ method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  const prefix = "/api/2026-10-31";
  const id = randomUUID();
  try {
    expect((await app.request(`${prefix}/collections`, post({ collection_id: id, request: {} }))).status).toBe(200);
    const collection = getCollection(fixture.inputs, id);
    const cancelled = CancelledCollectionSchema.parse(await (await app.request(
      `${prefix}/collections/cancel`, post({ collection_id: id }),
    )).json());
    expect(cancelled.has_work).toBe(true);
    expect(collection.state.work.rows().every(row => row.checked_at === null)).toBe(true);
    const invalid = await app.request(`${prefix}/collections/finalize`, post({
      collection_id: id, failure_code: "PLANNER_EXECUTION_FAILED",
      collection_timing: { duration_ms: "0", status: "failed" },
    }));
    expect(invalid.status).toBe(400);
    const outcome = FinalizedCollectionSchema.parse(await (await app.request(`${prefix}/collections/finalize`, post({
      collection_id: id, failure_code: "PLANNER_EXECUTION_FAILED",
      collection_timing: { duration_ms: 0, status: "failed" },
    }))).json());
    expect(outcome).toMatchObject({ status: "failed", failure_code: "PLANNER_EXECUTION_FAILED" });
    expect(outcome.api_timings.filter(timing => timing.operation === "fetch")).toEqual([
      { operation: "fetch", duration_ms: 0, status: "failed" },
    ]);
    await app.request(`${prefix}/collections/release`, post({
      run_id: collection.context.run_id, attempt: collection.context.writer.attempt,
    }));

    fixture.inputs.settings.dump_raw_document_contents = true;
    const feed = fixture.inputs.harvest.sources[0]!;
    fixture.transport.recordings.responses[feed.url] = [{ status: 503, body: "recorded failure" }];
    const secondId = randomUUID();
    expect((await app.request(`${prefix}/collections`, post({ collection_id: secondId, request: {} }))).status).toBe(200);
    const second = getCollection(fixture.inputs, secondId);
    const rawPath = rawDocumentContentsPath(fixture.inputs.settings.inputs.artifact_root, second.state.context);
    await mkdir(join(fixture.inputs.root, ...rawPath.split("/")), { recursive: true });
    const fetched = FetchResponseSchema.parse(await (await app.request(`${prefix}/fetch`, post({
      request_id: randomUUID(), collection_id: secondId, feed_id: feed.id,
      correlation_id: second.context.correlation_id, fetch_item_type: "feed",
    }))).json());
    expect(fetched.failure).not.toBeNull();
    await app.request(`${prefix}/collections/cancel`, post({ collection_id: secondId }));
    const priorCause = FinalizedCollectionSchema.parse(await (await app.request(`${prefix}/collections/finalize`, post({
      collection_id: secondId, failure_code: "EARLIER_FETCH_FAILURE",
      collection_timing: { duration_ms: 1, status: "failed" },
    }))).json());
    expect(priorCause.failure_code).toBe("EARLIER_FETCH_FAILURE");
  } finally { await app.close(); await fixture.close(); }
}, 120000);
