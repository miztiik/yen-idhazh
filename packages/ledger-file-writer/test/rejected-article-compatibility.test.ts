/** Refuse old rejected-file formats without inventing fetch evidence or rewriting bytes. */
import { expect, test } from "bun:test";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { z } from "zod";
import { RejectedArticleRowContract, RejectedArticleRowSchema, REJECTED_ARTICLE_VERSION, deriveCandidateId, deriveUrlKey } from "@idhazh/common-contracts";
import { describeObjectSchema, digestRows, persistLedger, readPlannerParquet, readStoredPlannerParquet } from "../src";
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
const priorPhysical = z.object(RejectedArticleRowSchema.shape).omit({
  http_status: true, fetch_failure: true, error_code: true,
  robots: true, robots_http_status: true, robots_failure: true,
});

function row() {
  return RejectedArticleRowSchema.parse({
    run_id: `${day}-1`, attempt: 1, date: day,
    candidate_id: deriveCandidateId(`${day}-1`, "fixture-feed", 0),
    url_key: deriveUrlKey("https://example.org/article"), feed_id: "fixture-feed",
    stage: "curate-article-portfolio", reason_code: "REJECTED_GLOBAL_CAPACITY_REACHED",
    freshness_cutoff_at: null,
  });
}
async function writePriorPhysical(root: string, stamp: string) {
  const rows = [priorPhysical.parse(row())];
  const columns = describeObjectSchema(priorPhysical).fields;
  const fileId = createPlannerFileId(Date.now());
  const metadata = buildPlannerEnvelopeMetadata({
    rowSchemaVersion: REJECTED_ARTICLE_VERSION, ledger: "rejected-articles",
    tier: "raw", covers: day, period: null, fileId,
    contentSha256: digestRows(rows, columns), writerVersion: "recorded-fixture",
    compression: "snappy", updatedAt: null,
  });
  metadata.set("schema_version", stamp);
  const path = join(root, "raw", "feed-ingest-plan", "rejected-articles", "2026", "10", "20", `${fileId}.parquet`);
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, (await serializeParquet(buildArrowTable(columns, rows), metadata, "snappy")).data);
  return path;
}

test("current rejected metadata round-trips and older stamps refuse without null-fill migration", async () => {
  const root = await mkdtemp(join(tmpdir(), "rejected-current-format-"));
  try {
    const current = row();
    const result = await persistLedger({
      ledger: "rejected-articles", outputRoot: root, rows: [current], rowContract: RejectedArticleRowContract,
      registryEntry: registration, ledgerSettings: settings, period: { tier: "raw", covers: day },
    });
    expect((await readPlannerParquet(join(root, result.files[0]!.path), "rejected-articles", RejectedArticleRowContract)).rows).toEqual([current]);
    for (const stamp of ["2026-10-27", "2026-10-29", "2026-10-29T20:15"]) {
      const path = await writePriorPhysical(root, stamp);
      const before = await readFile(path);
      await expect(readStoredPlannerParquet(path, "rejected-articles")).rejects.toThrow();
      await expect(readPlannerParquet(path, "rejected-articles", RejectedArticleRowContract)).rejects.toThrow();
      expect(await readFile(path)).toEqual(before);
    }
    const partial = await writePriorPhysical(root, REJECTED_ARTICLE_VERSION);
    const stored = await readStoredPlannerParquet(partial, "rejected-articles");
    expect(stored.rows[0]).not.toHaveProperty("fetch_failure");
    await expect(readPlannerParquet(partial, "rejected-articles", RejectedArticleRowContract)).rejects.toThrow("columns");
  } finally { await rm(root, { recursive: true, force: true }); }
});
