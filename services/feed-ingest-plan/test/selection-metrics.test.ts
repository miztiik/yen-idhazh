/** Do completed selections save exact metrics without treating missing evidence as zero? */
import { expect, test } from "bun:test";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import {
  PlanRunRowSchema, PlanRunRowContract, SelectedArticleMetadataSchema, deriveUrlKey,
  SelectedFeedBatchSchema, selectedArticleMetadata, PLANNER_API_PREFIX,
} from "@idhazh/common-contracts";
import { persistLedger, readPlannerParquet } from "@idhazh/ledger-file-writer";
import { plannerRecordings } from "../../../packages/ledger-file-writer/test/planner-recordings";
import { summarizeSelectionMetrics } from "../src/summarize-selection-metrics";
import { recordedPlan } from "./plan-recordings";
import { recordedPersistenceBatch } from "./persistence-recordings";
import { createPlanTestServer } from "./plan-test-server";
import { stageStore } from "../src/api/stage-store";
import { currentExecutionState } from "../src/api/document-state";
import { PersistenceResponseSchema, SelectionResponseSchema } from "../src/api/stage-response.schema";
import { FetchResponseSchema, ParseResponseSchema } from "../src/api/document-response.schema";
import { operationLink } from "../src/api/operation-context";

async function selected(canonical_url: string, feed_id: string, score: number) {
  const rows = await Bun.file(new URL(
    "../../../tests/fixtures/feed-ingest-plan/entry-points/selected-articles.rows.json", import.meta.url)).json();
  return SelectedArticleMetadataSchema.parse({
    ...selectedArticleMetadata({ ...rows[0], article_text: "" }), canonical_url, url_key: deriveUrlKey(canonical_url), feed_id,
    ratings: {
      base_article_score: score, marginal_score: score, feed_authority_score: 0, recency_score: 0,
      adjustments: [
        { term: "article_pass_rate", value: 0 }, { term: "substance_quality_score", value: score },
        { term: "domain_diversity_penalty", value: 0 }, { term: "feed_diversity_penalty", value: 0 },
        { term: "novelty_bonus", value: 0 },
      ],
    },
  });
}

test("counts canonical websites and feed first uses even with zero novelty, without changing metadata", async () => {
  const articles = await Promise.all([
    selected("https://a.example.co.uk/one", "first-feed", -0.25),
    selected("https://b.example.co.uk/two", "second-feed", 0.5),
    selected("https://localhost/three", "first-feed", 1.25),
    selected("https://LOCALHOST./four", "third-feed", 0.5),
  ]);
  const before = structuredClone(articles);
  expect(summarizeSelectionMetrics(articles, true)).toEqual({
    selected_website_groups: 2, selected_feeds: 3, mean_substance_score: 0.5,
  });
  expect(articles).toEqual(before);
  expect(summarizeSelectionMetrics([], true)).toEqual({
    selected_website_groups: 0, selected_feeds: 0, mean_substance_score: null,
  });
  const privateSites = await Promise.all([
    selected("https://one.eu.org/story", "same-feed", 0),
    selected("https://two.eu.org/story", "same-feed", 0),
  ]);
  expect(summarizeSelectionMetrics(privateSites, true).selected_website_groups).toBe(2);
  expect(summarizeSelectionMetrics(privateSites, false).selected_website_groups).toBe(1);
});

test("refuses absent, duplicate and non-finite substance terms rather than skipping or zero filling", async () => {
  const article = await selected("https://example.org/one", "first-feed", 0.5);
  const withoutSubstance = article.ratings.adjustments.filter(entry => entry.term !== "substance_quality_score");
  for (const adjustments of [
    withoutSubstance, [...article.ratings.adjustments, { term: "substance_quality_score" as const, value: 0 }],
    ...[NaN, Infinity, -Infinity].map(value => article.ratings.adjustments.map(entry =>
      entry.term === "substance_quality_score" ? { ...entry, value } : entry)),
  ]) {
    expect(() => summarizeSelectionMetrics([{ ...article, ratings: { ...article.ratings, adjustments } }], true)).toThrow();
  }
});

test("requires native metric availability, empty consistency and positive bounded nonempty counts", () => {
  const run = plannerRecordings().find(row => row.name === "plan-runs")!.row;
  expect(PlanRunRowSchema.parse(run).selection_metrics).toBeNull();
  const empty = { selected_website_groups: 0, selected_feeds: 0, mean_substance_score: null };
  expect(PlanRunRowSchema.parse({ ...run, selection_metrics: empty }).selection_metrics).toEqual(empty);
  const metrics = { selected_website_groups: 1, selected_feeds: 2, mean_substance_score: -0.1 };
  const nonempty = { ...run, selected_count: 2, selection_metrics: metrics };
  expect(PlanRunRowSchema.parse(nonempty).selection_metrics).toEqual(metrics);
  const { selection_metrics: omitted, ...missing } = run;
  expect(PlanRunRowSchema.safeParse(missing).success).toBe(false);
  for (const invalid of [
    { ...nonempty, selection_metrics: null }, { ...nonempty, selection_metrics: empty },
    { ...run, selection_metrics: metrics },
    ...[
      { selected_feeds: 0 }, { selected_feeds: 3 }, { selected_feeds: 1.5 },
      { selected_website_groups: 0 }, { selected_website_groups: 3 }, { selected_website_groups: -1 },
      { mean_substance_score: null }, { mean_substance_score: Infinity }, { mean_substance_score: NaN },
    ].map(change => ({ ...nonempty, selection_metrics: { ...metrics, ...change } })),
  ]) expect(PlanRunRowSchema.safeParse(invalid).success).toBe(false);
});

const json = (body: unknown) => ({
  method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
});

async function savedRuns(inputs: Awaited<ReturnType<typeof recordedPlan>>["inputs"], day: string) {
  // Only this test's newly generated day directory is enumerated.
  const { readdir } = await import("node:fs/promises");
  const directory = join(inputs.outputRoot, "raw", "feed-ingest-plan", "plan-runs", ...day.split("-"));
  const files = await readdir(directory);
  return (await Promise.all(files.map(file => readPlannerParquet(
    join(directory, file), "plan-runs", PlanRunRowContract)))).flatMap(file => file.rows);
}

test("standalone persistence saves complete and empty metrics through actual raw and compact readback", async () => {
  for (const empty of [false, true]) {
    const fixture = await recordedPlan();
    const app = createPlanTestServer(fixture.inputs, fixture.runtime);
    try {
      const batch = await recordedPersistenceBatch(fixture.inputs, fixture.runtime, { empty });
      const before = structuredClone(batch.articles);
      const response = await app.request(`${PLANNER_API_PREFIX}/persist-selected-articles`, json({ links: [operationLink(batch)] }));
      expect(response.status).toBe(200);
      const persisted = PersistenceResponseSchema.parse(await response.json());
      const native = await readPlannerParquet(join(fixture.inputs.outputRoot, persisted.run_files!.files[0]!.path),
        "plan-runs", PlanRunRowContract);
      const row = native.rows[0]!;
      expect(row.selected_count).toBe(batch.articles.length);
      expect(row.selection_metrics).toEqual(summarizeSelectionMetrics(batch.articles, true));
      const compact = await persistLedger({
        ledger: "plan-runs", rowContract: PlanRunRowContract, rows: native.rows,
        outputRoot: fixture.inputs.outputRoot, registryEntry: fixture.inputs.registrations.plan_runs,
        ledgerSettings: fixture.inputs.ledgerSettings,
        period: { tier: "compact", period: "daily", covers: row.date, builtFrom: native.rows.length },
      });
      expect(compact.status).toBe("written");
      const packed = await readPlannerParquet(join(fixture.inputs.outputRoot, compact.files[0]!.path),
        "plan-runs", PlanRunRowContract);
      expect(packed.rows).toEqual(native.rows);
      expect(stageStore(fixture.inputs).read("selected", batch, SelectedFeedBatchSchema).articles).toEqual(before);
    } finally { await app.close(); await fixture.close(); }
  }
});

test("standalone persistence failure retains completed selection and honest counts in the native run", async () => {
  const fixture = await recordedPlan();
  const app = createPlanTestServer(fixture.inputs, fixture.runtime);
  try {
    const batch = await recordedPersistenceBatch(fixture.inputs, fixture.runtime);
    const directory = join(fixture.inputs.outputRoot, "raw", "feed-ingest-plan");
    await mkdir(directory, { recursive: true });
    await writeFile(join(directory, "selected-articles"), "recorded obstruction");
    const response = await app.request(`${PLANNER_API_PREFIX}/persist-selected-articles`, json({ links: [operationLink(batch)] }));
    expect(response.status).toBe(500);
    const [row] = await savedRuns(fixture.inputs, batch.context.date);
    expect(row).toMatchObject({
      status: "failed", failure_code: "PERSIST_FAILED", selected_count: batch.articles.length,
      selection_metrics: summarizeSelectionMetrics(batch.articles, true), selected_articles_artifact: null,
    });
    expect(row!.api_timings.at(-1)).toMatchObject({ operation: "persist", status: "failed" });
    await rm(join(directory, "selected-articles"));
    const repeated = await app.request(`${PLANNER_API_PREFIX}/persist-selected-articles`, json({ links: [operationLink(batch)] }));
    expect(repeated.status).toBe(500);
    expect(await savedRuns(fixture.inputs, batch.context.date)).toEqual([row!]);
  } finally { await app.close(); await fixture.close(); }
});

test("standalone partition failure retains the completed selected population", async () => {
  const fixture = await recordedPlan();
  const app = createPlanTestServer(fixture.inputs, fixture.runtime);
  try {
    const batch = await recordedPersistenceBatch(fixture.inputs, fixture.runtime, { partition_enabled: true });
    stageStore(fixture.inputs).replace("selected", SelectedFeedBatchSchema, {
      ...batch,
      articles: batch.articles.map(article => ({ ...article, editorial_rank: 2 })),
    });
    const response = await app.request(`${PLANNER_API_PREFIX}/partition-articles`, json({ links: [operationLink(batch)] }));
    expect(response.status).toBe(500);
    const [row] = await savedRuns(fixture.inputs, batch.context.date);
    expect(row).toMatchObject({
      status: "failed", failure_code: "PARTITION_FAILED", selected_count: batch.articles.length,
      selection_metrics: summarizeSelectionMetrics(batch.articles, true), dispatch_count: 0,
    });
  } finally { await app.close(); await fixture.close(); }
});

test("real standalone selection saves completed-empty, nonempty and failed outcomes", async () => {
  for (const mode of ["nonempty", "empty", "selection-failed"] as const) {
    const fixture = await recordedPlan();
    fixture.inputs.harvest.config.partition.enabled = false;
    if (mode === "empty") fixture.inputs.harvest.config.triage.min_words = 1_000_000;
    if (mode === "selection-failed") fixture.inputs.harvest.config.curate_articles.substance.headline.punctuation_patterns = ["["];
    const app = createPlanTestServer(fixture.inputs, fixture.runtime);
    try {
      const fetchedResponse = await app.request(`${PLANNER_API_PREFIX}/fetch`, json({
        feed_id: "recorded-news",
        fetch_item_type: "article", url: "https://news.example/second",
      }));
      const fetched = FetchResponseSchema.parse(await fetchedResponse.json());
      const parsedResponse = await app.request(`${PLANNER_API_PREFIX}/parse`, json({
        links: [operationLink(fetched)],
      }));
      const parsed = ParseResponseSchema.parse(await parsedResponse.json());
      const response = await app.request(`${PLANNER_API_PREFIX}/select-articles`, json({ links: [operationLink(parsed)] }));
      if (mode === "selection-failed") {
        expect(response.status).toBe(400);
        expect(await response.json()).toMatchObject({ code: "INVALID_INPUT" });
        const [row] = await savedRuns(fixture.inputs, fetched.run_id.slice(0, 10));
        expect(row).toMatchObject({
          status: "failed", failure_code: "SELECTION_FAILED", selected_count: 0, selection_metrics: null,
        });
        expect(row!.selection_started_at_utc).not.toBeNull();
        continue;
      }
      expect(response.status).toBe(200);
      const selection = SelectionResponseSchema.parse(await response.json());
      expect(selection.articles.length).toBe(mode === "empty" ? 0 : 1);
      const state = await currentExecutionState(fixture.inputs, selection.run_id);
      const metrics = state!.completed_selection!.selection_metrics;
      const persistedResponse = await app.request(`${PLANNER_API_PREFIX}/persist-selected-articles`, json({ links: [operationLink(selection)] }));
      expect(persistedResponse.status).toBe(200);
      const persisted = PersistenceResponseSchema.parse(await persistedResponse.json());
      const native = await readPlannerParquet(join(fixture.inputs.outputRoot, persisted.run_files!.files[0]!.path),
        "plan-runs", PlanRunRowContract);
      expect(native.rows[0]!.selection_metrics).toEqual(metrics);
      expect(metrics).toEqual(summarizeSelectionMetrics(selection.articles, true));
    } finally { await app.close(); await fixture.close(); }
  }
});
