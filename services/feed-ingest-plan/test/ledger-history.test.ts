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
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { PersistLedgerResult } from "@idhazh/ledger-file-writer";
import { tableFromIPC, tableToIPC } from "apache-arrow";
import initializeParquet, {
  Table as WasmTable, WriterPropertiesBuilder, readMetadata, readParquet, writeParquet,
} from "parquet-wasm/esm";
import { plannerRecordings } from "../../../packages/ledger-file-writer/test/planner-recordings";
import { readLedgerParquet } from "../src/read-ledger-history/read-parquet";
import { readLedgerDay } from "../src/read-ledger-history/read-period";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { readPlannerDay } from "../src/read-ledger-history/read-planner-history";
import { readPublisherPublication } from "../src/read-ledger-history/read-publisher-publication";
import { classifyPublicationHistoryError } from "../src/read-ledger-history/classify-publication-history-error";
import { LedgerHistoryReadError } from "../src/read-ledger-history/ledger-history-error";
import { ItemHealthPublicationSchema, PublishedRowSchema, PUBLISHED_ROW_SCHEMA_VERSION } from "../src/metrics/publication-evidence";
import { ITEM_HEALTH_ROW_SCHEMA_VERSION } from "../src/read-ledger-history/item-health-version";
import { compactRows, registration, settings, writer, writeRows } from "./partition-fixtures";
import { fixtureGit } from "./publication-recordings";

const day = "2026-10-20";
const publishedContract = { schema: PublishedRowSchema, schemaVersion: PUBLISHED_ROW_SCHEMA_VERSION };
beforeAll(async () => { await initializeParquet(); });
function selection(date = day, attempt = 1) {
  return SelectedArticleRowSchema.parse(plannerRecordings(date, attempt).find(record => record.name === "selected-articles")!.row);
}
async function commitRaw(root: string, written: PersistLedgerResult) {
  const repository = dirname(root);
  await fixtureGit(repository, ["init", "--initial-branch=main"]);
  await fixtureGit(repository, ["add", "--", ...written.files.map(file => `state/${file.path}`)]);
  await fixtureGit(repository, ["commit", "--allow-empty", "-m", "Record native fixture members"]);
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
}, 30_000);

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

test("native monthly and yearly precedence reads only the requested day's original rows", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-coarse-periods-"));
  try {
    const original = selection();
    const neighbor = selection("2026-10-19");
    const daily = await compactRows(root, "selected-articles", day, SelectedArticleRowContract, [original], "daily");
    const indexes: Partial<Record<"daily" | "monthly" | "yearly", string>> = { daily: daily.indexPath };
    for (const period of ["monthly", "yearly"] as const) {
      const compact = await compactRows(root, "selected-articles", day, SelectedArticleRowContract, [original, neighbor], period);
      indexes[period] = compact.indexPath;
      const current = await readPlannerDay(root, registration("selected-articles"), { day, indexes, raw_files: [] }, SelectedArticleRowContract);
      expect(current.complete).toBe(true);
      expect(current.represented).toBe(true);
      expect(current.rows).toEqual([original]);
      const quiet = await readPlannerDay(root, registration("selected-articles"), {
        day: "2026-10-18", indexes, raw_files: [],
      }, SelectedArticleRowContract);
      expect(quiet).toMatchObject({ complete: true, represented: true, rows: [] });
      const native = await readPlannerParquet(compact.path!, "selected-articles", SelectedArticleRowContract);
      expect(native.rows).toHaveLength(2);
      expect(native.rows.every(row => !("unit_id" in row) && !("article_text" in row))).toBe(true);
    }
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("named empty, lost, expired and missing periods preserve each family's completeness rules", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-states-"));
  try {
    const original = selection();
    const raw = await writeRows(root, "selected-articles", day, SelectedArticleRowContract, [original]);
    const indexPath = join(root, "compact", "feed-ingest-plan", "selected-articles", "index", "daily.json");
    await mkdir(dirname(indexPath), { recursive: true });
    const read = () => readPlannerDay(root, registration("selected-articles"), {
      day, indexes: { daily: indexPath }, raw_files: raw.files.map(file => file.path),
    }, SelectedArticleRowContract);
    for (const state of ["empty", "lost"] as const) {
      await writeFile(indexPath, JSON.stringify({
        version: COMPACT_INDEX_VERSION, ledger: "selected-articles", period: "daily",
        entries: [{ covers: day, rows: 0, bytes: 0, state }],
      }));
      const held = await read();
      expect(held.rows).toEqual([original]);
      expect(held.complete).toBe(state === "empty");
      expect(held.represented).toBe(true);
      const quiet = await readPlannerDay(root, registration("selected-articles"), {
        day, indexes: { daily: indexPath }, raw_files: [],
      }, SelectedArticleRowContract);
      expect(quiet).toMatchObject({ complete: state === "empty", represented: false, rows: [] });
    }
    await writeFile(indexPath, JSON.stringify({
      version: COMPACT_INDEX_VERSION, ledger: "selected-articles", period: "daily",
      entries: [{ covers: day, rows: 1, bytes: 100, state: "packed" }],
    }));
    expect((await read()).complete).toBe(false);
    expect((await read()).rows).toEqual([original]);
    await rm(indexPath);
    expect((await read()).complete).toBe(true);
    expect((await readPlannerDay(root, registration("selected-articles"), { day }, SelectedArticleRowContract)).complete).toBe(false);

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
});

test("explicit completed files retain integrity and genuine publications require an unambiguous publisher join", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-raw-index-"));
  try {
    const written = await writeRows(root, "selected-articles", day, SelectedArticleRowContract, [selection()]);
    const read = () => readPlannerDay(root, registration("selected-articles"), {
      day, raw_files: written.files.map(file => file.path),
    }, SelectedArticleRowContract);
    expect((await read()).rows).toEqual([selection()]);
    await rm(join(root, written.files[0]!.path));
    const missing = await read();
    expect(missing.complete).toBe(false);
    expect(missing.rows).toEqual([]);
    const empty = await readPlannerDay(root, registration("selected-articles"), { day, raw_files: [] }, SelectedArticleRowContract);
    expect(empty.complete).toBe(true);
    expect(empty.represented).toBe(false);
    expect(empty.rows).toEqual([]);

    const publisherRoot = join(root, "publisher");
    const stateRoot = join(publisherRoot, "state");
    const selected = { ...selection(), publisher_id: "recorded-publisher" };
    const writerIdentity = writer(selected.run_id);
    const identity = { date: day, run_id: selected.run_id, item_id: "recorded-item-01",
      url_key: selected.url_key, source_id: selected.feed_id, stage: "publish" as const, outcome: "ok" as const };
    const healthContract = { schema: ItemHealthPublicationSchema, schemaVersion: ITEM_HEALTH_ROW_SCHEMA_VERSION };
    const health = await writeRows(stateRoot, "item-health", day, healthContract,
      [identity, identity, { ...identity, stage: "extract" }], writerIdentity);
    const publication = await writeRows(stateRoot, "published", day, publishedContract,
      [{ version: PUBLISHED_ROW_SCHEMA_VERSION, published_on: day, url_key: selected.url_key, item_id: identity.item_id }], writerIdentity);
    const snapshots = await writeRows(stateRoot, "selected-articles", day, SelectedArticleRowContract, [selected]);
    await commitRaw(stateRoot, snapshots);
    const localFiles = (written: PersistLedgerResult) => written.files.map(file => `state/${file.path}`);
    const request = {
      root: publisherRoot, day, published: registration("published"), item_health: registration("item-health"),
      selections: registration("selected-articles"),
      published_days: [{ day, raw_files: localFiles(publication) }], health_days: [{ day, raw_files: localFiles(health) }],
    };
    const counted = await readPublisherPublication(request);
    expect(counted.availability).toBe("available");
    expect(counted.counts.get("recorded-publisher")).toBe(1);
    expect(counted.gaps).toEqual([]);
    const notPublished = await readPublisherPublication({ ...request, published_days: [{ day, raw_files: [] }] });
    expect(notPublished.availability).toBe("available");
    expect(notPublished.counts.size).toBe(0);
    const compact = await compactRows(stateRoot, "selected-articles", day, SelectedArticleRowContract, [selected], "daily");
    expect((await readPublisherPublication(request)).counts).toEqual(counted.counts);
    await rm(compact.path!);
    await writeFile(compact.indexPath, JSON.stringify({
      ...compact.index, entries: [{ covers: day, rows: 0, bytes: 0, state: "lost" }],
    }));
    expect((await readPublisherPublication(request)).availability).toBe("unavailable");
    await rm(compact.indexPath);

    for (const row of [
      { ...selected, run_id: `${day}-999999` },
      { ...selected, publisher_id: null },
    ]) {
      const changed = await writeRows(stateRoot, "selected-articles", day, SelectedArticleRowContract, [row]);
      await commitRaw(stateRoot, changed);
      // Earlier committed siblings remain visible; a later snapshot cannot hide them.
      expect((await readPublisherPublication(request)).availability).toBe(row.publisher_id === null ? "unavailable" : "available");
    }
    const changedPublisher = await writeRows(stateRoot, "selected-articles", day, SelectedArticleRowContract,
      [{ ...selected, attempt: 2, publisher_id: "conflicting-publisher" }]);
    await commitRaw(stateRoot, { status: "written", files: [...snapshots.files, ...changedPublisher.files] });
    const ambiguous = await readPublisherPublication(request);
    expect(ambiguous.availability).toBe("unavailable");
    expect(ambiguous.counts.size).toBe(0);
    const extraOwner = await writeRows(stateRoot, "item-health", day, healthContract,
      [{ ...identity, run_id: `${day}-2` }], writer(`${day}-2`));
    const ownerGap = await readPublisherPublication({
      ...request, health_days: [{ day, raw_files: [...localFiles(health), ...localFiles(extraOwner)] }],
    });
    expect(ownerGap.gaps).toContain("publication_owner_unavailable");

    const invalidIndex = join(publisherRoot, "invalid-publication-index.json");
    for (const contents of ["{", JSON.stringify({ version: "not-a-version" })]) {
      await writeFile(invalidIndex, contents);
      const invalid = await readPublisherPublication({
        ...request, published_days: [{ day, raw_index: "invalid-publication-index.json" }],
      });
      expect(invalid.availability).toBe("unavailable");
      expect(invalid.counts.size).toBe(0);
      expect(invalid.gaps).toEqual(["invalid_publication_history"]);
    }
    for (const error of [new TypeError("programming error"), new Error("programming error"), new SyntaxError("programming error"), "not an error"]) {
      expect(classifyPublicationHistoryError(error)).toBeNull();
    }
    expect(classifyPublicationHistoryError(new LedgerHistoryReadError("integrity diagnostic"))).toBe("integrity diagnostic");
    for (const bytes of [new Uint8Array([1, 2, 3]), new Uint8Array(20)]) {
      await writeFile(join(stateRoot, publication.files[0]!.path), bytes);
      await expect(readLedgerDay({ ledger: "published", day, contract: publishedContract,
        rawFiles: publication.files.map(file => join(stateRoot, file.path)) })).rejects.toThrow();
      const corrupt = await readPublisherPublication(request);
      expect(corrupt.availability).toBe("unavailable");
      expect(corrupt.counts.size).toBe(0);
      expect(corrupt.gaps).toEqual(["invalid_publication_history"]);
    }
  } finally { await rm(root, { recursive: true, force: true }); }
}, 60_000);

test("native digest tampering, wrong ledger, schema, index counts and undeclared planner identity are rejected", async () => {
  const root = await mkdtemp(join(tmpdir(), "history-integrity-"));
  try {
    const written = await writeRows(root, "selected-articles", day, SelectedArticleRowContract, [selection()]);
    const path = join(root, written.files[0]!.path);
    await expect(readPlannerParquet(path, "plan-runs", SelectedArticleRowContract)).rejects.toThrow("current ledger contract");
    await expect(readPlannerParquet(path, "selected-articles", { ...SelectedArticleRowContract, schemaVersion: "2026-10-24" }))
      .rejects.toThrow("current ledger contract");
    const compact = await compactRows(root, "selected-articles", day, SelectedArticleRowContract, [selection()], "daily");
    for (const patch of [{ rows: 2 }, { bytes: 1 }, { file_sha256: "0".repeat(64) }]) {
      await writeFile(compact.indexPath, JSON.stringify({
        ...compact.index, entries: [{ ...compact.index.entries[0], ...patch }],
      }));
      const refused = await readPlannerDay(root, registration("selected-articles"), {
        day, indexes: { daily: compact.indexPath },
      }, SelectedArticleRowContract);
      expect(refused.complete).toBe(false);
      expect(refused.rows).toEqual([]);
      expect(refused.gaps.length).toBeGreaterThan(0);
    }
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
      .rejects.toThrow("unsupported row schema");
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
