/** Refused planner formats become explicit unavailable publication coverage, not current data. */
import { expect, test } from "bun:test";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { tableFromIPC } from "apache-arrow";
import initialize, { readMetadata, readParquet } from "parquet-wasm/esm";
import { CompactIndexSchema } from "@idhazh/common-contracts";
import { persistLedger } from "../src";
import { selectPlannerPublication } from "../src/planner-publication";
import { plannerRecordings } from "./planner-recordings";
import { serializeParquet } from "../src/parquet/wasm-serializer";
import { projectPlannerPublication } from "../../../frontend/scripts/planner-publication.mjs";

test("real old Parquet is retained while daily, monthly and yearly publication exposes no trusted rows", async () => {
  const { filesFor, newestFile } = await import(pathToFileURL(resolve("..", "..", "frontend", "src", "lib", "data", "slice.ts")).href);
  const root = await mkdtemp(join(tmpdir(), "planner-publication-"));
  try {
    await initialize();
    const record = plannerRecordings()[0]!;
    const files: { ledger: "discovered-articles"; path: string }[] = [];
    const indexes: Record<string, ReturnType<typeof CompactIndexSchema.parse>> = {};
    const originals = new Map<string, Uint8Array>();
    for (const period of ["daily", "monthly", "yearly"] as const) {
      const covers = period === "daily" ? "2026-10-20" : period === "monthly" ? "2026-10" : "2026";
      const result = await persistLedger({
        ledger: record.name, rowContract: record.contract, rows: [record.row], outputRoot: root,
        registryEntry: { name: record.name, family: "feed-ingest-plan", grain: "raw-and-compact",
          lifecycle_status: "active", prefix: ["feed-ingest-plan", record.name] },
        ledgerSettings: { format: "parquet", compression_raw: "snappy", compression_compact: "snappy" },
        period: { tier: "compact", period, covers, builtFrom: 1 },
      });
      const path = result.files[0]!.path;
      const bytes = await readFile(join(root, path));
      const metadata = readMetadata(bytes);
      const footer = metadata.fileMetadata();
      try {
        const values = new Map(footer.keyValueMetadata());
        values.set("envelope_version", "2026-10-29");
        values.set("schema_version", "2026-10-25");
        const old = (await serializeParquet(tableFromIPC(readParquet(bytes).intoIPCStream()), values, "snappy")).data;
        await writeFile(join(root, path), old);
      } finally { footer.free(); metadata.free(); }
      originals.set(path, await readFile(join(root, path)));
      files.push({ ledger: "discovered-articles", path });
      indexes[`compact/feed-ingest-plan/discovered-articles/index/${period}.json`] = CompactIndexSchema.parse({
        version: "2026-10-25", ledger: "discovered-articles", period,
        entries: [{ covers, rows: 1, bytes: bytes.length, state: "packed" }],
      });
    }
    const request = { files, indexes };
    const before = JSON.stringify(request);
    const result = await selectPlannerPublication(root, request);
    expect(result.files).toEqual([]);
    expect(result.refused).toHaveLength(3);
    for (const index of Object.values(result.indexes)) {
      const entry = index.entries[0]!;
      if (index.period === "daily") expect(entry).toMatchObject({ state: "lost", rows: 0, bytes: 0, file_sha256: null });
      else {
        expect(entry).toMatchObject({ state: "empty", rows: 0, bytes: 0, file_sha256: null });
        expect(entry.lost_days).toHaveLength(index.period === "monthly" ? 31 : 365);
        expect(entry.set_aside).toBe(1);
      }
      const entries = index.entries.map(({ file_sha256, ...entry }) => ({
        ...entry, ...(file_sha256 === undefined ? {} : { file_sha256 }),
      }));
      const selection = filesFor("2026-10-20", "2026-10-20",
        index.period === "daily" ? entries : [], index.period === "monthly" ? entries : [],
        index.period === "yearly" ? entries : []);
      expect(selection).toMatchObject({ files: [], lostDays: ["2026-10-20"] });
      expect(newestFile(index.period === "daily" ? entries : [], index.period === "monthly" ? entries : [],
        index.period === "yearly" ? entries : [])).toBeNull();
    }
    expect(JSON.stringify(request)).toBe(before);
    for (const [path, bytes] of originals) expect<Uint8Array>(await readFile(join(root, path))).toEqual(bytes);
    const copy = {
      files: [...files.map(file => file.path), ...Object.keys(indexes), "compact/other/index/daily.json"],
      indexes: { ...Object.fromEntries(Object.entries(indexes).map(([path, index]) => [path, JSON.stringify(index)])),
        "compact/other/index/daily.json": "unchanged unrelated index" },
      refused: [], missing: [], logs: [],
    };
    const projected = projectPlannerPublication(copy, root);
    expect(projected.files).not.toEqual(expect.arrayContaining(files.map(file => file.path)));
    expect(projected.indexes["compact/other/index/daily.json"]).toBe("unchanged unrelated index");
    expect(projected.logs).toHaveLength(3);
    expect(projected.logs[0]).toContain("covered days are unavailable");
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("current-file corruption still fails publication rather than being excused as an old format", async () => {
  const root = await mkdtemp(join(tmpdir(), "planner-publication-invalid-"));
  try {
    const record = plannerRecordings()[0]!;
    const result = await persistLedger({
      ledger: record.name, rowContract: record.contract, rows: [record.row], outputRoot: root,
      registryEntry: { name: record.name, family: "feed-ingest-plan", grain: "raw-and-compact",
        lifecycle_status: "active", prefix: ["feed-ingest-plan", record.name] },
      ledgerSettings: { format: "parquet", compression_raw: "snappy", compression_compact: "snappy" },
      period: { tier: "compact", period: "daily", covers: "2026-10-20", builtFrom: 1 },
    });
    const path = result.files[0]!.path;
    const request = { files: [{ ledger: "discovered-articles", path }], indexes: {} };
    expect((await selectPlannerPublication(root, request)).files).toEqual([path]);
    const copy = { files: [path, "compact/other/daily/2026/10/20.parquet"], indexes: {},
      refused: [], missing: [], logs: [] };
    expect(projectPlannerPublication(copy, root)).toEqual(copy);
    await writeFile(join(root, path), new Uint8Array([1, 2, 3]));
    await expect(selectPlannerPublication(root, request)).rejects.toThrow();
  } finally { await rm(root, { recursive: true, force: true }); }
});
