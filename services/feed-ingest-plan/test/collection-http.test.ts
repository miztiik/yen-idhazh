/** Do unfinished collections refuse selection and prevent duplicate feed claims over real HTTP? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { createPlanTestServer } from "./plan-test-server";
import { recordedPlan } from "./plan-recordings";
import { getCollection } from "../src/api/collection-operation";

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
    const original = getCollection(fixture.inputs, first);
    const baseline = original.state.baseline;
    const blocked = await app.request(`${prefix}/collections`, post({ collection_id: second, request: {} }));
    expect(blocked.ok).toBe(false);
    expect(await blocked.json()).toMatchObject({ code: "REQUEST_BUSY" });
    expect(original.state.baseline).toBe(baseline);
    expect((await app.request(`${prefix}/collections/cancel`, post({ collection_id: first }))).status).toBe(200);
    expect((await app.request(`${prefix}/collections`, post({ collection_id: second, request: {} }))).status).toBe(200);
    const expired = await app.request(`${prefix}/select-articles`, post({ batch_id: original.parsed_batch_id }));
    expect(expired.status).toBe(404);
    expect(await expired.json()).toMatchObject({ code: "ARTIFACT_NOT_FOUND" });
    expect(fixture.transport.requests).toEqual([]);
  } finally { await app.close(); await fixture.close(); }
});
