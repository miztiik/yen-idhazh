/** Verify named current planner history without weakening the other families' native protocol. */
import { beforeAll, expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { mkdtemp, mkdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import {
  COMPACT_INDEX_VERSION, PlanRunRowContract, SelectedArticleRowContract,
  SelectedArticleRowSchema,
} from "@idhazh/common-contracts";
import { persistLedger, PlannerUnsupportedFormatError } from "@idhazh/ledger-file-writer";
import { tableFromIPC, tableToIPC } from "apache-arrow";
import initializeParquet, {
  Table as WasmTable, WriterPropertiesBuilder, readMetadata, readParquet, writeParquet,
} from "parquet-wasm/esm";
import { plannerRecordings } from "../../../packages/ledger-file-writer/test/planner-recordings";
import { readLedgerParquet } from "../src/read-ledger-history/read-parquet";
import { readLedgerDay } from "../src/read-ledger-history/read-period";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { readPlannerDay } from "../src/read-ledger-history/read-planner-history";
import { PublishedRowSchema, PUBLISHED_ROW_SCHEMA_VERSION } from "../src/metrics/publication-evidence";
import {
  compactRows, registration, settings, writer, writeRows,
} from "./partition-fixtures";

const day = "2026-10-20";
const publishedContract = { schema: PublishedRowSchema, schemaVersion: PUBLISHED_ROW_SCHEMA_VERSION };
beforeAll(async () => { await initializeParquet(); });
function selection(date = day, attempt = 1) {
  return SelectedArticleRowSchema.parse(plannerRecordings(date, attempt).find(record => record.name === "selected-articles")!.row);
}
test("native raw and daily reads preserve another family's original writer identity", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-other-family-"));
  try {
    const row = PublishedRowSchema.parse({
      version: PUBLISHED_ROW_SCHEMA_VERSION, url_key: selection().url_key, published_on: day, item_id: "recorded-item-01",
    });
    const writerIdentity = writer(`${day}-1`, 1, 3);
    const request = {
      ledger: "published", registryEntry: registration("published"), outputRoot: root,
      ledgerSettings: settings, rowContract: publishedContract, period: { tier: "raw" as const, covers: day }, rows: [row],
    };
    await expect(persistLedger(request)).rejects.toThrow();
    const raw = await persistLedger({ ...request, writerContext: writerIdentity });
    const path = join(root, raw.files[0]!.path);
    const original = await readLedgerParquet(path, "published", publishedContract);
    expect(original.rows[0]!.identity).toMatchObject({ attempt: 1, shard: 3, run_id: writerIdentity.run_id, unit_id: raw.files[0]!.unit_id });
    const compact = await persistLedger({
      ...request, writerContext: { ...writerIdentity, attempt: 9, producer: "tests.compactor" },
      period: { tier: "compact", period: "daily", covers: day, builtFrom: 1 }, rows: original.rows,
    });
    const indexPath = join(root, "compact", "published", "index", "daily.json");
    await mkdir(dirname(indexPath), { recursive: true });
    await writeFile(indexPath, JSON.stringify({
      version: COMPACT_INDEX_VERSION, ledger: "published", period: "daily", entries: [{
        covers: day, rows: 1, bytes: (await stat(join(root, compact.files[0]!.path))).size, state: "packed",
      }],
    }));
    const reopened = await readLedgerDay({ ledger: "published", day, contract: publishedContract,
      indexes: { daily: indexPath }, rawFiles: [path] });
    expect(reopened.rows).toEqual(original.rows);
    expect(reopened.files[0]!.envelope.identity.attempt).toBe(9);
    expect(reopened.rows[0]!.identity.attempt).toBe(1);
    const bytes = await readFile(path);
    const metadata = readMetadata(bytes);
    const footer = metadata.fileMetadata();
    const pairs = new Map<string, string>(footer.keyValueMetadata());
    footer.free(); metadata.free();
    const table = tableFromIPC(readParquet(bytes).intoIPCStream()).select(
      tableFromIPC(readParquet(bytes).intoIPCStream()).schema.fields.map(field => field.name).filter(name => name !== "unit_id"),
    );
    await writeFile(path, writeParquet(WasmTable.fromIPCStream(tableToIPC(table, "stream")),
      new WriterPropertiesBuilder().setKeyValueMetadata(pairs).build()));
    await expect(readLedgerParquet(path, "published", publishedContract)).rejects.toThrow();
    const planner = await writeRows(root, "selected-articles", day, SelectedArticleRowContract, [selection()]);
    const current = await readPlannerParquet(join(root, planner.files[0]!.path), "selected-articles", SelectedArticleRowContract);
    expect(current.rows).toEqual([selection()]);
    expect(current.envelope).not.toHaveProperty("identity");
    await expect(readLedgerParquet(join(root, planner.files[0]!.path), "selected-articles", SelectedArticleRowContract)).rejects.toThrow();
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("plan completion observed after midnight stays in its original run-day partition", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-late-plan-"));
  try {
    const row = PlanRunRowContract.schema.parse({
      ...plannerRecordings(day).find(record => record.name === "plan-runs")!.row,
      started_at: `${day}T23:59:59.999Z`, evaluated_at: "2026-10-21T00:00:00Z",
      selection_started_at_utc: "2026-10-21T00:00:00Z", duration_ms: 1000,
    });
    const written = await writeRows(root, "plan-runs", day, PlanRunRowContract, [row]);
    const held = await readPlannerParquet(join(root, written.files[0]!.path), "plan-runs", PlanRunRowContract);
    expect(held.envelope.covers).toBe(day);
    expect(held.rows).toEqual([row]);
    expect(held.rows[0]!.date).not.toBe(held.rows[0]!.evaluated_at.slice(0, 10));
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("native compact precedence reads only the requested day's original rows", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-coarse-periods-"));
  try {
    const neighbor = selection("2026-10-19");
    for (const period of ["daily", "monthly", "yearly"] as const) {
      const periodRoot = join(root, period);
      const stateRoot = join(periodRoot, "state");
      const row = selection(day, period === "yearly" ? 3 : period === "monthly" ? 2 : 1);
      const compact = await compactRows(stateRoot, "selected-articles", day, SelectedArticleRowContract,
        period === "daily" ? [row] : [row, neighbor], period);
      const input = { day, raw_files: [] };
      const current = await readPlannerDay(periodRoot, registration("selected-articles"), input, SelectedArticleRowContract);
      expect(current.complete).toBe(true);
      expect(current.represented).toBe(true);
      expect(current.rows).toEqual([row]);
      if (period !== "daily") {
        const quiet = await readPlannerDay(periodRoot, registration("selected-articles"), {
          ...input, day: "2026-10-18",
        }, SelectedArticleRowContract);
        expect(quiet).toMatchObject({ complete: true, represented: true, rows: [] });
      }
      const native = await readPlannerParquet(compact.path!, "selected-articles", SelectedArticleRowContract);
      expect(native.rows).toHaveLength(period === "daily" ? 1 : 2);
      expect(native.rows.every(row => !("unit_id" in row) && !("article_text" in row))).toBe(true);
    }
  } finally { await rm(root, { recursive: true, force: true }); }
}, 30_000);

test("planner compact members keep native validation and never fall through on a named gap", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-states-"));
  try {
    const original = selection();
    const compact = await compactRows(join(root, "state"), "selected-articles", day,
      SelectedArticleRowContract, [original], "daily");
    const path = compact.path!;
    const read = (requestedDay = day) => readPlannerDay(root, registration("selected-articles"), {
      day: requestedDay, ...(requestedDay === "2026-10-19" ? { raw_files: [] } : {}),
    }, SelectedArticleRowContract);
    expect(await read()).toMatchObject({ complete: true, represented: true, rows: [original] });
    const empty = await compactRows(join(root, "state"), "selected-articles", "2026-10-19",
      SelectedArticleRowContract, [], "daily");
    expect(empty.path).toBeUndefined();
    expect(await read("2026-10-19")).toMatchObject({ complete: true, represented: false, rows: [] });

    const saved = await readFile(path);
    await writeFile(path, new Uint8Array([1, 2, 3]));
    const refused = await read();
    expect(refused.complete).toBe(false);
    expect(refused.rows).toEqual([]);
    await writeFile(path, saved);
    await rm(path);
    expect(await read()).toMatchObject({ complete: true, represented: false, rows: [] });

    const publication = await writeRows(root, "published", day, publishedContract, [{
      version: PUBLISHED_ROW_SCHEMA_VERSION, url_key: original.url_key, published_on: day, item_id: "recorded-item-01",
    }], writer(`${day}-1`));
    const externalIndex = join(root, "compact", "published", "index", "daily.json");
    await mkdir(dirname(externalIndex), { recursive: true });
    for (const state of ["empty", "lost"] as const) {
      await writeFile(externalIndex, JSON.stringify({
        version: COMPACT_INDEX_VERSION, ledger: "published", period: "daily",
        entries: [{ covers: day, rows: 0, bytes: 0, state }],
      }));
      const held = await readLedgerDay({
        ledger: "published", day, contract: publishedContract, indexes: { daily: externalIndex },
        rawFiles: publication.files.map(file => join(root, file.path)),
      });
      expect(held.status).toBe(state);
      expect(held.rows).toEqual([]);
    }
    const expired = join(dirname(externalIndex), "yearly.json");
    await writeFile(expired, JSON.stringify({
      version: COMPACT_INDEX_VERSION, ledger: "published", period: "yearly", expired_through: "2026", entries: [],
    }));
    expect((await readLedgerDay({ ledger: "published", day, contract: publishedContract,
      indexes: { yearly: expired }, rawFiles: publication.files.map(file => join(root, file.path)) })).status).toBe("missing");
  } finally { await rm(root, { recursive: true, force: true }); }
}, 30_000);

test("explicit completed files distinguish missing membership from an explicitly empty day", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-raw-index-"));
  try {
    const written = await writeRows(join(root, "state"), "selected-articles", day, SelectedArticleRowContract, [selection()]);
    const read = () => readPlannerDay(root, registration("selected-articles"), {
      day, raw_files: written.files.map(file => `state/${file.path}`),
    }, SelectedArticleRowContract);
    expect((await read()).rows).toEqual([selection()]);
    await rm(join(root, "state", written.files[0]!.path));
    const missing = await read();
    expect(missing.complete).toBe(false);
    expect(missing.rows).toEqual([]);
    const empty = await readPlannerDay(root, registration("selected-articles"), { day, raw_files: [] }, SelectedArticleRowContract);
    expect(empty.complete).toBe(true);
    expect(empty.represented).toBe(false);
    expect(empty.rows).toEqual([]);

  } finally { await rm(root, { recursive: true, force: true }); }
}, 60_000);

test("the surviving publication reader refuses genuine corrupt publication bytes", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-publication-integrity-"));
  try {
    const publication = await writeRows(root, "published", day, publishedContract,
      [{ version: PUBLISHED_ROW_SCHEMA_VERSION, published_on: day, url_key: selection().url_key, item_id: "recorded-item-01" }],
      writer(`${day}-1`));
    const input: Parameters<typeof readLedgerDay>[0] = { ledger: "published", day, contract: publishedContract,
      rawFiles: publication.files.map(file => join(root, file.path)) };
    expect((await readLedgerDay(input)).rows).toHaveLength(1);
    for (const bytes of [new Uint8Array([1, 2, 3]), new Uint8Array(20)]) {
      await writeFile(join(root, publication.files[0]!.path), bytes);
      await expect(readLedgerDay(input)).rejects.toThrow();
    }
  } finally { await rm(root, { recursive: true, force: true }); }
}, 60_000);

test("native digest tampering, wrong ledger, schema and undeclared planner identity are rejected", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-integrity-"));
  try {
    const written = await writeRows(root, "selected-articles", day, SelectedArticleRowContract, [selection()]);
    const path = join(root, written.files[0]!.path);
    await expect(readPlannerParquet(path, "plan-runs", SelectedArticleRowContract)).rejects.toThrow();
    await expect(readPlannerParquet(path, "selected-articles", {
      ...SelectedArticleRowContract, schemaVersion: "2026-10-24", acceptedSchemaVersions: ["2026-10-24"],
    }))
      .rejects.toThrow("current row schema");
    const compact = await compactRows(join(root, "state"), "selected-articles", day,
      SelectedArticleRowContract, [selection()], "daily");
    const compactPath = compact.path!;
    const compactBytes = await readFile(compactPath);
    await writeFile(compactPath, new Uint8Array([1, 2, 3]));
    const refused = await readPlannerDay(root, registration("selected-articles"), {
      day,
    }, SelectedArticleRowContract);
    expect(refused.complete).toBe(false);
    expect(refused.rows).toEqual([]);
    expect(refused.gaps.length).toBeGreaterThan(0);
    await writeFile(compactPath, compactBytes);
    const bytes = await readFile(path);
    const renamed = join(dirname(path), `${randomUUID()}.parquet`);
    await writeFile(renamed, bytes);
    await expect(readPlannerParquet(renamed, "selected-articles", SelectedArticleRowContract)).rejects.toThrow("filename");
    const metadata = readMetadata(bytes);
    const footer = metadata.fileMetadata();
    const pairs = new Map<string, string>(footer.keyValueMetadata());
    footer.free(); metadata.free();
    const table = tableFromIPC(readParquet(bytes).intoIPCStream());
    const rewrite = (values: Map<string, string>) => writeFile(path,
      writeParquet(WasmTable.fromIPCStream(tableToIPC(table, "stream")),
        new WriterPropertiesBuilder().setKeyValueMetadata(values).build()));
    await rewrite(new Map([...pairs, ["schema_version", "2026-10-25"]]));
    await expect(readPlannerParquet(path, "selected-articles", SelectedArticleRowContract))
      .rejects.toBeInstanceOf(PlannerUnsupportedFormatError);
    await rewrite(pairs);
    await rewrite(new Map([...pairs, ["content_sha256", "0".repeat(64)]]));
    await expect(readPlannerParquet(path, "selected-articles", SelectedArticleRowContract)).rejects.toThrow("digest");
    for (const key of ["unit_id", "git_sha", "written_at_ms", "built_from"]) {
      await rewrite(new Map([...pairs, [key, "undeclared"]]));
      await expect(readPlannerParquet(path, "selected-articles", SelectedArticleRowContract)).rejects.toThrow("undeclared");
    }
    const missing = new Map(pairs);
    missing.delete("schema_version");
    await rewrite(missing);
    await expect(readPlannerParquet(path, "selected-articles", SelectedArticleRowContract)).rejects.toThrow("missing schema_version");
  } finally { await rm(root, { recursive: true, force: true }); }
}, 30_000);
