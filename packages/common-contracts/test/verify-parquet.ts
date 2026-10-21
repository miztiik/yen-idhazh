/** Do named planner files reproduce their declared rows, native types and recorded commitments? */
import { mkdtemp, readFile, realpath, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { isDeepStrictEqual } from "node:util";
import { isAbsolute, join, relative, resolve } from "node:path";
import {
  CandidateRejectionRecordSchema, CONTRACT_VERSION, DateStampSchema, FeedIngestDispatchSchema,
  PositiveCountSchema, Sha256Schema, deriveCandidateId, deriveUrlKey,
} from "../src/index";
import { createFileId, createUnitId, digestRows, persistLedger } from "../../ledger-file-writer/src/index";
import type { LedgerRegistration, LogicalField, PersistLedgerResult } from "../../ledger-file-writer/src/index";
import { readLedgerParquet } from "../../../services/feed-ingest-plan/src/read-ledger-history/read-parquet";

export function validateLedgerFilePath(
  path: string, fileId: string, covers: string, registration: LedgerRegistration,
): string {
  DateStampSchema.parse(covers);
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(fileId)) {
    throw new Error("files.file_id must be a version 8 UUID");
  }
  if (registration.prefix.length === 0 || registration.prefix.some(part => !/^[a-z0-9][a-z0-9-]*$/.test(part))) {
    throw new Error("registration.prefix must contain validated directory identifiers");
  }
  const expected = ["raw", ...registration.prefix, ...covers.split("-"), `${fileId}.parquet`].join("/");
  if (path !== expected) throw new Error("files.path differs from the registered raw ledger identity");
  return path;
}

export async function verifyParquetFiles(
  root: string, ledger: "dispatches" | "rejections", written: PersistLedgerResult,
  registration: LedgerRegistration,
) {
  if (registration.name !== ledger) throw new Error("registration.name differs from the requested ledger");
  if (written === undefined || written === null || !Array.isArray(written.files)) {
    throw new Error(`${ledger}.files evidence is absent`);
  }
  if (written.status === "empty") {
    if (written.files.length !== 0) throw new Error(`${ledger}.empty must have no files`);
    return { status: "verified_empty" as const, row_count: 0, files: [] };
  }
  if (written.status !== "written" || written.files.length === 0) {
    throw new Error(`${ledger}.status must declare written files or an explicit empty result`);
  }
  const rootPath = await realpath(root);
  const seen = new Set<string>();
  const verified = [];
  let rowCount = 0;
  for (const file of written.files) {
    const path = validateLedgerFilePath(file.path, file.file_id, file.covers, registration);
    if (seen.has(path)) throw new Error(`${ledger}.files.path is duplicated`);
    seen.add(path);
    PositiveCountSchema.parse(file.row_count);
    Sha256Schema.parse(file.content_sha256);
    const actualPath = await realpath(resolve(rootPath, ...path.split("/")));
    const local = relative(rootPath, actualPath);
    if (isAbsolute(local) || local === ".." || local.startsWith(`..\\`) || local.startsWith("../")) {
      throw new Error(`${ledger}.files.path escapes its output root`);
    }
    const actual = ledger === "dispatches"
      ? await readLedgerParquet(actualPath, ledger, { schema: FeedIngestDispatchSchema, schemaVersion: CONTRACT_VERSION })
      : await readLedgerParquet(actualPath, ledger, { schema: CandidateRejectionRecordSchema, schemaVersion: CONTRACT_VERSION });
    if (actual.envelope.tier !== "raw" || actual.envelope.file_id !== file.file_id
      || actual.envelope.unit_id !== file.unit_id || actual.envelope.covers !== file.covers
      || actual.envelope.content_sha256 !== file.content_sha256 || actual.rows.length !== file.row_count) {
      throw new Error(`${ledger}.files envelope, content_sha256 or row_count differs from native readback`);
    }
    rowCount += actual.rows.length;
    verified.push({ path, content_sha256: actual.envelope.content_sha256, row_count: actual.rows.length });
  }
  return { status: "verified" as const, row_count: rowCount, files: verified };
}

export async function verifyRecordedCompatibility() {
  const fixture = FeedIngestDispatchSchema.parse(JSON.parse(await readFile(
    new URL("../../../tests/fixtures/ledger-file-writer/feed-ingest-dispatch-row.json", import.meta.url), "utf8",
  )));
  if (deriveCandidateId(fixture.content.run_id, fixture.content.source_id, fixture.content.entry_ordinal) !== fixture.content.candidate_id
    || deriveUrlKey(fixture.content.canonical_url) !== fixture.content.url_key) {
    throw new Error("recorded fixture candidate_id or url_key differs from the identity contract");
  }
  const unit = createUnitId({
    ledger: "covers", covers: "2026-10-20", runId: "2026-10-20-123",
    job: null, pipelineName: "plan", taskName: "source-runs", shard: 2, producer: "test.writer",
  });
  if (unit !== "6375f642-cc1d-54e3-bf2f-60112d783f1b"
    || createFileId({ unit, attempt: 3, writtenAtMs: 1792497600000 }) !== "01a1592e-c600-84d0-96e4-7bb01708ce01") {
    throw new Error("recorded compatibility unit_id or file_id differs");
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
  if (reading !== "9514b5931807b27fbaf18c43c7371ada4bab45fd745ff4b3564dad032cdad67e") {
    throw new Error("recorded canonical content_sha256 differs");
  }
  const root = await mkdtemp(join(tmpdir(), "feed-parquet-compatibility-"));
  try {
    const registration: LedgerRegistration = {
      name: "dispatches", family: "feed-ingest-plan", grain: "raw-and-compact",
      lifecycle_status: "active", prefix: ["feed-ingest-plan", "dispatches"],
    };
    const written = await persistLedger({
      ledger: "dispatches", rowContract: { schema: FeedIngestDispatchSchema, schemaVersion: CONTRACT_VERSION },
      rows: [fixture], outputRoot: root, period: { tier: "raw", covers: fixture.content.date },
      writerContext: { run_id: fixture.content.run_id, attempt: 1, job: null,
        pipeline_name: "plan", task_name: "seal-article-ledger", shard: 0,
        producer: "tests.verify-parquet", git_sha: "a".repeat(40) },
      registryEntry: registration,
      ledgerSettings: { format: "parquet", compression_raw: "snappy", compression_compact: "zstd" },
    });
    const checked = await verifyParquetFiles(root, "dispatches", written, registration);
    const file = checked.files[0];
    if (file === undefined) throw new Error("recorded fixture dispatch file is absent");
    const actual = await readLedgerParquet(join(root, ...file.path.split("/")), "dispatches",
      { schema: FeedIngestDispatchSchema, schemaVersion: CONTRACT_VERSION });
    if (!isDeepStrictEqual(actual.rows[0]?.row, fixture)) {
      throw new Error("recorded fixture dispatch rows differ after native Parquet readback");
    }
    return { status: "verified" as const, canonical_content_sha256: reading, row_count: checked.row_count };
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

if (import.meta.main) console.log(JSON.stringify(await verifyRecordedCompatibility()));
