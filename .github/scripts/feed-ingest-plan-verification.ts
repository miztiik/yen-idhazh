/** Do named planner files reproduce their declared rows, native types and recorded commitments? */
import { mkdtemp, readFile, realpath, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { isDeepStrictEqual } from "node:util";
import { isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  CandidateRejectionContract, CONTRACT_VERSION, DateStampSchema,
  readFeedIngestDispatch, LedgerCompletionEvidenceSchema,
  PositiveCountSchema, Sha256Schema, deriveCandidateId, deriveUrlKey,
} from "../../packages/common-contracts/src/index";
import { createFileId, createUnitId, digestRows, persistLedger } from "../../packages/ledger-file-writer/src/index";
import type { LedgerRegistration, LogicalField, PersistLedgerResult } from "../../packages/ledger-file-writer/src/index";
import { readLedgerParquet } from "../../services/feed-ingest-plan/src/read-ledger-history/read-parquet";
import { SeenRowSchema } from "../../services/feed-ingest-plan/src/screen-article-candidates/seen-evidence";
import type { summarizePlan } from "../../services/feed-ingest-plan/src/run-feed-plan";
import {
  ArticleAssessmentContract, DiversityMetricContract, DispatchContract, SourceRunContract, legacyAuditSchemas,
} from "../../services/feed-ingest-plan/src/metrics/audit-contracts";

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
  root: string, ledger: "dispatches" | "rejections" | "article-assessments" | "diversity" | "source-runs", written: PersistLedgerResult,
  registration: LedgerRegistration, expectedRows?: readonly object[],
) {
  if (registration.name !== ledger) throw new Error("registration.name differs from the requested ledger");
  if (written === undefined || written === null || !Array.isArray(written.files)) {
    throw new Error(`${ledger}.files evidence is absent`);
  }
  if (written.status === "empty") {
    if (written.files.length !== 0) throw new Error(`${ledger}.empty must have no files`);
    if (expectedRows !== undefined && expectedRows.length !== 0) throw new Error(`${ledger}.rows differ from native empty result`);
    return { status: "verified_empty" as const, row_count: 0, files: [] };
  }
  if (written.status !== "written" || written.files.length === 0) {
    throw new Error(`${ledger}.status must declare written files or an explicit empty result`);
  }
  const rootPath = await realpath(root);
  const seen = new Set<string>();
  const verified = [];
  const rows: object[] = [];
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
      ? await readLedgerParquet(actualPath, ledger, DispatchContract)
      : ledger === "rejections"
        ? await readLedgerParquet(actualPath, ledger, CandidateRejectionContract)
        : ledger === "article-assessments"
          ? await readLedgerParquet(actualPath, ledger, ArticleAssessmentContract)
          : ledger === "diversity"
            ? await readLedgerParquet(actualPath, ledger, DiversityMetricContract)
            : await readLedgerParquet(actualPath, ledger, SourceRunContract);
    if (actual.envelope.tier !== "raw" || actual.envelope.file_id !== file.file_id
      || actual.envelope.unit_id !== file.unit_id || actual.envelope.covers !== file.covers
      || actual.envelope.content_sha256 !== file.content_sha256 || actual.rows.length !== file.row_count) {
      throw new Error(`${ledger}.files envelope, content_sha256 or row_count differs from native readback`);
    }
    rowCount += actual.rows.length;
    if (expectedRows !== undefined) rows.push(...actual.rows.map(held => held.row));
    verified.push({ path, content_sha256: actual.envelope.content_sha256, row_count: actual.rows.length });
  }
  if (expectedRows !== undefined && !isDeepStrictEqual(rows, expectedRows)) {
    throw new Error(`${ledger}.rows differ from native readback`);
  }
  return { status: "verified" as const, row_count: rowCount, files: verified };
}

export function verifyLedgerReceipt(ledger: string, written: PersistLedgerResult, receipt: unknown): void {
  const evidence = LedgerCompletionEvidenceSchema.parse(receipt);
  if (evidence.ledger !== ledger || evidence.files.length !== written.files.length
    || evidence.row_count !== written.files.reduce((count, file) => count + file.row_count, 0)) {
    throw new Error(`${ledger}.receipt ledger, files or row_count differs from actual writes`);
  }
  for (const file of written.files) {
    const held = evidence.files.find(item => item.file_id === file.file_id);
    if (held === undefined || held.content_sha256 !== file.content_sha256 || held.row_count !== file.row_count) {
      throw new Error(`${ledger}.receipt file_id, content_sha256 or row_count differs from actual writes`);
    }
  }
}

export async function verifyPlanningCompletion(root: string, summary: ReturnType<typeof summarizePlan>) {
  const { readPlanningHistory } = await import("../../services/feed-ingest-plan/src/metrics/planning-populations");
  const { selectCompleteAttempt } = await import("../../services/feed-ingest-plan/src/read-ledger-history/complete-attempt");
  const metrics = summary.metrics;
  const proof = summary.planning_completion;
  if (!summary.planning_complete || proof === null || proof.status !== "complete"
    || metrics === undefined || summary.source_records === null || summary.files.source_runs === undefined) {
    throw new Error("planning_completion requires actual source records and all original ledger files");
  }
  const named = (files: readonly PersistLedgerResult[]) => ({
    day: summary.date, rawFiles: files.flatMap(result => result.files.map(file => {
      const path = file.path;
      if (isAbsolute(path) || path.split("/").includes("..") || path.includes("\\")) {
        throw new Error("planning_completion.files.path must be a relative POSIX path");
      }
      return resolve(root, ...path.split("/"));
    })),
  });
  const history = await readPlanningHistory({
    sources: named([summary.files.source_runs]), ledgers: {
      "article-assessments": named([metrics.files.assessments]), diversity: named([metrics.files.diversity]),
      "editorial-selections": named([summary.files.selections]), dispatches: named([summary.files.dispatches]),
      rejections: named([summary.files.harvest_rejections, summary.files.screening_rejections, summary.files.curation_rejections]),
    },
  });
  const selected = selectCompleteAttempt(history, summary.run_id).selected;
  if (selected === null || selected.run_id !== proof.run_id || selected.date !== proof.date
    || selected.attempt !== proof.attempt || selected.correlation_id !== proof.correlation_id
    || selected.correlation_id !== summary.correlation_id
    || selected.sources.length !== proof.source_count || !isDeepStrictEqual(selected.sources, summary.source_records)
    || selected.sources.some(row => !isDeepStrictEqual(row.completion_evidence, proof.completion_evidence))
    || !isDeepStrictEqual(proof, metrics.planning_completion)
    || !isDeepStrictEqual(summary.files.source_runs, metrics.files.source_runs)
    || !isDeepStrictEqual(summary.source_records, metrics.source_records)) {
    throw new Error("planning_completion differs from original native selector proof");
  }
  return selected;
}

export async function verifyRecordedCompatibility() {
  const legacySeen = await readLedgerParquet(
    fileURLToPath(new URL("../../tests/fixtures/ledger-file-writer/legacy-seen-day.parquet", import.meta.url)),
    "seen", { schema: SeenRowSchema, schemaVersion: "2026-08-31" },
  );
  if (legacySeen.envelope.version !== "2026-10-01T16:50" || legacySeen.rows.length === 0
    || legacySeen.rows.some(({ identity }) => identity.job === null || identity.pipeline_name !== null || identity.task_name !== null)) {
    throw new Error("Recorded legacy seen identities differ from their stored envelope");
  }
  const fixture = readFeedIngestDispatch(JSON.parse(await readFile(
    new URL("../../tests/fixtures/ledger-file-writer/feed-ingest-dispatch-row.json", import.meta.url), "utf8",
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
      ledger: "dispatches", rowContract: DispatchContract,
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
    const actual = await readLedgerParquet(join(root, ...file.path.split("/")), "dispatches", DispatchContract);
    if (!isDeepStrictEqual(actual.rows[0]?.row, fixture)) {
      throw new Error("recorded fixture dispatch rows differ after native Parquet readback");
    }
    const legacy = legacyAuditSchemas.Dispatch.parse(JSON.parse(await readFile(
      new URL("../../tests/fixtures/contracts/feed-ingest-dispatch/one-article.json", import.meta.url), "utf8",
    )));
    const legacyWritten = await persistLedger({
      ledger: "dispatches", rowContract: { schema: legacyAuditSchemas.Dispatch, schemaVersion: CONTRACT_VERSION },
      rows: [legacy], outputRoot: root, period: { tier: "raw", covers: legacy.content.date },
      writerContext: { run_id: legacy.content.run_id, attempt: 1, job: null,
        pipeline_name: "plan", task_name: "seal-article-ledger", shard: 0,
        producer: "tests.verify-legacy-parquet", git_sha: "a".repeat(40) },
      registryEntry: registration,
      ledgerSettings: { format: "parquet", compression_raw: "snappy", compression_compact: "zstd" },
    });
    const legacyChecked = await verifyParquetFiles(root, "dispatches", legacyWritten, registration,
      [readFeedIngestDispatch(legacy)]);
    return { status: "verified" as const, canonical_content_sha256: reading,
      row_count: checked.row_count, legacy_row_count: legacyChecked.row_count,
      legacy_seen_row_count: legacySeen.rows.length };
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

if (import.meta.main) console.log(JSON.stringify(await verifyRecordedCompatibility()));
