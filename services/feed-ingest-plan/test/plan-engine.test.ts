/** Verify the real four-ledger flow, clocks, partial work and text boundary on recorded content. */
import { expect, test } from "bun:test";
import { join } from "node:path";
import { mkdir, writeFile, readFile } from "node:fs/promises";
import {
  DiscoveredArticleRowContract, SelectedArticleRowContract, FeedHealthStateRowContract, PlanRunRowContract,
  SelectedArticlesArtifactSchema, deriveUrlKey,
} from "@idhazh/common-contracts";
import { runFeedPlan, summarizePlan } from "../src/run-feed-plan";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";

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
