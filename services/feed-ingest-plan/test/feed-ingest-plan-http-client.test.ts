/** Does the workflow client use an existing listener without taking over its lifetime? */
import { expect, test } from "bun:test";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { createPlanApp, servePlan } from "../src/api/server";
import { requestPlannerHttp } from "../scripts/feed-ingest-plan-http-client";
import { recordedPlan } from "./plan-recordings";
import { collectionForRun } from "../src/api/collection-operation";

test("a disabled listener fails before planning and remains under its caller's control", async () => {
  const fixture = await recordedPlan();
  fixture.inputs.settings.listener.port = 0;
  fixture.inputs.settings.enabled = false;
  const server = servePlan(fixture.inputs, fixture.runtime);
  try {
    const directory = join(fixture.directory, "evidence");
    await mkdir(directory);
    const base = `http://${fixture.inputs.settings.listener.hostname}:${server.port}/api/2026-10-31`;
    await expect(requestPlannerHttp(base, fixture.inputs, {}, directory))
      .rejects.toThrow("Planner listener is not enabled and responsive");
    expect(fixture.transport.requests).toHaveLength(0);
    expect(await Bun.file(join(directory, "response.json")).exists()).toBe(false);
    expect((await fetch(`${base}/health`)).status).toBe(200);
  } finally { await server.stop(true); await fixture.close(); }
});

test("the workflow reads health before releasing the finalized collection", async () => {
  const fixture = await recordedPlan();
  fixture.inputs.settings.listener.port = 0;
  const app = createPlanApp(fixture.inputs, fixture.runtime);
  const calls: { path: string; body: unknown }[] = [];
  const server = Bun.serve({
    hostname: "127.0.0.1", port: 0, idleTimeout: 0,
    async fetch(request, server) {
      let body: unknown;
      try { body = await request.clone().json(); } catch {}
      calls.push({ path: new URL(request.url).pathname, body });
      return app.fetch(request, { beginPlanning: () => server.timeout(request, 0),
        stage_origin: `http://127.0.0.1:${server.port}` });
    },
  });
  try {
    const directory = join(fixture.directory, "evidence");
    await mkdir(directory);
    const base = `http://127.0.0.1:${server.port}/api/2026-10-31`;
    const result = await requestPlannerHttp(base, fixture.inputs, {}, directory);
    expect(result.health).toBeDefined();
    const summary = calls.findIndex(call => call.path.endsWith("/feed-health-state")
      && typeof call.body === "object" && call.body !== null && "action" in call.body && call.body.action === "summarize");
    const release = calls.findIndex(call => call.path.endsWith("/collections/release"));
    expect(summary).toBeGreaterThanOrEqual(0);
    expect(release).toBeGreaterThan(summary);
    expect(collectionForRun(fixture.inputs, result.summary.run_id)).toBeUndefined();
  } finally { await server.stop(true); await app.close(); await fixture.close(); }
}, 120000);
