/** Do real planner results retain native file evidence independently of optional reporting? */
import { expect, test } from "bun:test";
import { mkdir, mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";
import { createHash } from "node:crypto";
import { FeedIngestDispatchSchema, RawDayIndexSchema } from "../../../packages/common-contracts/src/index";
import { persistLedger } from "../../../packages/ledger-file-writer/src/index";
import { runFeedPlan, summarizePlan } from "../../../services/feed-ingest-plan/src/run-feed-plan";
import { recordedPlan } from "../../../services/feed-ingest-plan/test/plan-recordings";
import { source } from "../../../services/feed-ingest-plan/test/harvest-recordings";
import { verifyLedgerReceipt, verifyParquetFiles, verifyPlanningCompletion, verifyRecordedCompatibility } from "../feed-ingest-plan-verification";
import { createExecutionOutputs, createSeenDayInputs, writeGitHubOutputs } from "../feed-ingest-plan-outputs";
import { formatExecutionReport, writePlannerReport } from "../feed-ingest-plan-report";
import type { ProgressRecord } from "../../../services/feed-ingest-plan/src/logging/progress-logger";
import { readSeenEvidence, requiredSeenDays } from "../../../services/feed-ingest-plan/src/read-ledger-history/read-seen-evidence";
import { utcTimestamp } from "../../../services/feed-ingest-plan/src/harvest-feeds/harvest-types";
import { main } from "../../../services/feed-ingest-plan/src/index";
import { recordPublicationMetrics } from "../../../services/feed-ingest-plan/src/metrics/metrics-recorder";
import {
  DigestPublicationSchema, PUBLISHED_ROW_SCHEMA_VERSION, PublishedRowSchema,
} from "../../../services/feed-ingest-plan/src/metrics/publication-evidence";
import { readLedgerParquet } from "../../../services/feed-ingest-plan/src/read-ledger-history/read-parquet";
import { DispatchContract } from "../../../services/feed-ingest-plan/src/metrics/audit-contracts";
import { generatePublicationInput } from "../../../services/feed-ingest-plan/test/full-audit-recording";
import { verifyFullAuditFixture } from "../feed-ingest-plan-audit-fixture";

test("full-audit outputs require actual completed observer evidence and remain explicitly generated fixtures", async () => {
  const fixture = await recordedPlan();
  try {
    const summary = await main(["--cli"], {
      inputs: fixture.inputs, output: () => {},
      runtime: { ...fixture.runtime, observe_publication: (plan, metrics) =>
        generatePublicationInput(plan, metrics, fixture.inputs, join(fixture.directory, "publication")) },
    });
    if (!("files" in summary)) throw new Error("Missing summary");
    expect(createExecutionOutputs(summary, fixture.inputs.registrations).audited_complete).toBe("true");
    expect(() => createExecutionOutputs({ ...summary, publication: null }, fixture.inputs.registrations)).toThrow("audited_complete");
    expect(await verifyFullAuditFixture(join(fixture.directory, "workflow-generated-audit"))).toMatchObject({
      scope: "generated_fixture", audited_complete: true, attempt: 1,
    });
  } finally { await fixture.close(); }
}, 30000);

test("generated publication evidence joins actual main output and writes native observer files, not production publication", async () => {
  const fixture = await recordedPlan();
  try {
    const summary = await main(["--cli", "--partition-strategy=none"], {
      inputs: fixture.inputs, runtime: fixture.runtime, output: () => {},
    });
    if (!("files" in summary) || summary.metrics === undefined) throw new Error("Actual CLI omitted planning evidence");
    const metrics = summary.metrics;
    const sources = metrics.files.source_runs;
    const first = summary.files.dispatches.files[0];
    if (first === undefined) throw new Error("Generated publication fixture requires a real selected dispatch");
    const dispatches = await readLedgerParquet(join(fixture.inputs.outputRoot, ...first.path.split("/")), "dispatches",
      DispatchContract);
    const writer = dispatches.envelope.identity;
    const digest = DigestPublicationSchema.parse({
      date: summary.date, generated_at: summary.observed_at,
      runs: [{ n: 1, run_id: summary.run_id, items_added: dispatches.rows.length }],
      items: dispatches.rows.map(({ row }, index) => ({
        item_id: `fixture-${String(index + 1).padStart(2, "0")}`,
        source_id: row.selection.source_id, source_kind: row.selection.source.kind,
        source_url: row.content.canonical_url, title: row.content.title,
        source_name: row.selection.source.title, introduced_by_run: 1,
      })),
      leads: [],
    });
    const digestPath = join(fixture.directory, "generated-publication-digest.json");
    await writeFile(digestPath, JSON.stringify(digest));
    const published = await persistLedger({
      ledger: "published", outputRoot: fixture.inputs.outputRoot,
      registryEntry: { name: "published", family: "published", grain: "raw-and-compact",
        lifecycle_status: "active", prefix: ["published"] },
      writerContext: writer, ledgerSettings: fixture.inputs.ledgerSettings,
      period: { tier: "raw", covers: summary.date },
      rowContract: { schema: PublishedRowSchema, schemaVersion: PUBLISHED_ROW_SCHEMA_VERSION },
      rows: dispatches.rows.map(({ row }, index) => PublishedRowSchema.parse({
        version: PUBLISHED_ROW_SCHEMA_VERSION, item_id: digest.items[index]!.item_id,
        published_on: summary.date, url_key: row.content.url_key,
      })),
    });
    const named = (files: readonly { files: readonly { path: string }[] }[], day = summary.date) => ({
      day, rawFiles: files.flatMap(held => held.files.map(file => join(fixture.inputs.outputRoot, ...file.path.split("/")))),
    });
    // One prior UTC day is a fixed test fixture, not an inferred historical observation.
    const prior = new Date(Date.parse(`${summary.date}T00:00:00Z`) - 86_400_000).toISOString().slice(0, 10);
    const empty = named([], prior);
    const outputRoot = join(fixture.directory, "generated-observer-output");
    const observed = await recordPublicationMetrics({
      run_id: summary.run_id, correlation_id: summary.correlation_id, as_of: summary.observed_at,
      config_sha256: dispatches.rows[0]!.row.content.policy.config_sha256,
      config: { ...fixture.inputs.harvest.config.metrics, rolling_window_days: 1, overlap_windows_days: [1] },
      writer: { ...writer, producer: "tests.generated-publication" }, outputRoot,
      ledgerSettings: fixture.inputs.ledgerSettings,
      registrations: { diversity: fixture.inputs.registrations.diversity, sources: fixture.inputs.registrations.source_runs },
      publication_days: [
        { published: { ...empty, schema_version: PUBLISHED_ROW_SCHEMA_VERSION },
          health: { day: prior, status: "empty", rows: [] }, digest_path: null },
        { published: { ...named([published]), schema_version: PUBLISHED_ROW_SCHEMA_VERSION }, digest_path: digestPath,
          health: { day: summary.date, status: "rows", rows: dispatches.rows.map(({ row }, index) => ({
            date: summary.date, run_id: summary.run_id, item_id: digest.items[index]!.item_id,
            url_key: row.content.url_key, source_id: row.selection.source_id, stage: "publish", outcome: "ok",
          })) } },
      ],
      planning_days: [
        { sources: empty, ledgers: { "article-assessments": empty, diversity: empty,
          "editorial-selections": empty, dispatches: empty, rejections: empty } },
        { sources: named([sources]), ledgers: {
          "article-assessments": named([metrics.files.assessments]), diversity: named([metrics.files.diversity]),
          "editorial-selections": named([summary.files.selections]), dispatches: named([summary.files.dispatches]),
          rejections: named([summary.files.harvest_rejections, summary.files.screening_rejections, summary.files.curation_rejections]),
        } },
      ],
      event_pairs: [],
    });
    expect(observed.audited_complete).toBe(false);
    expect(observed.status).toBe("publication_metrics_recorded_audit_pending");
    await verifyParquetFiles(outputRoot, "diversity", observed.files.diversity, fixture.inputs.registrations.diversity, observed.rows);
    verifyLedgerReceipt("diversity", observed.files.diversity, observed.receipts.diversity);
    if (observed.files.sources === null) throw new Error("Generated same-day publication omitted real source observations");
    await verifyParquetFiles(outputRoot, "source-runs", observed.files.sources,
      fixture.inputs.registrations.source_runs, observed.source_observations);
    expect(observed.source_observations.reduce((count, row) => count + row.published_count!, 0)).toBe(digest.items.length);
    expect(observed.source_observations.every(row => row.observation_phase === "publication_complete")).toBe(true);
    expect(summary.audited_complete).toBe(false);
  } finally {
    await fixture.close();
  }
});

test("actual CLI planning proof and all native files survive both real report modes, never complete audit", async () => {
  const fixture = await recordedPlan([source(), source({ id: "inactive-news", status: "draft" })]);
  try {
    const progress: ProgressRecord[] = [];
    const summary = await main(["--cli", "--partition-strategy=none"], {
      inputs: fixture.inputs, runtime: { ...fixture.runtime, progress: record => progress.push(record) }, output: () => {},
    });
    if (!("files" in summary) || summary.metrics === undefined) throw new Error("Actual CLI omitted metric evidence");
    const metrics = summary.metrics;
    const outputs = createExecutionOutputs(summary, fixture.inputs.registrations);
    const hostFixture = await Bun.file(new URL("../../../tests/fixtures/ledger-file-writer/host-fingerprint-row.json", import.meta.url)).json();
    const host = {
      row: { ...hostFixture, date: summary.date, run_id: summary.run_id },
      writer: { run_id: summary.run_id, attempt: summary.planning_completion!.attempt, job: hostFixture.job,
        pipeline_name: hostFixture.pipeline_name, task_name: hostFixture.task_name, shard: hostFixture.shard,
        producer: "telemetry.silicon", git_sha: fixture.runtime.git_sha },
    };
    const executionSummary = formatExecutionReport({
      response: summary, host, progress, historyStagingMs: null,
    });
    expect(executionSummary).toContain("SOURCE&#95;INACTIVE | 1/2 configured sources");
    for (const response of [
      { ...summary, correlation_id: "another-correlation" },
      { ...summary, planning_completion: { ...summary.planning_completion!, attempt: summary.planning_completion!.attempt + 1 } },
    ]) expect(() => formatExecutionReport({ response, host, progress, historyStagingMs: null })).toThrow("source evidence");
    for (const mixedHost of [
      { ...host, row: { ...host.row, run_id: `${summary.date}-999` } },
      { ...host, writer: { ...host.writer, attempt: host.writer.attempt + 1 } },
    ]) expect(() => formatExecutionReport({ response: summary, host: mixedHost, progress, historyStagingMs: null })).toThrow("host evidence");
    expect(executionSummary).toContain(`| F1 | Hardware fingerprint | ${hostFixture.fingerprint ?? "Unavailable"} |`);
    expect(executionSummary).toContain(`requested limit ${summary.request.article_limit}`);
    expect(executionSummary).toContain("Screened eligible does not mean previously unpublished");
    const completedArticles = progress.filter(entry => entry.eventType === "ARTICLE_HARVEST_COMPLETED");
    const fetches = completedArticles.filter(entry => entry.diagnostics?.fetch_ms !== null && entry.diagnostics?.fetch_ms !== undefined);
    const extracts = completedArticles.filter(entry => entry.diagnostics?.extract_ms !== null && entry.diagnostics?.extract_ms !== undefined);
    expect(executionSummary).toContain(`| C11 | Refused before permitted fetching | 1/${completedArticles.length}`);
    expect(executionSummary).toContain(`| C12 | Permitted article fetch operations | ${fetches.length}/${completedArticles.length}`);
    expect(executionSummary).toContain(`| C13 | Extraction operations | ${extracts.length}/${fetches.length}`);
    expect(executionSummary).toContain(`${(fetches.reduce((sum, entry) => sum + entry.diagnostics!.fetch_ms!, 0) / 1000).toFixed(3)} seconds summed over ${fetches.length}`);
    expect(executionSummary).toContain("http&#95;status / 200");
    expect(() => formatExecutionReport({
      response: summary, host, historyStagingMs: null,
      progress: progress.map((entry, index) => index === 0 ? { ...entry, diagnostics: { error_code: "unsafe arbitrary prose" } } : entry),
    })).toThrow();
    const unavailable = formatExecutionReport({ response: summary, host: null, progress: [], historyStagingMs: null });
    expect(unavailable).toContain("| F1 | Hardware fingerprint | Unavailable |");
    expect(unavailable).toContain("| C9 | Article harvest operations | Unavailable |");
    expect(unavailable).toContain("| C10 | Extraction outcomes | Unavailable |");
    expect(unavailable).toContain("| C11 | Refused before permitted fetching | Unavailable |");
    expect(outputs.metrics_status).toBe("assessment_diversity_recorded_audit_pending");
    expect(outputs.audited_complete).toBe("false");
    expect(outputs.planning_complete).toBe("true");
    expect(outputs.status).toBe("planning_complete_audit_pending");
    const proof = await verifyPlanningCompletion(fixture.inputs.outputRoot, summary);
    expect(proof.sources).toEqual(summary.source_records!);
    if (summary.files.source_runs === undefined || summary.source_records === null) throw new Error("Actual source records absent");
    await verifyParquetFiles(fixture.inputs.outputRoot, "source-runs", summary.files.source_runs,
      fixture.inputs.registrations.source_runs, summary.source_records);
    expect(JSON.parse(outputs.source_run_files!)).toEqual(summary.files.source_runs.files.map(file => file.path));
    const completion = summary.planning_completion!;
    await expect(verifyPlanningCompletion(fixture.inputs.outputRoot, {
      ...summary, planning_completion: { ...completion, attempt: completion.attempt + 1 },
    })).rejects.toThrow("selector proof");
    expect(() => createExecutionOutputs({ ...summary, planning_complete: false }, fixture.inputs.registrations))
      .toThrow("audited_complete");
    const files = [...new Set([...Object.values(summary.files), ...Object.values(metrics.files)]
      .flatMap(result => result?.files.map(file => file.path) ?? []))];
    expect(JSON.parse(outputs.current_run_files!)).toEqual(expect.arrayContaining(files));
    expect(JSON.parse(outputs.current_run_files!)).toHaveLength(files.length);
    const original = await Promise.all(files.map(path => readFile(join(fixture.inputs.outputRoot, ...path.split("/")))));
    const summaryPath = join(fixture.directory, "actual-main-report.md");
    const annotations: string[] = [];
    const outputBefore = createExecutionOutputs(summary, fixture.inputs.registrations);
    const seenPaths = summary.files.seen.files.map(file => file.path);
    const seenBefore = await readSeenEvidence(fixture.inputs.outputRoot, seenPaths);
    for (const enabled of [false, true]) {
      await writePlannerReport({ enabled, events: fixture.events, summaryPath, executionSummary, annotate: line => annotations.push(line) });
      if (enabled) {
        expect(annotations.length).toBeGreaterThan(0);
        expect((await readFile(summaryPath, "utf8")).length).toBeGreaterThan(0);
      } else {
        expect(annotations).toEqual([]);
        await expect(stat(summaryPath)).rejects.toMatchObject({ code: "ENOENT" });
      }
      for (const [index, path] of files.entries()) {
        const bytes = await readFile(join(fixture.inputs.outputRoot, ...path.split("/")));
        expect(bytes).toEqual(original[index]!);
        expect(createHash("sha256").update(bytes).digest("hex"))
          .toBe(createHash("sha256").update(original[index]!).digest("hex"));
      }
      expect(createExecutionOutputs(summary, fixture.inputs.registrations)).toEqual(outputBefore);
      expect(await verifyPlanningCompletion(fixture.inputs.outputRoot, summary)).toEqual(proof);
      await verifyParquetFiles(fixture.inputs.outputRoot, "source-runs", summary.files.source_runs,
        fixture.inputs.registrations.source_runs, summary.source_records);
      expect(await readSeenEvidence(fixture.inputs.outputRoot, seenPaths)).toEqual(seenBefore);
    }
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
        ...metrics.receipts.assessments, files: [], row_count: 0, logical: null,
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

test("invalid actual CLI audit measurements produce no summary or assessment/diversity files", async () => {
  const fixture = await recordedPlan();
  try {
    fixture.inputs.harvest.config.metrics.top_source_counts = [1, 0, 5];
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
      rowContract: DispatchContract,
      period: { tier: "raw", covers: row.content.date }, registryEntry: registration,
      writerContext: { run_id: row.content.run_id, attempt: 1, job: null, pipeline_name: "plan",
        task_name: "seal-article-ledger", shard: 0, producer: "tests.outputs", git_sha: "a".repeat(40) },
      ledgerSettings: { format: "parquet", compression_raw: "snappy", compression_compact: "zstd" },
    });
    const receipt = { ledger: "dispatches", row_count: 1, files: result.files.map(file => ({
      file_id: file.file_id, content_sha256: file.content_sha256, row_count: file.row_count,
    })) };
    expect((await verifyParquetFiles(root, "dispatches", result, registration, [row])).row_count).toBe(1);
    await expect(verifyParquetFiles(root, "dispatches", result, registration, [])).rejects.toThrow("rows");
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
  expect(await verifyRecordedCompatibility()).toMatchObject({ status: "verified", row_count: 1, legacy_row_count: 1 });
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
    expect(second.selected_candidate_ids).toEqual(first.selected_candidate_ids);
    expect(second.assignments).toEqual(first.assignments);
    for (const [summary, fixture] of [[first, disabled], [second, enabled]] as const) {
      if (summary.files.source_runs === undefined || summary.source_records === null) throw new Error("Source proof absent");
      const paths = [...Object.values(summary.files), ...Object.values(summary.metrics!.files)]
        .flatMap(result => result?.files.map(file => file.path) ?? []);
      const before = await Promise.all(paths.map(path => readFile(join(fixture.inputs.outputRoot, ...path.split("/")))));
      await writePlannerReport({
        enabled: fixture.inputs.harvest.config.workflow_reporting.enabled, events: fixture.events,
        summaryPath: join(fixture.directory, "configured-report.md"), annotate: () => {},
      });
      for (const [index, path] of paths.entries()) {
        expect(await readFile(join(fixture.inputs.outputRoot, ...path.split("/")))).toEqual(before[index]!);
      }
      await verifyParquetFiles(fixture.inputs.outputRoot, "source-runs", summary.files.source_runs,
        fixture.inputs.registrations.source_runs, summary.source_records);
      await verifyPlanningCompletion(fixture.inputs.outputRoot, summary);
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
    expect(actual.evidence.rows).toEqual(
      [...result.evidence.seen.new_rows].sort((a, b) => a.url_key.localeCompare(b.url_key)),
    );
  } finally {
    await fixture.close();
  }
});

test("a missing named raw index stays missing while an actual current sighting is recorded", async () => {
  const fixture = await recordedPlan();
  try {
    fixture.inputs.clock_config.collect.seen_window_days = 0;
    const now = utcTimestamp(fixture.runtime.clock);
    fixture.inputs.settings.inputs.seen_days = createSeenDayInputs(fixture.inputs.registrations.seen.prefix,
      requiredSeenDays(now, fixture.inputs.clock_config.collect.seen_window_days));
    const result = await runFeedPlan({ article_limit: 1 }, fixture.inputs, fixture.runtime);
    expect(result.evidence.seen.absence_proof).toBe("unavailable");
    expect(result.evidence.seen.window?.days[0]?.status).toBe("missing");
    expect(result.evidence.seen.new_rows.length).toBeGreaterThan(0);
    expect(result.files.seen.status).toBe("written");
    const files = result.files.seen.files.map(file => file.path);
    expect(JSON.parse(createExecutionOutputs(summarizePlan(result), fixture.inputs.registrations).seen_files!))
      .toEqual(files);
    const actual = await readSeenEvidence(fixture.inputs.outputRoot, files);
    expect(actual.evidence.availability).toBe("available");
    if (actual.evidence.availability !== "available") throw new Error("Actual first-sight file was not readable");
    expect(actual.evidence.rows).toEqual(
      [...result.evidence.seen.new_rows].sort((a, b) => a.url_key.localeCompare(b.url_key)),
    );
  } finally {
    await fixture.close();
  }
});
