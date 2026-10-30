/** Can retained rejected-article files be verified and compacted without inventing evidence? */
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { expect, test } from "bun:test";
import { z } from "zod";
import {
  ArticleFetchEvidenceSchema, LegacyRejectedArticleRowSchema,
  PlannerMaintenanceRequestSchema, RejectedArticleRowContract, RejectedArticleRowSchema,
  REJECTED_ARTICLE_VERSION, deriveCandidateId, deriveUrlKey,
} from "@idhazh/common-contracts";
import { describeObjectSchema, digestRows, maintainPlannerPeriod, persistLedger, readPlannerParquet, readStoredPlannerParquet } from "../src";
import type { LedgerPeriod, LedgerRowContract } from "../src";
import { buildArrowTable } from "../src/parquet/arrow-builder";
import { buildPlannerEnvelopeMetadata } from "../src/parquet/envelope-footer";
import { serializeParquet } from "../src/parquet/wasm-serializer";
import { createPlannerFileId } from "../src/uuid/file-id";

const day = "2026-10-20";
const run = `${day}-1`;
const registration = {
  name: "rejected-articles", family: "feed-ingest-plan", grain: "raw-and-compact" as const,
  lifecycle_status: "active" as const, prefix: ["feed-ingest-plan", "rejected-articles"],
};
const settings = {
  format: "parquet" as const, compression_raw: "snappy" as const, compression_compact: "zstd" as const,
};

function oldRow(ordinal: number) {
  return LegacyRejectedArticleRowSchema.parse({
    run_id: run, attempt: 1, date: day, candidate_id: deriveCandidateId(run, "fixture-feed", ordinal),
    url_key: deriveUrlKey(`https://example.com/article-${ordinal}`), feed_id: "fixture-feed",
    stage: "curate-article-portfolio", reason_code: "RETIRED_REASON", freshness_cutoff_at: null,
  });
}

function failureRow(ordinal: number) {
  return RejectedArticleRowSchema.parse({
    ...oldRow(ordinal), candidate_id: null, stage: "harvest-feeds", reason_code: "FETCH_FAILED_HTTP",
    http_status: 503, fetch_failure: "http", error_code: null,
    robots: "allowed", robots_http_status: 404, robots_failure: "http",
  });
}

async function writeRows(
  root: string, contract: LedgerRowContract<object>, rows: object[],
  period: LedgerPeriod = { tier: "raw", covers: day },
): Promise<string> {
  if (contract.schema === RejectedArticleRowSchema && contract.schemaVersion === REJECTED_ARTICLE_VERSION) {
    const result = await persistLedger({
      ledger: "rejected-articles", outputRoot: join(root, "state"),
      rowContract: contract, registryEntry: registration, ledgerSettings: settings,
      ...(period.tier === "raw" ? { period, rows } : { period, rows }),
    });
    if (result.status !== "written") throw new Error("Recorded rejected rows must produce a file");
    return join(root, "state", result.files[0]!.path);
  }
  const columns = describeObjectSchema(contract.schema).fields;
  const records = rows.map(row => Object.fromEntries(Object.entries(row)));
  const fileId = createPlannerFileId(Date.now());
  const metadata = buildPlannerEnvelopeMetadata({
    rowSchemaVersion: REJECTED_ARTICLE_VERSION, ledger: "rejected-articles",
    tier: period.tier, covers: period.covers, period: period.tier === "raw" ? null : period.period,
    fileId, contentSha256: digestRows(records, columns), writerVersion: "recorded-fixture",
    compression: "snappy", updatedAt: null,
  });
  metadata.set("schema_version", contract.schemaVersion);
  const directory = join(root, "state", period.tier, "feed-ingest-plan", "rejected-articles",
    ...(period.tier === "raw" ? period.covers.split("-") : [period.period, ...period.covers.split("-").slice(0, -1)]));
  const path = join(directory, period.tier === "raw" ? `${fileId}.parquet` : `${period.covers.split("-").at(-1)}.parquet`);
  const serialized = await serializeParquet(buildArrowTable(columns, records), metadata, "snappy");
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, serialized.data);
  return path;
}

function git(root: string, ...args: string[]) {
  return execFileSync("git", args, { cwd: root, encoding: "utf8" }).trim();
}

test("exact old physical schemas gain null evidence after verification, beside current rows", async () => {
  const root = await mkdtemp(join(process.cwd(), ".rejected-compatibility-"));
  try {
    git(root, "init", "--quiet");
    git(root, "config", "user.name", "Fixture");
    git(root, "config", "user.email", "fixture@example.invalid");
    const expected = [];
    for (const [ordinal, schemaVersion] of (["2026-10-27", "2026-10-29"] as const).entries()) {
      const row = oldRow(ordinal);
      const path = await writeRows(root, { schema: LegacyRejectedArticleRowSchema, schemaVersion }, [row],
        ordinal === 0 ? { tier: "compact", period: "daily", covers: day, builtFrom: 1 }
          : { tier: "raw", covers: day });
      const before = await readFile(path);
      const stored = await readStoredPlannerParquet(path, "rejected-articles");
      expect(stored.rows).toEqual([row]);
      expect(stored.rows[0]).not.toHaveProperty("fetch_failure");
      const readback = await readPlannerParquet(path, "rejected-articles", RejectedArticleRowContract);
      const migrated = RejectedArticleRowSchema.parse(row);
      expect(readback.rows).toEqual([migrated]);
      expect(readback.envelope.row_schema_version).toBe(schemaVersion);
      expect(readback.rows[0]).toMatchObject(ArticleFetchEvidenceSchema.parse({}));
      expect(await readFile(path)).toEqual(before);
      expected.push(migrated);
    }
    const current = [failureRow(2), failureRow(3)];
    const currentPath = await writeRows(root, RejectedArticleRowContract, current);
    expect((await readPlannerParquet(currentPath, "rejected-articles", RejectedArticleRowContract)).rows).toEqual(current);
    expected.push(...current);
    git(root, "add", "state");
    git(root, "commit", "--quiet", "-m", "Record mixed rejected-article fixtures");
    const stagingRoot = `.planner-maintenance-${randomUUID().replaceAll("-", "")}`;
    await mkdir(join(root, stagingRoot));
    const request = PlannerMaintenanceRequestSchema.parse({
      revision: git(root, "rev-parse", "HEAD"), staging_root: stagingRoot,
      ledger: "rejected-articles", period: "monthly", covers: "2026-10",
      max_raw_files_per_period: 100, registry_entry: registration, ledger_settings: settings,
    });
    const compacted = await maintainPlannerPeriod(root, request);
    expect(compacted.status).toBe("written");
    if (compacted.status !== "written") return;
    expect(compacted.row_count).toBe(4);
    const compact = await readPlannerParquet(join(root, compacted.output_path), "rejected-articles", RejectedArticleRowContract);
    expect(compact.envelope.row_schema_version).toBe(REJECTED_ARTICLE_VERSION);
    expect(compact.rows).toEqual(expected);
    expect(compact.rows.filter(row => row.candidate_id === null)).toHaveLength(2);
  } finally { await rm(root, { recursive: true, force: true }); }
}, 60_000);

test("refuses unknown stamps and mismatched physical fields before filling evidence", async () => {
  const root = await mkdtemp(join(process.cwd(), ".rejected-schema-refusal-"));
  try {
    const historical = oldRow(0);
    const current = failureRow(1);
    const malformed = z.strictObject({
      ...RejectedArticleRowSchema.shape, error_code: z.string().nullable(),
    });
    await expect(persistLedger({
      ledger: "rejected-articles", outputRoot: join(root, "state"),
      rowContract: { ...RejectedArticleRowContract, schemaVersion: "2026-10-29" },
      registryEntry: registration, ledgerSettings: settings,
      period: { tier: "raw", covers: day }, rows: [current],
    })).rejects.toThrow("requires its declared current planner row contract");
    const cases: { schema: z.ZodType<object>; version: string; row: object; error: string }[] = [
      { schema: LegacyRejectedArticleRowSchema, version: "2099-01-01", row: historical, error: "unsupported row schema" },
      { schema: LegacyRejectedArticleRowSchema, version: REJECTED_ARTICLE_VERSION, row: historical, error: "Arrow columns differ" },
      { schema: RejectedArticleRowSchema, version: "2026-10-29", row: current, error: "Arrow columns differ" },
      { schema: z.strictObject({ ...LegacyRejectedArticleRowSchema.shape, attempt: z.string() }),
        version: "2026-10-27", row: { ...historical, attempt: "1" }, error: "Arrow type differs" },
      { schema: z.strictObject({ ...LegacyRejectedArticleRowSchema.shape, candidate_id: z.string().nullable() }),
        version: "2026-10-27", row: historical, error: "Arrow nullability differs" },
      { schema: malformed, version: REJECTED_ARTICLE_VERSION,
        row: { ...current, error_code: "invalid-code" }, error: "Invalid string" },
    ];
    for (const fixture of cases) {
      const path = await writeRows(root, { schema: fixture.schema, schemaVersion: fixture.version }, [fixture.row]);
      await expect(readPlannerParquet(path, "rejected-articles", RejectedArticleRowContract)).rejects.toThrow(fixture.error);
    }
  } finally { await rm(root, { recursive: true, force: true }); }
});
