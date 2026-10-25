/** Do real planner results retain native file evidence independently of optional reporting? */
import { expect, test } from "bun:test";
import { mkdir, mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";
import { createHash } from "node:crypto";
import { readFeedIngestDispatch, RawDayIndexSchema, SourceRunRecordSchema } from "../../../packages/common-contracts/src/index";
import { persistLedger } from "../../../packages/ledger-file-writer/src/index";
import { runFeedPlan, summarizePlan } from "../../../services/feed-ingest-plan/src/run-feed-plan";
import { recordedPlan } from "../../../services/feed-ingest-plan/test/plan-recordings";
import { source } from "../../../services/feed-ingest-plan/test/harvest-recordings";
import { verifyLedgerReceipt, verifyParquetFiles, verifyPlanningCompletion, verifyRecordedCompatibility } from "../feed-ingest-plan-verification";
import { createExecutionOutputs, createSeenDayInputs, writeGitHubOutputs } from "../feed-ingest-plan-outputs";
import { formatExecutionReport, readExecutionReport, writePlannerReport } from "../feed-ingest-plan-report";
import { formatResourceReport } from "../feed-ingest-plan-resource-report";
import { recordProfileEvidence } from "./feed-ingest-plan-profile-recording";
import { ResourceProofSchema } from "../feed-ingest-plan-profile-schema";
import type { ProgressRecord } from "../../../services/feed-ingest-plan/src/logging/progress-logger";
import { readSeenEvidence, requiredSeenDays } from "../../../services/feed-ingest-plan/src/read-ledger-history/read-seen-evidence";
import { utcTimestamp } from "../../../services/feed-ingest-plan/src/harvest-feeds/harvest-types";
import { main } from "../../../services/feed-ingest-plan/src/index";
import { recordPublicationMetrics } from "../../../services/feed-ingest-plan/src/metrics/metrics-recorder";
import {
  DigestPublicationSchema, PUBLISHED_ROW_SCHEMA_VERSION, PublishedRowSchema,
} from "../../../services/feed-ingest-plan/src/metrics/publication-evidence";
import { readLedgerParquet } from "../../../services/feed-ingest-plan/src/read-ledger-history/read-parquet";
import { DispatchContract, DocumentObservationContract } from "../../../services/feed-ingest-plan/src/metrics/audit-contracts";
import { readIngestEvidence } from "../../../services/feed-ingest-plan/src/read-ledger-history/read-ingest-evidence";
import { rollupIngestOutcomes } from "../../../services/feed-ingest-plan/src/rollup-ingest-outcomes";
import { settleIngestObservations } from "../../../services/feed-ingest-plan/src/settle-ingest-observations";
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
    const dispatches = await readLedgerParquet(join(fixture.inputs.outputRoot, ...first.path.split("/")), "article-dispatches",
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
    const emptyCurrent = named([], summary.date);
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
        { sources: empty, feed_runs: empty, ledgers: { "article-assessments": empty, diversity: empty,
          "editorial-selections": empty, dispatches: empty, rejections: empty } },
        { sources: { day: summary.date }, feed_runs: named([sources]), ledgers: {
          "article-assessments": named([metrics.files.assessments]), diversity: emptyCurrent,
          "editorial-selections": named([summary.files.selections]), dispatches: emptyCurrent, rejections: emptyCurrent,
        }, renamed: {
          "article-selection-diversity": named([metrics.files.diversity]),
          "article-dispatches": named([summary.files.dispatches]),
          "ingest-rejections": named([summary.files.harvest_rejections, summary.files.screening_rejections, summary.files.curation_rejections]),
        } },
      ],
      event_pairs: [],
    });
    expect(observed.audited_complete).toBe(false);
    expect(observed.status).toBe("publication_metrics_recorded_audit_pending");
    await verifyParquetFiles(outputRoot, "article-selection-diversity", observed.files.diversity, fixture.inputs.registrations.diversity, observed.rows);
    verifyLedgerReceipt("article-selection-diversity", observed.files.diversity, observed.receipts.diversity);
    if (observed.files.sources === null) throw new Error("Generated same-day publication omitted real source observations");
    await verifyParquetFiles(outputRoot, "feed-runs", observed.files.sources,
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
    await verifyParquetFiles(fixture.inputs.outputRoot, "ingest-observations", summary.files.document_observations,
      fixture.inputs.registrations.document_observations);
    expect(JSON.parse(outputs.document_observation_files!)).toEqual(summary.files.document_observations.files.map(file => file.path));
    const observationFiles = await Promise.all(summary.files.document_observations.files.map(file =>
      readLedgerParquet(join(fixture.inputs.outputRoot, ...file.path.split("/")),
        "ingest-observations", DocumentObservationContract)));
    if (observationFiles.length === 0) throw new Error("Recorded planner omitted its named observation fixture");
    const observations = observationFiles.flatMap(file => file.rows.map(held => held.row));
    const legacyObservations = await persistLedger({
      ledger: "document-observations", outputRoot: fixture.inputs.outputRoot,
      registryEntry: fixture.inputs.legacy_registrations.document_observations,
      writerContext: observationFiles[0]!.envelope.identity,
      ledgerSettings: fixture.inputs.ledgerSettings, period: { tier: "raw", covers: summary.date },
      rowContract: DocumentObservationContract, rows: observations,
    });
    const nextDay = utcTimestamp(() => new Date(Date.parse(`${summary.date}T00:00:00Z`) + 86_401_000));
    const merged = await readIngestEvidence({
      root: fixture.inputs.outputRoot, now: nextDay, window_days: 1,
      registration: fixture.inputs.registrations.document_observations,
      legacy_registration: fixture.inputs.legacy_registrations.document_observations,
      days: [{ day: summary.date, raw_files: summary.files.document_observations.files.map(file => file.path) }],
      legacy_days: [{ day: summary.date, raw_files: legacyObservations.files.map(file => file.path) }],
    });
    const settled = settleIngestObservations(observations, summary.date, summary.date);
    const expected = rollupIngestOutcomes(settled.rows, true);
    expect(merged.gaps).toEqual([]);
    expect(merged.sources).toEqual(expected.sources);
    expect(merged.publishers).toEqual(expected.publishers);
    expect(merged.unallocated).toEqual(expected.unallocated);
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
    const identity = { git_sha: fixture.runtime.git_sha, run_id: summary.run_id,
      attempt: summary.planning_completion!.attempt, correlation_id: summary.correlation_id };
    const sourceId = summary.source_records!.find(source => source.fetch_status === "success")!.source_id;
    const evidence = await recordProfileEvidence(fixture.directory, identity, sourceId, {
      machineMemoryEnabled: false, cpuWindowMs: 1000,
    });
    const resourceInput = { response: summary, gitSha: identity.git_sha, machineMemoryEnabled: false, ...evidence };
    const evidenceBefore = JSON.stringify(evidence);
    const resourceReport = formatResourceReport(resourceInput);
    const cacheEvidence = ResourceProofSchema.parse(await Bun.file(
      new URL("../../../tests/fixtures/host-probes/cache-resource-proof.json", import.meta.url),
    ).json());
    Object.assign(cacheEvidence, identity);
    if (cacheEvidence.task_profile === null || cacheEvidence.cache?.latency === null || cacheEvidence.cache === null) {
      throw new Error("Recorded cache report fixture must contain its actual task and latency evidence");
    }
    // Only attempt labels change; hardware, counters, timings and latency readings stay recorded.
    cacheEvidence.task_profile.profile.identity.run_id = identity.run_id;
    cacheEvidence.task_profile.profile.identity.correlation_id = identity.correlation_id;
    const cacheInput = { ...resourceInput, resourceProof: cacheEvidence };
    const cacheReport = formatResourceReport(cacheInput);
    const withoutCache = formatResourceReport({ ...cacheInput, resourceProof: { ...cacheEvidence, cache: null } });
    expect(cacheReport.annotations.slice(0, -1)).toEqual([...withoutCache.annotations]);
    expect(cacheReport.summary.split("## Table L -")[0]!.trim()).toBe(withoutCache.summary.trim());
    const cacheSection = cacheReport.summary.split("## Table L -")[1]!;
    const cacheHtml = Bun.markdown.html(cacheSection);
    expect(cacheHtml.match(/<table>/g)).toHaveLength(1);
    expect(cacheHtml.match(/<th>/g)).toHaveLength(3);
    expect(cacheHtml.match(/<td>/g)).toHaveLength(15);
    expect(cacheHtml).toContain("permission denied");
    expect(cacheHtml).toContain("count null, not zero");
    expect(cacheHtml).toContain("1.246 ns/load");
    expect(cacheHtml).toContain("NOT direct L3-hit latency");
    expect(cacheHtml).toContain("perf-build Python executions 0");
    expect(cacheReport.annotations.at(-1)).toContain("Actual hardware counters were not measured");
    for (const status of ["disabled", "unavailable"] as const) {
      const selected = structuredClone(cacheEvidence);
      const off = selected.cache!.default_off.latency;
      selected.cache!.latency = status === "disabled" ? off : { ...off, status, reason: "tool_missing" };
      const rendered = Bun.markdown.html(formatResourceReport({ ...cacheInput, resourceProof: selected }).summary);
      expect(rendered).toContain(status === "disabled" ? "disabled (configured off)" : "unavailable (tool missing)");
      expect(rendered).toContain("no latency reading");
    }
    for (const tamper of ["target", "handle", "result", "task-result", "initial", "host", "python"] as const) {
      const foreign = structuredClone(cacheEvidence);
      const cache = foreign.cache!;
      if (tamper === "target") cache.task_api!.target.pid++;
      if (tamper === "handle") cache.task_api!.handle = "b0d6a594-059f-46e1-bd6d-682452627e53";
      if (tamper === "result") cache.counters!.events[0]!.reason = "tool_missing";
      if (tamper === "task-result") foreign.task_profile!.cache_counters!.target.pid++;
      if (tamper === "initial") cache.task_api!.initial.target.pid++;
      if (tamper === "host") cache.latency!.host!.release = "another-kernel";
      if (tamper === "python") Object.assign(cache.tool_install, { python_execution_count: 1 });
      expect(() => formatResourceReport({ ...cacheInput, resourceProof: foreign })).toThrow();
    }
    expect(JSON.stringify(evidence)).toBe(evidenceBefore);
    expect(resourceReport.summary).toContain("partial window");
    expect(resourceReport.summary).toContain("Preserved; no new profile");
    expect(resourceReport.summary).toContain("RSS 600 kB; sampled max 600 kB");
    expect(resourceReport.summary).toContain("Disabled; no task meminfo/vmstat reads");
    expect(resourceReport.summary).toContain("not PID CPU or task-exclusive usage");
    expect(resourceReport.summary).toContain("not exact task peaks");
    expect(resourceReport.summary).toContain("configured off");
    expect(Bun.markdown.html(resourceReport.summary)).toContain("cache-derived buffer");
    expect(resourceReport.summary).toContain(`${evidence.resourceProof.copy!.on!.l3_cache_bytes} bytes`);
    expect(resourceReport.annotations.filter(line => !line.includes("PID CPU"))).toHaveLength(5);
    expect(resourceReport.annotations.filter(line => line.includes("PID CPU"))).toHaveLength(4);
    expect(resourceReport.annotations.some(line => line.includes("3000 ms CPU") && line.includes("%25 of one core"))).toBe(true);
    expect(resourceReport.annotations.every(line => line.startsWith("::notice title=") && !line.includes("\n"))).toBe(true);
    for (const [letter, columns, count] of [["H", 7, 4], ["I", 4, 4], ["J", 3, 7], ["K", 7, 4]] as const) {
      const section = resourceReport.summary.split(`## Table ${letter} -`)[1]?.split("\n## ")[0];
      if (section === undefined) throw new Error(`Missing resource table ${letter}`);
      const html = Bun.markdown.html(section);
      expect(html.match(/<table>/g)).toHaveLength(1);
      expect(html.match(/<th>/g)).toHaveLength(columns);
      expect(html.match(/<td>/g)).toHaveLength(columns * count);
    }
    const pidSection = resourceReport.summary.split("## Table K -")[1]!;
    const firstPid = pidSection.split("\n").find(line => line.startsWith("| K1 |"))!.split("|");
    const processCpu = evidence.stageProof.documents[0]!.profiling!.profiles[0]!.processes.worker;
    expect(Number.parseFloat(firstPid[4]!)).toBeCloseTo(processCpu.cpu_interval_ms, 3);
    expect(Number.parseFloat(firstPid[5]!)).toBe(3000);
    expect(Number.parseFloat(firstPid[6]!)).toBeGreaterThan(100);
    expect(Number.parseFloat(firstPid[6]!)).toBeCloseTo(processCpu.cpu.value!.percent_one_core, 3);
    const ids = [...resourceReport.summary.matchAll(/^\| ([A-Z]\d+) \|/gm)].map(match => match[1]);
    expect(new Set(ids).size).toBe(ids.length);
    const fullEvidence = await recordProfileEvidence(fixture.directory, identity, sourceId, {
      machineMemoryEnabled: true, cpuWindowMs: 1, resourceProof: evidence.resourceProof,
    });
    const fullReport = formatResourceReport({ ...resourceInput, ...fullEvidence, machineMemoryEnabled: true });
    expect(fullReport.summary).toContain("full window recorded");
    expect(fullReport.summary).toContain("total 16384256 kB");
    expect(fullReport.summary).toContain("sampled min available 8192000 kB");
    expect(fullEvidence.stageProof.documents.every(document =>
      document.profiling!.profiles.every(profile => profile.full_window_count > 0))).toBe(true);
    const unchangedCounters = await recordProfileEvidence(fixture.directory, identity, sourceId, {
      machineMemoryEnabled: false, cpuWindowMs: 1, withTicks: false, resourceProof: evidence.resourceProof,
    });
    expect(Bun.markdown.html(formatResourceReport({ ...resourceInput, ...unchangedCounters }).summary)).toContain("Unavailable (no ticks)");
    expect(formatResourceReport({ ...resourceInput, ...unchangedCounters }).summary).toContain("no measured full window");
    const zeroPid = formatResourceReport({ ...resourceInput, ...unchangedCounters }).summary
      .split("## Table K -")[1]!.split("\n").find(line => line.startsWith("| K1 |"))!.split("|");
    expect(Number.parseFloat(zeroPid[5]!)).toBe(0);
    expect(Number.parseFloat(zeroPid[6]!)).toBe(0);
    for (const machineMemoryEnabled of [false, true]) {
      const absent = formatResourceReport({ response: summary, machineMemoryEnabled });
      expect(absent.summary).toContain("| H1 | Task profiles | Not recorded | Unavailable");
      expect(absent.summary).toContain("resource-proof.json absent");
      expect(absent.summary).toContain(`Whole-machine task RAM: **${machineMemoryEnabled ? "enabled" : "disabled"}**`);
      expect(absent.summary).not.toContain("0 total");
    }
    for (const change of [
      { run_id: `${summary.date}-999` }, { attempt: identity.attempt + 1 },
      { correlation_id: "b0d6a594-059f-46e1-bd6d-682452627e53" }, { git_sha: "b".repeat(40) },
    ]) {
      expect(() => formatResourceReport({ ...resourceInput,
        resourceProof: { ...evidence.resourceProof, ...change } })).toThrow("Resource evidence differs");
      expect(() => formatResourceReport({ ...resourceInput,
        stageProof: { ...evidence.stageProof, ...change } })).toThrow("Resource evidence differs");
    }
    expect(() => formatResourceReport({ ...resourceInput, runNumber: "foreign" })).toThrow("completed planning attempt");
    expect(() => formatResourceReport({ ...resourceInput, runAttempt: String(identity.attempt + 1) })).toThrow("completed planning attempt");
    expect(() => formatResourceReport({ ...resourceInput, machineMemoryEnabled: true })).toThrow("workflow input");
    for (const tamper of ["request", "count", "cpu", "pid-cpu", "replay", "journal", "disabled-machine"] as const) {
      const stageProof = structuredClone(evidence.stageProof);
      const document = stageProof.documents[0]!;
      const profile = document.profiling!.profiles[0]!;
      if (tamper === "request") profile.identity.request_id = "b0d6a594-059f-46e1-bd6d-682452627e53";
      if (tamper === "count") document.profiling!.after_checks_count = 3;
      if (tamper === "cpu" && profile.cpu.value !== null) profile.cpu.value.user = -1;
      if (tamper === "pid-cpu" && profile.processes.worker.cpu.value !== null) {
        profile.processes.worker.cpu.value.percent_one_core = -1;
      }
      if (tamper === "replay") document.calls.find(call => call.stage === "fetch_replay_after_restart")!.response_sha256 = "b".repeat(64);
      if (tamper === "journal") document.journal_records_sha256!.after_checks = "b".repeat(64);
      if (tamper === "disabled-machine") profile.machine_available_min_kb = 1;
      expect(() => formatResourceReport({ ...resourceInput, stageProof })).toThrow();
    }
    const unsafeResource = structuredClone(evidence.resourceProof);
    unsafeResource.host.release = "bad | <script>\r\n::error title=injected::run";
    const escapedResource = formatResourceReport({ ...resourceInput, resourceProof: unsafeResource });
    expect(escapedResource.summary).not.toContain("<script>");
    expect(escapedResource.summary).toContain("&#124;");
    expect(escapedResource.annotations.join("\n")).not.toContain("injected");
    const reportDirectory = join(fixture.directory, "report-inputs");
    await mkdir(reportDirectory);
    for (const [name, value] of Object.entries({
      "response.json": summary, "events.json": fixture.events, "host.json": host,
      "history-staging-ms.json": null, "stage-api-proof.json": evidence.stageProof, "resource-proof.json": evidence.resourceProof,
    })) await writeFile(join(reportDirectory, name), JSON.stringify(value));
    await writeFile(join(reportDirectory, "progress.jsonl"), progress.map(entry => JSON.stringify(entry)).join("\n"));
    const cliSummary = join(reportDirectory, "summary.md");
    const recordedReport = await readExecutionReport(reportDirectory, { gitSha: identity.git_sha,
      runNumber: summary.run_id.split("-").at(-1)!, runAttempt: String(identity.attempt), machineMemoryEnabled: false,
    });
    const cliOutput: string[] = [];
    await writePlannerReport({ enabled: true, events: fixture.events, summaryPath: cliSummary,
      ...recordedReport, annotate: line => cliOutput.push(line) });
    expect(await readFile(cliSummary, "utf8")).toContain(resourceReport.summary);
    for (const notice of resourceReport.annotations) expect(cliOutput).toContain(notice);
    await writeFile(join(reportDirectory, "resource-proof.json"), JSON.stringify(cacheEvidence));
    const visibleCacheReport = await readExecutionReport(reportDirectory, {
      gitSha: identity.git_sha, runNumber: summary.run_id.split("-").at(-1)!, runAttempt: String(identity.attempt),
      machineMemoryEnabled: false,
    });
    const cacheSummary = join(reportDirectory, "cache-summary.md");
    const cacheNotices: string[] = [];
    await writePlannerReport({
      enabled: true, events: fixture.events, summaryPath: cacheSummary, ...visibleCacheReport,
      annotate: line => cacheNotices.push(line),
    });
    expect(Bun.markdown.html(await readFile(cacheSummary, "utf8"))).toContain("Separate optional cache measurements");
    expect(cacheNotices).toContain(cacheReport.annotations.at(-1)!);
    const reviewDirectory = new URL("../../../test-results/host-probes/", import.meta.url);
    await mkdir(reviewDirectory, { recursive: true });
    await writeFile(new URL("resource-report.md", reviewDirectory), cacheReport.summary);
    await writeFile(new URL("resource-report.html", reviewDirectory), Bun.markdown.html(cacheReport.summary));
    expect(executionSummary).toContain("SOURCE&#95;INACTIVE | 1/2 configured sources");
    const activeSource = summary.source_records?.find(row => row.fetch_status === "success");
    const inactiveSource = summary.source_records?.find(row => row.fetch_status === "not_requested");
    if (activeSource === undefined || inactiveSource === undefined) throw new Error("Report fixture requires fetched and inactive sources");
    const refusalSources = [
      { ...activeSource, parsed_count: 20, drop_reasons: [
        { subject: "article", stage: "curate-article-portfolio", reason: "SOURCE_QUOTA_EXCEEDED", count: 3 },
        { subject: "article", stage: "screen-article-candidates", reason: "STUB_CONTENT", count: 4 },
        { subject: "article", stage: "harvest-feeds", reason: "FETCH_FAILED_HTTP", count: 4 },
        { subject: "article", stage: "screen-article-candidates", reason: "DUPLICATE_CANONICAL_URL", count: 1 },
        { subject: "article", stage: "curate-article-portfolio", reason: "DUPLICATE_CANONICAL_URL", count: 1 },
        { subject: "article", stage: "screen-article-candidates", reason: "PAYWALL_OR_BLOCKED", count: 2 },
        { subject: "article", stage: "harvest-feeds", reason: "EXTRACT_EMPTY", count: 2 },
      ] },
      { ...activeSource, source_id: "second-news", source: { ...activeSource.source, source_id: "second-news" },
        parsed_count: 10, drop_reasons: [
          { subject: "article", stage: "harvest-feeds", reason: "FETCH_FAILED_HTTP", count: 1 },
          { subject: "article", stage: "screen-article-candidates", reason: "DUPLICATE_CANONICAL_URL", count: 1 },
          { subject: "article", stage: "curate-article-portfolio", reason: "MMR_PORTFOLIO_CUTOFF", count: 1 },
        ] },
      inactiveSource,
      ...["failed-one", "failed-two"].map(sourceId => ({
        ...activeSource, source_id: sourceId, source: { ...activeSource.source, source_id: sourceId },
        fetch_status: "http_failure", parse_status: "not_attempted", parsed_count: null, parse_duration_ms: null,
        last_failure_at: activeSource.observed_at, last_failure_reason: "FETCH_FAILED_HTTP",
        drop_reasons: [{ subject: "feed", stage: "harvest-feeds", reason: "FETCH_FAILED_HTTP", count: 1 }],
      })),
    ].map(row => SourceRunRecordSchema.parse({ ...row, expected_source_count: 5 }));
    const refusalInput = { response: { ...summary, source_records: refusalSources }, host, progress, historyStagingMs: null };
    const groupedReport = formatExecutionReport(refusalInput);
    const refusalRows = groupedReport.match(/^\| D\d+ \|.*$/gm);
    if (refusalRows === null) throw new Error("Report fixture requires refusal rows");
    expect(refusalRows.map(row => row.split("|").slice(2, -1).map(cell => cell.trim()))).toEqual([
      ["feed", "harvest feeds", "FETCH&#95;FAILED&#95;HTTP", "2/5 configured sources"],
      ["feed", "harvest feeds", "SOURCE&#95;INACTIVE", "1/5 configured sources"],
      ["article", "harvest feeds", "FETCH&#95;FAILED&#95;HTTP", "5/30 observed parsed entries"],
      ["article", "harvest feeds", "EXTRACT&#95;EMPTY", "2/30 observed parsed entries"],
      ["article", "screen article candidates", "STUB&#95;CONTENT", "4/30 observed parsed entries"],
      ["article", "screen article candidates", "DUPLICATE&#95;CANONICAL&#95;URL", "2/30 observed parsed entries"],
      ["article", "screen article candidates", "PAYWALL&#95;OR&#95;BLOCKED", "2/30 observed parsed entries"],
      ["article", "curate article portfolio", "SOURCE&#95;QUOTA&#95;EXCEEDED", "3/30 observed parsed entries"],
      ["article", "curate article portfolio", "DUPLICATE&#95;CANONICAL&#95;URL", "1/30 observed parsed entries"],
      ["article", "curate article portfolio", "MMR&#95;PORTFOLIO&#95;CUTOFF", "1/30 observed parsed entries"],
    ]);
    const refusalMarkdown = groupedReport.split("## Table D - Refusals\n")[1]?.split("## Table E -")[0];
    if (refusalMarkdown === undefined) throw new Error("Report fixture requires Table D");
    const refusalHtml = Bun.markdown.html(refusalMarkdown);
    expect(refusalHtml).toContain("<table>");
    expect(refusalHtml.match(/<th>/g)).toHaveLength(5);
    expect(refusalHtml.match(/<td>/g)).toHaveLength(refusalRows.length * 5);
    expect(groupedReport).toContain("| C1 | Offered feed entries | 30 articles; 2/5 sources measured |");
    expect(groupedReport).toContain("| C8 | Feed fetch failures | 2/4 attempted feeds |");
    const reversedReport = formatExecutionReport({
      ...refusalInput, response: { ...refusalInput.response, source_records: refusalSources.toReversed()
        .map(row => ({ ...row, drop_reasons: row.drop_reasons.toReversed() })) },
    });
    expect(reversedReport.match(/^\| D\d+ \|.*$/gm)).toEqual(refusalRows);
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
    await verifyParquetFiles(fixture.inputs.outputRoot, "feed-runs", summary.files.source_runs,
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
      await writePlannerReport({ enabled, events: fixture.events, summaryPath, executionSummary, resourceReport,
        annotate: line => annotations.push(line) });
      if (enabled) {
        expect(annotations.length).toBeGreaterThan(0);
        expect((await readFile(summaryPath, "utf8")).length).toBeGreaterThan(0);
        expect(await readFile(summaryPath, "utf8")).toContain(resourceReport.summary);
        for (const notice of resourceReport.annotations) expect(annotations).toContain(notice);
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
      await verifyParquetFiles(fixture.inputs.outputRoot, "feed-runs", summary.files.source_runs,
        fixture.inputs.registrations.source_runs, summary.source_records);
      expect(await readSeenEvidence(fixture.inputs.outputRoot, seenPaths)).toEqual(seenBefore);
    }
    for (const [key, ledger] of [["assessments", "article-assessments"], ["diversity", "article-selection-diversity"]] as const) {
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
    await expect(verifyParquetFiles(fixture.inputs.outputRoot, "article-selection-diversity",
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
    expect((await verifyParquetFiles(fixture.inputs.outputRoot, "article-dispatches",
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
    const row = readFeedIngestDispatch(await Bun.file(
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
    expect((await verifyParquetFiles(fixture.inputs.outputRoot, "article-dispatches", result.files.dispatches,
      fixture.inputs.registrations.dispatches)).status).toBe("verified_empty");
    expect(result.files.screening_rejections.status).toBe("empty");
    expect((await verifyParquetFiles(fixture.inputs.outputRoot, "ingest-rejections", result.files.screening_rejections,
      fixture.inputs.registrations.rejections)).row_count).toBe(0);
    expect((await verifyParquetFiles(fixture.inputs.outputRoot, "article-assessments", result.metrics.files.assessments,
      fixture.inputs.registrations.assessments)).status).toBe("verified_empty");
    verifyLedgerReceipt("article-assessments", result.metrics.files.assessments, result.metrics.receipts.assessments);
    expect(outputs.assessments_files).toBe("[]");
    expect(() => verifyLedgerReceipt("article-assessments", { status: "empty", files: [] },
      { ledger: "article-assessments", row_count: 0, files: [] })).not.toThrow();
    await expect(verifyParquetFiles(fixture.inputs.outputRoot, "article-dispatches",
      JSON.parse("{}"), fixture.inputs.registrations.dispatches)).rejects.toThrow("absent");
    await expect(verifyParquetFiles(fixture.inputs.outputRoot, "article-dispatches",
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
      await verifyParquetFiles(fixture.inputs.outputRoot, "feed-runs", summary.files.source_runs,
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
