/** Verify the real four-ledger flow, clocks, partial work and text boundary on recorded content. */
import { expect, test } from "bun:test";
import { basename, dirname, join } from "node:path";
import { mkdir, writeFile, readFile, stat } from "node:fs/promises";
import { createHash } from "node:crypto";
import {
  DiscoveredArticleRowContract, SelectedArticleRowContract, FeedHealthStateRowContract, PlanRunRowContract,
  SelectedArticlesArtifactSchema, deriveUrlKey,
  RAW_DAY_INDEX_VERSION,
} from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import { runFeedPlan, summarizePlan } from "../src/run-feed-plan";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";
import { executeSelection } from "../src/api/selection-operation";
import { endpointKey } from "../src/read-ledger-history/read-feed-history";

async function writeHistoricalHealth(recorded: Awaited<ReturnType<typeof recordedPlan>>, day: string) {
  const row = FeedHealthStateRowContract.schema.parse({
    date: day, run_id: `${day}-900`, attempt: 1, feed_id: "recorded-news",
    endpoint_key: endpointKey("https://news.example/feed.xml"), checked_at: `${day}T10:00:00Z`,
    permission: "allowed", availability: "unknown", strikes: null, rested_runs: null,
    last_failure_code: "FETCH_FAILED_HTTP", status: 503, reliability: null,
    feed_reads: 1, productive_reads: 0, failed_reads: 1, article_candidates: 0, articles_selected: 0,
    feed_requests: 2, article_requests: 3, robots_requests: 1, counts_complete: true, rejection_counts: [],
    items: 0, outcome: "transient",
  });
  const result = await persistLedger({
    ledger: "feed-health-state", registryEntry: recorded.inputs.registrations.feed_health_state, rowContract: FeedHealthStateRowContract,
    outputRoot: recorded.inputs.outputRoot, ledgerSettings: recorded.inputs.ledgerSettings,
    period: { tier: "raw", covers: day }, updatedAt: `${day}T11:00:00Z`, rows: [row],
  });
  const path = join(recorded.inputs.outputRoot, result.files[0]!.path);
  const index = join(dirname(path), "index.json");
  const names = [basename(path)];
  await writeFile(index, JSON.stringify({
    version: RAW_DAY_INDEX_VERSION, ledger: "feed-health-state", date: day, files: names, bytes: [(await stat(path)).size],
    content_sha256: createHash("sha256").update(names.join("\n")).digest("hex"), listed_at: `${day}T12:00:00Z`,
  }));
  return { path, index, index_bytes: await readFile(index, "utf8") };
}

test("real composition separates run and selection clocks and reads native dispatches with exact choices", async () => {
  const recorded = await recordedPlan();
  recorded.runtime.selection_clock = () => new Date("2026-10-22T00:00:02Z");
  try {
    const result = await runFeedPlan({ article_limit: 2, partition_strategy: "round-robin", shards: 2 }, recorded.inputs, recorded.runtime);
    expect(result.row.status).toBe("completed");
    expect(result.row.date).toBe("2026-10-21");
    expect(result.row.evaluated_at).toBe("2026-10-21T23:59:59Z");
    expect(result.row.selection_started_at_utc).toBe("2026-10-22T00:00:02Z");
    expect(result.selected.map(article => article.url_key)).toEqual([
      deriveUrlKey("https://news.example/second"), deriveUrlKey("https://news.example/story?a=1&b=2"),
    ]);
    expect(result.selected.map(article => article.worker_assignment)).toEqual([0, 1]);
    const selected = await readPlannerParquet(join(recorded.inputs.outputRoot, result.files.selected_articles!.files[0]!.path),
      "selected-articles", SelectedArticleRowContract);
    const artifact = SelectedArticlesArtifactSchema.parse(JSON.parse(await readFile(join(recorded.inputs.root, result.row.selected_articles_artifact!), "utf8")));
    expect(artifact.articles.map(article => article.url_key)).toEqual(selected.rows.map(article => article.url_key));
    expect(artifact.articles.every(article => article.article_text.length > 0)).toBe(true);
    expect(selected.rows.map(article => article.editorial_rank)).toEqual([1, 2]);
    expect(selected.rows.map(article => article.worker_assignment)).toEqual([0, 1]);
    for (const row of selected.rows) {
      expect(Object.keys(row)).not.toContain("article_text");
      expect(Object.keys(row)).not.toContain("unit_id");
      expect(Object.keys(row)).not.toContain("git_sha");
      expect(row.ratings.marginal_score).toBeCloseTo(row.ratings.base_article_score
        + row.ratings.adjustments.reduce((total, adjustment) => total + (adjustment.value ?? 0), 0), 12);
    }
    expect(Object.keys(selected.envelope)).not.toContain("unit_id");
    expect(JSON.stringify(recorded.events)).not.toContain(artifact.articles[0]!.article_text);
    const health = (await Promise.all(result.files.feed_health_state!.files.map(file =>
      readPlannerParquet(join(recorded.inputs.outputRoot, file.path), "feed-health-state", FeedHealthStateRowContract)))).flatMap(file => file.rows);
    expect(health.reduce((sum, row) => sum + (row.feed_requests ?? 0), 0)).toBe(1);
    expect(health.reduce((sum, row) => sum + (row.article_requests ?? 0), 0)).toBe(2);
    expect(health.reduce((sum, row) => sum + (row.robots_requests ?? 0), 0)).toBe(1);
    expect(health.reduce((sum, row) => sum + (row.articles_selected ?? 0), 0)).toBe(2);
    const run = await readPlannerParquet(join(recorded.inputs.outputRoot, result.files.plan_runs!.files[0]!.path), "plan-runs", PlanRunRowContract);
    expect(run.rows).toEqual([result.row]);
    expect(result.row.api_timings.some(timing => timing.operation === "feed-health-summary" && timing.status === "completed")).toBe(true);
  } finally { await recorded.close(); }
});

test("freshness equality is admitted; a smaller override really rejects; empty is not complete", async () => {
  const recorded = await recordedPlan([source({ url: "https://news.example/empty.xml" })]);
  try {
    const result = await runFeedPlan({}, recorded.inputs, recorded.runtime);
    expect(result.row.status).toBe("completed");
    expect(result.row.selected_count).toBe(0);
    expect(result.files.selected_articles).toEqual({ status: "empty", files: [] });
    expect(result.row.selected_articles_artifact).not.toBeNull();
    const artifact = SelectedArticlesArtifactSchema.parse(JSON.parse(await readFile(join(recorded.inputs.root, result.row.selected_articles_artifact!), "utf8")));
    expect(artifact.articles).toEqual([]);
    const health = await readPlannerParquet(join(recorded.inputs.outputRoot, result.files.feed_health_state!.files[0]!.path),
      "feed-health-state", FeedHealthStateRowContract);
    expect(health.rows[0]).toMatchObject({ outcome: "ok", items: 0, feed_reads: 1, productive_reads: 0, failed_reads: 1 });
  } finally { await recorded.close(); }
});

test("named native first sight wins for undated articles; arbitrary empty history proves no absence", async () => {
  const recorded = await recordedPlan();
  try {
    const first = await runFeedPlan({}, recorded.inputs, recorded.runtime);
    const originalSettings = JSON.stringify(recorded.inputs.settings);
    await writeHistoricalHealth(recorded, "2026-10-20");
    const fresh = await executeSelection({ batch_id: first.batches.parsed_batch_id! }, recorded.inputs, {
      ...recorded.runtime, selection_clock: () => new Date("2026-10-22T00:10:00Z"),
    });
    expect(JSON.stringify(recorded.inputs.settings)).toBe(originalSettings);
    expect(fresh.batch.evaluated_at).toBe(first.row.evaluated_at);
    expect(fresh.batch.selection_started_at_utc).toBe("2026-10-22T00:10:00Z");
    expect(fresh.batch.request_report.through_day).toBe("2026-10-21");
    expect(fresh.batch.health_rows[0]!.reliability).toMatchObject({ productive: 1, attempted: 2, production_factor: 0.5, complete: false });
    expect(fresh.batch.articles.every(article => article.ratings.adjustments.find(adjustment => adjustment.term === "feed_reliability")!.value! < 0)).toBe(true);
    recorded.runtime.run_number = "701";
    recorded.runtime.clock = () => new Date("2026-10-22T00:10:00Z");
    const second = await runFeedPlan({}, recorded.inputs, recorded.runtime);
    const key = deriveUrlKey("https://news.example/second");
    expect(second.selected.find(article => article.url_key === key)?.timing_at)
      .toBe(first.selected.find(article => article.url_key === key)?.timing_at);
    expect(second.files.discovered_articles).toEqual({ status: "empty", files: [] });
    const discovery = await readPlannerParquet(join(recorded.inputs.outputRoot, first.files.discovered_articles!.files[0]!.path),
      "discovered-articles", DiscoveredArticleRowContract);
    expect(discovery.rows.map(row => row.url_key).sort()).toEqual(first.selected.map(article => article.url_key).sort());
  } finally { await recorded.close(); }
});

test("invalid controls, disabled runs, inactive ledgers and unavailable named history fail before fetching", async () => {
  const recorded = await recordedPlan();
  try {
    for (const request of [{ article_limit: 0 }, { shards: 3, partition_strategy: "none" }, { unknown: true }]) {
      await expect(runFeedPlan(request, recorded.inputs, recorded.runtime)).rejects.toThrow();
    }
    recorded.inputs.settings.enabled = false;
    await expect(runFeedPlan({}, recorded.inputs, recorded.runtime)).rejects.toThrow("disabled");
    expect(recorded.transport.requests).toHaveLength(0);
    recorded.inputs.settings.enabled = true;
    await writeHistoricalHealth(recorded, "2026-10-19");
    const damaged = await writeHistoricalHealth(recorded, "2026-10-20");
    await writeFile(damaged.index, "{\"malformed_index\":true}");
    recorded.runtime.run_number = "702";
    const partialHistory = await runFeedPlan({}, recorded.inputs, recorded.runtime);
    expect(partialHistory.row.status).toBe("completed");
    expect(partialHistory.files.selected_articles!.status).toBe("written");
    expect(partialHistory.selected.length).toBeGreaterThan(0);
    const captured = await readPlannerParquet(join(recorded.inputs.outputRoot, partialHistory.files.feed_health_state!.files[0]!.path),
      "feed-health-state", FeedHealthStateRowContract);
    expect(captured.rows[0]!.reliability).toMatchObject({ productive: 1, attempted: 2, complete: false });
    await writeFile(damaged.index, damaged.index_bytes);
    await writeFile(damaged.path, "corrupt Parquet");
    recorded.runtime.run_number = "703";
    const corruptFile = await runFeedPlan({}, recorded.inputs, recorded.runtime);
    expect(corruptFile.row.status).toBe("completed");
    expect(corruptFile.files.selected_articles!.status).toBe("written");
    const retained = await readPlannerParquet(join(recorded.inputs.outputRoot, corruptFile.files.feed_health_state!.files[0]!.path),
      "feed-health-state", FeedHealthStateRowContract);
    expect(retained.rows[0]!.reliability).toMatchObject({ productive: 2, attempted: 3, complete: false });
  } finally { await recorded.close(); }
});

test("real dispatch persistence failure leaves earlier files but emits no storage completion", async () => {
  const recorded = await recordedPlan();
  try {
    const obstruction = join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan", "selected-articles");
    await mkdir(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan"), { recursive: true });
    await writeFile(obstruction, "not a directory");
    const result = await runFeedPlan({}, recorded.inputs, recorded.runtime);
    expect(result.row.status).toBe("partial");
    expect(result.row.failure_code).not.toBeNull();
    expect(result.files.selected_articles).toBeUndefined();
    expect(result.files.feed_health_state!.status).toBe("written");
    expect(result.files.plan_runs!.status).toBe("written");
    expect(summarizePlan(result).planning_complete).toBe(false);
  } finally { await recorded.close(); }
});
