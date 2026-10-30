/** Does a rejected raw write replay reuse only a verified identical physical file? */
import { mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { expect, test } from "bun:test";
import {
  RejectedArticleRowContract, RejectedArticleRowSchema, deriveUrlKey,
} from "@idhazh/common-contracts";
import { persistLedger } from "../src";
import { createRejectedRawFileId } from "../src/uuid/file-id";

test("replayed rejected raw rows reuse their file and refuse an existing corrupt target", async () => {
  const root = await mkdtemp(join(process.cwd(), ".rejected-replay-"));
  try {
    const row = RejectedArticleRowSchema.parse({
      run_id: "2026-10-20-1", attempt: 1, date: "2026-10-20",
      candidate_id: null, url_key: deriveUrlKey("https://example.com/article"),
      feed_id: "fixture-feed", stage: "harvest-feeds", reason_code: "EXTRACT_EMPTY",
      freshness_cutoff_at: null, http_status: 200, robots: "allowed",
    });
    const input = {
      ledger: "rejected-articles", outputRoot: root, rowContract: RejectedArticleRowContract,
      registryEntry: {
        name: "rejected-articles", family: "feed-ingest-plan", grain: "raw-and-compact" as const,
        lifecycle_status: "active" as const, prefix: ["feed-ingest-plan", "rejected-articles"],
      },
      ledgerSettings: {
        format: "parquet" as const, compression_raw: "snappy" as const, compression_compact: "zstd" as const,
      },
      period: { tier: "raw" as const, covers: row.date }, rows: [row],
    };
    const first = await persistLedger(input);
    expect(first.status).toBe("written");
    const firstFile = first.files[0]!;
    const path = join(root, firstFile.path);
    const bytes = await readFile(path);
    const replay = await persistLedger({ ...input, rows: [{ ...row }, { ...row }] });
    expect(replay).toEqual(first);
    expect(await readFile(path)).toEqual(bytes);
    expect(await readdir(dirname(path))).toEqual([`${firstFile.file_id}.parquet`]);
    const changed = await persistLedger({ ...input, rows: [{ ...row, http_status: 204 }] });
    expect(changed.files[0]!.file_id).not.toBe(firstFile.file_id);
    await writeFile(path, "not a parquet file");
    await expect(persistLedger(input)).rejects.toThrow();
    expect(await readFile(path, "utf8")).toBe("not a parquet file");
    expect(await readdir(dirname(path))).toHaveLength(2);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("rejected raw identities bind the exact schema stamp, day and canonical row digest", () => {
  const digest = "a".repeat(64);
  const id = createRejectedRawFileId("2026-10-29T20:15", "2026-10-20", digest);
  expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  expect(createRejectedRawFileId("2026-10-29T20:15", "2026-10-20", digest)).toBe(id);
  expect(createRejectedRawFileId("2026-10-29", "2026-10-20", digest)).not.toBe(id);
  expect(createRejectedRawFileId("2026-10-29T20:15", "2026-10-21", digest)).not.toBe(id);
  expect(createRejectedRawFileId("2026-10-29T20:15", "2026-10-20", "b".repeat(64))).not.toBe(id);
});
