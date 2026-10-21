/** Do measured distributions and real durable audit files tell the same bounded story? */
import { expect, test } from "bun:test";
import { mkdir, readdir, unlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { z } from "zod";
import { ArticleAssessmentRecordSchema, CONTRACT_VERSION, DiversityMetricRowSchema, deriveUrlKey } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import { runFeedPlan } from "../src/run-feed-plan";
import { recordPlanningMetrics, preparePlanningMetrics } from "../src/metrics/metrics-recorder";
import { effectiveSources, measuredRatio, sourceGini, topSourceShare, validateCounts } from "../src/metrics/diversity-metrics";
import { readLedgerParquet } from "../src/read-ledger-history/read-parquet";
import { SeenRowSchema } from "../src/screen-article-candidates/seen-evidence";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";

async function auditFiles(output: string) {
  const directory = join(output, "raw", "feed-ingest-plan");
  const entries = await readdir(directory, { recursive: true });
  return entries.filter(path => /^(article-assessments|diversity|source-runs)([/\\]|$)/.test(path.toString()));
}

test("hand-computable distributions preserve zeros, signed loss and exact concentration counts", () => {
  expect(effectiveSources([1, 1, 1, 1])).toBeCloseTo(4, 12);
  expect(effectiveSources([9, 0, 0])).toBe(1);
  expect(effectiveSources([])).toBe(0);
  expect(effectiveSources([0, 0])).toBe(0);
  expect(sourceGini([1, 1, 1])).toBe(0);
  expect(sourceGini([9, 0, 0])).toBeCloseTo(2 / 3, 12);
  expect(sourceGini([0, 0])).toBeNull();
  expect(topSourceShare([8, 1, 1], 1)).toEqual({ numerator: 8, denominator: 10, value: 0.8 });
  expect(topSourceShare([8, 1, 1], 5)).toEqual({ numerator: 10, denominator: 10, value: 1 });
  expect(topSourceShare([], 10)).toEqual({ numerator: 0, denominator: 0, value: null });
  expect(effectiveSources([9, 1]) - effectiveSources([1, 1])).toBeLessThan(0);
  for (const invalid of [NaN, Infinity, -1, 0.5, Number.MAX_SAFE_INTEGER + 1]) {
    expect(() => validateCounts([invalid], "samples")).toThrow("samples");
  }
  expect(() => measuredRatio(2, 1, "coverage")).toThrow("coverage.numerator");
  expect(() => topSourceShare([1], 2)).toThrow("top_source_counts.2");
});

test("real harvest through partition writes typed assessment/diversity receipts and never source completion", async () => {
  const recorded = await recordedPlan([
    source(), source({ id: "carrier", kind: "research" }), source({ id: "inactive", status: "draft" }),
    source({ id: "empty", url: "https://news.example/empty.xml" }),
  ]);
  try {
    const result = await runFeedPlan({ partition_strategy: "round-robin", shards: 2 }, recorded.inputs, recorded.runtime);
    const entries = recorded.inputs.registrations;
    const batch = preparePlanningMetrics(result, recorded.inputs, entries);
    const before = structuredClone(result);
    const audit = await recordPlanningMetrics(result, recorded.inputs, entries);
    expect(result).toEqual(before);
    expect(audit).toMatchObject({ audited_complete: false, status: "assessment_diversity_recorded_audit_pending" });
    expect(audit.source_summaries).toHaveLength(4);
    expect(audit.receipts.assessments.row_count).toBe(batch.assessments.length);
    expect(audit.receipts.diversity.row_count).toBe(batch.diversity.length);
    async function verify<T extends object>(
      key: "assessments" | "diversity", schema: z.ZodType<T>,
      ledger: "article-assessments" | "diversity", expected: readonly T[],
    ) {
      const files = audit.files[key].files;
      expect(files.length).toBe(1);
      const file = files[0]!;
      const loaded = await readLedgerParquet(join(recorded.inputs.outputRoot, file.path), ledger, {
        schema, schemaVersion: CONTRACT_VERSION,
      });
      expect(loaded.rows.map(item => item.row)).toEqual([...expected]);
      expect(loaded.envelope.content_sha256).toBe(file.content_sha256);
      expect(loaded.envelope.identity.attempt).toBe(result.context.writer.attempt);
      expect(audit.receipts[key].files[0]).toEqual({
        file_id: file.file_id, content_sha256: file.content_sha256, row_count: file.row_count,
      });
    }
    await verify("assessments", ArticleAssessmentRecordSchema, "article-assessments", batch.assessments);
    await verify("diversity", DiversityMetricRowSchema, "diversity", batch.diversity);
    const selected = batch.diversity.filter(row => row.basis === "selected");
    expect(selected.find(row => row.metric === "source_gini")!.source_count).toBe(3);
    expect(selected.find(row => row.metric === "top_source_concentration" && row.top_k === 1)).toMatchObject({
      numerator: 2, denominator: 2, value: 1,
    });
    const counts = batch.diversity.filter(row => row.metric === "source_kind_distribution" && row.unit === "count");
    expect(counts.find(row => row.basis === "eligible" && row.dimension_value === "research")!.value).toBe(2);
    for (const row of batch.diversity.filter(row => row.basis === "published" || row.basis === "leads")) {
      expect(row.availability).toBe("unavailable");
      expect(row.value).toBeNull();
      expect(row.item_count).toBeNull();
    }
    expect(audit.evidence.trace).toEqual(result.evidence.curation.trace);
    expect((await auditFiles(recorded.inputs.outputRoot)).some(path => path.toString().startsWith("source-runs"))).toBe(false);
    expect(result.events.some(event => JSON.stringify(event).includes("plan_complete"))).toBe(false);
  } finally { await recorded.close(); }
}, 30000);

test("known-empty article input yields explicit empty assessment evidence, not a fabricated file", async () => {
  const recorded = await recordedPlan([source({ url: "https://news.example/empty.xml" })]);
  try {
    const result = await runFeedPlan({ partition_strategy: "none" }, recorded.inputs, recorded.runtime);
    const entries = recorded.inputs.registrations;
    const batch = preparePlanningMetrics(result, recorded.inputs, entries);
    const audit = await recordPlanningMetrics(result, recorded.inputs, entries);
    expect(audit.files.assessments).toEqual({ status: "empty", files: [] });
    expect(audit.receipts.assessments).toEqual({ ledger: "article-assessments", row_count: 0, files: [] });
    expect(batch.diversity.find(row => row.metric === "effective_number_of_sources" && row.basis === "selected")).toMatchObject({
      value: 0, availability: "available",
    });
    expect(batch.diversity.find(row => row.metric === "selection_coverage")).toMatchObject({
      value: null, numerator: 0, denominator: 0, unavailable_reason: "empty_denominator",
    });
    expect(audit.audited_complete).toBe(false);
  } finally { await recorded.close(); }
}, 30000);

test("one unsupported count or negative age refuses the whole batch before any audit file and preserves inputs", async () => {
  for (const mode of ["top_k", "negative"] as const) {
    const recorded = await recordedPlan();
    if (mode === "top_k") recorded.inputs.harvest.config.metrics.top_source_counts = [1, 2, 5];
    else recorded.runtime.clock = () => new Date("2026-10-21T09:00:00Z");
    try {
      const result = await runFeedPlan({ partition_strategy: "none" }, recorded.inputs, recorded.runtime);
      const before = structuredClone(result);
      const entries = recorded.inputs.registrations;
      const beforeInputs = structuredClone(recorded.inputs);
      const beforeEntries = structuredClone(entries);
      await expect(recordPlanningMetrics(result, recorded.inputs, entries)).rejects.toThrow(mode === "top_k" ? "top_source_counts.2" : "age_hours");
      expect(result).toEqual(before);
      expect(recorded.inputs).toEqual(beforeInputs);
      expect(entries).toEqual(beforeEntries);
      expect(await auditFiles(recorded.inputs.outputRoot)).toEqual([]);
    } finally { await recorded.close(); }
  }
}, 30000);

test("actual settled first sight for an undated rejected candidate refuses the entire recording", async () => {
  const recorded = await recordedPlan([source({ url: "https://news.example/article-failures.xml" })]);
  try {
    const entries = recorded.inputs.registrations;
    const stored = await persistLedger({
      ledger: "seen", registryEntry: entries.seen, outputRoot: recorded.inputs.outputRoot,
      writerContext: {
        run_id: "2026-10-20-699", attempt: 1, job: null, pipeline_name: "feed-ingest-plan",
        task_name: "plan", shard: 0, producer: "tests.audit", git_sha: "a".repeat(40),
      },
      ledgerSettings: recorded.inputs.ledgerSettings, period: { tier: "raw", covers: "2026-10-20" },
      rowContract: { schema: SeenRowSchema, schemaVersion: "2026-08-31" },
      rows: [{ version: "2026-08-31", url_key: deriveUrlKey("https://news.example/second"),
        first_seen_at: "2026-10-20T10:00:00Z", first_seen_run: "2026-10-20-699" }],
    });
    recorded.inputs.settings.inputs.seen_files = stored.files.map(file => `state/${file.path}`);
    const result = await runFeedPlan({ freshness_hours: 1, partition_strategy: "none" }, recorded.inputs, recorded.runtime);
    expect(result.evidence.screening.rejections.some(row => row.drop_reason === "STALE_MAX_AGE_EXCEEDED")).toBe(true);
    const before = structuredClone(result);
    const beforeInputs = structuredClone(recorded.inputs);
    await expect(recordPlanningMetrics(result, recorded.inputs, entries)).rejects.toThrow("first_seen timestamp and age");
    expect(result).toEqual(before);
    expect(recorded.inputs).toEqual(beforeInputs);
    expect(await auditFiles(recorded.inputs.outputRoot)).toEqual([]);
  } finally { await recorded.close(); }
}, 30000);

test("new first sight from the runner's complete bounded window is preflighted after its real write", async () => {
  const recorded = await recordedPlan([source({ url: "https://news.example/article-failures.xml" })]);
  try {
    recorded.inputs.clock_config.collect.seen_window_days = 0;
    recorded.inputs.settings.inputs.seen_days = [{ day: "2026-10-21", raw_files: [] }];
    const result = await runFeedPlan({ partition_strategy: "none" }, recorded.inputs, recorded.runtime);
    expect(result.evidence.seen.absence_proof).toBe("within_configured_window");
    expect(result.evidence.seen.new_rows.length).toBeGreaterThan(0);
    expect(result.files.seen.status).toBe("written");
    expect(result.evidence.screening.admitted.some(article => article.freshness.timing_source === "first_seen")).toBe(true);
    await expect(recordPlanningMetrics(result, recorded.inputs)).rejects.toThrow("publication_clock");
    expect(await auditFiles(recorded.inputs.outputRoot)).toEqual([]);
    expect(result.evidence.seen.evidence.availability).toBe("available");
  } finally { await recorded.close(); }
}, 30000);

test("paused registry and a real obstructed write cannot return completion; partial files stay incomplete", async () => {
  const recorded = await recordedPlan();
  try {
    const result = await runFeedPlan({ partition_strategy: "none" }, recorded.inputs, recorded.runtime);
    const entries = recorded.inputs.registrations;
    await expect(recordPlanningMetrics(result, recorded.inputs, {
      ...entries, diversity: { ...entries.diversity, lifecycle_status: "paused" },
    })).rejects.toThrow();
    expect(await auditFiles(recorded.inputs.outputRoot)).toEqual([]);
    await mkdir(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan"), { recursive: true });
    await writeFile(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan", "diversity"), "A real file blocks the directory.");
    await expect(recordPlanningMetrics(result, recorded.inputs, entries)).rejects.toThrow();
    const files = await auditFiles(recorded.inputs.outputRoot);
    expect(files.some(path => path.toString().startsWith("article-assessments"))).toBe(true);
    expect(files.some(path => path.toString().startsWith("source-runs"))).toBe(false);
    expect(result.status).toBe("dispatches_persisted_audit_pending");
  } finally { await recorded.close(); }
}, 30000);

test("two real attempts keep separate receipts and cannot combine earlier events or required files", async () => {
  const recorded = await recordedPlan();
  try {
    const entries = recorded.inputs.registrations;
    const first = await runFeedPlan({ partition_strategy: "none" }, recorded.inputs, recorded.runtime);
    const firstAudit = await recordPlanningMetrics(first, recorded.inputs, entries);
    recorded.inputs.settings.run.attempt++;
    const second = await runFeedPlan({ partition_strategy: "none" }, recorded.inputs, recorded.runtime);
    const secondAudit = await recordPlanningMetrics(second, recorded.inputs, entries);
    expect(firstAudit.receipts.assessments.files[0]!.file_id).not.toBe(secondAudit.receipts.assessments.files[0]!.file_id);
    expect(secondAudit.source_summaries[0]!.attempt).toBe(2);
    expect(secondAudit.receipts.assessments.row_count).toBe(firstAudit.receipts.assessments.row_count);
    const ownEvents = second.events;
    second.events = first.events;
    expect(() => preparePlanningMetrics(second, recorded.inputs, entries)).toThrow("events.run");
    second.events = ownEvents;
    second.files.dispatches = first.files.dispatches;
    await expect(recordPlanningMetrics(second, recorded.inputs, entries)).rejects.toThrow("writer");
  } finally { await recorded.close(); }
}, 30000);

test("a missing actual stage file refuses recording before creating either audit ledger", async () => {
  const recorded = await recordedPlan();
  try {
    const result = await runFeedPlan({ partition_strategy: "none" }, recorded.inputs, recorded.runtime);
    await unlink(join(recorded.inputs.outputRoot, result.files.dispatches.files[0]!.path));
    await expect(recordPlanningMetrics(result, recorded.inputs)).rejects.toThrow();
    expect(await auditFiles(recorded.inputs.outputRoot)).toEqual([]);
  } finally { await recorded.close(); }
}, 30000);
