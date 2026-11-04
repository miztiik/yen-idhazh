/** Does the workflow client use an existing listener without taking over its lifetime? */
import { expect, test } from "bun:test";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { createPlanApp, servePlan } from "../src/api/server";
import { requestPlannerHttp } from "../scripts/feed-ingest-plan-http-client";
import { recordedPlan } from "./plan-recordings";
import { collectionForRun } from "../src/api/collection-operation";
import {
  PLANNER_API_PREFIX, PlanRunRowContract, PlannerHealthOutcomeSchema, PlannerRunResponseSchema, PlannerSavedResponseSchema,
} from "@idhazh/common-contracts";
import { FeedHealthStateUpdateResponseSchema } from "../src/api/feed-health-state.schema";
import { readPlannerParquet } from "@idhazh/ledger-file-writer";
import { PersistenceResponseSchema } from "../src/api/stage-response.schema";
import { stageStore } from "../src/api/stage-store";

test("a disabled listener fails before planning and remains under its caller's control", async () => {
  const fixture = await recordedPlan();
  fixture.inputs.settings.listener.port = 0;
  fixture.inputs.settings.enabled = false;
  const server = servePlan(fixture.inputs, fixture.runtime);
  try {
    const directory = join(fixture.directory, "evidence");
    await mkdir(directory);
    const base = `http://${fixture.inputs.settings.listener.hostname}:${server.port}${PLANNER_API_PREFIX}`;
    await expect(requestPlannerHttp(base, fixture.inputs, {}, directory))
      .rejects.toThrow("Planner listener is not enabled and responsive");
    expect(fixture.transport.requests).toHaveLength(0);
    expect(await Bun.file(join(directory, "response.json")).exists()).toBe(false);
    expect((await fetch(`${base}/health`)).status).toBe(200);
  } finally { await server.stop(true); await fixture.close(); }
});

test("the complete HTTP result contains its report and releases work before client-side saving", async () => {
  const fixture = await recordedPlan();
  fixture.inputs.settings.listener.port = 0;
  const app = createPlanApp(fixture.inputs, fixture.runtime);
  const calls: { path: string; body: unknown }[] = [];
  let callsAtPlanReply: number | undefined;
  const server = Bun.serve({
    hostname: "127.0.0.1", port: 0, idleTimeout: 0,
    async fetch(request, server) {
      let body: unknown;
      try { body = await request.clone().json(); } catch {}
      calls.push({ path: new URL(request.url).pathname, body });
      const response = await app.fetch(request, { beginPlanning: () => server.timeout(request, 0),
        stage_origin: `http://127.0.0.1:${server.port}` });
      if (new URL(request.url).pathname.endsWith("/plan")) callsAtPlanReply = calls.length;
      return response;
    },
  });
  try {
    const directory = join(fixture.directory, "evidence");
    await mkdir(directory);
    const base = `http://127.0.0.1:${server.port}${PLANNER_API_PREFIX}`;
    const result = await requestPlannerHttp(base, fixture.inputs, {}, directory);
    expect(result.health).toBeDefined();
    expect(fixture.transport.requests.map(request => request.url.href).sort()).toEqual([
      "https://news.example/feed.xml", "https://news.example/story/?utm_source=feed&b=2&a=1", "https://news.example/second",
    ].sort());
    const health = PlannerHealthOutcomeSchema.parse(result.health);
    if (health === null || health.status !== "summarized") throw new Error("The recorded plan must return its actual health summary");
    expect(result.summary.health).toEqual(health);
    expect(health.rows.reduce((sum, row) => sum + row.feed_requests!, 0)).toBe(1);
    expect(health.rows.reduce((sum, row) => sum + row.article_requests!, 0)).toBe(2);
    expect(health.rows.every(row => row.counts_complete)).toBe(true);
    for (const row of health.rows) {
      expect(row).not.toHaveProperty("permission");
      expect(row).not.toHaveProperty("robots_requests");
    }
    const summary = calls.findIndex(call => call.path.endsWith("/feed-health-state")
      && typeof call.body === "object" && call.body !== null && "action" in call.body && call.body.action === "summarize");
    const release = calls.findIndex(call => call.path.endsWith("/collections/release"));
    expect(summary).toBeGreaterThanOrEqual(0);
    expect(release).toBeGreaterThan(summary);
    expect(calls.length).toBe(callsAtPlanReply!);
    expect(collectionForRun(fixture.inputs, result.summary.run_id)).toBeUndefined();
    await server.stop(true);
    expect(PlannerRunResponseSchema.parse(await Bun.file(join(directory, "response.json")).json())).toEqual(result.summary);
    expect(FeedHealthStateUpdateResponseSchema.parse(await Bun.file(join(directory, "health.json")).json())).toEqual(health);
  } finally { await server.stop(true); await app.close(); await fixture.close(); }
}, 120000);

test("real report, recording and lost-release-response failures retain independent completed output", async () => {
  for (const mode of ["release", "report-and-release", "record-and-release"] as const) {
    const fixture = await recordedPlan();
    const app = createPlanApp(fixture.inputs, fixture.runtime);
    const order: string[] = [];
    let stopping: Promise<void> | undefined;
    let persisted: ReturnType<typeof PersistenceResponseSchema.parse> | undefined;
    const emit = fixture.runtime.log!;
    fixture.runtime.log = event => {
      emit(event);
      if (event.data.operation === "plan" && event.data.phase !== "started") order.push("terminal");
    };
    const stages = Bun.serve({
      hostname: "127.0.0.1", port: 0, idleTimeout: 0,
      async fetch(request, server) {
        const path = new URL(request.url).pathname;
        const body = await request.clone().json();
        const previous = fixture.runtime.observation_clock;
        const summary = path.endsWith("/feed-health-state") && body.action === "summarize";
        if (summary) {
          order.push("report");
          if (mode === "report-and-release") fixture.runtime.observation_clock = () => new Date(Number.NaN);
        }
        let response: Response;
        try { response = await app.fetch(request); }
        finally {
          if (previous === undefined) delete fixture.runtime.observation_clock;
          else fixture.runtime.observation_clock = previous;
        }
        if (response.ok && path.endsWith("/persist-selected-articles")) {
          persisted = PersistenceResponseSchema.parse(await response.clone().json());
        }
        if (path.endsWith("/collections/release")) {
          expect(response.status).toBe(200);
          order.push("release");
          stopping = server.stop(true);
        }
        return response;
      },
    });
    const listener = Bun.serve({
      hostname: "127.0.0.1", port: 0, idleTimeout: 0,
      fetch: request => app.fetch(request, { stage_origin: `http://127.0.0.1:${stages.port}` }),
    });
    try {
      if (mode === "record-and-release") {
        const parent = join(fixture.inputs.outputRoot, "raw", "feed-ingest-plan");
        await mkdir(parent, { recursive: true });
        await writeFile(join(parent, "plan-runs"), "recorded run-output obstruction");
      }
      const directory = join(fixture.directory, "evidence");
      await mkdir(directory);
      const pending = requestPlannerHttp(`http://127.0.0.1:${listener.port}${PLANNER_API_PREFIX}`, fixture.inputs, {}, directory);
      if (mode === "record-and-release") {
        await expect(pending).rejects.toMatchObject({ failure: {
          operation: "record-run", safe_cause: "system-error",
          causes: expect.arrayContaining([expect.objectContaining({ operation: "collection-release" })]),
        } });
        const saved = PlannerSavedResponseSchema.parse(await Bun.file(join(directory, "response.json")).json());
        expect(saved).not.toHaveProperty("planning_complete");
        expect(saved.failure?.operation).toBe("record-run");
        expect(order).toEqual(["release", "terminal"]);
      } else {
        const result = await pending;
        expect(result.http_status).toBe(500);
        expect(result.summary).toMatchObject({
          planning_complete: true, status: "completed", failure_code: null,
        });
        expect(result.summary.failure).not.toBeNull();
        expect(result.summary.health?.status).toBe(mode === "release" ? "summarized" : "failed");
        if (mode === "report-and-release") {
          expect(result.summary.failure?.error_type).toBe("RangeError");
          expect(result.summary.failure?.causes.some(cause => cause.operation === "collection-release")).toBe(true);
          expect(result.summary.health).toMatchObject({ status: "failed", failure: { error_type: "RangeError" } });
        } else {
          expect(result.summary.failure).toMatchObject({
            operation: "collection-release", execution: { traceId: result.summary.traceId, spanId: null },
          });
          expect(await Bun.file(join(directory, "health.json")).json()).toEqual(result.summary.health);
        }
        const row = await readPlannerParquet(join(fixture.inputs.outputRoot, result.summary.files.plan_runs!.files[0]!.path),
          "plan-runs", PlanRunRowContract);
        expect(row.rows[0]).toMatchObject({
          status: "completed", failure_code: null, selected_count: result.summary.selected_count,
          duration_ms: result.summary.duration_ms, api_timings: result.summary.api_timings,
        });
        expect(await Bun.file(join(directory, "response.json")).json()).toEqual(result.summary);
        expect(order).toEqual(["report", "release", "terminal"]);
      }
      expect(persisted?.files.status).toBe("written");
      if (persisted === undefined) throw new Error("The actual persistence response was not captured");
      expect((await readFile(join(fixture.inputs.root, persisted.artifact))).length).toBeGreaterThan(0);
      expect(collectionForRun(fixture.inputs, "2026-10-21-700")).toBeUndefined();
      expect(stageStore(fixture.inputs).isRunActive("2026-10-21-700")).toBe(false);
    } finally { await stopping; await stages.stop(true); await listener.stop(true); await app.close(); await fixture.close(); }
  }
}, 120000);

test("local report-file and verification failures retain the complete saved outcome after server release", async () => {
  for (const mode of ["report-file", "verification"] as const) {
    const fixture = await recordedPlan();
    const app = createPlanApp(fixture.inputs, fixture.runtime);
    const server = Bun.serve({
      hostname: "127.0.0.1", port: 0, idleTimeout: 0,
      async fetch(request, server) {
        const response = await app.fetch(request, { stage_origin: `http://127.0.0.1:${server.port}` });
        if (response.ok && new URL(request.url).pathname.endsWith("/plan") && mode === "verification") {
          const result = PlannerRunResponseSchema.parse(await response.clone().json());
          await rm(join(fixture.inputs.root, result.selected_articles_artifact!));
        }
        return response;
      },
    });
    try {
      const directory = join(fixture.directory, "evidence");
      await mkdir(directory);
      if (mode === "report-file") await mkdir(join(directory, "health.json"));
      await expect(requestPlannerHttp(`http://127.0.0.1:${server.port}${PLANNER_API_PREFIX}`, fixture.inputs, {}, directory))
        .rejects.toMatchObject({ failure: { operation: mode === "report-file" ? "write-report" : "verify-output" } });
      await server.stop(true);
      const saved = PlannerRunResponseSchema.parse(await Bun.file(join(directory, "response.json")).json());
      expect(saved).toMatchObject({ planning_complete: true, status: "completed", failure_code: null });
      expect(saved.failure?.operation).toBe(mode === "report-file" ? "write-report" : "verify-output");
      expect(saved.health?.status).toBe("summarized");
      expect(saved.files.selected_articles?.status).toBe("written");
      if (mode === "verification") expect(await Bun.file(join(directory, "health.json")).json()).toEqual(saved.health);
      const row = await readPlannerParquet(join(fixture.inputs.outputRoot, saved.files.plan_runs!.files[0]!.path),
        "plan-runs", PlanRunRowContract);
      expect(row.rows[0]).toMatchObject({ status: "completed", failure_code: null, selected_count: saved.selected_count });
      expect(collectionForRun(fixture.inputs, saved.run_id)).toBeUndefined();
      expect(stageStore(fixture.inputs).isRunActive(saved.run_id)).toBe(false);
    } finally { await server.stop(true); await app.close(); await fixture.close(); }
  }
}, 120000);
