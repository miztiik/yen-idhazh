/** Does named native history retain original identities and distinguish proof from missing evidence? */
import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join } from "node:path";
import {
  ArticleAssessmentRecordSchema, CandidateRejectionRecordSchema, CONTRACT_VERSION,
  DiversityMetricRowSchema, EditorialSelectionRowSchema, FeedIngestDispatchSchema, SourceRunRecordSchema,
} from "@idhazh/common-contracts";
import type { LedgerCompletionEvidence } from "@idhazh/common-contracts";
import { appendIdentityColumns, describeObjectSchema, digestRows, persistLedger } from "@idhazh/ledger-file-writer";
import type { PersistLedgerResult, StoredLedgerRow } from "@idhazh/ledger-file-writer";
import { Int64, tableFromIPC, vectorFromArray } from "apache-arrow";
import { Table as WasmTable, WriterPropertiesBuilder, readMetadata, readParquet, writeParquet } from "parquet-wasm/esm";
import { tableToIPC } from "apache-arrow";
import { readLedgerParquet } from "../src/read-ledger-history/read-parquet";
import { readLedgerDay } from "../src/read-ledger-history/read-period";
import { selectCompleteAttempt } from "../src/read-ledger-history/complete-attempt";
import type { AttemptHistory } from "../src/read-ledger-history/complete-attempt";
import { readHistoricalSelections } from "../src/partition-article-shards/read-editorial-selection";
import { partitionArticles, persistDispatches } from "../src/partition-article-shards/shard-packer";
import { fixtureInput, readWritten, registration, settings, writer, writeRows } from "./partition-fixtures";

const selectionContract = { schema: EditorialSelectionRowSchema, schemaVersion: CONTRACT_VERSION };
function evidence(ledger: LedgerCompletionEvidence["ledger"], written: PersistLedgerResult): LedgerCompletionEvidence {
  if (written.status === "skipped") throw new Error("Fixture completion ledger was skipped");
  return {
    ledger, row_count: written.files.reduce((count, file) => count + file.row_count, 0),
    files: written.files.map(({ file_id, content_sha256, row_count }) => ({ file_id, content_sha256, row_count })),
  };
}
async function completeHistory(root: string) {
  const input = await fixtureInput(root, { count: 1 });
  const packed = partitionArticles({
    selections: input.curation.rows, candidates: input.candidates,
    context: input.context, settings: input.planning.config.partition,
  });
  const dispatch = await persistDispatches(packed, {
    outputRoot: root, writerContext: writer(input.fixture.run_id), ledgerSettings: settings,
    registration: registration("dispatches"), date: input.fixture.date,
  });
  const assessments = await writeRows(root, "article-assessments", input.fixture.date,
    ArticleAssessmentRecordSchema, input.curation.assessments, writer(input.fixture.run_id));
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
    observed_at: input.fixture.observed_at, expected_source_count: 1,
    completion_evidence: zero ? completion.map(item => ({ ...item, row_count: 0, files: [] })) : completion,
  });
  const sourceWritten = await writeRows(root, "source-runs", input.fixture.date,
    SourceRunRecordSchema, [source()], writer(input.fixture.run_id));
  const sources = await readWritten(root, "source-runs", input.fixture.date,
    { schema: SourceRunRecordSchema, schemaVersion: CONTRACT_VERSION }, sourceWritten);
  const ledgers: AttemptHistory["ledgers"] = {
    "editorial-selections": await readWritten(root, "editorial-selections", input.fixture.date, selectionContract, input.persisted.selections),
    dispatches: await readWritten(root, "dispatches", input.fixture.date, { schema: FeedIngestDispatchSchema, schemaVersion: CONTRACT_VERSION }, dispatch),
    "article-assessments": await readWritten(root, "article-assessments", input.fixture.date, { schema: ArticleAssessmentRecordSchema, schemaVersion: CONTRACT_VERSION }, assessments),
    rejections: await readWritten(root, "rejections", input.fixture.date, { schema: CandidateRejectionRecordSchema, schemaVersion: CONTRACT_VERSION }, empty),
    diversity: await readWritten(root, "diversity", input.fixture.date, { schema: DiversityMetricRowSchema, schemaVersion: CONTRACT_VERSION }, empty),
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

test("raw, daily, monthly and yearly native reads preserve original row identity and coarser precedence", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-periods-"));
  try {
    const input = await fixtureInput(root, { count: 1 });
    const raw = await readWritten(root, "editorial-selections", input.fixture.date, selectionContract, input.persisted.selections);
    const indexes: Partial<Record<"daily" | "monthly" | "yearly", string>> = {};
    expect(raw.tier).toBe("raw");
    expect(raw.rows).toHaveLength(1);
    const original = raw.rows[0]!;
    for (const period of ["daily", "monthly", "yearly"] as const) {
      const compact = await compactSelections(root, input, raw.rows, period);
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
      if (period !== "daily") expect(current.notices.some(notice => notice.startsWith("overlapping-periods"))).toBe(true);
    }
    const otherDay = "2026-10-20";
    const neighbor = await writeRows(root, "editorial-selections", otherDay, EditorialSelectionRowSchema,
      [{ ...original.row, date: otherDay }], writer(input.fixture.run_id));
    const neighborRows = await readWritten(root, "editorial-selections", otherDay, selectionContract, neighbor);
    const compact = await compactSelections(root, input, [...raw.rows, ...neighborRows.rows], "monthly");
    const onlyRequested = await readLedgerDay({
      ledger: "editorial-selections", day: input.fixture.date, contract: selectionContract, indexes: { monthly: compact.indexPath },
    });
    expect(onlyRequested.files[0]!.rows).toHaveLength(2);
    expect(onlyRequested.rows).toEqual([original]);
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
    await expect(readLedgerParquet(path, "dispatches", selectionContract)).rejects.toThrow("ledger or row schema");
    await expect(readLedgerParquet(path, "editorial-selections", { ...selectionContract, schemaVersion: "2026-10-19" })).rejects.toThrow("ledger or row schema");
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
      [{ ...source(2), expected_source_count: 2 }], writer(input.fixture.run_id, 2));
    const sources = await readWritten(root, "source-runs", input.fixture.date,
      { schema: SourceRunRecordSchema, schemaVersion: CONTRACT_VERSION },
      { status: "written", files: [...sourceWritten.files, ...partial.files] });
    const resolution = selectCompleteAttempt({ ...history, sources });
    expect(resolution.selected?.attempt).toBe(1);
    expect(resolution.findings.find(finding => finding.attempt === 2)?.status).toBe("incomplete");
    const zero = await writeRows(root, "source-runs", input.fixture.date, SourceRunRecordSchema, [source(3, true)], writer(input.fixture.run_id, 3));
    const zeroSources = await readWritten(root, "source-runs", input.fixture.date,
      { schema: SourceRunRecordSchema, schemaVersion: CONTRACT_VERSION },
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
