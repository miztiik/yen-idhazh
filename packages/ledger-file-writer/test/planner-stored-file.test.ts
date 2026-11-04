/** Read intact stored fields across row stamps while keeping full-row checks strict. */
import { expect, test } from "bun:test";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { z } from "zod";
import { RejectedArticleRowContract, RejectedArticleRowSchema, REJECTED_ARTICLE_VERSION, deriveUrlKey } from "@idhazh/common-contracts";
import {
  describeObjectSchema, digestRows, persistLedger, readPlannerParquet, readStoredPlannerParquet,
  PlannerUnsupportedFormatError,
} from "../src";
import { buildArrowTable } from "../src/parquet/arrow-builder";
import { buildPlannerEnvelopeMetadata } from "../src/parquet/envelope-footer";
import { serializeParquet } from "../src/parquet/wasm-serializer";
import { createPlannerFileId } from "../src/uuid/file-id";

const day = "2026-10-20";
const registration = {
  name: "rejected-articles", family: "feed-ingest-plan", grain: "raw-and-compact" as const,
  lifecycle_status: "active" as const, prefix: ["feed-ingest-plan", "rejected-articles"],
};
const settings = { format: "parquet" as const, compression_raw: "snappy" as const, compression_compact: "zstd" as const };
const storedSchema = z.object(RejectedArticleRowSchema.shape).omit({
  http_status: true, fetch_failure: true, error_code: true,
  pacing_time_ms: true, pacing_settings: true,
});

function row() {
  return RejectedArticleRowSchema.parse({
    run_id: `${day}-1`, attempt: 1, date: day,
    candidate_id: "00000000-0000-4000-8000-000000000001",
    url_key: deriveUrlKey("https://example.org/article"), feed_id: "fixture-feed",
    stage: "curate-article-portfolio", reason_code: "REJECTED_GLOBAL_CAPACITY_REACHED",
    freshness_cutoff_at: null,
  });
}
async function writeStoredFields(root: string, stamp: string, changes: Readonly<Record<string, string>> = {}) {
  const rows = [storedSchema.parse(row())];
  const columns = describeObjectSchema(storedSchema).fields;
  const fileId = createPlannerFileId(Date.now());
  const metadata = buildPlannerEnvelopeMetadata({
    rowSchemaVersion: REJECTED_ARTICLE_VERSION, ledger: "rejected-articles",
    tier: "raw", covers: day, period: null, fileId,
    contentSha256: digestRows(rows, columns), writerVersion: "recorded-fixture",
    compression: "snappy", updatedAt: null,
  });
  metadata.set("schema_version", stamp);
  for (const [key, value] of Object.entries(changes)) metadata.set(key, value);
  const path = join(root, "raw", "feed-ingest-plan", "rejected-articles", "2026", "10", "20", `${fileId}.parquet`);
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, (await serializeParquet(buildArrowTable(columns, rows), metadata, "snappy")).data);
  return path;
}

test("current rows round-trip and stored fields survive row stamps without null-fill", async () => {
  const root = await mkdtemp(join(process.cwd(), ".rejected-current-format-check-"));
  try {
    const current = row();
    const result = await persistLedger({
      ledger: "rejected-articles", outputRoot: root, rows: [current], rowContract: RejectedArticleRowContract,
      registryEntry: registration, ledgerSettings: settings, period: { tier: "raw", covers: day },
    });
    const currentPath = join(root, result.files[0]!.path);
    expect((await readPlannerParquet(currentPath, "rejected-articles", RejectedArticleRowContract)).rows).toEqual([current]);
    const storedCurrent = await readStoredPlannerParquet(currentPath, "rejected-articles");
    expect(Object.keys(storedCurrent.rows[0]!).sort()).toEqual(Object.keys(RejectedArticleRowSchema.shape).sort());
    for (const stamp of ["2026-10-27", "2026-10-29", "2026-10-29T20:15", "2026-10-31", "2026-11-01", "2027-01-01", REJECTED_ARTICLE_VERSION]) {
      const path = await writeStoredFields(root, stamp);
      const before = await readFile(path);
      const stored = await readStoredPlannerParquet(path, "rejected-articles");
      expect(stored.envelope.row_schema_version).toBe(stamp);
      expect(stored.rows).toEqual([storedSchema.parse(current)]);
      expect(stored.rows[0]).not.toHaveProperty("fetch_failure");
      if (stamp === REJECTED_ARTICLE_VERSION) {
        await expect(readPlannerParquet(path, "rejected-articles", RejectedArticleRowContract)).rejects.toThrow("columns");
      } else {
        await expect(readPlannerParquet(path, "rejected-articles", RejectedArticleRowContract))
          .rejects.toBeInstanceOf(PlannerUnsupportedFormatError);
      }
      expect(await readFile(path)).toEqual(before);
    }
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("stored reads still refuse unsupported envelopes, invalid stamps, wrong ledgers and damaged digests", async () => {
  const root = await mkdtemp(join(process.cwd(), ".planner-stored-integrity-check-"));
  try {
    const unsupported = await writeStoredFields(root, REJECTED_ARTICLE_VERSION, { envelope_version: "2026-10-29" });
    const before = await readFile(unsupported);
    await expect(readStoredPlannerParquet(unsupported, "rejected-articles")).rejects.toBeInstanceOf(PlannerUnsupportedFormatError);
    await expect(readPlannerParquet(unsupported, "rejected-articles", RejectedArticleRowContract))
      .rejects.toBeInstanceOf(PlannerUnsupportedFormatError);
    expect(await readFile(unsupported)).toEqual(before);
    for (const [stamp, changes, message] of [
      ["not-a-date", {}, "Invalid"],
      ["2026-10-27", { ledger: "selected-articles" }, "registered ledger"],
      ["2026-10-27", { content_sha256: "f".repeat(64) }, "digest"],
    ] as const) {
      const path = await writeStoredFields(root, stamp, changes);
      const bytes = await readFile(path);
      await expect(readStoredPlannerParquet(path, "rejected-articles")).rejects.toThrow(message);
      await expect(readPlannerParquet(path, "rejected-articles", RejectedArticleRowContract)).rejects.toThrow(message);
      expect(await readFile(path)).toEqual(bytes);
    }
  } finally { await rm(root, { recursive: true, force: true }); }
});
