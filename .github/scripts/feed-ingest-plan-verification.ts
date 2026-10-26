/** Independently verify current planner files and unchanged other-family compatibility vectors. */
import { mkdtemp, readFile, realpath, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { isDeepStrictEqual } from "node:util";
import { isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "../../packages/common-contracts/node_modules/zod";
import {
  DateStampSchema, DiscoveredArticleRowContract, FeedHealthStateRowContract, PlanRunRowContract,
  SelectedArticleRowContract, SelectedArticlesArtifactSchema, selectedArticleMetadata, Sha256Schema,
  RunIdSchema, TimestampSchema, SchemaVersionSchema,
} from "../../packages/common-contracts/src/index";
import { createFileId, createUnitId, digestRows, persistLedger } from "../../packages/ledger-file-writer/src/index";
import type { LedgerRegistration, LedgerRowContract, LogicalField, PersistLedgerResult } from "../../packages/ledger-file-writer/src/index";
import { readLedgerParquet } from "../../services/feed-ingest-plan/src/read-ledger-history/read-parquet";
import { readPlannerParquet } from "../../services/feed-ingest-plan/src/read-ledger-history/read-planner-parquet";
import { plannerRecordings } from "../../packages/ledger-file-writer/test/planner-recordings";
import { RelativePathSchema } from "../../services/feed-ingest-plan/src/config/service-settings";
import { PlanResponseSchema } from "../../services/feed-ingest-plan/src/api/plan-response.schema";

export const plannerContracts = {
  "discovered-articles": DiscoveredArticleRowContract, "selected-articles": SelectedArticleRowContract,
  "feed-health-state": FeedHealthStateRowContract, "plan-runs": PlanRunRowContract,
};
export type PlannerLedger = keyof typeof plannerContracts;
export function validateLedgerFilePath(path: string, fileId: string, covers: string, registration: LedgerRegistration) {
  DateStampSchema.parse(covers);
  const name = z.enum(["discovered-articles", "selected-articles", "feed-health-state", "plan-runs"]).parse(registration.name);
  if (registration.family !== "feed-ingest-plan" || registration.prefix.join("/") !== `feed-ingest-plan/${name}`
    || !/^[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(fileId)
    || path !== `raw/feed-ingest-plan/${name}/${covers.replaceAll("-", "/")}/${fileId}.parquet`) {
    throw new Error("Planner output path differs from its registered current identity");
  }
  return path;
}
export async function verifyParquetFiles(
  root: string, ledger: PlannerLedger, written: PersistLedgerResult, registration: LedgerRegistration,
  expectedRows?: readonly object[],
) {
  if (registration.name !== ledger) throw new Error("Planner receipt names a different ledger");
  if (written.status === "skipped") throw new Error("Required planner write was skipped");
  if (written.status === "empty") {
    if (written.files.length || (expectedRows !== undefined && expectedRows.length)) throw new Error("Explicit empty write has no rows or files");
    return { row_count: 0, rows: [] as object[], files: [] as string[] };
  }
  const rows: object[] = [];
  const files: string[] = [];
  const localRoot = await realpath(root);
  for (const file of written.files) {
    const path = validateLedgerFilePath(file.path, file.file_id, file.covers, registration);
    if (files.includes(path) || file.unit_id !== undefined) throw new Error("Planner receipt repeats a file or injects generic unit identity");
    const actualPath = await realpath(resolve(localRoot, ...path.split("/")));
    const local = relative(localRoot, actualPath);
    if (isAbsolute(local) || local === ".." || local.startsWith(`..\\`) || local.startsWith("../")) throw new Error("Planner file escapes its output root");
    const contract: LedgerRowContract<object> = plannerContracts[ledger];
    const actual = await readPlannerParquet(actualPath, ledger, contract);
    if (actual.envelope.tier !== "raw" || actual.envelope.file_id !== file.file_id
      || actual.envelope.covers !== file.covers || actual.envelope.content_sha256 !== file.content_sha256
      || actual.rows.length !== file.row_count) throw new Error("Planner receipt differs from native file readback");
    rows.push(...actual.rows);
    files.push(path);
  }
  if (written.files.length === 0 || (expectedRows !== undefined && !isDeepStrictEqual(rows, expectedRows))) {
    throw new Error("Planner written rows differ from the declared result");
  }
  return { row_count: rows.length, rows, files };
}

export async function verifyPlanningCompletion(
  root: string, raw: unknown, registrations: {
    discovered_articles: LedgerRegistration; selected_articles: LedgerRegistration;
    feed_health_state: LedgerRegistration; plan_runs: LedgerRegistration;
  }, repositoryRoot = resolve(root, ".."),
) {
  const summary = PlanResponseSchema.parse(raw);
  const verified: Partial<Record<PlannerLedger, Awaited<ReturnType<typeof verifyParquetFiles>>>> = {};
  for (const [key, name] of [
    ["discovered_articles", "discovered-articles"], ["selected_articles", "selected-articles"],
    ["feed_health_state", "feed-health-state"], ["plan_runs", "plan-runs"],
  ] as const) {
    const files = summary.files[key];
    if (files !== undefined) verified[name] = await verifyParquetFiles(root, name, files, registrations[key]);
    else if (summary.planning_complete) throw new Error("Completed planner run lacks an explicit ledger result");
  }
  const run = verified["plan-runs"]?.rows.map(row => PlanRunRowContract.schema.parse(row));
  const expectedRun = PlanRunRowContract.schema.parse(Object.fromEntries(Object.keys(PlanRunRowContract.schema.shape)
    .map(key => [key, summary[key as keyof typeof summary]])));
  if (run?.length !== 1 || !isDeepStrictEqual(run[0], expectedRun)) {
    throw new Error("Planner response differs from its explicit native run outcome");
  }
  const selected = (verified["selected-articles"]?.rows ?? []).map(row => SelectedArticleRowContract.schema.parse(row));
  if (summary.planning_complete && selected.length !== summary.selected_count) throw new Error("Selected file does not match the completed run count");
  if (summary.selected_articles_artifact !== null) {
    const path = resolve(repositoryRoot, RelativePathSchema.parse(summary.selected_articles_artifact));
    const local = relative(await realpath(repositoryRoot), await realpath(path));
    if (isAbsolute(local) || local === ".." || local.startsWith(`..\\`) || local.startsWith("../")) throw new Error("Selected artifact escapes its repository");
    const artifact = SelectedArticlesArtifactSchema.parse(JSON.parse(await readFile(path, "utf8")));
    if (artifact.run_id !== summary.run_id || artifact.attempt !== summary.attempt || artifact.date !== summary.date
      || artifact.evaluated_at !== summary.evaluated_at || artifact.articles.length !== summary.selected_count) {
      throw new Error("Selected artifact header or count differs from its run");
    }
    const expected = artifact.articles.map(article => ({
      ...selectedArticleMetadata(article), run_id: artifact.run_id, attempt: artifact.attempt, date: artifact.date,
    }));
    if (selected.length && !isDeepStrictEqual(selected, expected)) throw new Error("Artifact and committed allowlisted projection differ");
    if (!isDeepStrictEqual(artifact.articles.map(article => article.url_key), summary.selected_url_keys)) {
      throw new Error("Artifact order differs from the selected response");
    }
    if (!isDeepStrictEqual(artifact.articles.map(({ url_key, editorial_rank, worker_assignment }) =>
      ({ url_key, editorial_rank, worker_assignment })), summary.assignments)) throw new Error("Artifact worker assignments differ from the selected response");
  } else if (summary.planning_complete) throw new Error("Completed planner run lacks its selected artifact");
  return verified;
}

export async function verifyRecordedCompatibility() {
  const seenSchema = z.strictObject({
    version: SchemaVersionSchema, url_key: Sha256Schema,
    first_seen_at: TimestampSchema, first_seen_run: RunIdSchema,
  });
  const legacySeen = await readLedgerParquet(
    fileURLToPath(new URL("../../tests/fixtures/ledger-file-writer/legacy-seen-day.parquet", import.meta.url)),
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
    return { status: "verified", canonical_content_sha256: reading, planner_row_count: count, legacy_seen_row_count: legacySeen.rows.length };
  } finally { await rm(directory, { recursive: true, force: true }); }
}
if (import.meta.main) console.log(JSON.stringify(await verifyRecordedCompatibility()));
