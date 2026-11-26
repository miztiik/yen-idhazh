/** Which verified non-planner Parquet records already exist in one job-local day? */
import { lstat, readFile, readdir, realpath } from "node:fs/promises";
import { join } from "node:path";
import { z } from "zod";
import {
  FileEnvelopeSchema, FOOTER_METADATA_KEYS, OPTIONAL_FOOTER_METADATA_KEYS, RowIdentitySchema, validateEnvelopeContainer,
} from "@idhazh/common-contracts";
import type { FileEnvelope } from "@idhazh/common-contracts";
import { PersistedLedgerFileSchema } from "./ledger-file-receipt";
import { buildRawDayPath, toRelativePath } from "./ledger-paths";
import type { LedgerRegistration, LedgerRowContract, PersistedLedgerFile, StoredLedgerRow } from "./ledger-types";
import { checkParquetFields, readParquetFooter, readVerifiedParquetRows } from "./parquet/read-verified-table";
import { initializeParquetWasm } from "./parquet/wasm-serializer";
import { validatePeriod, validateRegistration } from "./registration";
import { buildIdentityCells } from "./row-identity";
import { appendIdentityColumns, describeObjectSchema } from "./row-schema";
import { createFileId } from "./uuid/file-id";
import { createUnitId } from "./uuid/unit-id";

const RawFileNameSchema = z.uuid({ version: "v8" });
const rawFailure = (message: string, cause?: unknown) => new Error(`Raw ledger ${message}`, { cause });
const decimal = (cell: string | undefined) => cell !== undefined && /^\d+$/.test(cell) ? Number(cell) : undefined;

function readEnvelope(bytes: Uint8Array): FileEnvelope {
  const values = readParquetFooter(bytes, FOOTER_METADATA_KEYS, OPTIONAL_FOOTER_METADATA_KEYS, rawFailure);
  return validateEnvelopeContainer(FileEnvelopeSchema.parse({
    version: values.get("envelope_version"), row_schema_version: values.get("schema_version"),
    tier: values.get("tier"), ledger: values.get("ledger"), covers: values.get("covers"),
    period: values.get("period") ?? null, written_at_ms: decimal(values.get("written_at_ms")),
    identity: {
      run_id: values.get("run_id"), attempt: decimal(values.get("attempt")), job: values.get("job") ?? null,
      pipeline_name: values.get("pipeline_name") ?? null, task_name: values.get("task_name") ?? null,
      shard: decimal(values.get("shard")), producer: values.get("producer"), git_sha: values.get("git_sha"),
    },
    unit_id: values.get("unit_id"), file_id: values.get("file_id"), content_sha256: values.get("content_sha256"),
    writer: values.get("writer"), writer_version: values.get("writer_version"), compression: values.get("compression"),
    built_from: values.has("built_from") ? decimal(values.get("built_from")) : null,
  }), "parquet");
}

async function findPrivateDay(root: string, relativeDay: string): Promise<string | null> {
  try {
    let path = await realpath(root);
    for (const segment of relativeDay.split("/")) {
      path = join(path, segment);
      if (!(await lstat(path)).isDirectory()) throw rawFailure("day is not a regular directory below its root");
    }
    return path;
  } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") return null;
    throw error;
  }
}

export async function* readPrivateRawDay<T extends object>(
  root: string, registration: LedgerRegistration, covers: string,
  contract: LedgerRowContract<T> | LedgerRowContract<T>[],
): AsyncGenerator<{ envelope: FileEnvelope; rows: StoredLedgerRow<T>[]; receipt: PersistedLedgerFile }> {
  const ledger = registration.name;
  validateRegistration(ledger, registration);
  validatePeriod({ tier: "raw", covers });
  const relativeDay = toRelativePath(root, buildRawDayPath(root, registration.prefix, covers));
  const directory = await findPrivateDay(root, relativeDay);
  if (directory === null) return;
  const contracts = Array.isArray(contract) ? contract : [contract];
  const identityNames = Object.keys(RowIdentitySchema.shape);
  await initializeParquetWasm();
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (!entry.name.endsWith(".parquet")) continue; // An atomic write's temporary file is not a completed record.
    const file_id = entry.name.slice(0, -".parquet".length);
    if (!entry.isFile() || file_id !== file_id.toLowerCase() || !RawFileNameSchema.safeParse(file_id).success) {
      throw rawFailure("day contains an invalid Parquet member");
    }
    const bytes = await readFile(join(directory, entry.name));
    const envelope = readEnvelope(bytes);
    const version = contracts.find(known => known.schemaVersion === envelope.row_schema_version);
    const writer = envelope.identity;
    const unit_id = createUnitId({
      ledger, covers, runId: writer.run_id, job: writer.job, pipelineName: writer.pipeline_name,
      taskName: writer.task_name, shard: writer.shard, producer: writer.producer,
    });
    if (envelope.tier !== "raw" || envelope.ledger !== ledger || envelope.covers !== covers
      || version === undefined || envelope.unit_id !== unit_id
      || envelope.file_id !== file_id
      || createFileId({ unit: unit_id, attempt: writer.attempt, writtenAtMs: envelope.written_at_ms }) !== file_id) {
      throw rawFailure("file does not match its declared identity, day and schema");
    }
    const business = describeObjectSchema(version.schema).fields;
    const decoded = readVerifiedParquetRows(bytes, envelope.content_sha256, rawFailure);
    checkParquetFields(decoded.fields, appendIdentityColumns(business, envelope.version), rawFailure);
    const stamped = buildIdentityCells(ledger, covers, writer, unit_id);
    const rows = decoded.rows.map(cells => {
      const identity = RowIdentitySchema.parse(Object.fromEntries(identityNames.map(name => [name, cells[name]])));
      if (Object.entries(stamped).some(([name, value]) => cells[name] !== value)) {
        throw rawFailure("row identity differs from its footer");
      }
      const row = version.schema.parse(Object.fromEntries(business.map(({ name }) => [name, cells[name]])));
      if ("version" in row && row.version !== envelope.row_schema_version) {
        throw rawFailure("row schema stamp differs from its footer");
      }
      return { identity, row };
    });
    yield { envelope, rows, receipt: PersistedLedgerFileSchema.parse({
      path: `${relativeDay}/${entry.name}`, file_id, unit_id, covers,
      content_sha256: envelope.content_sha256, row_count: rows.length,
    }) };
  }
}
