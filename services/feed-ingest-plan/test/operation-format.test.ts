/** Refuse old indexed receipts without changing them or repeating recorded source work. */
import { expect, test } from "bun:test";
import { Database } from "bun:sqlite";
import { join } from "node:path";
import { randomUUID } from "node:crypto";
import { PLANNER_OPERATION_VERSION } from "@idhazh/common-contracts";
import { recordedPlan } from "./plan-recordings";
import { createPlanTestServer } from "./plan-test-server";
import { openOperationStore } from "../src/api/operation-store";

test("current replay survives while old or unstamped receipts and documents refuse explicitly", async () => {
  const fixture = await recordedPlan();
  const server = createPlanTestServer(fixture.inputs, fixture.runtime);
  const request_id = randomUUID();
  const body = { request_id, correlation_id: randomUUID(), feed_id: fixture.inputs.harvest.sources[0]!.id, fetch_item_type: "feed" };
  try {
    const init = { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) };
    const fetched = await server.request("/api/2026-10-31/fetch", init);
    expect(fetched.status).toBe(200);
    const count = fixture.transport.requests.length;
    expect(await (await server.request("/api/2026-10-31/fetch", init)).json()).toEqual(await fetched.json());
    expect(fixture.transport.requests.length).toBe(count);
    const database = new Database(join(fixture.inputs.outputRoot, "planner-operations.sqlite"));
    const read = database.query<{ record: string }, [string]>("SELECT record FROM operations WHERE request_id = ?");
    const write = database.query("UPDATE operations SET record = ? WHERE request_id = ?");
    const original = JSON.parse(read.get(request_id)!.record);
    try {
      for (const version of ["2026-10-28", "2026-10-29", undefined]) {
        const saved = JSON.stringify({ ...original, version });
        write.run(saved, request_id);
        const store = await openOperationStore(fixture.inputs.outputRoot);
        try {
          expect(() => store.get(request_id)).toThrow("current receipt format");
        } finally { store.close(); }
        expect(read.get(request_id)!.record).toBe(saved);
      }
      const saved = JSON.stringify({ ...original, version: PLANNER_OPERATION_VERSION,
        artifact: { ...original.artifact, version: "2026-10-30" } });
      write.run(saved, request_id);
      const store = await openOperationStore(fixture.inputs.outputRoot);
      try { expect(() => store.get(request_id)).toThrow("current document format"); }
      finally { store.close(); }
      expect(read.get(request_id)!.record).toBe(saved);
      expect(fixture.transport.requests.length).toBe(count);
    } finally { database.close(); }
  } finally { await server.close(); await fixture.close(); }
});
