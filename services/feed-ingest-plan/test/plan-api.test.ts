/** Does the real Hono handler reject invalid requests before recorded harvesting? */
import { expect, test } from "bun:test";
import { fileURLToPath } from "node:url";
import { createPlanApp } from "../src/api/server";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { RecordedTransport, readRecordings } from "./harvest-recordings";
import { recordedPlan } from "./plan-recordings";
import { main } from "../src/index";
import { mkdir, unlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import type { PersistedLedgerFile } from "@idhazh/ledger-file-writer";
import { readLedgerParquet } from "../src/read-ledger-history/read-parquet";
import { SeenRowSchema } from "../src/screen-article-candidates/seen-evidence";
import { source } from "./harvest-recordings";
import { ArticleAssessmentRecordSchema, CONTRACT_VERSION, DiversityMetricRowSchema } from "@idhazh/common-contracts";
import { existsSync } from "node:fs";

test("health is explicit; disabled, malformed, oversized and unknown controls cannot fetch", async () => {
  const inputs = await loadPlanInputs(fileURLToPath(new URL("../../../", import.meta.url)));
  const transport = new RecordedTransport(await readRecordings());
  const app = createPlanApp(inputs, {
    git_sha: "a".repeat(40), boundary: { transport, resolve: transport.resolve },
  });

  const health = await app.request("/api/2026-10-20/health");
  expect(health.status).toBe(200);
  expect(await health.json()).toEqual({
    status: "available", planner_enabled: false, audited_completion_available: false,
  });
  const post = (body: string) => app.request("/api/2026-10-20/plan", {
    method: "POST", headers: { "Content-Type": "application/json" }, body,
  });
  const disabled = await post("{}");
  expect(disabled.status).toBe(503);
  expect((await disabled.json()).code).toBe("PLANNER_DISABLED");
  for (const request of [
    { freshness_hours: "18" }, { article_limit: null }, { shards: 1.5 },
    { date: "2026-10-21" }, { freshness_hours: 0 }, { partition_strategy: "random" },
    { partition_strategy: "none", shards: 2 }, { shards: inputs.harvest.config.partition.max_shards + 1 },
  ]) {
    const refused = await post(JSON.stringify(request));
    expect(refused.status).toBe(400);
    expect((await refused.json()).issues.length).toBeGreaterThan(0);
  }
  const malformed = await post("{");
  expect(malformed.status).toBe(400);
  expect((await malformed.json()).issues[0].field).toBe("body");
  const oversized = await post(" ".repeat(inputs.settings.listener.max_body_bytes + 1));
  expect(oversized.status).toBe(413);
  expect((await oversized.json()).code).toBe("BODY_TOO_LARGE");
  expect((await app.request("/api/old/health")).status).toBe(404);
  expect(transport.requests).toHaveLength(0);
});

test("actual API and awaited CLI compose the same recorded plan and disclose the same audit limit", async () => {
  const api = await recordedPlan();
  const cli = await recordedPlan();
  try {
    const app = createPlanApp(api.inputs, api.runtime);
    const response = await app.request("/api/2026-10-20/plan", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ freshness_hours: 18, article_limit: 1, partition_strategy: "none" }),
    });
    expect(response.status).toBe(409);
    const apiResult = await response.json();
    const printed: unknown[] = [];
    const cliResult = await main([
      "--cli", "--freshness-hours", "18", "--article-limit=1", "--partition-strategy", "none",
    ], { inputs: cli.inputs, runtime: cli.runtime, output: value => { printed.push(value); } });
    if (!("audited_complete" in cliResult)) throw new Error("CLI unexpectedly started a server");
    expect(cliResult.audited_complete).toBe(false);
    expect(printed).toEqual([cliResult]);
    for (const field of ["run_id", "correlation_id", "date", "observed_at", "request",
      "strategy", "dispatch_count", "selected_candidate_ids", "assignments", "audit", "status"] as const) {
      expect(apiResult[field]).toEqual(cliResult[field]);
    }
    expect(apiResult.files.dispatches.status).toBe("written");
    expect(cliResult.files.dispatches.status).toBe("written");
    expect(api.transport.requests.length).toBeGreaterThan(0);
    expect(cli.transport.requests.map(request => request.url.href)).toEqual(api.transport.requests.map(request => request.url.href));
    expect(apiResult).not.toHaveProperty("article_text");
    expect(JSON.stringify(apiResult)).not.toContain(api.directory);
    expect(apiResult.audit.status).toBe("assessment_diversity_recorded_audit_pending");
    for (const summary of [apiResult, cliResult]) {
      expect(summary.metrics.audited_complete).toBe(false);
      expect(summary.metrics.status).toBe("assessment_diversity_recorded_audit_pending");
      expect(summary.metrics.source_summaries).toHaveLength(1);
    }
    for (const [recorded, summary] of [[api, apiResult], [cli, cliResult]] as const) {
      const metrics = summary.metrics!;
      const assessment = metrics.files.assessments.files[0]!;
      const diversity = metrics.files.diversity.files[0]!;
      const assessed = await readLedgerParquet(join(recorded.inputs.outputRoot, assessment.path), "article-assessments", {
        schema: ArticleAssessmentRecordSchema, schemaVersion: CONTRACT_VERSION,
      });
      const measured = await readLedgerParquet(join(recorded.inputs.outputRoot, diversity.path), "diversity", {
        schema: DiversityMetricRowSchema, schemaVersion: CONTRACT_VERSION,
      });
      expect(assessed.rows.length).toBe(metrics.receipts.assessments.row_count);
      expect(measured.rows.length).toBe(metrics.receipts.diversity.row_count);
      expect(metrics.receipts.assessments.files[0]!.content_sha256).toBe(assessed.envelope.content_sha256);
      expect(metrics.receipts.diversity.files[0]!.content_sha256).toBe(measured.envelope.content_sha256);
      expect(existsSync(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan", "source-runs"))).toBe(false);
    }
  } finally { await Promise.all([api.close(), cli.close()]); }
}, 30000);

test("one listener coordinates concurrent real requests and retains only its durable seen receipts", async () => {
  const recorded = await recordedPlan([source({ url: "https://news.example/article-failures.xml" })]);
  const receipts: { day: string; files: readonly PersistedLedgerFile[] }[] = [];
  let clocks = 0;
  try {
    recorded.inputs.clock_config.collect.seen_window_days = 0;
    recorded.inputs.settings.inputs.seen_days = [{ day: "2026-10-21", raw_files: [] }];
    delete recorded.runtime.run_number;
    recorded.runtime.clock = () => new Date(`2026-10-21T12:0${clocks++}:00Z`);
    recorded.runtime.on_seen_persisted = receipt => { receipts.push(receipt); };
    const app = createPlanApp(recorded.inputs, recorded.runtime);
    const post = () => app.request("/api/2026-10-20/plan", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
    });
    const responses = await Promise.all([post(), post()]);
    const [first, second] = await Promise.all(responses.map(response => response.json()));
    expect(responses.map(response => response.status)).toEqual([500, 500]);
    expect(clocks).toBe(2);
    expect(first.issues[0].message).toContain("first_seen");
    expect(second.issues[0].message).toContain("first_seen");
    expect(first).not.toHaveProperty("audited_complete");
    expect(second).not.toHaveProperty("metrics");
    expect(receipts).toHaveLength(1);
    const file = await readLedgerParquet(join(recorded.inputs.outputRoot, receipts[0]!.files[0]!.path), "seen", {
      schema: SeenRowSchema, schemaVersion: "2026-08-31",
    });
    expect(file.rows.every(row => row.row.first_seen_at === "2026-10-21T12:00:00Z")).toBe(true);
    expect(new Set(file.rows.map(row => row.row.first_seen_run)).size).toBe(1);
    expect(existsSync(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan", "article-assessments"))).toBe(false);
    expect(existsSync(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan", "diversity"))).toBe(false);
    const fetched = recorded.transport.requests.length;
    recorded.runtime.clock = () => new Date("2026-10-21T11:59:59Z");
    const backwards = await post();
    expect(backwards.status).toBe(500);
    expect((await backwards.json()).issues[0].field).toBe("now");
    recorded.runtime.clock = () => new Date(Number.NaN);
    expect((await post()).status).toBe(500);
    expect(recorded.transport.requests).toHaveLength(fetched);
  } finally { await recorded.close(); }
}, 30000);

test("a later dispatch failure does not lose already durable first sight from this listener", async () => {
  const recorded = await recordedPlan([source({ url: "https://news.example/article-failures.xml" })]);
  const receipts: { day: string; files: readonly PersistedLedgerFile[] }[] = [];
  let clocks = 0;
  try {
    recorded.inputs.clock_config.collect.seen_window_days = 0;
    recorded.inputs.settings.inputs.seen_days = [{ day: "2026-10-21", raw_files: [] }];
    delete recorded.runtime.run_number;
    recorded.runtime.clock = () => new Date(`2026-10-21T12:0${clocks++}:00Z`);
    recorded.runtime.on_seen_persisted = receipt => { receipts.push(receipt); };
    const blocked = join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan", "dispatches");
    await mkdir(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan"), { recursive: true });
    await writeFile(blocked, "A file cannot hold dispatches.");
    const app = createPlanApp(recorded.inputs, recorded.runtime);
    const post = () => app.request("/api/2026-10-20/plan", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
    });
    const failed = await post();
    expect(failed.status).toBe(500);
    expect((await failed.json()).code).toBe("PLAN_FAILED");
    expect(receipts).toHaveLength(1);
    await unlink(blocked);
    const retried = await post();
    expect(retried.status).toBe(500);
    expect((await retried.json()).issues[0].message).toContain("first_seen");
    expect(receipts).toHaveLength(1);
    const native = await readLedgerParquet(join(recorded.inputs.outputRoot, receipts[0]!.files[0]!.path), "seen", {
      schema: SeenRowSchema, schemaVersion: "2026-08-31",
    });
    expect(native.rows.every(row => row.row.first_seen_at === "2026-10-21T12:00:00Z")).toBe(true);
  } finally { await recorded.close(); }
}, 30000);

test("a listener ages accepted history at UTC midnight without inventing new-day evidence", async () => {
  const recorded = await recordedPlan([source({ url: "https://news.example/article-failures.xml" })]);
  const receipts: { day: string; files: readonly PersistedLedgerFile[] }[] = [];
  try {
    recorded.inputs.clock_config.collect.seen_window_days = 1;
    const authored = [
      { day: "2026-10-20", raw_files: [] as string[] },
      { day: "2026-10-21", raw_files: [] as string[] },
    ];
    recorded.inputs.settings.inputs.seen_days = authored;
    delete recorded.runtime.run_number;
    recorded.runtime.clock = () => new Date("2026-10-21T23:59:59Z");
    recorded.runtime.on_seen_persisted = receipt => { receipts.push(receipt); };
    const app = createPlanApp(recorded.inputs, recorded.runtime);
    const post = () => app.request("/api/2026-10-20/plan", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
    });
    const before = await post();
    expect(before.status).toBe(500);
    const first = await before.json();
    expect(first.issues[0].message).toContain("first_seen");
    expect(receipts).toHaveLength(1);

    recorded.runtime.clock = () => new Date("2026-10-22T00:00:01Z");
    recorded.inputs.harvest.sources.push(source({ id: "new-feed" }));
    const fetched = recorded.transport.requests.length;
    const after = await post();
    expect(after.status).toBe(500);
    const second = await after.json();
    expect(recorded.transport.requests.length).toBeGreaterThan(fetched);
    expect(second.issues[0].message).toContain("first_seen");
    expect(receipts).toHaveLength(1);
    const settled = await readLedgerParquet(join(recorded.inputs.outputRoot, receipts[0]!.files[0]!.path), "seen", {
      schema: SeenRowSchema, schemaVersion: "2026-08-31",
    });
    expect(settled.rows.every(row => row.row.first_seen_at === "2026-10-21T23:59:59Z")).toBe(true);
    expect(recorded.inputs.settings.inputs.seen_days).toEqual(authored);

    recorded.inputs.settings.inputs.seen_days = [
      ...authored, { day: "2026-10-22", raw_files: [] },
    ];
    const supplied = await post();
    expect(supplied.status).toBe(500);
    const third = await supplied.json();
    expect(third.issues[0].message).toContain("first_seen");
    expect(receipts).toHaveLength(2);
    const newlySeen = await readLedgerParquet(join(recorded.inputs.outputRoot, receipts[1]!.files[0]!.path), "seen", {
      schema: SeenRowSchema, schemaVersion: "2026-08-31",
    });
    const previous = new Set(settled.rows.map(row => row.row.url_key));
    expect(newlySeen.rows.every(row => !previous.has(row.row.url_key))).toBe(true);

    const requests = recorded.transport.requests.length;
    recorded.inputs.settings.inputs.seen_days = [authored[0]!, authored[0]!, authored[1]!];
    expect((await post()).status).toBe(500);
    recorded.inputs.settings.inputs.seen_days[0] = { day: "2026-10-19", raw_files: [] };
    recorded.inputs.settings.inputs.seen_days.splice(1, 1);
    expect((await post()).status).toBe(500);
    recorded.inputs.settings.inputs.seen_days = [...authored, { day: "2026-10-23", raw_files: [] }];
    expect((await post()).status).toBe(500);
    expect(recorded.transport.requests).toHaveLength(requests);
  } finally { await recorded.close(); }
}, 30000);
