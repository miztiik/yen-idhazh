/** Does the workflow client use an existing listener without taking over its lifetime? */
import { expect, test } from "bun:test";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { servePlan } from "../src/api/server";
import { requestPlannerHttp } from "../scripts/feed-ingest-plan-http-client";
import { recordedPlan } from "./plan-recordings";

test("the client retains verified output and batch health while its caller keeps the listener", async () => {
  const fixture = await recordedPlan();
  fixture.inputs.settings.listener.port = 0;
  const server = servePlan(fixture.inputs, fixture.runtime);
  try {
    const directory = join(fixture.directory, "evidence");
    await mkdir(directory);
    const base = `http://${fixture.inputs.settings.listener.hostname}:${server.port}/api/2026-10-20`;
    const result = await requestPlannerHttp(base, fixture.inputs, { article_limit: 1 }, directory);
    expect(result.http_status).toBe(200);
    expect(result.summary.planning_complete).toBe(true);
    expect(result.summary.selected_count).toBe(1);
    expect(result.outputs.planning_complete).toBe("true");
    expect(result.health?.rows).toHaveLength(1);
    expect(await Bun.file(join(directory, "response.json")).json()).toEqual(result.summary);
    expect(await Bun.file(join(directory, "health.json")).json()).toEqual(result.health);
    expect((await fetch(`${base}/health`)).status).toBe(200);
  } finally { await server.stop(true); await fixture.close(); }
});

test("a disabled listener fails before planning and remains under its caller's control", async () => {
  const fixture = await recordedPlan();
  fixture.inputs.settings.listener.port = 0;
  fixture.inputs.settings.enabled = false;
  const server = servePlan(fixture.inputs, fixture.runtime);
  try {
    const directory = join(fixture.directory, "evidence");
    await mkdir(directory);
    const base = `http://${fixture.inputs.settings.listener.hostname}:${server.port}/api/2026-10-20`;
    await expect(requestPlannerHttp(base, fixture.inputs, {}, directory))
      .rejects.toThrow("Planner listener is not enabled and responsive");
    expect(fixture.transport.requests).toHaveLength(0);
    expect(await Bun.file(join(directory, "response.json")).exists()).toBe(false);
    expect((await fetch(`${base}/health`)).status).toBe(200);
  } finally { await server.stop(true); await fixture.close(); }
});
