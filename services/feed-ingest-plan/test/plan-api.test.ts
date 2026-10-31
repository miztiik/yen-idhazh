/** Exercise listener refusals, parser admission and retained discovery on offline inputs. */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { existsSync } from "node:fs";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { fileURLToPath } from "node:url";
import { servePlan } from "../src/api/server";
import { createPlanTestServer } from "./plan-test-server";
import { recordedPlan } from "./plan-recordings";
import { PlanRunRowContract, SelectedArticlesArtifactSchema } from "@idhazh/common-contracts";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { ArticleParserPool } from "../src/harvest-feeds/article-parser-pool";

const prefix = "/api/2026-10-31";
const json = (body: unknown) => ({ method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });

test("health is explicit; disabled, malformed, oversized and unknown controls cannot fetch", async () => {
  const recorded = await recordedPlan();
  const app = createPlanTestServer(recorded.inputs, recorded.runtime);
  try {
    recorded.inputs.settings.enabled = false;
    expect(await (await app.request(`${prefix}/health`)).json()).toEqual({ status: "available", planner_enabled: false });
    expect((await app.request(`${prefix}/plan`, json({}))).status).toBe(503);
    expect((await app.request(`${prefix}/plan`, json({ article_limit: "2" }))).status).toBe(400);
    expect((await app.request(`${prefix}/plan`, json({ extra: true }))).status).toBe(400);
    expect((await app.request(`${prefix}/plan`, { ...json({}), body: "{" })).status).toBe(400);
    expect((await app.request(`${prefix}/persist-dispatches`, json({ batch_id: randomUUID() }))).status).toBe(404);
    expect((await app.request(`${prefix}/feeds`)).status).toBe(404);
    expect((await app.request("/api/2026-10-20/health")).status).toBe(404);
    for (const action of ["summarize", "record"]) {
      expect((await app.request(`${prefix}/feed-health-state`, json({ batch_id: randomUUID(), action }))).status).toBe(503);
    }
    expect(existsSync(join(recorded.inputs.outputRoot, "planner-operations.sqlite"))).toBe(false);
    expect((await app.request(`${prefix}/plan`, json({ padding: "x".repeat(recorded.inputs.settings.listener.max_body_bytes) }))).status).toBe(413);
    expect((await app.request(`${prefix}/fetch`, json({
      request_id: randomUUID(), correlation_id: randomUUID(), feed_id: "recorded-news", kind: "feed",
    }))).status).toBe(400);
    expect(recorded.transport.requests).toHaveLength(0);
    recorded.inputs.settings.enabled = true;
    recorded.runtime.run_number = "9".repeat(512);
    expect((await app.request(`${prefix}/plan`, json({}))).status).toBe(400);
    expect(recorded.transport.requests).toHaveLength(0);
    expect(existsSync(join(recorded.inputs.outputRoot, "raw"))).toBe(false);
  } finally { await app.close(); await recorded.close(); }
});

test("a required source write failure returns an API error, not proven planning completion", async () => {
  const recorded = await recordedPlan();
  const app = createPlanTestServer(recorded.inputs, recorded.runtime);
  try {
    await mkdir(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan"), { recursive: true });
    await writeFile(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan", "feed-health-state"), "obstruction");
    const response = await app.request(`${prefix}/plan`, json({}));
    expect(response.status).toBe(500);
    const summary = await response.json();
    expect(summary.planning_complete).toBe(false);
    expect(summary.status).toBe("partial");
    expect(summary.files.plan_runs.status).toBe("written");
    expect(summary.files.feed_health_state).toBeUndefined();
    expect(summary.files.selected_articles.status).toBe("written");
    const artifact = SelectedArticlesArtifactSchema.parse(JSON.parse(await readFile(join(recorded.directory, summary.selected_articles_artifact), "utf8")));
    expect(artifact.articles.length).toBeGreaterThan(0);
    expect(artifact.articles.every(article => article.article_text.length > 0)).toBe(true);
    const failedCapture = await recordedPlan();
    const failedApp = createPlanTestServer(failedCapture.inputs, failedCapture.runtime);
    try {
      failedCapture.runtime.progress = () => {
        failedCapture.inputs.settings.inputs.feed_health_days = [
          { day: "2026-10-21", raw_files: [] }, { day: "2026-10-21", raw_files: [] },
        ];
      };
      const failed = await (await failedApp.request(`${prefix}/plan`, json({}))).json();
      expect(failed.status).toBe("partial");
      const healthTimings = failed.api_timings.filter((timing: { operation: string }) => timing.operation.startsWith("feed-health-"));
      expect(healthTimings).toMatchObject([
        { operation: "feed-health-before-fetch", status: "completed" },
      ]);
      expect(failed.failure_code).toBe("REQUEST_CONFLICT");
      expect(healthTimings.every((timing: { duration_ms: number }) => Number.isSafeInteger(timing.duration_ms) && timing.duration_ms >= 0)).toBe(true);
      const requestCount = failedCapture.transport.requests.length;
      failedCapture.runtime.run_number = "701";
      delete failedCapture.runtime.progress;
      const failedBeforeWork = await (await failedApp.request(`${prefix}/plan`, json({}))).json();
      expect(failedBeforeWork.status).toBe("failed");
      expect(failedBeforeWork.api_timings.filter((timing: { operation: string }) => timing.operation.startsWith("feed-health-")))
        .toMatchObject([{ operation: "feed-health-before-fetch", status: "failed" }]);
      expect(failedCapture.transport.requests.length).toBe(requestCount);
    } finally { await failedApp.close(); await failedCapture.close(); }
  } finally { await app.close(); await recorded.close(); }
});

test("one listener retains durable seen receipts from an output root outside the checkout", async () => {
  const recorded = await recordedPlan();
  delete recorded.runtime.run_number;
  delete recorded.runtime.correlation_id;
  recorded.inputs.settings.listener.port = 0;
  recorded.inputs.settings.listener.parser_concurrency = 2;
  const original = recorded.transport.recordings.bodies.article;
  recorded.transport.recordings.bodies.article = original.replace("</article>", `${original.repeat(12)}</article>`);
  recorded.inputs.harvest.extraction.max_body_bytes = Buffer.byteLength(recorded.transport.recordings.bodies.article) + 1024;
  let activeParsers = 0;
  let peak = 0;
  let notify!: () => void;
  const parsing = new Promise<void>(resolve => { notify = resolve; });
  let articleParsingRequested = false;
  recorded.runtime.log = event => {
    recorded.events.push(event);
    if (event.operation === "parse" && event.phase === "started" && event.details.document_kind === "article") {
      articleParsingRequested = true;
    }
  };
  const pool = new ArticleParserPool(recorded.inputs.settings.listener.parser_concurrency, phase => {
    if (phase === "started") {
      activeParsers++; peak = Math.max(peak, activeParsers);
      if (articleParsingRequested) notify();
    }
    else activeParsers--;
  });
  recorded.runtime.parser_pool = pool;
  const server = servePlan(recorded.inputs, recorded.runtime);
  try {
    const url = `http://127.0.0.1:${server.port}${prefix}`;
    const first = fetch(`${url}/plan`, json({ article_limit: 2 }));
    await parsing;
    const second = fetch(`${url}/plan`, json({ article_limit: 1 }));
    expect((await fetch(`${url}/health`)).status).toBe(200);
    expect(activeParsers).toBeGreaterThan(0);
    const independent = await fetch(`${url}/fetch`, json({
      request_id: randomUUID(), correlation_id: randomUUID(), feed_id: "recorded-news",
      fetch_item_type: "article", url: "https://news.example/second",
    }));
    expect(independent.status).toBe(200);
    const results = await Promise.all([first, second].map(async pending => (await pending).json()));
    expect(peak).toBeGreaterThan(1);
    expect(peak).toBeLessThanOrEqual(recorded.inputs.settings.listener.parser_concurrency);
    expect(new Set(recorded.events.filter(event =>
      event.operation === "plan" && event.phase === "started").map(event => event.run_id)).size).toBe(2);
    expect(results[0].run_id).not.toBe(results[1].run_id);
    expect(results[0].batches.parsed_batch_id).not.toBe(results[1].batches.parsed_batch_id);
    for (const result of results) {
      expect(result.planning_complete).toBe(true);
      const row = await readPlannerParquet(join(recorded.inputs.outputRoot, result.files.plan_runs.files[0].path), "plan-runs", PlanRunRowContract);
      expect(row.rows[0]!.run_id).toBe(result.run_id);
    }
  } finally { await server.stop(true); pool.close(); await recorded.close(); }
});

test("a later dispatch failure does not lose discovery already persisted by this listener", async () => {
  const recorded = await recordedPlan();
  const app = createPlanTestServer(recorded.inputs, recorded.runtime);
  try {
    const obstruction = join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan", "selected-articles");
    await mkdir(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan"), { recursive: true });
    await writeFile(obstruction, "obstruction");
    expect((await app.request(`${prefix}/plan`, json({}))).status).toBe(500);
    await rm(obstruction);
    recorded.runtime.run_number = "701";
    recorded.runtime.clock = () => new Date("2026-10-22T00:10:00Z");
    const second = await (await app.request(`${prefix}/plan`, json({}))).json();
    expect(second.status).toBe("completed");
    expect(second.files.discovered_articles).toEqual({ status: "empty", files: [] });
    const fetchKey = randomUUID();
    const correlationId = randomUUID();
    const fetched = await (await app.request(`${prefix}/fetch`, json({
      request_id: fetchKey, correlation_id: correlationId, feed_id: "recorded-news", fetch_item_type: "article", url: "https://news.example/second",
    }))).json();
    await app.close();
    const loaded = await loadPlanInputs(fileURLToPath(new URL("../../../", import.meta.url)));
    const restartedInputs = { ...loaded, root: recorded.inputs.root, outputRoot: recorded.inputs.outputRoot,
      settings: recorded.inputs.settings, harvest: recorded.inputs.harvest };
    const restarted = createPlanTestServer(restartedInputs, { ...recorded.runtime, clock: () => new Date("2026-10-23T00:00:00Z") });
    try {
      const parsed = await (await restarted.request(`${prefix}/parse`, json({
        request_id: randomUUID(), fetch_request_id: fetchKey, article_id: fetched.article_id, correlation_id: correlationId,
      }))).json();
      const selected = await (await restarted.request(`${prefix}/select-articles`, json({ batch_id: parsed.batch_id }))).json();
      expect(selected.run_id).toBe(parsed.run_id);
      const partition = await (await restarted.request(`${prefix}/partition-articles`, json({ batch_id: selected.batch_id, strategy: "none" }))).json();
      const saved = await (await restarted.request(`${prefix}/feed-health-state`, json({ batch_id: selected.batch_id }))).json();
      const originalDay = saved.rows.find((row: { date: string }) => row.date === "2026-10-21");
      expect(originalDay.article_requests).toBe(1);
      expect(originalDay.robots_requests).toBe(1);
      expect(saved.rows.some((row: { date: string; article_requests: number }) => row.date === "2026-10-23" && row.article_requests > 0)).toBe(false);
      const persistedResponse = await restarted.request(`${prefix}/persist-selected-articles`, json({ batch_id: partition.batch_id }));
      expect(persistedResponse.status, await persistedResponse.clone().text()).toBe(200);
      const persisted = await persistedResponse.json();
      const run = (await readPlannerParquet(join(restartedInputs.outputRoot, persisted.run_files.files[0].path),
        "plan-runs", PlanRunRowContract)).rows[0]!;
      expect(run.duration_ms).toBeNull();
      expect(run.date).toBe("2026-10-22");
      expect(run.evaluated_at).toBe("2026-10-22T00:10:00Z");
      expect(run.selection_started_at_utc).toBe("2026-10-23T00:00:00Z");
    } finally { await restarted.close(); }
  } finally { await app.close(); await recorded.close(); }
});
