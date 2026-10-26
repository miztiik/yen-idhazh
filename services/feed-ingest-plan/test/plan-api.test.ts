/** Exercise the actual listener, independent stage APIs and real worker progress on offline inputs. */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { existsSync } from "node:fs";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { fileURLToPath } from "node:url";
import { createPlanApp, servePlan } from "../src/api/server";
import { main } from "../src/index";
import { recordedPlan } from "./plan-recordings";
import { FeedHealthStateRowContract, PlanRunRowContract, SelectedArticleRowContract, SelectedArticlesArtifactSchema, selectedArticleMetadata } from "@idhazh/common-contracts";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { currentExecutionState } from "../src/api/document-state";

const prefix = "/api/2026-10-20";
const json = (body: unknown) => ({ method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });

test("health is explicit; disabled, malformed, oversized and unknown controls cannot fetch", async () => {
  const recorded = await recordedPlan();
  const app = createPlanApp(recorded.inputs, recorded.runtime);
  try {
    recorded.inputs.settings.enabled = false;
    expect(await (await app.request(`${prefix}/health`)).json()).toEqual({ status: "available", planner_enabled: false });
    expect((await app.request(`${prefix}/plan`, json({}))).status).toBe(503);
    expect((await app.request(`${prefix}/plan`, json({ article_limit: "2" }))).status).toBe(400);
    expect((await app.request(`${prefix}/plan`, json({ extra: true }))).status).toBe(400);
    expect((await app.request(`${prefix}/plan`, { ...json({}), body: "{" })).status).toBe(400);
    expect((await app.request(`${prefix}/persist-dispatches`, json({ batch_id: randomUUID() }))).status).toBe(404);
    expect((await app.request(`${prefix}/feeds`)).status).toBe(404);
    for (const action of ["summarize", "record"]) {
      expect((await app.request(`${prefix}/feed-health-state`, json({ batch_id: randomUUID(), action }))).status).toBe(503);
    }
    expect(existsSync(join(recorded.inputs.outputRoot, "planner-operations.sqlite"))).toBe(false);
    expect((await app.request(`${prefix}/plan`, json({ padding: "x".repeat(recorded.inputs.settings.listener.max_body_bytes) }))).status).toBe(413);
    expect((await app.request(`${prefix}/fetch`, json({
      request_id: randomUUID(), correlation_id: randomUUID(), source_id: "recorded-news", kind: "feed",
    }))).status).toBe(400);
    expect(recorded.transport.requests).toHaveLength(0);
    recorded.inputs.settings.enabled = true;
    recorded.runtime.run_number = "9".repeat(512);
    expect((await app.request(`${prefix}/plan`, json({}))).status).toBe(400);
    expect(recorded.transport.requests).toHaveLength(0);
    expect(existsSync(join(recorded.inputs.outputRoot, "raw"))).toBe(false);
  } finally { app.close(); await recorded.close(); }
});

test("actual API and awaited CLI compose the same recorded plan and disclose the same audit limit", async () => {
  const api = await recordedPlan();
  const cli = await recordedPlan();
  for (const recorded of [api, cli]) {
    for (const url of ["https://news.example/feed.xml", "https://news.example/story/?b=2&a=1#section"]) {
      recorded.transport.recordings.responses[url]!.unshift({ status: 403, body: "" });
    }
  }
  const app = createPlanApp(api.inputs, api.runtime);
  const server = Bun.serve({ port: 0, hostname: "127.0.0.1", fetch: app.fetch });
  try {
    const url = `http://127.0.0.1:${server.port}${prefix}`;
    const key = randomUUID();
    const response = await fetch(`${url}/plan`, { ...json({ article_limit: 1 }), headers: {
      "content-type": "application/json", "Idempotency-Key": key,
    } });
    expect(response.status).toBe(200);
    const summary = await response.json();
    const requests = api.transport.requests.length;
    expect(api.transport.requests.find(request => request.url.pathname === "/story/")?.url.href)
      .toBe("https://news.example/story/?b=2&a=1#section");
    expect(summary.selected_count).toBe(1);
    expect(summary.api_timings.filter((timing: { operation: string }) => timing.operation.startsWith("feed-health-")))
      .toMatchObject([
        { operation: "feed-health-before-fetch", status: "completed" },
        { operation: "feed-health-for-selection", status: "completed" },
      ]);
    const replay = await (await fetch(`${url}/plan`, { ...json({ article_limit: 1 }), headers: {
      "content-type": "application/json", "Idempotency-Key": key,
    } })).json();
    expect(replay).toEqual(summary);
    expect(api.transport.requests.length).toBe(requests);
    const cliSummary = await main(["--cli", "--article-limit=1"], { inputs: cli.inputs, runtime: cli.runtime, output: () => {} });
    expect("selected_url_keys" in cliSummary && cliSummary.selected_url_keys).toEqual(summary.selected_url_keys);
    const healthFolder = join(api.inputs.outputRoot, "raw", "feed-ingest-plan", "feed-health-state", "2026", "10", "21");
    const before = await readdir(healthFolder);
    const originalPaths: string[] = [join(api.directory, summary.selected_articles_artifact)];
    for (const family of ["selected_articles", "feed_health_state", "plan_runs"]) {
      for (const file of summary.files[family].files) originalPaths.push(join(api.inputs.outputRoot, file.path));
    }
    const originalBytes = await Promise.all(originalPaths.map(path => readFile(path)));
    api.runtime.selection_clock = () => new Date("2026-10-22T00:01:00Z");
    const selected = await (await fetch(`${url}/select-articles`, json({ batch_id: summary.batches.parsed_batch_id }))).json();
    const repeated = await (await fetch(`${url}/select-articles`, json({ batch_id: summary.batches.parsed_batch_id }))).json();
    expect(selected.batch_id).not.toBe(repeated.batch_id);
    expect(selected.run_id).not.toBe(summary.run_id);
    expect(repeated.run_id).not.toBe(selected.run_id);
    expect(repeated.run_id).not.toBe(summary.run_id);
    expect(await readdir(healthFolder)).toEqual(before);
    expect(selected.articles.every((article: object) => !Object.hasOwn(article, "article_text"))).toBe(true);
    const invalidPartition = await fetch(`${url}/partition-articles`, json({
      batch_id: selected.batch_id, strategy: "none", shards: 2,
    }));
    expect(invalidPartition.status).toBe(400);
    expect((await invalidPartition.json()).code).toBe("INVALID_REQUEST");
    const partition = await (await fetch(`${url}/partition-articles`, json({ batch_id: selected.batch_id, strategy: "none" }))).json();
    expect(partition.run_id).toBe(selected.run_id);
    const alternative = await (await fetch(`${url}/partition-articles`, json({
      batch_id: selected.batch_id, strategy: "round-robin", shards: 2,
    }))).json();
    expect(partition.dispatch_count).toBe(1);
    expect(partition.articles.map((article: { worker_assignment: number }) => article.worker_assignment)).toEqual([0]);
    expect(alternative.run_id).not.toBe(partition.run_id);
    const decisionHealth = await (await fetch(`${url}/feed-health-state`, json({ batch_id: selected.batch_id }))).json();
    expect(decisionHealth.rows).toHaveLength(1);
    expect(decisionHealth.rows[0]).toMatchObject({
      run_id: selected.run_id, date: "2026-10-22", checked_at: null, outcome: null, items: null,
      feed_reads: 0, productive_reads: 0, failed_reads: 0, feed_requests: 0, article_requests: 0,
      robots_requests: 0, article_candidates: 2, articles_selected: 1, counts_complete: true,
    });
    const selectedResponse = await fetch(`${url}/persist-selected-articles`, json({ batch_id: partition.batch_id }));
    expect(selectedResponse.status).toBe(200);
    const selectedSaved = await selectedResponse.json();
    expect(selectedSaved.run_status).toBe("completed");
    const selectedRun = (await readPlannerParquet(join(api.inputs.outputRoot, selectedSaved.run_files.files[0].path),
      "plan-runs", PlanRunRowContract)).rows[0]!;
    expect(selectedRun).toMatchObject({
      run_id: selected.run_id, date: "2026-10-22", selected_count: 1, strategy: "none",
      evaluated_at: summary.evaluated_at, selection_started_at_utc: "2026-10-22T00:01:00Z",
    });
    expect(selectedRun.api_timings.map(timing => timing.operation)).toEqual(["feed-health-for-selection", "select", "partition", "persist"]);
    const selectedArtifactBytes = await readFile(join(api.directory, selectedSaved.artifact));
    const selectedPaths: string[] = [join(api.directory, selectedSaved.artifact)];
    for (const saved of [selectedSaved.files, selectedSaved.run_files, decisionHealth.files]) {
      for (const file of saved.files) selectedPaths.push(join(api.inputs.outputRoot, file.path));
    }
    const selectedBytes = await Promise.all(selectedPaths.map(path => readFile(path)));
    const alternativeResponse = await fetch(`${url}/persist-selected-articles`, json({ batch_id: alternative.batch_id }));
    expect(alternativeResponse.status).toBe(200);
    const alternativeSaved = await alternativeResponse.json();
    const alternativeRun = (await readPlannerParquet(join(api.inputs.outputRoot, alternativeSaved.run_files.files[0].path),
      "plan-runs", PlanRunRowContract)).rows[0]!;
    expect(alternativeRun.run_id).toBe(alternative.run_id);
    expect(alternativeRun.strategy).toBe("round-robin");
    expect(alternativeRun.api_timings.map(timing => timing.operation)).toEqual(["partition", "persist"]);
    expect(await readFile(join(api.directory, selectedSaved.artifact))).toEqual(selectedArtifactBytes);
    expect(await (await fetch(`${url}/persist-selected-articles`, json({ batch_id: partition.batch_id }))).json()).toEqual(selectedSaved);
    const deliveredChoice = SelectedArticlesArtifactSchema.parse(JSON.parse(selectedArtifactBytes.toString("utf8")));
    const selectedRows = (await readPlannerParquet(join(api.inputs.outputRoot, selectedSaved.files.files[0].path),
      "selected-articles", SelectedArticleRowContract)).rows;
    expect(selectedRows).toEqual(deliveredChoice.articles.map(article => ({
      ...selectedArticleMetadata(article), run_id: deliveredChoice.run_id, attempt: deliveredChoice.attempt, date: deliveredChoice.date,
    })));
    const repeatedPartition = await (await fetch(`${url}/partition-articles`, json({ batch_id: repeated.batch_id, strategy: "bin-pack", shards: 2 }))).json();
    const repeatedSaved = await (await fetch(`${url}/persist-selected-articles`, json({ batch_id: repeatedPartition.batch_id }))).json();
    expect(repeatedSaved.run_status).toBe("partial");
    expect(repeatedSaved.run_files.status).toBe("written");
    expect(repeatedSaved.artifact).not.toBe(selectedSaved.artifact);
    expect(api.transport.requests.length).toBe(requests);
    const artifact = SelectedArticlesArtifactSchema.parse(JSON.parse(await readFile(join(api.directory, summary.selected_articles_artifact), "utf8")));
    expect(artifact.articles.every(article => article.article_text.length > 0)).toBe(true);
    expect(JSON.stringify(summary)).not.toContain(artifact.articles[0]!.article_text);
    const feedKey = randomUUID();
    const feedCorrelation = randomUUID();
    const feed = await (await fetch(`${url}/fetch`, json({
      request_id: feedKey, correlation_id: feedCorrelation, feed_id: "recorded-news", kind: "feed",
    }))).json();
    expect(Object.hasOwn(feed, "body")).toBe(false);
    const beforeFeedParse = api.transport.requests.length;
    const offered = await (await fetch(`${url}/parse`, json({
      request_id: randomUUID(), fetch_request_id: feedKey, article_id: feed.article_id, correlation_id: feedCorrelation,
    }))).json();
    expect(api.transport.requests.length).toBe(beforeFeedParse);
    expect(Object.hasOwn(offered, "parsed")).toBe(false);
    expect(offered.offers).toHaveLength(2);
    expect((await fetch(`${url}/select-articles`, json({ batch_id: offered.batch_id }))).status).toBe(409);
    const fetchedOffers = await Promise.all(offered.offers.map(async (offer: { offer_id: string }) => {
      const key = randomUUID();
      const fetched = await (await fetch(`${url}/fetch`, json({
        request_id: key, correlation_id: feedCorrelation, feed_id: "recorded-news",
        kind: "article", batch_id: offered.batch_id, offer_id: offer.offer_id,
      }))).json();
      return { key, fetched };
    }));
    const requestsBeforeParse = api.transport.requests.length;
    await Promise.all(fetchedOffers.map(async ({ key, fetched }: { key: string; fetched: { article_id: string } }) => {
      const parsed = await (await fetch(`${url}/parse`, json({
        request_id: randomUUID(), fetch_request_id: key, article_id: fetched.article_id, correlation_id: feedCorrelation,
      }))).json();
      expect(parsed.batch_id).toBe(offered.batch_id);
    }));
    expect(api.transport.requests.length).toBe(requestsBeforeParse);
    const choices = await Promise.all([0, 1].map(async () =>
      (await fetch(`${url}/select-articles`, json({ batch_id: offered.batch_id }))).json()));
    const complete = choices.find(choice => choice.run_id === offered.run_id);
    const beforeOriginalPersistence = choices.find(choice => choice.run_id !== offered.run_id);
    expect(complete).toBeDefined();
    expect(beforeOriginalPersistence).toBeDefined();
    expect(complete.articles).toHaveLength(2);
    expect(beforeOriginalPersistence.run_id).not.toBe(complete.run_id);
    const freshHealth = await (await fetch(`${url}/feed-health-state`, json({ batch_id: beforeOriginalPersistence.batch_id }))).json();
    expect(freshHealth.rows.every((row: { feed_reads: number; article_requests: number; feed_requests: number; robots_requests: number }) =>
      row.feed_reads === 0 && row.article_requests === 0 && row.feed_requests === 0 && row.robots_requests === 0)).toBe(true);
    const freshPartition = await (await fetch(`${url}/partition-articles`, json({ batch_id: beforeOriginalPersistence.batch_id, strategy: "round-robin", shards: 2 }))).json();
    const freshFinal = await (await fetch(`${url}/persist-selected-articles`, json({ batch_id: freshPartition.batch_id }))).json();
    expect(freshFinal.run_status).toBe("completed");
    expect((await readPlannerParquet(join(api.inputs.outputRoot, freshFinal.run_files.files[0].path),
      "plan-runs", PlanRunRowContract)).rows[0]!.run_id).toBe(beforeOriginalPersistence.run_id);
    const packed = await (await fetch(`${url}/partition-articles`, json({ batch_id: complete.batch_id, strategy: "none" }))).json();
    const healthResponse = await (await fetch(`${url}/feed-health-state`, json({ batch_id: complete.batch_id }))).json();
    expect(healthResponse.files.status).toBe("written");
    expect(healthResponse.reliability.window_days).toBe(api.inputs.clock_config.collect.reliability_window_days);
    const final = await (await fetch(`${url}/persist-selected-articles`, json({ batch_id: packed.batch_id }))).json();
    expect(final.run_status).toBe("completed");
    expect(final.run_files.status).toBe("written");
    const delivered = SelectedArticlesArtifactSchema.parse(JSON.parse(await readFile(join(api.directory, final.artifact), "utf8")));
    expect(delivered.articles.map(article => article.url_key)).toEqual(complete.articles.map((article: { url_key: string }) => article.url_key));
    expect(delivered.articles.every(article => article.article_text.length > 0)).toBe(true);
    expect(delivered.articles.find(article => article.categories.length > 0)!.categories).toHaveLength(4);
    const earlyKey = randomUUID();
    const earlyCorrelation = randomUUID();
    const earlyFetch = await (await fetch(`${url}/fetch`, json({
      request_id: earlyKey, correlation_id: earlyCorrelation, feed_id: "recorded-news",
      kind: "article", url: "https://news.example/second",
    }))).json();
    const earlyParsed = await (await fetch(`${url}/parse`, json({
      request_id: randomUUID(), fetch_request_id: earlyKey, article_id: earlyFetch.article_id, correlation_id: earlyCorrelation,
    }))).json();
    const closedHealth = await (await fetch(`${url}/feed-health-state`, json({ batch_id: earlyParsed.batch_id }))).json();
    const closedPaths: string[] = closedHealth.files.files.map((file: { path: string }) => join(api.inputs.outputRoot, file.path));
    const closedBytes = await Promise.all(closedPaths.map(path => readFile(path)));
    const afterHealth = await (await fetch(`${url}/select-articles`, json({ batch_id: earlyParsed.batch_id }))).json();
    expect(afterHealth.run_id).not.toBe(earlyParsed.run_id);
    const afterHealthRows = await (await fetch(`${url}/feed-health-state`, json({ batch_id: afterHealth.batch_id }))).json();
    expect(afterHealthRows.rows[0]).toMatchObject({
      run_id: afterHealth.run_id, checked_at: null, feed_reads: 0, productive_reads: 0, failed_reads: 0,
      feed_requests: 0, article_requests: 0, robots_requests: 0,
    });
    const afterHealthPartition = await (await fetch(`${url}/partition-articles`, json({ batch_id: afterHealth.batch_id, strategy: "none" }))).json();
    const afterHealthResponse = await fetch(`${url}/persist-selected-articles`, json({ batch_id: afterHealthPartition.batch_id }));
    expect(afterHealthResponse.status).toBe(200);
    const afterHealthSaved = await afterHealthResponse.json();
    expect(afterHealthSaved.run_status).toBe("completed");
    expect((await readPlannerParquet(join(api.inputs.outputRoot, afterHealthSaved.run_files.files[0].path),
      "plan-runs", PlanRunRowContract)).rows[0]!.run_id).toBe(afterHealth.run_id);
    const closedExecution = await currentExecutionState(api.inputs, earlyParsed.run_id);
    const workOnlyRun = await closedExecution?.run_result;
    expect(workOnlyRun?.row).toMatchObject({ run_id: earlyParsed.run_id, selected_count: 0, selected_articles_artifact: null });
    expect(await Promise.all(closedPaths.map(path => readFile(path)))).toEqual(closedBytes);
    expect(await Promise.all(originalPaths.map(path => readFile(path)))).toEqual(originalBytes);
    expect(await Promise.all(selectedPaths.map(path => readFile(path)))).toEqual(selectedBytes);
  } finally { await server.stop(true); app.close(); await api.close(); await cli.close(); }
});

test("a required source write failure returns an API error, not proven planning completion", async () => {
  const recorded = await recordedPlan();
  const app = createPlanApp(recorded.inputs, recorded.runtime);
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
    const failedApp = createPlanApp(failedCapture.inputs, failedCapture.runtime);
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
        { operation: "feed-health-for-selection", status: "failed" },
      ]);
      expect(healthTimings.every((timing: { duration_ms: number }) => Number.isSafeInteger(timing.duration_ms) && timing.duration_ms >= 0)).toBe(true);
      const requestCount = failedCapture.transport.requests.length;
      failedCapture.runtime.run_number = "701";
      delete failedCapture.runtime.progress;
      const failedBeforeWork = await (await failedApp.request(`${prefix}/plan`, json({}))).json();
      expect(failedBeforeWork.status).toBe("failed");
      expect(failedBeforeWork.api_timings.filter((timing: { operation: string }) => timing.operation.startsWith("feed-health-")))
        .toMatchObject([{ operation: "feed-health-before-fetch", status: "failed" }]);
      expect(failedCapture.transport.requests.length).toBe(requestCount);
    } finally { failedApp.close(); await failedCapture.close(); }
  } finally { app.close(); await recorded.close(); }
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
      request_id: randomUUID(), correlation_id: randomUUID(), feed_id: "recorded-news", kind: "feed",
    }));
    expect(independent.status).toBe(200);
    expect(activeParsers).toBeGreaterThan(0);
    const results = await Promise.all([first, second].map(async pending => (await pending).json()));
    expect(peak).toBeGreaterThan(1);
    expect(peak).toBeLessThanOrEqual(recorded.inputs.settings.listener.parser_concurrency);
    const firstCompletion = recorded.events.findIndex(event => event.operation === "plan" && event.phase === "completed");
    expect(new Set(recorded.events.slice(0, firstCompletion).filter(event =>
      event.operation === "plan" && event.phase === "started").map(event => event.run_id)).size).toBe(2);
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
  const app = createPlanApp(recorded.inputs, recorded.runtime);
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
      request_id: fetchKey, correlation_id: correlationId, feed_id: "recorded-news", kind: "article", url: "https://news.example/second",
    }))).json();
    app.close();
    const loaded = await loadPlanInputs(fileURLToPath(new URL("../../../", import.meta.url)));
    const restartedInputs = { ...loaded, root: recorded.inputs.root, outputRoot: recorded.inputs.outputRoot,
      settings: recorded.inputs.settings, harvest: recorded.inputs.harvest };
    const restarted = createPlanApp(restartedInputs, { ...recorded.runtime, clock: () => new Date("2026-10-23T00:00:00Z") });
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
      expect(persistedResponse.status).toBe(200);
      const persisted = await persistedResponse.json();
      const run = (await readPlannerParquet(join(restartedInputs.outputRoot, persisted.run_files.files[0].path),
        "plan-runs", PlanRunRowContract)).rows[0]!;
      expect(run.duration_ms).toBeNull();
      expect(run.date).toBe("2026-10-22");
      expect(run.evaluated_at).toBe("2026-10-22T00:10:00Z");
      expect(run.selection_started_at_utc).toBe("2026-10-23T00:00:00Z");
    } finally { restarted.close(); }
  } finally { app.close(); await recorded.close(); }
});

test("a listener keeps first-seen evidence stable across UTC midnight", async () => {
  const recorded = await recordedPlan();
  let workClock = "2026-10-21T23:59:59Z";
  recorded.runtime.observation_clock = () => new Date(workClock);
  recorded.runtime.selection_clock = () => new Date("2026-10-22T00:00:05Z");
  recorded.transport.on_request = request => {
    if (request.url.pathname !== "/feed.xml" && request.url.pathname !== "/robots.txt") workClock = "2026-10-22T00:00:01Z";
  };
  const app = createPlanApp(recorded.inputs, recorded.runtime);
  try {
    const response = await app.request(`${prefix}/plan`, json({ article_limit: 2 }));
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
  } finally { app.close(); await recorded.close(); }
});
