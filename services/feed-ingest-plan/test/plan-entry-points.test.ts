/** Do one real API child and one awaited CLI child retain valid selected output? */
import { expect, test } from "bun:test";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  DiscoveredArticleRowContract, FeedHealthStateRowContract, FeedIngestEventSchema,
  PlanRunRowContract, RejectedArticleRowContract, SelectedArticleRowContract,
  SelectedArticlesArtifactSchema, selectedArticleMetadata,
  readArticleEntities, FetchedDocumentSchema,
} from "@idhazh/common-contracts";
import type { LedgerRowContract } from "@idhazh/ledger-file-writer";
import { invokePlannerHttp } from "../scripts/feed-ingest-plan-supervisor";
import { PlanResponseSchema } from "../src/api/plan-response.schema";
import { FeedHealthStateUpdateResponseSchema } from "../src/api/feed-health-state.schema";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { recordedPlannerProcess } from "./planner-process-recordings";
import { summarizeSelectionMetrics } from "../src/summarize-selection-metrics";
import { articleEntitiesPath } from "../src/selected-artifact-path";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";
import { captureDocumentContext } from "../src/api/operation-context";
import { fetchDocument } from "../src/api/fetch-operation";
import { stageStore } from "../src/api/stage-store";

const recordings = new URL("../../../tests/fixtures/feed-ingest-plan/entry-points/", import.meta.url);

test("one recorded API request writes a valid selected artifact", async () => {
  const fixture = await recordedPlannerProcess();
  fixture.startup.planning.partition.enabled = true;
  try {
    const result = await invokePlannerHttp(fixture.inputs, fixture.startup, {
      article_limit: 1, include_selected_urls: true,
    }, fixture.evidence, {
      serverEntry: fixture.serverEntry,
    });
    const summary = PlanResponseSchema.parse(result.summary);
    expect(result.http_status).toBe(200);
    expect(summary.planning_complete).toBe(true);
    expect(summary.selected_count).toBe(1);
    expect(summary.include_selected_urls).toBe(true);
    expect(await Bun.file(join(fixture.evidence, "response.json")).json()).toEqual(summary);
    expect(summary).not.toHaveProperty("selected_url_keys");
    expect(summary.dispatch_count).toBe(fixture.startup.planning.partition.default_shards);
    expect(summary.assignments[0]!.worker_assignment).not.toBeNull();
    expect(summary.selection_started_at_utc).toBe("2026-10-22T00:00:00Z");
    expect(summary.evaluated_at).toBe(fixture.startup.runtime.captured_at.replace(/\.\d{3}Z$/, "Z"));
    expect(JSON.stringify(summary)).not.toContain("article_text");
    const artifact = SelectedArticlesArtifactSchema.parse(await Bun.file(
      join(fixture.directory, summary.selected_articles_artifact!)).json());
    expect(artifact.run_id).toBe(summary.run_id);
    expect(artifact.attempt).toBe(summary.attempt);
    expect(artifact.articles).toHaveLength(1);
    expect(artifact.articles[0]!.article_text.length).toBeGreaterThan(0);
    expect(summary.selected_article_ids).toEqual(artifact.articles.map(article => article.url_key));
    expect(summary.assignments).toEqual(artifact.articles.map(article => ({
      article_id: article.url_key, canonical_url: article.canonical_url,
      editorial_rank: article.editorial_rank, worker_assignment: article.worker_assignment,
    })));
    const entities = (await readFile(join(fixture.directory, articleEntitiesPath(
      fixture.inputs.settings.inputs.artifact_root, { run_id: summary.run_id, writer: { attempt: summary.attempt } },
    )), "utf8")).trim().split("\n").map(line => readArticleEntities(JSON.parse(line)));
    expect(entities.length).toBeGreaterThanOrEqual(artifact.articles.length);
    expect(entities.every(record => record.run_id === summary.run_id && record.attempt === summary.attempt)).toBe(true);
    expect(summary.selection_metrics).toEqual(summarizeSelectionMetrics(artifact.articles, true));
    const runs = await Promise.all(summary.files.plan_runs!.files.map(file =>
      readPlannerParquet(join(fixture.inputs.outputRoot, file.path), "plan-runs", PlanRunRowContract)));
    expect(runs.flatMap(file => file.rows).map(row => row.selection_metrics)).toEqual([summary.selection_metrics]);
    const selected = (await Promise.all(summary.files.selected_articles!.files.map(file =>
      readPlannerParquet(join(fixture.inputs.outputRoot, file.path), "selected-articles", SelectedArticleRowContract))))
      .flatMap(file => file.rows);
    expect(selected).toEqual(artifact.articles.map(article => ({
      ...selectedArticleMetadata(article), run_id: artifact.run_id, attempt: artifact.attempt, date: artifact.date,
    })));
    const events = FeedIngestEventSchema.array().parse((await readFile(
      join(fixture.directory, "recorded-events.jsonl"), "utf8")).trim().split("\n").map(line => JSON.parse(line)));
    expect(events.filter(event => event.data.operation === "plan" && event.data.phase === "started")).toHaveLength(1);
    expect(await Bun.file(join(fixture.directory, "recorded-progress.json")).json()).toMatchObject({
      eventType: "FEED_FETCH_COMPLETED", before_completion: true,
    });
    const child = await Bun.file(join(fixture.directory, "recorded-startup.json")).json();
    expect(child.pid).not.toBe(process.pid);
    expect(() => process.kill(child.pid, 0)).toThrow();
    const probe = Bun.serve({
      hostname: fixture.inputs.settings.listener.hostname, port: fixture.inputs.settings.listener.port,
      fetch: () => new Response(),
    });
    await probe.stop(true);
    if (process.env.IDHAZH_CAPTURE_PLANNER_RECORDINGS === "1") {
      await mkdir(recordings, { recursive: true });
      await Promise.all([
        writeFile(new URL("response.json", recordings), `${JSON.stringify(summary, null, 2)}\n`),
        writeFile(new URL("health.json", recordings), `${JSON.stringify(
          FeedHealthStateUpdateResponseSchema.parse(result.health), null, 2)}\n`),
        writeFile(new URL("selected-articles.json", recordings), `${JSON.stringify(artifact, null, 2)}\n`),
        writeFile(new URL("../report-events.json", recordings), `${JSON.stringify(events, null, 2)}\n`),
      ]);
      async function captureRows<T extends object>(
        family: keyof typeof summary.files, ledger: Parameters<typeof readPlannerParquet>[1], contract: LedgerRowContract<T>,
      ) {
        const receipt = summary.files[family];
        if (receipt === undefined) throw new Error(`Verified API result omitted ${ledger} receipts`);
        const rows = (await Promise.all(receipt.files.map(file =>
          readPlannerParquet(join(fixture.inputs.outputRoot, file.path), ledger, contract)))).flatMap(file => file.rows);
        const transcript = contract.schema.array().parse(rows);
        await writeFile(new URL(`${ledger}.rows.json`, recordings), `${JSON.stringify(transcript, null, 2)}\n`);
      }
      await Promise.all([
        captureRows("discovered_articles", "discovered-articles", DiscoveredArticleRowContract),
        captureRows("selected_articles", "selected-articles", SelectedArticleRowContract),
        captureRows("rejected_articles", "rejected-articles", RejectedArticleRowContract),
        captureRows("feed_health_state", "feed-health-state", FeedHealthStateRowContract),
        captureRows("plan_runs", "plan-runs", PlanRunRowContract),
      ]);
      const refused = await recordedPlan([source({ url: "https://news.example/network-error" })]);
      const context = captureDocumentContext(refused.inputs, refused.runtime);
      const store = stageStore(refused.inputs);
      store.beginFetch(context);
      try {
        const fetched = await fetchDocument({
          feed_id: "recorded-news", fetch_item_type: "feed",
        }, context, refused.inputs, refused.runtime, null);
        const document = FetchedDocumentSchema.parse(fetched.artifact);
        expect(document.failure).toBe("network");
        await writeFile(new URL("../../../tests/fixtures/contracts/fetched-document/refused.json", import.meta.url),
          `${JSON.stringify(document, null, 2)}\n`);
      } finally {
        store.finishFetch(context.context, false);
        await refused.close();
      }
    }
    const recorded = SelectedArticlesArtifactSchema.parse(await Bun.file(new URL("selected-articles.json", recordings)).json());
    expect(artifact.articles.map(article => ({
      url_key: article.url_key, feed_id: article.feed_id, canonical_url: article.canonical_url, article_text: article.article_text,
      editorial_rank: article.editorial_rank, ratings: article.ratings,
      word_count: article.word_count, substance_word_count: article.substance_word_count,
    }))).toEqual(recorded.articles.map(article => ({
      url_key: article.url_key, feed_id: article.feed_id, canonical_url: article.canonical_url, article_text: article.article_text,
      editorial_rank: article.editorial_rank, ratings: article.ratings,
      word_count: article.word_count, substance_word_count: article.substance_word_count,
    })));
  } finally { await fixture.close(); }
});

test("one awaited CLI invocation writes one valid result", async () => {
  const fixture = await recordedPlannerProcess(undefined, { reserveListener: false });
  fixture.startup.planning.partition.enabled = false;
  const child = Bun.spawn([process.execPath, fileURLToPath(new URL("./planner-cli-recording.ts", import.meta.url)),
    "--cli", "--article-limit=1"], {
    cwd: fixture.directory, stdin: new Blob([JSON.stringify(fixture.startup)]), stdout: "pipe", stderr: "pipe",
  });

  try {
    const [stdout, stderr, exit] = await Promise.all([
      new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited,
    ]);
    expect(exit, stderr).toBe(0);
    const lines = stdout.trim().split("\n");
    expect(lines).toHaveLength(1);
    const summary = PlanResponseSchema.parse(JSON.parse(lines[0]!));
    expect(summary.planning_complete).toBe(true);
    expect(summary.selected_count).toBe(1);
    expect(summary.dispatch_count).toBe(0);
    expect(summary.strategy).toBe("none");
    expect(summary.include_selected_urls).toBe(false);
    expect(summary.selection_started_at_utc).toBe("2026-10-22T00:00:00Z");
    expect(summary.evaluated_at).toBe(fixture.startup.runtime.captured_at.replace(/\.\d{3}Z$/, "Z"));
    expect(JSON.stringify(summary)).not.toContain("article_text");
    expect(summary.assignments).toEqual([{
      article_id: summary.selected_article_ids[0]!, editorial_rank: 1, worker_assignment: null,
    }]);
    const artifact = SelectedArticlesArtifactSchema.parse(await Bun.file(
      join(fixture.directory, summary.selected_articles_artifact!)).json());
    expect(artifact.run_id).toBe(summary.run_id);
    expect(artifact.articles).toHaveLength(1);
    expect(artifact.articles[0]!.article_text.length).toBeGreaterThan(0);
    expect(summary.selection_metrics).toEqual(summarizeSelectionMetrics(artifact.articles, true));
    const events = FeedIngestEventSchema.array().parse((await readFile(
      join(fixture.directory, "recorded-events.jsonl"), "utf8")).trim().split("\n").map(line => JSON.parse(line)));
    expect(events.filter(event => event.data.operation === "plan" && event.data.phase === "started")).toHaveLength(1);
  } finally {
    if (child.exitCode === null) { child.kill(); await child.exited; }
    await fixture.close();
  }
});

test("the actual awaited CLI fails for a report failure without rewriting completed planning", async () => {
  const fixture = await recordedPlannerProcess(undefined, { reserveListener: false });
  fixture.startup.planning.partition.enabled = false;
  const child = Bun.spawn([process.execPath, fileURLToPath(new URL("./planner-cli-recording.ts", import.meta.url)),
    "--cli", "--article-limit=1"], {
    cwd: fixture.directory, stdin: new Blob([JSON.stringify(fixture.startup)]), stdout: "pipe", stderr: "pipe",
    env: { ...process.env, IDHAZH_TEST_REPORT_CLOCK_FAILURE: "1" },
  });
  try {
    const [stdout, stderr, exit] = await Promise.all([
      new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited,
    ]);
    expect(exit, stderr).toBe(2);
    const summary = PlanResponseSchema.parse(JSON.parse(stdout.trim()));
    expect(summary).toMatchObject({
      planning_complete: true, status: "completed", failure_code: null, selected_count: 1,
      health: { status: "failed", failure: { error_type: "RangeError" } },
      failure: { error_type: "RangeError" },
    });
    const runs = await Promise.all(summary.files.plan_runs!.files.map(file =>
      readPlannerParquet(join(fixture.inputs.outputRoot, file.path), "plan-runs", PlanRunRowContract)));
    expect(runs.flatMap(file => file.rows)).toMatchObject([{
      status: "completed", failure_code: null, selected_count: 1,
      api_timings: summary.api_timings, duration_ms: summary.duration_ms,
    }]);
    const artifact = SelectedArticlesArtifactSchema.parse(await Bun.file(
      join(fixture.directory, summary.selected_articles_artifact!)).json());
    expect(artifact.articles).toHaveLength(1);
    const events = FeedIngestEventSchema.array().parse((await readFile(
      join(fixture.directory, "recorded-events.jsonl"), "utf8")).trim().split("\n").map(line => JSON.parse(line)));
    expect(events.filter(event => event.data.operation === "plan" && event.data.phase === "failed")).toHaveLength(1);
    expect(events.some(event => event.data.operation === "plan" && event.data.phase === "completed")).toBe(false);
  } finally {
    if (child.exitCode === null) { child.kill(); await child.exited; }
    await fixture.close();
  }
});
