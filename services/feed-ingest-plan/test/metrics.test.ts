/** Do measured distributions and real durable audit files tell the same bounded story? */
import { expect, test } from "bun:test";
import { mkdir, readdir, stat, unlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { z } from "zod";
import {
  ArticleAssessmentRecordSchema, CONTRACT_VERSION, DiversityMetricRowSchema,
  deriveUrlKey,
} from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { PersistLedgerResult } from "@idhazh/ledger-file-writer";
import { runFeedPlan } from "../src/run-feed-plan";
import { recordPlanningMetrics, preparePlanningMetrics, recordPublicationMetrics } from "../src/metrics/metrics-recorder";
import type { PublicationRecorderInput } from "../src/metrics/metrics-recorder";
import { effectiveSources, measuredRatio, sourceGini, topSourceShare, validateCounts } from "../src/metrics/diversity-metrics";
import { readLedgerDay } from "../src/read-ledger-history/read-period";
import { readLedgerParquet } from "../src/read-ledger-history/read-parquet";
import { SeenRowSchema } from "../src/screen-article-candidates/seen-evidence";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";
import { PublishedRowSchema, RecordedEventPairSchema } from "../src/metrics/publication-evidence";
import type { DigestPublication, ItemHealthPublication } from "../src/metrics/publication-evidence";
import { registration } from "./partition-fixtures";
import { readPlanningHistory, settlePlanningDay } from "../src/metrics/planning-populations";
import { recordedPairKey } from "../src/metrics/fingerprint-dedup";
import { loadHarvestInputs } from "../src/harvest-feeds/load-harvest-inputs";
import {
  ArticleAssessmentContract, DiversityMetricContract, SourceRunContract,
} from "../src/metrics/audit-contracts";

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
  expect(topSourceShare([1], 2)).toEqual({ numerator: 1, denominator: 1, value: 1 });
  expect(topSourceShare([8, 1], 3)).toEqual({ numerator: 9, denominator: 9, value: 1 });
});

test("real harvest through partition seals representable raw source completion only after all five verified ledgers", async () => {
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
        schema, schemaVersion: key === "assessments"
          ? ArticleAssessmentContract.schemaVersion : DiversityMetricContract.schemaVersion,
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
    expect((await auditFiles(recorded.inputs.outputRoot)).some(path => path.toString().startsWith("source-runs"))).toBe(true);
    expect(audit.planning_completion).toMatchObject({
      status: "complete", run_id: result.context.run_id, attempt: result.context.writer.attempt, source_count: 4,
    });
    expect(audit.planning_completion.completion_evidence).toHaveLength(5);
    expect(audit.receipts.rejections.row_count).toBe(result.evidence.harvest.rejections.length
      + result.evidence.screening.rejections.length + result.evidence.curation.rejections.length);
    expect(audit.receipts.rejections.files).toEqual([
      ...result.files.harvest_rejections.files, ...result.files.screening_rejections.files, ...result.files.curation_rejections.files,
    ].map(({ file_id, content_sha256, row_count }) => ({ file_id, content_sha256, row_count })));
    const sources = await readLedgerParquet(join(recorded.inputs.outputRoot, audit.files.source_runs.files[0]!.path),
      "source-runs", SourceRunContract);
    expect(sources.rows.map(row => row.row)).toEqual(audit.source_records);
    expect(audit.source_records.every(row => row.observation_phase === "plan_complete" && row.published_count === null && row.lead_count === null)).toBe(true);
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
    expect(audit.receipts.assessments).toMatchObject({ ledger: "article-assessments", row_count: 0, files: [], logical: { row_count: 0 } });
    expect(batch.diversity.find(row => row.metric === "effective_number_of_sources" && row.basis === "selected")).toMatchObject({
      value: 0, availability: "available",
    });
    expect(batch.diversity.find(row => row.metric === "selection_coverage")).toMatchObject({
      value: null, numerator: 0, denominator: 0, unavailable_reason: "empty_denominator",
    });
    expect(audit.audited_complete).toBe(false);
  } finally { await recorded.close(); }
}, 30000);

test("configured concentration counts and signed future ages survive native audit writes", async () => {
  for (const mode of ["top_k", "negative"] as const) {
    const recorded = await recordedPlan();
    if (mode === "top_k") recorded.inputs.harvest.config.metrics.top_source_counts = [1, 3, 5];
    else recorded.runtime.clock = () => new Date("2026-10-21T09:00:00Z");
    try {
      const result = await runFeedPlan({ partition_strategy: "none" }, recorded.inputs, recorded.runtime);
      const audit = await recordPlanningMetrics(result, recorded.inputs);
      const file = audit.files.assessments.files[0]!;
      const assessments = await readLedgerParquet(
        join(recorded.inputs.outputRoot, file.path), "article-assessments", ArticleAssessmentContract,
      );
      if (mode === "top_k") {
        const diversityFile = audit.files.diversity.files[0]!;
        const diversity = await readLedgerParquet(join(recorded.inputs.outputRoot, diversityFile.path),
          "diversity", DiversityMetricContract);
        expect(diversity.rows.some(held => held.row.metric === "top_source_concentration" && held.row.top_k === 3)).toBe(true);
      } else {
        expect(assessments.rows.some(held => held.row.age_hours !== null && held.row.age_hours < 0)).toBe(true);
      }
    } finally { await recorded.close(); }
  }
}, 30000);

test("actual settled first sight for an undated rejected candidate is saved without changing its basis", async () => {
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
    const audit = await recordPlanningMetrics(result, recorded.inputs, entries);
    const file = audit.files.assessments.files[0]!;
    const saved = await readLedgerParquet(join(recorded.inputs.outputRoot, file.path),
      "article-assessments", ArticleAssessmentContract);
    expect(saved.rows.some(held => held.row.timing_basis === "first_seen"
      && held.row.timing_at === "2026-10-20T10:00:00Z")).toBe(true);
    expect(result).toEqual(before);
    expect(recorded.inputs).toEqual(beforeInputs);
    expect(audit.audited_complete).toBe(false);
  } finally { await recorded.close(); }
}, 30000);

test("new first sight from the runner's complete bounded window is saved and read back natively", async () => {
  const recorded = await recordedPlan([source({ url: "https://news.example/article-failures.xml" })]);
  try {
    recorded.inputs.clock_config.collect.seen_window_days = 0;
    recorded.inputs.settings.inputs.seen_days = [{ day: "2026-10-21", raw_files: [] }];
    const result = await runFeedPlan({ partition_strategy: "none" }, recorded.inputs, recorded.runtime);
    expect(result.evidence.seen.absence_proof).toBe("within_configured_window");
    expect(result.evidence.seen.new_rows.length).toBeGreaterThan(0);
    expect(result.files.seen.status).toBe("written");
    expect(result.evidence.screening.admitted.some(article => article.freshness.timing_source === "first_seen")).toBe(true);
    const audit = await recordPlanningMetrics(result, recorded.inputs);
    const file = audit.files.assessments.files[0]!;
    const saved = await readLedgerParquet(join(recorded.inputs.outputRoot, file.path),
      "article-assessments", ArticleAssessmentContract);
    expect(saved.rows.some(held => held.row.timing_basis === "first_seen"
      && held.row.timing_at === result.evidence.seen.new_rows[0]!.first_seen_at)).toBe(true);
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

async function observedPublication(hasPublication = true) {
  const recorded = await recordedPlan([
    source(), source({ id: "carrier", kind: "research" }),
    source({ id: "inactive", status: "draft" }), source({ id: "empty", url: "https://news.example/empty.xml" }),
  ]);
  try {
    const result = await runFeedPlan({ partition_strategy: "none" }, recorded.inputs, recorded.runtime);
    const audit = await recordPlanningMetrics(result, recorded.inputs);
    const date = result.context.date;
    const sources = audit.files.source_runs;
    const selections = result.evidence.curation.rows;
    const digest: DigestPublication = {
      date, generated_at: result.context.now, runs: [{ n: 1, run_id: result.context.run_id, items_added: hasPublication ? selections.length : 0 }],
      items: (hasPublication ? selections : []).map((selection, index) => ({
        item_id: `ai-0${index + 1}`, source_id: selection.source_id, source_kind: "vendor",
        source_url: selection.canonical_url, introduced_by_run: 1,
        title: result.evidence.harvest.candidates.find(item => item.candidate_id === selection.candidate_id)!.title,
        source_name: selection.source.title,
      })), leads: hasPublication ? [{ item_id: "ai-01" }] : [],
    };
    const digestPath = join(recorded.directory, "digest.json");
    await writeFile(digestPath, JSON.stringify(digest));
    const publishedRows = digest.items.map(item => PublishedRowSchema.parse({
      version: CONTRACT_VERSION, item_id: item.item_id, published_on: date, url_key: deriveUrlKey(item.source_url),
    }));
    const published = await persistLedger({
      ledger: "published", outputRoot: recorded.inputs.outputRoot,
      registryEntry: { name: "published", family: "published", grain: "raw-and-compact", lifecycle_status: "active", prefix: ["published"] },
      writerContext: result.context.writer, ledgerSettings: recorded.inputs.ledgerSettings,
      period: { tier: "raw", covers: date }, rowContract: { schema: PublishedRowSchema, schemaVersion: CONTRACT_VERSION }, rows: publishedRows,
    });
    const health: ItemHealthPublication[] = digest.items.map(item => ({
      date, run_id: result.context.run_id, item_id: item.item_id, url_key: deriveUrlKey(item.source_url),
      source_id: item.source_id, stage: "publish", outcome: "ok",
    }));
    const paths = (files: readonly PersistLedgerResult[], day = date) => ({
      day, rawFiles: files.flatMap(result => result.files.map(file => join(recorded.inputs.outputRoot, file.path))),
    });
    const planning = {
      sources: paths([sources]), ledgers: {
        "article-assessments": paths([audit.files.assessments]), diversity: paths([audit.files.diversity]),
        "editorial-selections": paths([result.files.selections]), dispatches: paths([result.files.dispatches]),
        rejections: paths([result.files.harvest_rejections, result.files.screening_rejections, result.files.curation_rejections]),
      },
    };
    const prior = "2026-10-20";
    const emptyPaths = paths([], prior);
    const input: PublicationRecorderInput = {
      run_id: result.context.run_id, correlation_id: result.context.correlation_id,
      as_of: result.context.now, config_sha256: result.evidence.harvest.inputs.config_sha256,
      config: { ...result.evidence.harvest.config.metrics, rolling_window_days: 1, overlap_windows_days: [1] },
      writer: { ...result.context.writer, producer: "tests.publication-observer" },
      outputRoot: join(recorded.directory, "observer"), ledgerSettings: recorded.inputs.ledgerSettings,
      registrations: { diversity: recorded.inputs.registrations.diversity, sources: registration("source-runs") },
      publication_days: [
        { published: { ...paths([], prior), schema_version: CONTRACT_VERSION }, health: { day: prior, status: "empty", rows: [] }, digest_path: null },
        { published: { ...paths([published]), schema_version: CONTRACT_VERSION }, health: { day: date, status: health.length === 0 ? "empty" : "rows", rows: health }, digest_path: digestPath },
      ],
      planning_days: [
        { sources: emptyPaths, ledgers: { "article-assessments": emptyPaths, diversity: emptyPaths,
          "editorial-selections": emptyPaths, dispatches: emptyPaths, rejections: emptyPaths } }, planning,
      ], event_pairs: [],
    };
    return { recorded, result, audit, digest, digestPath, input, planning };
  } catch (error) { await recorded.close(); throw error; }
}

test("actual native publication completes the audit with a closed complete evidence window", async () => {
  const fixture = await observedPublication();
  try {
    const written = await recordPublicationMetrics({
      ...fixture.input, as_of: "2026-10-22T00:00:00Z", through: fixture.result.context.date,
      config: { ...fixture.input.config, top_source_counts: [3] },
    });
    expect(written.status).toBe("audit_complete");
    expect(written.audited_complete).toBe(true);
    expect(written.receipts.diversity.row_count).toBe(written.rows.length);
    expect(written.receipts.diversity.files).toEqual(written.files.diversity.files.map(
      ({ file_id, content_sha256, row_count }) => ({ file_id, content_sha256, row_count })));
    const rows = written.rows.filter(row => row.window_start === null);
    const metric = (name: string, basis: string, unit?: string) => rows.find(row =>
      row.metric === name && row.basis === basis && (unit === undefined || row.unit === unit))!;
    expect(metric("active_source_coverage", "eligible")).toMatchObject({ value: 2 / 3, numerator: 2, denominator: 3 });
    expect(metric("selection_coverage", "selected")).toMatchObject({ value: 1 / 2, numerator: 1, denominator: 2 });
    expect(metric("effective_number_of_sources", "eligible").value).toBeCloseTo(2, 12);
    expect(metric("effective_number_of_sources", "published")).toMatchObject({ value: 1, item_count: 2 });
    expect(metric("source_gini", "published").value).toBeCloseTo(2 / 3, 12);
    expect(metric("top_source_concentration", "published")).toMatchObject({ top_k: 3, value: 1, numerator: 2, denominator: 2 });
    expect(rows.find(row => row.metric === "source_kind_distribution" && row.basis === "published" && row.dimension_value === "vendor" && row.unit === "count")!.value).toBe(2);
    expect(rows.find(row => row.metric === "lost_diversity_by_stage" && row.stage === "deduplication")!.value).toBeCloseTo(1, 12);
    expect(rows.find(row => row.metric === "lost_diversity_by_stage" && row.stage === "lead_selection")!.value).toBe(0);
    expect(written.source_observations).toHaveLength(4);
    expect(written.source_observations.reduce((sum, source) => sum + source.published_count!, 0)).toBe(2);
    expect(written.source_observations.reduce((sum, source) => sum + source.lead_count!, 0)).toBe(1);
    expect(written.source_observations.find(row => row.source_id === fixture.result.evidence.harvest.inputs.sources[0]!.id)!.source.kind).toBe("reporting");
    const [nativeMetrics, nativeSources] = await Promise.all([
      readLedgerParquet(join(fixture.input.outputRoot, written.files.diversity.files[0]!.path), "diversity",
        DiversityMetricContract),
      readLedgerParquet(join(fixture.input.outputRoot, written.files.sources!.files[0]!.path), "source-runs",
        SourceRunContract),
    ]);
    expect(nativeMetrics.rows.map(held => held.row)).toEqual(written.rows);
    expect(nativeSources.rows.map(held => held.row)).toEqual(written.source_observations);
    expect(nativeSources.rows.every(held => held.identity.covers === "2026-10-22")).toBe(true);
    const observerDay = await readLedgerDay({
      ledger: "source-runs", day: "2026-10-22", contract: SourceRunContract,
      rawFiles: written.files.sources!.files.map(file => join(fixture.input.outputRoot, file.path)),
    });
    expect(observerDay.rows.map(held => held.row)).toEqual(written.source_observations);
    expect(observerDay.rows.every(held => held.row.date === fixture.result.context.date
      && held.row.observed_at === "2026-10-22T00:00:00Z"
      && held.identity.covers === "2026-10-22")).toBe(true);
    const backdated = await persistLedger({
      ledger: "source-runs", outputRoot: fixture.input.outputRoot,
      registryEntry: registration("source-runs"),
      writerContext: { ...fixture.input.writer, producer: "tests.wrong-source-day" },
      ledgerSettings: fixture.input.ledgerSettings,
      period: { tier: "raw", covers: "2026-10-21" }, partition_date: "2026-10-21",
      rowContract: SourceRunContract, rows: written.source_observations,
    });
    if (backdated.status !== "written") throw new Error("Expected the malformed partition fixture to be written");
    await expect(readLedgerDay({
      ledger: "source-runs", day: "2026-10-21", contract: SourceRunContract,
      rawFiles: backdated.files.map(file => join(fixture.input.outputRoot, file.path)),
    })).rejects.toThrow("Source-run partition differs from its observation phase");
    expect(settlePlanningDay(await readPlanningHistory(fixture.planning)).runs).toHaveLength(1);
    const rollingPublishedRows = written.rows.filter(row => row.window_start !== null && row.basis === "published");
    expect(rollingPublishedRows.length).toBeGreaterThan(0);
    expect(rollingPublishedRows.every(row => row.availability === "available")).toBe(true);
  } finally { await fixture.recorded.close(); }
}, 30000);

test("an actual recorded zero-publication run completes zero source observations without substituting its selections", async () => {
  const fixture = await observedPublication(false);
  try {
    const written = await recordPublicationMetrics(fixture.input);
    expect(fixture.audit.planning_completion.status).toBe("complete");
    expect(fixture.audit.source_records.reduce((sum, row) => sum + row.selected_count!, 0)).toBe(2);
    expect(written.source_observations.every(row => row.published_count === 0 && row.lead_count === 0)).toBe(true);
    expect(written.rows.find(row => row.window_start === null && row.basis === "published" && row.metric === "effective_number_of_sources")).toMatchObject({
      availability: "available", value: 0, item_count: 0,
    });
    expect(written.rows.find(row => row.window_start === null && row.stage === "publication" && row.metric === "lost_diversity_by_stage")).toMatchObject({
      value: 1, before_value: 1, after_value: 0,
    });
    expect(written.files.sources).not.toBeNull();
  } finally { await fixture.recorded.close(); }
}, 30000);

test("two actual runs retain changed source snapshots while rolling instances and unique articles use different populations", async () => {
  const fixture = await observedPublication();
  try {
    const inputs = fixture.recorded.inputs;
    inputs.harvest = loadHarvestInputs({
      config: inputs.harvest.config, taxonomy: { ...inputs.harvest.taxonomy, ...inputs.harvest.registry },
      sources: { feeds: inputs.harvest.sources.map(source =>
        source.id === "carrier" ? { ...source, status: "draft" } : source.id === "recorded-news" ? { ...source, kind: "research" } : source) },
      extraction: { extract: inputs.harvest.extraction },
    });
    fixture.recorded.runtime.run_number = "701";
    const second = await runFeedPlan({ partition_strategy: "none" }, inputs, fixture.recorded.runtime);
    const audit = await recordPlanningMetrics(second, inputs);
    await writeFile(fixture.digestPath, JSON.stringify({
      ...fixture.digest, runs: [...fixture.digest.runs, { n: 2, run_id: second.context.run_id, items_added: 0 }],
    }));
    const append = (left: { day: string; rawFiles: string[] }, files: readonly PersistLedgerResult[]) => ({
      ...left, rawFiles: [...left.rawFiles, ...files.flatMap(result => result.files.map(file => join(inputs.outputRoot, file.path)))],
    });
    const first = fixture.planning;
    const history = {
      sources: append(first.sources, [audit.files.source_runs]), ledgers: {
        "article-assessments": append(first.ledgers["article-assessments"], [audit.files.assessments]),
        diversity: append(first.ledgers.diversity, [audit.files.diversity]),
        "editorial-selections": append(first.ledgers["editorial-selections"], [second.files.selections]),
        dispatches: append(first.ledgers.dispatches, [second.files.dispatches]),
        rejections: append(first.ledgers.rejections, [second.files.harvest_rejections, second.files.screening_rejections, second.files.curation_rejections]),
      },
    };
    const observed = await recordPublicationMetrics({
      ...fixture.input, run_id: second.context.run_id, correlation_id: second.context.correlation_id,
      writer: second.context.writer, config_sha256: second.evidence.harvest.inputs.config_sha256,
      as_of: "2026-10-22T00:00:00Z", through: "2026-10-21",
      planning_days: [fixture.input.planning_days[0]!, history],
    });
    const rows = observed.rows.filter(row => row.window_start !== null);
    expect(rows.find(row => row.metric === "active_source_coverage")).toMatchObject({ numerator: 2, denominator: 3, item_count: 6 });
    expect(rows.find(row => row.metric === "effective_number_of_sources" && row.basis === "eligible")!.value).toBeCloseTo(effectiveSources([4, 2, 0]), 12);
    expect(rows.find(row => row.metric === "effective_number_of_sources" && row.basis === "selected")!.item_count).toBe(2);
    expect(rows.find(row => row.metric === "source_kind_distribution" && row.basis === "eligible" && row.dimension_value === "research" && row.unit === "count")!.value).toBe(4);
    expect(rows.find(row => row.metric === "source_kind_distribution" && row.basis === "selected" && row.dimension_value === "reporting" && row.unit === "count")!.value).toBe(2);
    expect(rows.find(row => row.metric === "source_kind_distribution" && row.basis === "published" && row.dimension_value === "vendor" && row.unit === "count")!.value).toBe(2);
    expect(observed.rows.find(row => row.window_start === null && row.metric === "effective_number_of_sources" && row.basis === "published")!.value).toBe(0);
  } finally { await fixture.recorded.close(); }
}, 30000);

test("a real obstructed source write cannot return the completed five-ledger attempt", async () => {
  const recorded = await recordedPlan();
  try {
    const result = await runFeedPlan({ partition_strategy: "none" }, recorded.inputs, recorded.runtime);
    await writeFile(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan", "source-runs"), "obstruction");
    await expect(recordPlanningMetrics(result, recorded.inputs)).rejects.toThrow();
    const files = await auditFiles(recorded.inputs.outputRoot);
    expect(files.some(path => path.toString().startsWith("article-assessments"))).toBe(true);
    expect(files.some(path => path.toString().startsWith("diversity"))).toBe(true);
    expect(files.some(path => /^source-runs[/\\]/.test(path.toString()))).toBe(false);
  } finally { await recorded.close(); }
}, 30000);

test("a completed bounded window writes later source observations without changing the original run day", async () => {
  const fixture = await observedPublication();
  try {
    const written = await recordPublicationMetrics({ ...fixture.input, as_of: "2026-10-22T00:00:00Z", through: "2026-10-21" });
    const rolling = written.rows.filter(row => row.window_start !== null);
    expect(written.history).toEqual({ start: "2026-10-21", end: "2026-10-21", coverage_days: 2, required_days: 2 });
    expect(rolling.filter(row => row.basis === "published").every(row => row.availability === "available")).toBe(true);
    expect(rolling.find(row => row.metric === "event_repetition_rate")!.value).toBe(0);
    expect(rolling.find(row => row.metric === "novel_source_contribution" && row.unit === "count")!.value).toBe(2);
    expect(rolling.find(row => row.metric === "novel_source_contribution" && row.unit === "ratio")!.value).toBe(1);
    expect(rolling.find(row => row.metric === "source_event_overlap" && row.dimension === "source" && row.unit === "ratio")!.value).toBe(0);
    expect(written.source_observations).toHaveLength(4);
    expect(written.source_observations.every(row => row.date === fixture.result.context.date
      && row.run_id === fixture.result.context.run_id && row.observed_at === "2026-10-22T00:00:00Z")).toBe(true);
    expect(written.files.sources).not.toBeNull();
    expect(written.unavailable.source_observations).toBeNull();
  } finally { await fixture.recorded.close(); }
}, 30000);

test("native public boundary refuses foreign source attribution and does not measure an omitted member as a complete day", async () => {
  const fixture = await observedPublication();
  try {
    const configured = await recordPublicationMetrics({ ...fixture.input,
      outputRoot: join(fixture.recorded.directory, "configured-top-k"),
      config: { ...fixture.result.evidence.harvest.config.metrics, top_source_counts: [2] },
    });
    expect(configured.rows.some(row => row.metric === "top_source_concentration" && row.top_k === 2)).toBe(true);
    await expect(recordPublicationMetrics({ ...fixture.input,
      writer: { ...fixture.input.writer, attempt: fixture.input.writer.attempt + 1 },
    })).rejects.toThrow("writer attempt");
    await expect(stat(fixture.input.outputRoot)).rejects.toThrow();
    const changed = structuredClone(fixture.digest);
    changed.items[0]!.source_id = "foreign-source";
    await writeFile(fixture.digestPath, JSON.stringify(changed));
    await expect(recordPublicationMetrics(fixture.input)).rejects.toThrow("source identities disagree");
    await expect(stat(fixture.input.outputRoot)).rejects.toThrow();
    const knownSource = structuredClone(fixture.digest);
    knownSource.items[0]!.source_id = "carrier";
    await writeFile(fixture.digestPath, JSON.stringify(knownSource));
    const current = fixture.input.publication_days[1]!;
    const switched = {
      ...current, health: { ...current.health, rows: current.health.rows.map((row, n) =>
        n === 0 ? { ...row, source_id: "carrier" } : row) },
    };
    await expect(recordPublicationMetrics({ ...fixture.input,
      publication_days: [fixture.input.publication_days[0]!, switched],
    })).rejects.toThrow("proven selected run");
    await expect(stat(fixture.input.outputRoot)).rejects.toThrow();
    const foreign = structuredClone(fixture.digest);
    foreign.items[0]!.source_url = "https://news.example/foreign";
    await writeFile(fixture.digestPath, JSON.stringify(foreign));
    const foreignPublished = await persistLedger({
      ledger: "published", outputRoot: fixture.recorded.inputs.outputRoot,
      registryEntry: { name: "published", family: "published", grain: "raw-and-compact", lifecycle_status: "active", prefix: ["published"] },
      writerContext: fixture.input.writer, ledgerSettings: fixture.input.ledgerSettings,
      period: { tier: "raw", covers: foreign.date }, rowContract: { schema: PublishedRowSchema, schemaVersion: CONTRACT_VERSION },
      rows: foreign.items.map(item => PublishedRowSchema.parse({
        version: CONTRACT_VERSION, published_on: foreign.date, item_id: item.item_id, url_key: deriveUrlKey(item.source_url),
      })),
    });
    await expect(recordPublicationMetrics({ ...fixture.input, publication_days: [fixture.input.publication_days[0]!, {
      ...current, published: { ...current.published, rawFiles: foreignPublished.files.map(file => join(fixture.recorded.inputs.outputRoot, file.path)) },
      health: { ...current.health, rows: current.health.rows.map((row, n) =>
        n === 0 ? { ...row, url_key: deriveUrlKey(foreign.items[0]!.source_url) } : row) },
    }] })).rejects.toThrow("proven selected run");
    await expect(stat(fixture.input.outputRoot)).rejects.toThrow();
    const omitted = { ...fixture.digest, items: fixture.digest.items.slice(1), leads: [],
      runs: fixture.digest.runs.map(run => ({ ...run, items_added: 1 })) };
    await writeFile(fixture.digestPath, JSON.stringify(omitted));
    const observed = await recordPublicationMetrics(fixture.input);
    expect(observed.rows.filter(row => row.basis === "published").every(row => row.availability === "unavailable")).toBe(true);
    expect(observed.source_observations).toEqual([]);
    expect(observed.files.sources).toBeNull();
  } finally { await fixture.recorded.close(); }
}, 30000);

test("caller event titles, outlet names and current lists cannot replace the native digest evidence", async () => {
  const fixture = await observedPublication();
  try {
    const date = "2026-10-20";
    const prior = {
      date, generated_at: `${date}T23:00:00Z`, runs: [{ n: 1, run_id: `${date}-1`, items_added: 1 }],
      items: [{ ...fixture.digest.items[0]!, item_id: "ai-03", source_url: "https://news.example/prior", introduced_by_run: 1 }],
      leads: [],
    };
    const path = join(fixture.recorded.directory, "prior-digest.json");
    await writeFile(path, JSON.stringify(prior));
    const written = await persistLedger({
      ledger: "published", outputRoot: fixture.recorded.inputs.outputRoot,
      registryEntry: { name: "published", family: "published", grain: "raw-and-compact", lifecycle_status: "active", prefix: ["published"] },
      writerContext: { ...fixture.input.writer, run_id: `${date}-1` }, ledgerSettings: fixture.input.ledgerSettings,
      period: { tier: "raw", covers: date }, rowContract: { schema: PublishedRowSchema, schemaVersion: CONTRACT_VERSION },
      rows: [PublishedRowSchema.parse({ version: CONTRACT_VERSION, published_on: date, item_id: "ai-03", url_key: deriveUrlKey(prior.items[0]!.source_url) })],
    });
    const items = [...prior.items, ...fixture.digest.items];
    const stamp = (await Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/publication-evidence.json", import.meta.url)).json()).event_stamp;
    const pairs = items.flatMap((left, n) => items.slice(n + 1).map(right => {
      const [a, b] = [deriveUrlKey(left.source_url), deriveUrlKey(right.source_url)].sort();
      return RecordedEventPairSchema.parse({ ...stamp, left_url_key: a, right_url_key: b,
        pair_key: recordedPairKey(a!, b!), verdict: "YES", verdict_swapped: "YES", usable: true });
    }));
    const input = {
      ...fixture.input, as_of: "2026-10-22T00:00:00Z", through: "2026-10-21", event_pairs: pairs,
      publication_days: [{
        published: { day: date, rawFiles: written.files.map(file => join(fixture.recorded.inputs.outputRoot, file.path)), schema_version: CONTRACT_VERSION },
        health: { day: date, status: "empty" as const, rows: [] }, digest_path: path,
      }, fixture.input.publication_days[1]!],
      // These unrecognised caller fields cannot enter the public recorder's derived populations.
      current: [], event_evidence: { pairs, items: items.map((item, n) =>
        ({ ...item, title: "Recorded event fire", source_name: `foreign-${n}` })) },
    };
    const observed = await recordPublicationMetrics(input);
    expect(observed.rows.find(row => row.window_start !== null && row.metric === "event_repetition_rate")).toMatchObject({
      availability: "available", value: 0, numerator: 0, denominator: 2,
    });
    expect(observed.rows.find(row => row.window_start !== null && row.metric === "effective_number_of_sources" && row.basis === "published")!.item_count).toBe(2);
    expect(observed.rows.find(row => row.window_start !== null && row.metric === "novel_source_contribution" && row.unit === "count")!.value).toBe(0);
  } finally { await fixture.recorded.close(); }
}, 30000);

test("missing native planning proof stays unavailable while independently recorded publication counts survive", async () => {
  const fixture = await observedPublication();
  try {
    const incomplete = {
      ...fixture.planning,
      sources: { ...fixture.planning.sources, rawFiles: [join(fixture.recorded.directory, "absent.parquet")] },
    };
    const written = await recordPublicationMetrics({ ...fixture.input, as_of: "2026-10-22T00:00:00Z", through: "2026-10-21",
      planning_days: [incomplete] });
    const rolling = written.rows.filter(row => row.window_start !== null);
    expect(rolling.find(row => row.metric === "effective_number_of_sources" && row.basis === "published")!.value).toBe(1);
    expect(rolling.find(row => row.metric === "source_gini" && row.basis === "published")).toMatchObject({
      value: null, unavailable_reason: "incomplete_history", history_coverage_days: 0,
    });
    expect(rolling.find(row => row.metric === "active_source_coverage")).toMatchObject({
      value: null, unavailable_reason: "incomplete_history", history_coverage_days: 0,
    });
    const native = await readPlanningHistory(fixture.planning);
    const settled = settlePlanningDay(native);
    expect(settled.status).toBe("rows");
    expect(settled.runs[0]!.eligible).toHaveLength(4);
  } finally { await fixture.recorded.close(); }
}, 30000);
