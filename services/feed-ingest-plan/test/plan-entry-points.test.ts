/** Do one real API child and one awaited CLI child retain valid selected output? */
import { expect, test } from "bun:test";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  DiscoveredArticleRowContract, FeedHealthStateRowContract, FeedIngestEventSchema,
  PlanRunRowContract, RejectedArticleRowContract, SelectedArticleRowContract,
  SelectedArticlesArtifactSchema, selectedArticleMetadata,
} from "@idhazh/common-contracts";
import type { LedgerRowContract } from "@idhazh/ledger-file-writer";
import { invokePlannerHttp } from "../scripts/feed-ingest-plan-supervisor";
import { PlanResponseSchema } from "../src/api/plan-response.schema";
import { FeedHealthStateUpdateResponseSchema } from "../src/api/feed-health-state.schema";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { recordedPlannerProcess } from "./planner-process-recordings";

const recordings = new URL("../../../tests/fixtures/feed-ingest-plan/entry-points/", import.meta.url);

test("one recorded API request writes a valid selected artifact", async () => {
  const fixture = await recordedPlannerProcess();
  fixture.startup.planning.partition.enabled = true;
  try {
    const result = await invokePlannerHttp(fixture.inputs, fixture.startup, { article_limit: 1 }, fixture.evidence, {
      serverEntry: fixture.serverEntry,
    });
    const summary = PlanResponseSchema.parse(result.summary);
    expect(result.http_status).toBe(200);
    expect(summary.planning_complete).toBe(true);
    expect(summary.selected_count).toBe(1);
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
    const selected = (await Promise.all(summary.files.selected_articles!.files.map(file =>
      readPlannerParquet(join(fixture.inputs.outputRoot, file.path), "selected-articles", SelectedArticleRowContract))))
      .flatMap(file => file.rows);
    expect(selected).toEqual(artifact.articles.map(article => ({
      ...selectedArticleMetadata(article), run_id: artifact.run_id, attempt: artifact.attempt, date: artifact.date,
    })));
    const events = FeedIngestEventSchema.array().parse((await readFile(
      join(fixture.directory, "recorded-events.jsonl"), "utf8")).trim().split("\n").map(line => JSON.parse(line)));
    expect(events.filter(event => event.operation === "plan" && event.phase === "started")).toHaveLength(1);
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
    }
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
    expect(summary.batches.partition_batch_id).toBeUndefined();
    expect(summary.selection_started_at_utc).toBe("2026-10-22T00:00:00Z");
    expect(summary.evaluated_at).toBe(fixture.startup.runtime.captured_at.replace(/\.\d{3}Z$/, "Z"));
    expect(JSON.stringify(summary)).not.toContain("article_text");
    expect(summary.assignments).toEqual([{
      url_key: summary.selected_url_keys[0]!, editorial_rank: 1, worker_assignment: null,
    }]);
    const artifact = SelectedArticlesArtifactSchema.parse(await Bun.file(
      join(fixture.directory, summary.selected_articles_artifact!)).json());
    expect(artifact.run_id).toBe(summary.run_id);
    expect(artifact.articles).toHaveLength(1);
    expect(artifact.articles[0]!.article_text.length).toBeGreaterThan(0);
    const events = FeedIngestEventSchema.array().parse((await readFile(
      join(fixture.directory, "recorded-events.jsonl"), "utf8")).trim().split("\n").map(line => JSON.parse(line)));
    expect(events.filter(event => event.operation === "plan" && event.phase === "started")).toHaveLength(1);
  } finally {
    if (child.exitCode === null) { child.kill(); await child.exited; }
    await fixture.close();
  }
});
