/** Verify named compatibility fixtures without making the workflow depend on them. */
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { isDeepStrictEqual } from "node:util";
import { z } from "zod";
import {
  Sha256Schema, RunIdSchema, TimestampSchema, SchemaVersionSchema, RelPathSchema,
  readSelectedArticlesArtifact, migratePreviousSelectedMetadata,
} from "@idhazh/common-contracts";
import { createFileId, createUnitId, digestRows, persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, LogicalField } from "@idhazh/ledger-file-writer";
import { plannerRecordings } from "../../../packages/ledger-file-writer/test/planner-recordings";
import { readLedgerParquet } from "../src/read-ledger-history/read-parquet";
import { plannerContracts, verifyParquetFiles } from "../scripts/feed-ingest-plan-verification";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";

export async function verifyRecordedCompatibility() {
  const fixtures = new URL("../../../tests/fixtures/ledger-file-writer/planner-2026-10-25/", import.meta.url);
  const previousFiles = z.array(z.strictObject({
    ledger: z.enum(["selected-articles", "plan-runs"]), path: RelPathSchema,
    sha256: Sha256Schema, content_sha256: Sha256Schema, rows: z.array(z.record(z.string(), z.unknown())),
  })).length(2).parse(await Bun.file(new URL("files.json", fixtures)).json());
  let previousCount = 0;
  for (const fixture of previousFiles) {
    const path = fileURLToPath(new URL(fixture.path, fixtures));
    const before = await readFile(path);
    if (createHash("sha256").update(before).digest("hex") !== fixture.sha256) throw new Error("Previous planner fixture bytes changed");
    const contract = plannerContracts[fixture.ledger];
    const read = await readPlannerParquet<object>(path, fixture.ledger, contract);
    const expected = fixture.ledger === "selected-articles"
      ? fixture.rows.map(migratePreviousSelectedMetadata) : fixture.rows;
    if (read.envelope.row_schema_version !== "2026-10-25" || read.envelope.content_sha256 !== fixture.content_sha256
      || !isDeepStrictEqual(read.rows, expected) || !before.equals(await readFile(path))) {
      throw new Error("Previous planner rows lost their original digest, fields or age evidence");
    }
    previousCount += read.rows.length;
  }
  const previousArtifact = await Bun.file(new URL("selected-articles.json", fixtures)).json();
  const artifact = readSelectedArticlesArtifact(previousArtifact);
  const previousArticles = z.array(z.record(z.string(), z.unknown())).parse(previousArtifact.articles);
  if (!isDeepStrictEqual(artifact.articles, previousArticles.map(migratePreviousSelectedMetadata))
    || artifact.articles.some(article => article.published_at !== null || article.published_at_source !== "legacy-unavailable")) {
    throw new Error("Previous artifact publication or age evidence changed");
  }
  const seenSchema = z.strictObject({
    version: SchemaVersionSchema, url_key: Sha256Schema,
    first_seen_at: TimestampSchema, first_seen_run: RunIdSchema,
  });
  const legacySeen = await readLedgerParquet(
    fileURLToPath(new URL("../../../tests/fixtures/ledger-file-writer/legacy-seen-day.parquet", import.meta.url)),
    "seen", { schema: seenSchema, schemaVersion: "2026-08-31" },
  );
  if (legacySeen.envelope.version !== "2026-10-01T16:50" || legacySeen.rows.length === 0
    || legacySeen.rows.some(({ identity }) => identity.job === null || identity.pipeline_name !== null || identity.task_name !== null)) {
    throw new Error("The unchanged global seen compatibility vector lost its original identity");
  }
  const unit = createUnitId({
    ledger: "covers", covers: "2026-10-20", runId: "2026-10-20-123",
    job: null, pipelineName: "plan", taskName: "source-runs", shard: 2, producer: "test.writer",
  });
  if (unit !== "6375f642-cc1d-54e3-bf2f-60112d783f1b"
    || createFileId({ unit, attempt: 3, writtenAtMs: 1792497600000 }) !== "01a1592e-c600-84d0-96e4-7bb01708ce01") {
    throw new Error("The unchanged generic UUID compatibility vector differs");
  }
  const fields: LogicalField[] = [
    ...["big", "float_one", "negative_zero", "small"].map(name => ({
      name, nullable: false, type: { kind: "scalar" as const, scalar: "float64" as const, nullable: false },
    })),
    { name: "list", nullable: false, type: { kind: "list", nullable: false, itemNullable: false,
      itemType: { kind: "scalar", scalar: "string", nullable: false } } },
    { name: "maybe", nullable: true, type: { kind: "scalar", scalar: "string", nullable: true } },
    { name: "nested", nullable: false, type: { kind: "struct", nullable: false, fields: [
      { name: "items", nullable: false, type: { kind: "list", nullable: false, itemNullable: false,
        itemType: { kind: "scalar", scalar: "string", nullable: false } } },
      { name: "value", nullable: true, type: { kind: "scalar", scalar: "int64", nullable: true } },
    ] } },
    { name: "z-unicode", nullable: false, type: { kind: "scalar", scalar: "string", nullable: false } },
  ];
  const reading = digestRows([{
    big: 1e20, float_one: 1.0, list: ["na\u00efve", "\u6771\u4eac"], maybe: null,
    negative_zero: -0.0, nested: { items: ["\u00c9diteur"], value: null },
    small: 1e-7, "z-unicode": "Caf\u00e9 \u6771\u4eac",
  }], fields);
  if (reading !== "9514b5931807b27fbaf18c43c7371ada4bab45fd745ff4b3564dad032cdad67e") throw new Error("Canonical compatibility bytes differ");
  const directory = await mkdtemp(join(tmpdir(), "planner-native-"));
  try {
    let count = 0;
    for (const fixture of plannerRecordings()) {
      const registration: LedgerRegistration = { name: fixture.name, family: "feed-ingest-plan",
        prefix: ["feed-ingest-plan", fixture.name], grain: "raw-and-compact", lifecycle_status: "active" };
      const written = await persistLedger({
        ledger: fixture.name, rowContract: fixture.contract, rows: [fixture.row], outputRoot: directory,
        registryEntry: registration, period: { tier: "raw", covers: "2026-10-20" },
        ...(fixture.name === "feed-health-state" ? { updatedAt: "2026-10-20T12:00:00Z" } : {}),
        ledgerSettings: { format: "parquet", compression_raw: "snappy", compression_compact: "zstd" },
      });
      count += (await verifyParquetFiles(directory, fixture.name, written, registration, [fixture.row])).row_count;
    }
    return {
      status: "verified", canonical_content_sha256: reading, planner_row_count: count,
      legacy_seen_row_count: legacySeen.rows.length, legacy_planner_row_count: previousCount,
      legacy_planner_files: previousFiles.map(({ ledger, path, sha256, content_sha256 }) => ({ ledger, path, sha256, content_sha256 })),
    };
  } finally { await rm(directory, { recursive: true, force: true }); }
}
if (import.meta.main) console.log(JSON.stringify(await verifyRecordedCompatibility()));
