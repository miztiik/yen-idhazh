/** Does named native history retain original identities and distinguish proof from missing evidence? */
import { beforeAll, expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join } from "node:path";
import {
  ArticleAssessmentRecordSchema, CandidateRejectionContract, CONTRACT_VERSION,
  EditorialSelectionContract, EditorialSelectionRowSchema, SourceRunRecordSchema,
  PLANNER_EXCLUSIONS_VERSION, EXTRACTION_QUALITY_VERSION, PreviousHarvestDiagnosticsSchema,
} from "@idhazh/common-contracts";
import type { LedgerCompletionEvidence } from "@idhazh/common-contracts";
import { appendIdentityColumns, describeObjectSchema, digestRows, persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRowContract, PersistLedgerResult, StoredLedgerRow } from "@idhazh/ledger-file-writer";
import { Int64, tableFromIPC, vectorFromArray } from "apache-arrow";
import initializeParquet, { Table as WasmTable, WriterPropertiesBuilder, readMetadata, readParquet, writeParquet } from "parquet-wasm/esm";
import { tableToIPC } from "apache-arrow";
import { readLedgerParquet } from "../src/read-ledger-history/read-parquet";
import { readLedgerDay } from "../src/read-ledger-history/read-period";
import { resolveHealthInventory } from "../src/read-ledger-history/read-health-inventory";
import { selectCompleteAttempt } from "../src/read-ledger-history/complete-attempt";
import type { AttemptHistory } from "../src/read-ledger-history/complete-attempt";
import { readHistoricalSelections } from "../src/partition-article-shards/read-editorial-selection";
import { partitionArticles, persistDispatches } from "../src/partition-article-shards/shard-packer";
import { fixtureInput, readWritten, registration, settings, writer, writeRows } from "./partition-fixtures";
import {
  ArticleAssessmentContract, DiversityMetricContract, DispatchContract, SourceRunContract, legacyAuditSchemas,
} from "../src/metrics/audit-contracts";

const selectionContract = EditorialSelectionContract;
beforeAll(async () => { await initializeParquet(); });
function evidence(ledger: LedgerCompletionEvidence["ledger"], written: PersistLedgerResult): LedgerCompletionEvidence {
  if (written.status === "skipped") throw new Error("Fixture completion ledger was skipped");
  return {
    ledger, row_count: written.files.reduce((count, file) => count + file.row_count, 0),
    files: written.files.map(({ file_id, content_sha256, row_count }) => ({ file_id, content_sha256, row_count })),
    logical: null,
  };
}
async function completeHistory(root: string, observedAt?: string) {
  const input = await fixtureInput(root, { count: 1 });
  const packed = partitionArticles({
    selections: input.curation.rows, candidates: input.candidates,
    context: input.context, settings: input.planning.config.partition,
  });
  const dispatch = await persistDispatches(packed, {
    outputRoot: root, writerContext: writer(input.fixture.run_id), ledgerSettings: settings,
    registration: registration("dispatches"), date: input.fixture.date,
    correlation_id: input.fixture.correlation_id,
  });
  const assessments = await writeRows(root, "article-assessments", input.fixture.date,
    ArticleAssessmentRecordSchema, input.curation.assessments, writer(input.fixture.run_id),
    ArticleAssessmentContract.schemaVersion);
  const empty: PersistLedgerResult = { status: "empty", files: [] };
  const completion = [
    evidence("editorial-selections", input.persisted.selections), evidence("dispatches", dispatch),
    evidence("article-assessments", assessments), evidence("rejections", empty), evidence("diversity", empty),
  ];
  const source = (attempt = 1, zero = false) => SourceRunRecordSchema.parse({
    date: input.fixture.date, correlation_id: input.fixture.correlation_id, run_id: input.fixture.run_id,
    attempt, source_id: input.candidates[0]!.source_id, source: input.candidates[0]!.source, status: "active",
    fetch_status: "success", parse_status: "success", parsed_count: 1, harvested_count: 1,
    fresh_count: 1, duplicate_count: 0, eligible_count: 1, normalized_count: 1, selected_count: zero ? 0 : 1,
    published_count: null, lead_count: null, drop_reasons: [], fetch_duration_ms: 1, parse_duration_ms: 1,
    last_failure_at: null, last_failure_reason: null, history_success_fraction: null,
    history_success_attempts: null, history_window_days: null, observation_phase: "plan_complete",
    observed_at: observedAt ?? input.fixture.observed_at, expected_source_count: 1,
    completion_evidence: zero ? completion.map(item => ({ ...item, row_count: 0, files: [] })) : completion,
  });
  const sourceWritten = await writeRows(root, "source-runs", input.fixture.date,
    SourceRunRecordSchema, [source()], writer(input.fixture.run_id), SourceRunContract.schemaVersion);
  const sources = await readWritten(root, "source-runs", input.fixture.date,
    SourceRunContract, sourceWritten);
  const ledgers: AttemptHistory["ledgers"] = {
    "editorial-selections": await readWritten(root, "editorial-selections", input.fixture.date, selectionContract, input.persisted.selections),
    dispatches: await readWritten(root, "dispatches", input.fixture.date, DispatchContract, dispatch),
    "article-assessments": await readWritten(root, "article-assessments", input.fixture.date, ArticleAssessmentContract, assessments),
    rejections: await readWritten(root, "rejections", input.fixture.date, CandidateRejectionContract, empty),
    diversity: await readWritten(root, "diversity", input.fixture.date, DiversityMetricContract, empty),
  };
  return { input, source, sourceWritten, history: { sources, ledgers }, packed };
}
async function compactSelections(
  root: string, input: Awaited<ReturnType<typeof fixtureInput>>, rows: readonly StoredLedgerRow<ReturnType<typeof EditorialSelectionRowSchema.parse>>[],
  period: "daily" | "monthly" | "yearly",
) {
  const covers = period === "daily" ? input.fixture.date : period === "monthly" ? input.fixture.date.slice(0, 7) : input.fixture.date.slice(0, 4);
  const written = await persistLedger({
    ledger: "editorial-selections", registryEntry: registration("editorial-selections"), outputRoot: root,
    writerContext: { ...writer(input.fixture.run_id, 9, 6), producer: "tests.compactor" },
    ledgerSettings: settings, rowContract: selectionContract,
    period: { tier: "compact", period, covers, builtFrom: 1 }, rows,
  });
  const file = written.files[0]!;
  const path = join(root, file.path);
  const indexPath = join(root, "compact", "feed-ingest-plan", "editorial-selections", "index", `${period}.json`);
  await mkdir(dirname(indexPath), { recursive: true });
  const index = {
    version: "2026-10-07", ledger: "editorial-selections", period,
    entries: [{ covers, rows: file.row_count, bytes: (await stat(path)).size, state: "packed" }],
  };
  await writeFile(indexPath, JSON.stringify(index));
  return { path, indexPath, index };
}

async function migrateAuditFixture<TLegacy extends object, TCurrent extends object>(
  root: string, day: string, run: string, ledger: Parameters<typeof readLedgerDay>[0]["ledger"], path: string,
  legacySchema: LedgerRowContract<TLegacy>["schema"], currentContract: LedgerRowContract<TCurrent>,
): Promise<TCurrent> {
  const input: unknown = await Bun.file(new URL(path, import.meta.url)).json();
  const row = legacySchema.parse(input);
  const written = await writeRows(root, ledger, day, legacySchema, [row], writer(run), "2026-10-20");
  const pathBefore = join(root, written.files[0]!.path);
  const originalBytes = await readFile(pathBefore);
  const loaded = await readWritten(root, ledger, day, currentContract, written);
  expect(await readFile(pathBefore)).toEqual(originalBytes);
  expect(loaded.rows).toHaveLength(1);
  expect(loaded.rows[0]!.row).toMatchObject({ version: currentContract.schemaVersion });
  return loaded.rows[0]!.row;
}

test("native raw and daily reads preserve original writer identity instead of the compactor identity", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-periods-"));
  try {
    const input = await fixtureInput(root, { count: 1 });
    const raw = await readWritten(root, "editorial-selections", input.fixture.date, selectionContract, input.persisted.selections);
    expect(raw.tier).toBe("raw");
    expect(raw.rows).toHaveLength(1);
    const original = raw.rows[0]!;
    const compact = await compactSelections(root, input, raw.rows, "daily");
    const current = await readLedgerDay({
      ledger: "editorial-selections", day: input.fixture.date, contract: selectionContract,
      indexes: { daily: compact.indexPath }, rawFiles: input.persisted.selections.files.map(file => join(root, file.path)),
    });

    expect(current.tier).toBe("daily");
    expect(current.rows).toEqual([original]);
    expect(current.files[0]!.envelope.identity.attempt).toBe(9);
    expect(current.rows[0]!.identity.attempt).toBe(1);
    expect(current.rows[0]!.identity.shard).toBe(0);
    expect(current.rows[0]!.identity.unit_id).toBe(original.identity.unit_id);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("plan completion observed after midnight stays in its original run-day partition", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-late-plan-observation-"));
  try {
    const { input, history } = await completeHistory(root, "2026-10-22T00:00:00Z");
    expect(history.sources.rows).toHaveLength(1);
    expect(history.sources.rows[0]!.identity.covers).toBe(input.fixture.date);
    expect(history.sources.rows[0]!.row).toMatchObject({
      date: input.fixture.date, run_id: input.fixture.run_id, observed_at: "2026-10-22T00:00:00Z",
      observation_phase: "plan_complete",
    });
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("recorded audit rows migrate through native Parquet without invented evidence", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-legacy-contracts-"));
  const day = "2026-10-20";
  const run = `${day}-1`;
  try {
    const migrated = new Map<string, object>();
    migrated.set("article-assessments", await migrateAuditFixture(
      root, day, run, "article-assessments",
      "../../../tests/fixtures/contracts/feed-ingest-article-assessment/one-observation.json",
      legacyAuditSchemas.ArticleAssessment, ArticleAssessmentContract));
    migrated.set("diversity", await migrateAuditFixture(
      root, day, run, "diversity",
      "../../../tests/fixtures/contracts/feed-ingest-diversity/one-observation.json",
      legacyAuditSchemas.DiversityMetric, DiversityMetricContract));
    migrated.set("source-runs", await migrateAuditFixture(
      root, day, run, "source-runs",
      "../../../tests/fixtures/contracts/feed-ingest-source-run/one-observation.json",
      legacyAuditSchemas.SourceRun, SourceRunContract));
    migrated.set("dispatches", await migrateAuditFixture(
      root, day, run, "dispatches",
      "../../../tests/fixtures/contracts/feed-ingest-dispatch/one-article.json",
      legacyAuditSchemas.Dispatch, DispatchContract));
    migrated.set("editorial-selections", await migrateAuditFixture(
      root, day, run, "editorial-selections",
      "../../../tests/fixtures/contracts/feed-ingest-editorial-selection/one-article.json",
      EditorialSelectionContract.legacyVersions[CONTRACT_VERSION].schema, EditorialSelectionContract));
    migrated.set("rejections", await migrateAuditFixture(
      root, day, run, "rejections",
      "../../../tests/fixtures/contracts/feed-ingest-rejection/empty-feed.json",
      CandidateRejectionContract.legacyVersions[CONTRACT_VERSION].schema, CandidateRejectionContract));
    expect(migrated.get("article-assessments")).toMatchObject({
      timing_basis: "unavailable", timing_at: null, age_hours: null, max_age_hours: null, diagnostics: null,
    });
    expect(migrated.get("diversity")).toMatchObject({ top_k: null });
    expect(migrated.get("editorial-selections")).toMatchObject({
      version: EditorialSelectionContract.schemaVersion, ratings: { source_reliability: null },
    });
    expect(migrated.get("source-runs")).toMatchObject({ date: day, run_id: run });
    const sourceRun = SourceRunRecordSchema.parse(migrated.get("source-runs"));
    const previousSourceRun = SourceRunContract.legacyVersions![PLANNER_EXCLUSIONS_VERSION]!;
    const { publisher_id: _publisherId, ...legacySnapshot } = sourceRun.source;
    const previousRun = previousSourceRun.schema.parse({
      ...sourceRun, version: PLANNER_EXCLUSIONS_VERSION, source: legacySnapshot,
    });
    expect(previousSourceRun.migrate(previousRun).source.publisher_id).toBeNull();
    expect(previousSourceRun.schema.safeParse({
      ...sourceRun, version: PLANNER_EXCLUSIONS_VERSION,
    }).success).toBe(false);
    const originalSource = await Bun.file(new URL(
      "../../../tests/fixtures/contracts/feed-ingest-source-run/one-observation.json", import.meta.url,
    )).json();
    for (const version of ["2026-10-22", "2026-10-22T10:05"]) {
      const previousSource = SourceRunContract.legacyVersions![version]!;
      const previousRow = previousSource.schema.parse({ ...originalSource, version });
      const previousFile = await writeRows(root, "source-runs", day, previousSource.schema,
        [previousRow], writer(run), version);
      const sourceHistory = await readWritten(root, "source-runs", day, SourceRunContract, previousFile);
      expect(sourceHistory.rows[0]!.row).toMatchObject({ version: SourceRunContract.schemaVersion });
      expect(sourceHistory.rows[0]!.row.completion_evidence?.every(entry => entry.logical === null)).toBe(true);
    }
    const { diagnostics: _diagnostics, ...previousAssessment } = ArticleAssessmentRecordSchema.parse(migrated.get("article-assessments"));
    const assessmentSchema = ArticleAssessmentContract.legacyVersions["2026-10-22"].schema;
    const assessmentFile = await writeRows(root, "article-assessments", day, assessmentSchema,
      [assessmentSchema.parse({ ...previousAssessment, version: "2026-10-22" })], writer(run), "2026-10-22");
    const assessmentHistory = await readWritten(root, "article-assessments", day, ArticleAssessmentContract, assessmentFile);
    expect(assessmentHistory.rows[0]!.row.diagnostics).toBeNull();
    const previousRejection = CandidateRejectionContract.schema.parse(migrated.get("rejections"));
    if (previousRejection.drop_reason === "EXTRACT_FAILED" || previousRejection.drop_reason === "EXTRACT_EMPTY"
      || previousRejection.drop_reason === "ALREADY_PUBLISHED" || previousRejection.drop_reason === "SETTLED_FAILURE"
      || previousRejection.drop_reason === "BLOCKED_URL_MARKER") {
      throw new Error("Legacy rejection fixture has a current-only reason");
    }
    const {
      diagnostics: _rejectionDiagnostics, published_on: _publishedOn, failure_code: _failureCode,
      matched_url_marker: _matchedUrlMarker, ...details
    } = previousRejection.details;
    const rejectionSchema = CandidateRejectionContract.legacyVersions["2026-10-22"].schema;
    const rejectionFile = await writeRows(root, "rejections", day, rejectionSchema,
      [{ ...previousRejection, details, version: "2026-10-22" }], writer(run), "2026-10-22");
    const rejectionHistory = await readWritten(root, "rejections", day, CandidateRejectionContract, rejectionFile);
    expect(rejectionHistory.rows[0]!.row.details.diagnostics).toBeNull();
    const priorDiagnostics = PreviousHarvestDiagnosticsSchema.parse({ extract_ms: 2 });
    const priorAssessment = ArticleAssessmentContract.legacyVersions[PLANNER_EXCLUSIONS_VERSION];
    const priorAssessmentRow = { ...previousAssessment, version: PLANNER_EXCLUSIONS_VERSION, diagnostics: priorDiagnostics };
    const priorAssessmentFile = await writeRows(root, "article-assessments", day, priorAssessment.schema,
      [priorAssessmentRow], writer(run), PLANNER_EXCLUSIONS_VERSION);
    const readAssessment = await readWritten(root, "article-assessments", day, ArticleAssessmentContract, priorAssessmentFile);
    expect(readAssessment.rows[0]!.row).toMatchObject({
      version: ArticleAssessmentContract.schemaVersion, diagnostics: { extract_ms: 2, quality: null },
    });
    expect(priorAssessment.schema.safeParse({
      ...priorAssessmentRow, diagnostics: { ...priorDiagnostics, quality: null },
    }).success).toBe(false);
    const priorRejection = CandidateRejectionContract.legacyVersions[PLANNER_EXCLUSIONS_VERSION];
    const priorRejectionFile = await writeRows(root, "rejections", day, priorRejection.schema,
      [{ ...previousRejection, version: PLANNER_EXCLUSIONS_VERSION,
        details: { ...previousRejection.details, diagnostics: priorDiagnostics } }], writer(run), PLANNER_EXCLUSIONS_VERSION);
    const readRejection = await readWritten(root, "rejections", day, CandidateRejectionContract, priorRejectionFile);
    expect(readRejection.rows[0]!.row).toMatchObject({
      version: EXTRACTION_QUALITY_VERSION, details: { diagnostics: { extract_ms: 2, quality: null } },
    });
    expect(migrated.get("dispatches")).toHaveProperty("content");
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("native monthly and yearly precedence reads only the requested day's original rows", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-coarse-periods-"));
  try {
    const input = await fixtureInput(root, { count: 1 });
    const raw = await readWritten(root, "editorial-selections", input.fixture.date, selectionContract, input.persisted.selections);
    const original = raw.rows[0]!;
    const otherDay = "2026-10-20";
    const neighbor = await writeRows(root, "editorial-selections", otherDay, EditorialSelectionRowSchema,
      [{ ...original.row, date: otherDay }], writer(input.fixture.run_id), selectionContract.schemaVersion);
    const neighborRows = await readWritten(root, "editorial-selections", otherDay, selectionContract, neighbor);
    const indexes: Partial<Record<"daily" | "monthly" | "yearly", string>> = {};
    const daily = await compactSelections(root, input, raw.rows, "daily");
    indexes.daily = daily.indexPath;
    for (const period of ["monthly", "yearly"] as const) {
      const compact = await compactSelections(root, input, [...raw.rows, ...neighborRows.rows], period);
      indexes[period] = compact.indexPath;
      const current = await readLedgerDay({
        ledger: "editorial-selections", day: input.fixture.date, contract: selectionContract, indexes,
        rawFiles: input.persisted.selections.files.map(file => join(root, file.path)),
      });
      expect(current.tier).toBe(period);
      expect(current.rows).toEqual([original]);
      expect(current.files[0]!.envelope.identity.attempt).toBe(9);
      expect(current.rows[0]!.identity.attempt).toBe(1);
      expect(current.rows[0]!.identity.shard).toBe(0);
      expect(current.rows[0]!.identity.unit_id).toBe(original.identity.unit_id);
      expect(current.files[0]!.rows).toHaveLength(2);
      expect(current.notices.some(notice => notice.startsWith("overlapping-periods"))).toBe(true);
    }
    const rawName = basename(input.persisted.selections.files[0]!.path);
    const stale = `raw/feed-health/2025/01/01/${rawName}`;
    const recent = `raw/feed-health/2026/02/12/${rawName}`;
    const discovery = resolveHealthInventory({
      ledger: "feed-health", prefix: ["feed-health"], health_window_days: 31,
      inventory: { version: "2026-10-03T13:33", entries: [stale, recent].map(path => ({
        root: "state", path, bytes: 1, items: 0,
      })) },
      compact: {
        yearly: { version: "2026-10-07", ledger: "feed-health", period: "yearly",
          entries: [{ covers: "2025", rows: 1, bytes: 1 }] },
        monthly: { version: "2026-10-07", ledger: "feed-health", period: "monthly",
          entries: [{ covers: "2026-01", rows: 1, bytes: 1 }] },
        daily: { version: "2026-10-07", ledger: "feed-health", period: "daily",
          entries: [{ covers: "2026-02-01", rows: 1, bytes: 1 }] },
      },
    });
    expect(discovery.inputs.map(day => day.day)).toEqual([
      ...Array.from({ length: 29 }, (_, index) => `2026-01-${String(index + 3).padStart(2, "0")}`),
      "2026-02-01", "2026-02-12",
    ]);
    expect(discovery.files).toContain("state/compact/feed-health/monthly/2026/01.parquet");
    expect(discovery.files).toContain(`state/${recent}`);
    expect(discovery.files).not.toContain(`state/${stale}`);
    expect(discovery.inventory_complete).toBe(false);
    for (const inventory of [
      { version: "2099-01-01", entries: [] },
      { version: "2026-10-03T13:33", entries: [{ root: "state", path: "../escaped.parquet", bytes: 1, items: 0 }] },
      { version: "2026-10-03T13:33", entries: [{ root: "state", path: "raw/feed-health/2026/02/12/not-a-uuid.parquet", bytes: 1, items: 0 }] },
    ]) expect(() => resolveHealthInventory({
      ledger: "feed-health", prefix: ["feed-health"], health_window_days: 31, inventory, compact: {},
    })).toThrow();
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("named empty, lost, expired and missing periods never fall through to leftover raw files", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-states-"));
  try {
    const input = await fixtureInput(root, { count: 1 });
    const indexPath = join(root, "compact", "feed-ingest-plan", "editorial-selections", "index", "daily.json");
    await mkdir(dirname(indexPath), { recursive: true });
    const read = () => readLedgerDay({
      ledger: "editorial-selections", day: input.fixture.date, contract: selectionContract,
      indexes: { daily: indexPath }, rawFiles: input.persisted.selections.files.map(file => join(root, file.path)),
    });
    const base = { version: "2026-10-07", ledger: "editorial-selections", period: "daily" };
    for (const state of ["empty", "lost"] as const) {
      await writeFile(indexPath, JSON.stringify({ ...base, entries: [{ covers: input.fixture.date, rows: 0, bytes: 0, state }] }));
      const held = await read();
      expect(held.status).toBe(state);
      expect(held.files).toEqual([]);
    }
    await writeFile(indexPath, JSON.stringify({ ...base, entries: [{ covers: input.fixture.date, rows: 1, bytes: 100, state: "packed" }] }));
    expect((await read()).status).toBe("missing");
    await rm(indexPath);
    expect((await read()).notices).toContain("index-missing:daily");
    expect((await read()).status).toBe("rows");
    expect((await readLedgerDay({ ledger: "editorial-selections", day: input.fixture.date, contract: selectionContract })).status).toBe("missing");
    const expired = join(dirname(indexPath), "yearly.json");
    await writeFile(expired, JSON.stringify({ ...base, period: "yearly", expired_through: "2026", entries: [] }));
    expect((await readLedgerDay({ ledger: "editorial-selections", day: input.fixture.date, contract: selectionContract,
      indexes: { yearly: expired }, rawFiles: input.persisted.selections.files.map(file => join(root, file.path)) })).status).toBe("missing");
    const nativeRaw = `raw/feed-health/${input.fixture.date.replaceAll("-", "/")}/${basename(input.persisted.selections.files[0]!.path)}`;
    for (const state of ["empty", "lost"] as const) {
      const discovery = resolveHealthInventory({
        ledger: "feed-health", prefix: ["feed-health"], health_window_days: 31,
        inventory: { version: "2026-10-03T13:33",
          entries: [{ root: "state", path: nativeRaw, bytes: 1, items: 0 }] },
        compact: { daily: { version: "2026-10-07", ledger: "feed-health", period: "daily",
          entries: [{ covers: input.fixture.date, rows: 0, bytes: 0, state }] } },
      });
      expect(discovery.inputs).toEqual([]);
      expect(discovery.files).not.toContain(`state/${nativeRaw}`);
      expect(discovery.notices).toContain(`feed-inventory:covered-raw-day-unconfirmed:feed-health:${input.fixture.date}`);
    }
    const absent = resolveHealthInventory({
      ledger: "feed-health", prefix: ["feed-health"], health_window_days: 31, inventory: undefined, compact: {},
    });
    expect(absent.inputs).toEqual([]);
    expect(absent.inventory_complete).toBe(false);
    expect(absent.notices).toContain("feed-inventory:publication-inventory-missing:feed-health");
    expect(absent.notices).toContain("feed-inventory:raw-census-unproven:feed-health");
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("one named raw listing verifies its ordered filename digest, sizes and missing-file evidence", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-raw-index-"));
  try {
    const input = await fixtureInput(root, { count: 1 });
    const path = join(root, input.persisted.selections.files[0]!.path);
    const indexPath = join(dirname(path), "index.json");
    const names = [basename(path)];
    const index = {
      version: "2026-10-03", ledger: "editorial-selections", date: input.fixture.date,
      files: names, content_sha256: createHash("sha256").update(names.join("\n")).digest("hex"),
      bytes: [(await stat(path)).size], listed_at: input.fixture.observed_at,
    };
    const read = () => readLedgerDay({ ledger: "editorial-selections", day: input.fixture.date, contract: selectionContract, rawIndex: indexPath });
    await writeFile(indexPath, JSON.stringify(index));
    expect((await read()).rows).toHaveLength(1);
    await writeFile(indexPath, JSON.stringify({ ...index, content_sha256: "0".repeat(64) }));
    await expect(read()).rejects.toThrow("filename digest");
    await writeFile(indexPath, JSON.stringify({ ...index, bytes: [1] }));
    await expect(read()).rejects.toThrow("byte size");
    await writeFile(indexPath, JSON.stringify(index));
    await rm(path);
    expect((await read()).status).toBe("missing");
    await writeFile(indexPath, JSON.stringify({ ...index, files: [], bytes: [], content_sha256: createHash("sha256").update("").digest("hex") }));
    expect((await read()).status).toBe("empty");
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("native digest tampering, wrong ledger, schema, index counts and raw identity are rejected", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-integrity-"));
  try {
    const input = await fixtureInput(root, { count: 1 });
    const file = input.persisted.selections.files[0]!;
    const path = join(root, file.path);
    const raw = await readLedgerParquet(path, "editorial-selections", selectionContract);
    await expect(readLedgerParquet(path, "dispatches", selectionContract)).rejects.toThrow("Parquet ledger");
    await expect(readLedgerParquet(path, "editorial-selections", { ...selectionContract, schemaVersion: "2026-10-19" })).rejects.toThrow("Parquet row schema version");
    const compact = await compactSelections(root, input, raw.rows, "daily");
    await writeFile(compact.indexPath, JSON.stringify({ ...compact.index, entries: [{ ...compact.index.entries[0], rows: 2 }] }));
    await expect(readLedgerDay({ ledger: "editorial-selections", day: input.fixture.date, contract: selectionContract,
      indexes: { daily: compact.indexPath } })).rejects.toThrow("row count or byte size");
    await writeFile(compact.indexPath, JSON.stringify({ ...compact.index, entries: [{ ...compact.index.entries[0], state: "empty", rows: 0, bytes: 0 }] }));
    await expect(readLedgerDay({ ledger: "editorial-selections", day: input.fixture.date, contract: selectionContract,
      indexes: { daily: compact.indexPath } })).rejects.toThrow("declares no file");
    const bytes = await readFile(path);
    const metadata = readMetadata(bytes);
    const footer = metadata.fileMetadata();
    const pairs = new Map<string, string>(footer.keyValueMetadata());
    footer.free();
    metadata.free();
    pairs.set("content_sha256", "0".repeat(64));
    const table = tableFromIPC(readParquet(bytes).intoIPCStream());
    const originalDigest = pairs.get("content_sha256")!;
    await writeFile(path, writeParquet(WasmTable.fromIPCStream(tableToIPC(table, "stream")),
      new WriterPropertiesBuilder().setKeyValueMetadata(pairs).build()));
    await expect(readLedgerParquet(path, "editorial-selections", selectionContract)).rejects.toThrow("content digest");
    pairs.set("content_sha256", originalDigest);
    pairs.set("attempt", "02");
    await writeFile(path, writeParquet(WasmTable.fromIPCStream(tableToIPC(table, "stream")),
      new WriterPropertiesBuilder().setKeyValueMetadata(pairs).build()));
    await expect(readLedgerParquet(path, "editorial-selections", selectionContract)).rejects.toThrow("identifier differs");
    pairs.set("attempt", "01");
    const changedRow = { ...raw.rows[0]!.identity, ...raw.rows[0]!.row, shard: 7 };
    pairs.set("content_sha256", digestRows([changedRow], appendIdentityColumns(describeObjectSchema(EditorialSelectionRowSchema).fields)));
    const changedTable = table.setChild("shard", vectorFromArray([7n], new Int64()));
    await writeFile(path, writeParquet(WasmTable.fromIPCStream(tableToIPC(changedTable, "stream")),
      new WriterPropertiesBuilder().setKeyValueMetadata(pairs).build()));
    await expect(readLedgerParquet(path, "editorial-selections", selectionContract)).rejects.toThrow("Raw row identity");
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("complete original files beat a newer partial retry and replay exact original selected text", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-attempts-"));
  try {
    const { input, source, sourceWritten, history, packed } = await completeHistory(root);
    const complete = selectCompleteAttempt(history);
    expect(complete.selected?.attempt).toBe(1);
    expect(readHistoricalSelections(complete.selected!).map(article => article.content)).toEqual(packed.dispatches.map(row => row.content));
    const partial = await writeRows(root, "source-runs", input.fixture.date, SourceRunRecordSchema,
      [{ ...source(2), expected_source_count: 2 }], writer(input.fixture.run_id, 2), SourceRunContract.schemaVersion);
    const sources = await readWritten(root, "source-runs", input.fixture.date,
      SourceRunContract,
      { status: "written", files: [...sourceWritten.files, ...partial.files] });
    const resolution = selectCompleteAttempt({ ...history, sources });
    expect(resolution.selected?.attempt).toBe(1);
    expect(resolution.findings.find(finding => finding.attempt === 2)?.status).toBe("incomplete");
    const zero = await writeRows(root, "source-runs", input.fixture.date, SourceRunRecordSchema,
      [source(3, true)], writer(input.fixture.run_id, 3), SourceRunContract.schemaVersion);
    const zeroSources = await readWritten(root, "source-runs", input.fixture.date,
      SourceRunContract,
      { status: "written", files: [...sourceWritten.files, ...partial.files, ...zero.files] });
    const empty = selectCompleteAttempt({ ...history, sources: zeroSources });
    expect(empty.selected?.attempt).toBe(3);
    expect(readHistoricalSelections(empty.selected!)).toEqual([]);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("compacted original-file proof is explicitly unverifiable rather than a count-shaped success", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-proof-gap-"));
  try {
    const { input, history } = await completeHistory(root);
    const raw = history.ledgers["editorial-selections"];
    const selections = raw.rows.map(held => ({ identity: held.identity, row: EditorialSelectionRowSchema.parse(held.row) }));
    const compact = await compactSelections(root, input, selections, "monthly");
    const packed = await readLedgerDay({ ledger: "editorial-selections", day: input.fixture.date, contract: selectionContract,
      indexes: { monthly: compact.indexPath } });
    const resolution = selectCompleteAttempt({ ...history, ledgers: { ...history.ledgers, "editorial-selections": packed } });
    expect(packed.rows).toEqual(selections);
    expect(resolution.selected).toBeNull();
    expect(resolution.findings[0]!.status).toBe("unverifiable");
    expect(resolution.findings[0]!.reason).toContain("original raw-file membership");
    const source = history.sources.rows[0]!;
    const altered = SourceRunRecordSchema.parse({
      ...source.row, completion_evidence: source.row.completion_evidence!.map(item => ({
        ...item, files: item.files.map(file => ({ ...file, content_sha256: "0".repeat(64) })),
      })),
    });
    const unproved = selectCompleteAttempt({ ...history, sources: { ...history.sources, rows: [{ ...source, row: altered }] } });
    expect(unproved.selected).toBeNull();
    expect(unproved.findings[0]!.reason).toContain("commitment differs");
  } finally { await rm(root, { recursive: true, force: true }); }
});
