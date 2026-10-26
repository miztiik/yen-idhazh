/** Exercise the actual listener, independent stage APIs and real worker progress on offline inputs. */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { createPlanApp, servePlan } from "../src/api/server";
import { main } from "../src/index";
import { recordedPlan } from "./plan-recordings";
import { FeedHealthStateRowContract, PlanRunRowContract, SelectedArticlesArtifactSchema } from "@idhazh/common-contracts";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";

const prefix = "/api/2026-10-20";
const json = (body: unknown) => ({ method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });

test("health is explicit; disabled, malformed, oversized and unknown controls cannot fetch", async () => {
  const recorded = await recordedPlan();
  try {
    recorded.inputs.settings.enabled = false;
    const app = createPlanApp(recorded.inputs, recorded.runtime);
    expect(await (await app.request(`${prefix}/health`)).json()).toEqual({ status: "available", planner_enabled: false });
    expect((await app.request(`${prefix}/plan`, json({}))).status).toBe(503);
    expect((await app.request(`${prefix}/plan`, json({ article_limit: "2" }))).status).toBe(400);
    expect((await app.request(`${prefix}/plan`, json({ extra: true }))).status).toBe(400);
    expect((await app.request(`${prefix}/plan`, { ...json({}), body: "{" })).status).toBe(400);
    expect((await app.request(`${prefix}/persist-dispatches`, json({ batch_id: randomUUID() }))).status).toBe(404);
    expect((await app.request(`${prefix}/feeds`)).status).toBe(404);
    expect(recorded.transport.requests).toHaveLength(0);
  } finally { await recorded.close(); }
});

test("actual API and awaited CLI compose the same recorded plan and disclose the same audit limit", async () => {
  const api = await recordedPlan();
  const cli = await recordedPlan();
  const server = Bun.serve({ port: 0, hostname: "127.0.0.1", fetch: createPlanApp(api.inputs, api.runtime).fetch });
  try {
    const url = `http://127.0.0.1:${server.port}${prefix}`;
    const key = randomUUID();
    const response = await fetch(`${url}/plan`, { ...json({ article_limit: 2 }), headers: {
      "content-type": "application/json", "Idempotency-Key": key,
    } });
    expect(response.status).toBe(200);
    const summary = await response.json();
    const requests = api.transport.requests.length;
    const replay = await (await fetch(`${url}/plan`, { ...json({ article_limit: 2 }), headers: {
      "content-type": "application/json", "Idempotency-Key": key,
    } })).json();
    expect(replay).toEqual(summary);
    expect(api.transport.requests.length).toBe(requests);
    const cliSummary = await main(["--cli", "--article-limit=2"], { inputs: cli.inputs, runtime: cli.runtime, output: () => {} });
    expect("selected_url_keys" in cliSummary && cliSummary.selected_url_keys).toEqual(summary.selected_url_keys);
    const healthFolder = join(api.inputs.outputRoot, "raw", "feed-ingest-plan", "feed-health-state", "2026", "10", "21");
    const before = await readdir(healthFolder);
    const selected = await (await fetch(`${url}/select-articles`, json({ batch_id: summary.batches.parsed_batch_id }))).json();
    const repeated = await (await fetch(`${url}/select-articles`, json({ batch_id: summary.batches.parsed_batch_id }))).json();
    expect(selected.batch_id).not.toBe(repeated.batch_id);
    expect(await readdir(healthFolder)).toEqual(before);
    expect(selected.articles.every((article: object) => !Object.hasOwn(article, "article_text"))).toBe(true);
    const partition = await (await fetch(`${url}/partition-articles`, json({ batch_id: selected.batch_id, strategy: "none" }))).json();
    expect(partition.dispatch_count).toBe(1);
    expect(partition.articles.map((article: { worker_assignment: number }) => article.worker_assignment)).toEqual([0, 0]);
    const persisted = await (await fetch(`${url}/persist-selected-articles`, json({ batch_id: partition.batch_id }))).json();
    const artifact = SelectedArticlesArtifactSchema.parse(JSON.parse(await readFile(join(api.directory, persisted.artifact), "utf8")));
    expect(artifact.articles.every(article => article.article_text.length > 0)).toBe(true);
    expect(JSON.stringify(summary)).not.toContain(artifact.articles[0]!.article_text);
    const fetchId = randomUUID();
    const correlation = randomUUID();
    const fetched = await (await fetch(`${url}/fetch`, json({
      request_id: fetchId, correlation_id: correlation, source_id: "recorded-news",
      kind: "article", url: "https://news.example/second",
    }))).json();
    expect(fetched.failure).toBeNull();
    expect(Object.hasOwn(fetched, "body")).toBe(false);
    const parsed = await (await fetch(`${url}/parse`, json({
      request_id: randomUUID(), fetch_request_id: fetchId, article_id: fetched.article_id, correlation_id: correlation,
    }))).json();
    expect(parsed.parsed_count).toBe(1);
    expect(Object.hasOwn(parsed, "parsed")).toBe(false);
    const standalone = await (await fetch(`${url}/select-articles`, json({ batch_id: parsed.batch_id }))).json();
    expect(standalone.articles).toHaveLength(1);
    const recordedHealth = await (await fetch(`${url}/feed-health-state`, json({ batch_id: standalone.batch_id }))).json();
    expect(recordedHealth.status).toBe("recorded");
    expect(recordedHealth.rows.reduce((sum: number, row: { article_requests: number }) => sum + row.article_requests, 0)).toBe(1);
  } finally { await server.stop(true); await api.close(); await cli.close(); }
});

test("a required source write failure returns an API error, not proven planning completion", async () => {
  const recorded = await recordedPlan();
  try {
    await mkdir(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan"), { recursive: true });
    await writeFile(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan", "feed-health-state"), "obstruction");
    const response = await createPlanApp(recorded.inputs, recorded.runtime).request(`${prefix}/plan`, json({}));
    expect(response.status).toBe(500);
    const summary = await response.json();
    expect(summary.planning_complete).toBe(false);
    expect(summary.status).toBe("partial");
    expect(summary.files.plan_runs.status).toBe("written");
    expect(summary.files.feed_health_state).toBeUndefined();
  } finally { await recorded.close(); }
});

test("one listener retains durable seen receipts from an output root outside the checkout", async () => {
  const recorded = await recordedPlan();
  delete recorded.runtime.run_number;
  delete recorded.runtime.correlation_id;
  recorded.inputs.settings.listener.port = 0;
  const original = recorded.transport.recordings.bodies.article;
  recorded.transport.recordings.bodies.article = original.replace("</article>", `${original.repeat(12)}</article>`);
  recorded.inputs.harvest.extraction.max_body_bytes = Buffer.byteLength(recorded.transport.recordings.bodies.article) + 1024;
  let activeParsers = 0;
  let peak = 0;
  let notify!: () => void;
  const parsing = new Promise<void>(resolve => { notify = resolve; });
  recorded.runtime.log = event => {
    recorded.events.push(event);
    if (event.operation !== "parse") return;
    if (event.phase === "started") { activeParsers++; peak = Math.max(peak, activeParsers); notify(); }
    else activeParsers--;
  };
  const server = servePlan(recorded.inputs, recorded.runtime);
  try {
    const url = `http://127.0.0.1:${server.port}${prefix}`;
    const first = fetch(`${url}/plan`, json({ article_limit: 1 }));
    const second = fetch(`${url}/plan`, json({ article_limit: 1 }));
    await parsing;
    expect((await fetch(`${url}/health`)).status).toBe(200);
    expect(activeParsers).toBeGreaterThan(0);
    const independent = await fetch(`${url}/fetch`, json({
      request_id: randomUUID(), correlation_id: randomUUID(), source_id: "recorded-news", kind: "feed",
    }));
    expect(independent.status).toBe(200);
    expect(activeParsers).toBeGreaterThan(0);
    const results = await Promise.all([first, second].map(async pending => (await pending).json()));
    expect(peak).toBeGreaterThan(1);
    expect(results[0].run_id).not.toBe(results[1].run_id);
    expect(results[0].batches.parsed_batch_id).not.toBe(results[1].batches.parsed_batch_id);
    for (const result of results) {
      expect(result.planning_complete).toBe(true);
      const row = await readPlannerParquet(join(recorded.inputs.outputRoot, result.files.plan_runs.files[0].path), "plan-runs", PlanRunRowContract);
      expect(row.rows[0]!.run_id).toBe(result.run_id);
    }
  } finally { await server.stop(true); await recorded.close(); }
});

test("a later dispatch failure does not lose already durable first sight from this listener", async () => {
  const recorded = await recordedPlan();
  try {
    const obstruction = join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan", "selected-articles");
    await mkdir(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan"), { recursive: true });
    await writeFile(obstruction, "obstruction");
    const app = createPlanApp(recorded.inputs, recorded.runtime);
    expect((await app.request(`${prefix}/plan`, json({}))).status).toBe(500);
    await rm(obstruction);
    recorded.runtime.run_number = "701";
    recorded.runtime.clock = () => new Date("2026-10-22T00:10:00Z");
    const second = await (await app.request(`${prefix}/plan`, json({}))).json();
    expect(second.status).toBe("completed");
    expect(second.files.discovered_articles).toEqual({ status: "empty", files: [] });
  } finally { await recorded.close(); }
});

test("a listener keeps first-seen evidence stable across UTC midnight", async () => {
  const recorded = await recordedPlan();
  let workClock = "2026-10-21T23:59:59Z";
  recorded.runtime.observation_clock = () => new Date(workClock);
  recorded.runtime.selection_clock = () => new Date("2026-10-22T00:00:05Z");
  recorded.transport.on_request = request => {
    if (request.url.pathname !== "/feed.xml" && request.url.pathname !== "/robots.txt") workClock = "2026-10-22T00:00:01Z";
  };
  try {
    const response = await createPlanApp(recorded.inputs, recorded.runtime).request(`${prefix}/plan`, json({ article_limit: 2 }));
    expect(response.status).toBe(200);
    const result = await response.json();
    expect(result.date).toBe("2026-10-21");
    expect(result.evaluated_at).toBe("2026-10-21T23:59:59Z");
    expect(result.selection_started_at_utc).toBe("2026-10-22T00:00:05Z");
    expect(result.files.feed_health_state.files.map((file: { covers: string }) => file.covers)).toEqual(["2026-10-21", "2026-10-22"]);
    const rows = (await Promise.all(result.files.feed_health_state.files.map((file: { path: string }) =>
      readPlannerParquet(join(recorded.inputs.outputRoot, file.path), "feed-health-state", FeedHealthStateRowContract)))).flatMap(file => file.rows);
    expect(rows.find(row => row.date === "2026-10-21")).toMatchObject({
      checked_at: "2026-10-21T23:59:59Z", feed_reads: 1, feed_requests: 1, robots_requests: 1, article_requests: 0,
    });
    expect(rows.find(row => row.date === "2026-10-22")).toMatchObject({
      checked_at: null, outcome: null, feed_reads: 0, feed_requests: 0, article_requests: 2,
      article_candidates: 2, articles_selected: 2,
    });
  } finally { await recorded.close(); }
});
