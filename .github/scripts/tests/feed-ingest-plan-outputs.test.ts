/** Do real planner results retain native file evidence independently of optional reporting? */
import { expect, test } from "bun:test";
import { mkdir, mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";
import { createHash } from "node:crypto";
import { CONTRACT_VERSION, FeedIngestDispatchSchema, RawDayIndexSchema } from "../../../packages/common-contracts/src/index";
import { persistLedger } from "../../../packages/ledger-file-writer/src/index";
import { runFeedPlan, summarizePlan } from "../../../services/feed-ingest-plan/src/run-feed-plan";
import { recordedPlan } from "../../../services/feed-ingest-plan/test/plan-recordings";
import { source } from "../../../services/feed-ingest-plan/test/harvest-recordings";
import { verifyLedgerReceipt, verifyParquetFiles, verifyRecordedCompatibility } from "../feed-ingest-plan-verification";
import { createExecutionOutputs, createSeenDayInputs, writeGitHubOutputs } from "../feed-ingest-plan-outputs";
import { writePlannerReport } from "../feed-ingest-plan-report";
import { readSeenEvidence, requiredSeenDays } from "../../../services/feed-ingest-plan/src/read-ledger-history/read-seen-evidence";
import { utcTimestamp } from "../../../services/feed-ingest-plan/src/harvest-feeds/harvest-types";
import { main } from "../../../services/feed-ingest-plan/src/index";

test("the actual CLI returns native assessment/diversity files and matching receipts, never complete audit", async () => {
  const fixture = await recordedPlan();
  try {
    const summary = await main(["--cli", "--partition-strategy=none"], {
      inputs: fixture.inputs, runtime: fixture.runtime, output: () => {},
    });
    if (!("files" in summary) || summary.metrics === undefined) throw new Error("Actual CLI omitted metric evidence");
    const metrics = summary.metrics;
    const outputs = createExecutionOutputs(summary, fixture.inputs.registrations);
    expect(outputs.metrics_status).toBe("assessment_diversity_recorded_audit_pending");
    expect(outputs.audited_complete).toBe("false");
    for (const [key, ledger] of [["assessments", "article-assessments"], ["diversity", "diversity"]] as const) {
      const files = summary.metrics.files[key];
      const checked = await verifyParquetFiles(fixture.inputs.outputRoot, ledger, files, fixture.inputs.registrations[key]);
      expect(checked.row_count).toBe(summary.metrics.receipts[key].row_count);
      expect(checked.row_count).toBeGreaterThan(0);
      verifyLedgerReceipt(ledger, files, summary.metrics.receipts[key]);
      expect(JSON.parse(outputs[`${key}_files`]!)).toEqual(files.files.map(file => file.path));
    }
    expect(() => createExecutionOutputs({ ...summary, metrics: {
      ...metrics, receipts: { ...metrics.receipts, assessments: {
        ...metrics.receipts.assessments, files: [], row_count: 0,
      } },
    } }, fixture.inputs.registrations)).toThrow("receipt");
    const file = summary.metrics.files.diversity.files[0]!;
    await rm(join(fixture.inputs.outputRoot, ...file.path.split("/")));
    await expect(verifyParquetFiles(fixture.inputs.outputRoot, "diversity",
      summary.metrics.files.diversity, fixture.inputs.registrations.diversity)).rejects.toMatchObject({ code: "ENOENT" });
  } finally {
    await fixture.close();
  }
});

test("unsupported actual CLI audit measurements produce no summary or assessment/diversity files", async () => {
  const fixture = await recordedPlan();
  try {
    fixture.inputs.harvest.config.metrics.top_source_counts = [1, 2, 5];
    let outputs = 0;
    await expect(main(["--cli"], { inputs: fixture.inputs, runtime: fixture.runtime,
      output: () => { outputs += 1; } })).rejects.toThrow("top_source_counts");
    expect(outputs).toBe(0);
    for (const key of ["assessments", "diversity"] as const) {
      await expect(stat(join(fixture.inputs.outputRoot, "raw", ...fixture.inputs.registrations[key].prefix)))
        .rejects.toMatchObject({ code: "ENOENT" });
    }
  } finally {
    await fixture.close();
  }
});

test("uses actual selected identities, worker count and real files without a reporting dependency", async () => {
  const fixture = await recordedPlan();
  try {
    const result = await runFeedPlan({ article_limit: 1, shards: 2 }, fixture.inputs, fixture.runtime);
    const summary = summarizePlan(result);
    const outputs = createExecutionOutputs(summary, fixture.inputs.registrations);
    expect(outputs.audited_complete).toBe("false");
    expect(outputs.status).toBe("dispatches_persisted_audit_pending");
    expect(outputs.dispatch_count).toBe("2");
    expect(JSON.parse(outputs.matrix!)).toEqual({ include: [{ worker_assignment: 0 }, { worker_assignment: 1 }] });
    expect(JSON.parse(outputs.dispatch_files!)).toEqual(result.files.dispatches.files.map(file => file.path));
    expect((await verifyParquetFiles(fixture.inputs.outputRoot, "dispatches",
      result.files.dispatches, fixture.inputs.registrations.dispatches)).row_count).toBe(summary.assignments.length);
    const before = JSON.stringify(result.files);
    const summaryPath = join(fixture.directory, "summary.md");
    const annotations: string[] = [];
    await writePlannerReport({ enabled: false, events: result.events, summaryPath, annotate: line => annotations.push(line) });
    expect(annotations).toEqual([]);
    await writePlannerReport({ enabled: true, events: result.events, summaryPath, annotate: line => annotations.push(line) });
    expect(annotations.length).toBeGreaterThan(0);
    expect(JSON.stringify(result.files)).toBe(before);
    expect(createExecutionOutputs(summary, fixture.inputs.registrations)).toEqual(outputs);
    expect(() => createExecutionOutputs({ ...summary, audited_complete: true }, fixture.inputs.registrations)).toThrow("audited_complete");
    expect(() => createExecutionOutputs({ ...summary, dispatch_count: 3 }, fixture.inputs.registrations)).toThrow("worker count");
    const file = result.files.dispatches.files[0]!;
    expect(() => createExecutionOutputs({
      ...summary, files: { ...summary.files, dispatches: {
        status: "written", files: [{ ...file, path: "../secret\ninjected=true" }],
      } },
    }, fixture.inputs.registrations)).toThrow("path");
  } finally {
    await fixture.close();
  }
});

test("refuses mismatched counts, damaged bytes and missing actual files", async () => {
  const root = await mkdtemp(join(tmpdir(), "feed-native-files-"));
  try {
    const row = FeedIngestDispatchSchema.parse(await Bun.file(
      new URL("../../../tests/fixtures/ledger-file-writer/feed-ingest-dispatch-row.json", import.meta.url),
    ).json());
    const registration = { name: "dispatches", family: "feed-ingest-plan", grain: "raw-and-compact" as const,
      lifecycle_status: "active" as const, prefix: ["feed-ingest-plan", "dispatches"] };
    const result = await persistLedger({
      ledger: "dispatches", outputRoot: root, rows: [row],
      rowContract: { schema: FeedIngestDispatchSchema, schemaVersion: CONTRACT_VERSION },
      period: { tier: "raw", covers: row.content.date }, registryEntry: registration,
      writerContext: { run_id: row.content.run_id, attempt: 1, job: null, pipeline_name: "plan",
        task_name: "seal-article-ledger", shard: 0, producer: "tests.outputs", git_sha: "a".repeat(40) },
      ledgerSettings: { format: "parquet", compression_raw: "snappy", compression_compact: "zstd" },
    });
    const receipt = { ledger: "dispatches", row_count: 1, files: result.files.map(file => ({
      file_id: file.file_id, content_sha256: file.content_sha256, row_count: file.row_count,
    })) };
    expect(() => verifyLedgerReceipt("dispatches", result, receipt)).not.toThrow();
    expect(() => verifyLedgerReceipt("diversity", result, receipt)).toThrow("ledger");
    expect(() => verifyLedgerReceipt("dispatches", result, {
      ...receipt, files: receipt.files.map(file => ({ ...file, content_sha256: "0".repeat(64) })),
    })).toThrow("content_sha256");
    expect(() => verifyLedgerReceipt("dispatches", result, { ...receipt, files: [], row_count: 0 })).toThrow("files");
    await expect(verifyParquetFiles(root, "dispatches", {
      status: "written", files: result.files.map(file => ({ ...file, row_count: file.row_count + 1 })),
    }, registration)).rejects.toThrow("row_count");
    const file = result.files[0]!;
    const path = join(root, ...file.path.split("/"));
    const bytes = await readFile(path);
    await writeFile(path, bytes.subarray(0, 12));
    await expect(verifyParquetFiles(root, "dispatches", result, registration)).rejects.toThrow();
    await rm(path);
    await expect(verifyParquetFiles(root, "dispatches", result, registration)).rejects.toMatchObject({ code: "ENOENT" });
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("zero dispatches and zero rejections are explicit valid evidence, not missing files", async () => {
  const fixture = await recordedPlan([source({ url: "https://news.example/empty.xml" })]);
  try {
    const result = await main(["--cli", "--partition-strategy=none"], {
      inputs: fixture.inputs, runtime: fixture.runtime, output: () => {},
    });
    if (!("files" in result) || result.metrics === undefined) throw new Error("Actual CLI omitted metric evidence");
    const outputs = createExecutionOutputs(result, fixture.inputs.registrations);
    expect(outputs.dispatch_files).toBe("[]");
    expect(outputs.dispatch_count).toBe("1");
    expect(result.files.dispatches.status).toBe("empty");
    expect((await verifyParquetFiles(fixture.inputs.outputRoot, "dispatches", result.files.dispatches,
      fixture.inputs.registrations.dispatches)).status).toBe("verified_empty");
    expect(result.files.screening_rejections.status).toBe("empty");
    expect((await verifyParquetFiles(fixture.inputs.outputRoot, "rejections", result.files.screening_rejections,
      fixture.inputs.registrations.rejections)).row_count).toBe(0);
    expect((await verifyParquetFiles(fixture.inputs.outputRoot, "article-assessments", result.metrics.files.assessments,
      fixture.inputs.registrations.assessments)).status).toBe("verified_empty");
    verifyLedgerReceipt("article-assessments", result.metrics.files.assessments, result.metrics.receipts.assessments);
    expect(outputs.assessments_files).toBe("[]");
    expect(() => verifyLedgerReceipt("article-assessments", { status: "empty", files: [] },
      { ledger: "article-assessments", row_count: 0, files: [] })).not.toThrow();
    await expect(verifyParquetFiles(fixture.inputs.outputRoot, "dispatches",
      JSON.parse("{}"), fixture.inputs.registrations.dispatches)).rejects.toThrow("absent");
    await expect(verifyParquetFiles(fixture.inputs.outputRoot, "dispatches",
      { status: "written", files: [] }, fixture.inputs.registrations.dispatches)).rejects.toThrow("status");
  } finally {
    await fixture.close();
  }
});

test("writes GitHub output records with noncolliding delimiters and refuses key injection", async () => {
  const root = await mkdtemp(join(tmpdir(), "feed-outputs-"));
  try {
    const path = join(root, "outputs");
    await writeGitHubOutputs(path, { status: "pending", matrix: "first\r\ninjected=true\nEOF" });
    const text = await readFile(path, "utf8");
    const lines = text.split("\n");
    const headers = lines.filter(line => /^[a-z_]+<<output_[a-f0-9]+$/.test(line));
    expect(headers).toHaveLength(2);
    for (const header of headers) {
      const delimiter = header.split("<<")[1]!;
      expect(lines.filter(line => line === delimiter)).toHaveLength(1);
    }
    expect(text).not.toContain("\r");
    const before = text;
    await expect(writeGitHubOutputs(path, { "bad\nkey": "value" })).rejects.toThrow("key");
    expect(await readFile(path, "utf8")).toBe(before);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("checks recorded canonical bytes, identity values and real native dispatch compatibility", async () => {
  expect(await verifyRecordedCompatibility()).toMatchObject({ status: "verified", row_count: 1 });
});

test("report configuration cannot change real-run ledger commitments", async () => {
  const disabled = await recordedPlan();
  const enabled = await recordedPlan();
  try {
    disabled.inputs.harvest.config.workflow_reporting.enabled = false;
    enabled.inputs.harvest.config.workflow_reporting.enabled = true;
    const first = await main(["--cli", "--article-limit=1"], {
      inputs: disabled.inputs, runtime: disabled.runtime, output: () => {},
    });
    const second = await main(["--cli", "--article-limit=1"], {
      inputs: enabled.inputs, runtime: enabled.runtime, output: () => {},
    });
    if (!("files" in first) || !("files" in second) || first.metrics === undefined || second.metrics === undefined) {
      throw new Error("Actual CLI omitted metric evidence");
    }
    for (const name of ["dispatches", "selections", "harvest_rejections", "screening_rejections", "curation_rejections", "seen"] as const) {
      expect(second.files[name].files.map(file => file.content_sha256)).toEqual(
        first.files[name].files.map(file => file.content_sha256),
      );
    }
    for (const key of ["assessments", "diversity"] as const) {
      expect(second.metrics.files[key].files.map(file => file.content_sha256)).toEqual(
        first.metrics.files[key].files.map(file => file.content_sha256),
      );
    }
  } finally {
    await Promise.all([disabled.close(), enabled.close()]);
  }
});

test("forwards named-day proof to the actual runner and returns its real first-sight files", async () => {
  const fixture = await recordedPlan();
  try {
    fixture.inputs.clock_config.collect.seen_window_days = 0;
    const now = utcTimestamp(fixture.runtime.clock);
    fixture.inputs.settings.inputs.seen_days = createSeenDayInputs(fixture.inputs.registrations.seen.prefix,
      requiredSeenDays(now, fixture.inputs.clock_config.collect.seen_window_days));
    const input = fixture.inputs.settings.inputs.seen_days[0]!;
    const path = join(fixture.directory, ...input.raw_index!.split("/"));
    await mkdir(dirname(path), { recursive: true });
    await writeFile(path, JSON.stringify(RawDayIndexSchema.parse({
      version: "2026-10-03", ledger: "seen", date: input.day, files: [], bytes: [],
      content_sha256: createHash("sha256").update("").digest("hex"), listed_at: now,
    })));
    const result = await runFeedPlan({ article_limit: 1 }, fixture.inputs, fixture.runtime);
    const outputs = createExecutionOutputs(summarizePlan(result), fixture.inputs.registrations);
    expect(result.evidence.seen.absence_proof).toBe("within_configured_window");
    expect(result.evidence.seen.global_absence).toBe("unavailable");
    expect(result.evidence.seen.new_rows.length).toBeGreaterThan(0);
    const files = result.files.seen.files.map(file => file.path);
    expect(JSON.parse(outputs.seen_files!)).toEqual(files);
    const actual = await readSeenEvidence(fixture.inputs.outputRoot, files);
    expect(actual.evidence.availability).toBe("available");
    if (actual.evidence.availability !== "available") throw new Error("Actual first-sight file was not readable");
    expect(actual.evidence.rows).toEqual([...result.evidence.seen.new_rows].sort((a, b) => a.url_key.localeCompare(b.url_key)));
  } finally {
    await fixture.close();
  }
});

test("a missing named raw index stays unavailable and cannot manufacture new first sight", async () => {
  const fixture = await recordedPlan();
  try {
    fixture.inputs.clock_config.collect.seen_window_days = 0;
    const now = utcTimestamp(fixture.runtime.clock);
    fixture.inputs.settings.inputs.seen_days = createSeenDayInputs(fixture.inputs.registrations.seen.prefix,
      requiredSeenDays(now, fixture.inputs.clock_config.collect.seen_window_days));
    const result = await runFeedPlan({ article_limit: 1 }, fixture.inputs, fixture.runtime);
    expect(result.evidence.seen.absence_proof).toBe("unavailable");
    expect(result.evidence.seen.window?.days[0]?.status).toBe("missing");
    expect(result.files.seen).toEqual({ status: "empty", files: [] });
    expect(createExecutionOutputs(summarizePlan(result), fixture.inputs.registrations).seen_files).toBe("[]");
  } finally {
    await fixture.close();
  }
});
