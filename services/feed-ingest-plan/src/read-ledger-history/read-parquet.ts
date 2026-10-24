/** Do one named Parquet file's schema, rows, digest and original identities agree? */
import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import { DataType, tableFromIPC } from "apache-arrow";
import type { Field } from "apache-arrow";
import initializeParquet, { readMetadata, readParquet } from "parquet-wasm/esm";
import {
  FileEnvelopeSchema, FOOTER_METADATA_KEYS, OPTIONAL_FOOTER_METADATA_KEYS, RowIdentitySchema, SchemaVersionSchema,
  validateEnvelopeContainer,
} from "@idhazh/common-contracts";
import type { FileEnvelope, RowIdentity } from "@idhazh/common-contracts";
import {
  appendIdentityColumns, createFileId, createUnitId, describeObjectSchema, digestRows,
} from "@idhazh/ledger-file-writer";
import type { LedgerRowContract, LogicalField, LogicalType, StoredLedgerRow } from "@idhazh/ledger-file-writer";
import type { z } from "zod";
import { LedgerHistoryReadError } from "./ledger-history-error";

let initialization: ReturnType<typeof initializeParquet> | undefined;
export type ReadLedgerFile<T extends object> = Readonly<{
  envelope: FileEnvelope;
  rows: readonly StoredLedgerRow<T>[];
  bytes: number;
}>;
export type LedgerRowProjectionContract<T extends object> = Readonly<{
  schema: z.ZodType<T>;
  schemaVersion: string;
  projectedFields: readonly string[];
}>;

function normalize(value: unknown): unknown {
  if (typeof value === "bigint") {
    const number = Number(value);
    if (!Number.isSafeInteger(number)) throw new LedgerHistoryReadError("Ledger integer exceeds the safe numeric range");
    return number;
  }
  if (Array.isArray(value)) return value.map(normalize);
  if (typeof value !== "object" || value === null) return value;
  if ("toJSON" in value && typeof value.toJSON === "function") return normalize(value.toJSON());
  return Object.fromEntries(Object.entries(value).map(([key, cell]) => [key, normalize(cell)]));
}

function checkType(field: Field, expected: LogicalType): void {
  const type = field.type;
  if (field.nullable !== expected.nullable) throw new LedgerHistoryReadError(`Arrow nullability differs at ${field.name}`);
  if (expected.kind === "struct" && DataType.isStruct(type) && expected.fields !== undefined) {
    checkFields(type.children, expected.fields);
  } else if (expected.kind === "list" && DataType.isList(type) && expected.itemType !== undefined) {
    checkType(type.children[0]!, { ...expected.itemType, nullable: expected.itemNullable ?? false });
  } else if (!(expected.kind === "scalar" && (
    (expected.scalar === "string" && DataType.isUtf8(type))
    || (expected.scalar === "int64" && DataType.isInt(type) && type.bitWidth === 64 && type.isSigned)
    || (expected.scalar === "float64" && DataType.isFloat(type) && type.precision === 2)
    || (expected.scalar === "bool" && DataType.isBool(type))
  ))) throw new LedgerHistoryReadError(`Arrow type differs at ${field.name}`);
}
function checkFields(fields: readonly Field[], expected: readonly LogicalField[]): void {
  if (fields.length !== expected.length || new Set(fields.map(field => field.name)).size !== fields.length) {
    throw new LedgerHistoryReadError(`Arrow columns differ from the declared stored schema: expected ${expected.map(field => field.name).join(",")}; received ${fields.map(field => field.name).join(",")}`);
  }
  for (const column of expected) {
    const field = fields.find(field => field.name === column.name);
    if (field === undefined) throw new LedgerHistoryReadError(`Missing Arrow column ${column.name}`);
    checkType(field, column.type);
  }
}
function logicalField(field: Field): LogicalField {
  const type = field.type;
  let logical: LogicalType;
  if (DataType.isStruct(type)) {
    logical = { kind: "struct", nullable: field.nullable, fields: type.children.map(logicalField) };
  } else if (DataType.isList(type)) {
    const child = type.children[0];
    if (child === undefined) throw new LedgerHistoryReadError(`Arrow list has no item field at ${field.name}`);
    const item = logicalField(child);
    logical = { kind: "list", nullable: field.nullable, itemType: item.type, itemNullable: child.nullable };
  } else if (DataType.isUtf8(type)) {
    logical = { kind: "scalar", scalar: "string", nullable: field.nullable };
  } else if (DataType.isInt(type) && type.bitWidth === 64 && type.isSigned) {
    logical = { kind: "scalar", scalar: "int64", nullable: field.nullable };
  } else if (DataType.isFloat(type) && type.precision === 2) {
    logical = { kind: "scalar", scalar: "float64", nullable: field.nullable };
  } else if (DataType.isBool(type)) {
    logical = { kind: "scalar", scalar: "bool", nullable: field.nullable };
  } else {
    throw new LedgerHistoryReadError(`Unsupported Arrow type at ${field.name}`);
  }
  return { name: field.name, type: logical, nullable: field.nullable };
}
function readEnvelope(metadata: Map<unknown, unknown>): FileEnvelope {
  const values = new Map<string, string>();
  for (const [key, value] of metadata) {
    if (typeof key !== "string" || typeof value !== "string") throw new LedgerHistoryReadError("Parquet metadata must contain string pairs");
    values.set(key, value);
  }
  for (const key of FOOTER_METADATA_KEYS) {
    if (!(OPTIONAL_FOOTER_METADATA_KEYS as readonly string[]).includes(key) && !values.has(key)) {
      throw new LedgerHistoryReadError(`Missing Parquet envelope key ${key}`);
    }
  }
  const number = (key: string): number => {
    const text = values.get(key);
    if (text === undefined || !/^\d+$/.test(text) || !Number.isSafeInteger(Number(text))) {
      throw new LedgerHistoryReadError(`Invalid Parquet envelope integer ${key}`);
    }
    return Number(text);
  };
  const envelope = FileEnvelopeSchema.parse({
    version: values.get("envelope_version"), row_schema_version: values.get("schema_version"),
    tier: values.get("tier"), ledger: values.get("ledger"), covers: values.get("covers"),
    period: values.get("period") ?? null, written_at_ms: number("written_at_ms"),
    identity: {
      run_id: values.get("run_id"), attempt: number("attempt"), job: values.get("job") ?? null,
      pipeline_name: values.get("pipeline_name") ?? null, task_name: values.get("task_name") ?? null,
      shard: number("shard"), producer: values.get("producer"), git_sha: values.get("git_sha"),
    },
    unit_id: values.get("unit_id"), file_id: values.get("file_id"),
    content_sha256: values.get("content_sha256"), writer: values.get("writer"),
    writer_version: values.get("writer_version"), compression: values.get("compression"),
    built_from: values.has("built_from") ? number("built_from") : null,
  });
  try {
    return validateEnvelopeContainer(envelope, "parquet");
  } catch (error) {
    if (error instanceof Error && error.message === "writer does not match the observed container") {
      throw new LedgerHistoryReadError(error.message, { cause: error });
    }
    throw error;
  }
}
function parseParquet<T>(read: () => T): T {
  try {
    return read();
  } catch (error) {
    if (error instanceof Error && (error.message.startsWith("Parquet error: ") || error.message.startsWith("EOF: "))) {
      throw new LedgerHistoryReadError(error.message, { cause: error });
    }
    throw error;
  }
}
export async function readLedgerParquet<T extends object>(
  path: string, ledger: RowIdentity["ledger"], contract: LedgerRowContract<T> | LedgerRowProjectionContract<T>,
): Promise<ReadLedgerFile<T>> {
  initialization ??= initializeParquet();
  await initialization;
  const bytes = await readFile(path);
  const metadata = parseParquet(() => readMetadata(bytes));
  let envelope: FileEnvelope;
  const fileMetadata = metadata.fileMetadata();
  try {
    envelope = readEnvelope(fileMetadata.keyValueMetadata());
  } finally {
    fileMetadata.free();
    metadata.free();
  }
  if (envelope.ledger !== ledger) {
    throw new LedgerHistoryReadError("Parquet ledger differs from the requested contract");
  }
  const projectionContract = "projectedFields" in contract ? contract : undefined;
  const legacy = projectionContract !== undefined || envelope.row_schema_version === contract.schemaVersion
    ? undefined : "legacyVersions" in contract ? contract.legacyVersions?.[envelope.row_schema_version] : undefined;
  if (projectionContract !== undefined) {
    if (SchemaVersionSchema.parse(envelope.row_schema_version) > projectionContract.schemaVersion) {
      throw new LedgerHistoryReadError("Parquet projection schema is newer than its declared fields");
    }
  } else if (envelope.row_schema_version !== contract.schemaVersion && legacy === undefined) {
    throw new LedgerHistoryReadError("Parquet row schema version differs from the requested contract");
  }
  const storedSchema = legacy?.schema ?? contract.schema;
  const writer = envelope.identity;
  const unit = createUnitId({
    ledger, covers: envelope.covers, runId: writer.run_id, job: writer.job,
    pipelineName: writer.pipeline_name, taskName: writer.task_name, shard: writer.shard, producer: writer.producer,
  });
  if (unit !== envelope.unit_id || createFileId({
    unit, attempt: writer.attempt, writtenAtMs: envelope.written_at_ms,
  }) !== envelope.file_id) throw new LedgerHistoryReadError("Parquet file or unit identifier differs from its writer");
  if (envelope.tier === "raw" && basename(path) !== `${envelope.file_id}.parquet`) {
    throw new LedgerHistoryReadError("Raw filename differs from its envelope file identifier");
  }
  const table = tableFromIPC(parseParquet(() => readParquet(bytes)).intoIPCStream());
  const columns = projectionContract !== undefined ? table.schema.fields.map(logicalField)
    : appendIdentityColumns(describeObjectSchema(storedSchema).fields, envelope.version);
  if (projectionContract === undefined) checkFields(table.schema.fields, columns);
  else {
    const described = describeObjectSchema(projectionContract.schema).fields;
    const actual = new Map(table.schema.fields.map(field => [field.name, field]));
    for (const identity of appendIdentityColumns([], envelope.version)) {
      const field = actual.get(identity.name);
      if (field === undefined) throw new LedgerHistoryReadError(`Missing Arrow identity column ${identity.name}`);
      checkType(field, identity.type);
    }
    for (const projected of described) {
      const field = actual.get(projected.name);
      if (field === undefined) throw new LedgerHistoryReadError(`Missing Arrow projection column ${projected.name}`);
      checkType(field, projected.type);
    }
  }
  const records = table.toArray().map(value => {
    const record = normalize(value);
    if (typeof record !== "object" || record === null || Array.isArray(record)) throw new LedgerHistoryReadError("Stored row is not an object");
    return record as Record<string, unknown>;
  });
  if (digestRows(records, columns) !== envelope.content_sha256) throw new LedgerHistoryReadError("Parquet content digest differs from its rows");
  const rowFields = Object.keys(describeObjectSchema(storedSchema).root.properties as Record<string, unknown>);
  const rows = records.map(record => {
    const identity = RowIdentitySchema.parse(Object.fromEntries(
      Object.keys(RowIdentitySchema.shape).map(key => [key, record[key]]),
    ));
    if (identity.ledger !== ledger || !(identity.covers === envelope.covers
      || (envelope.tier === "compact" && identity.covers.startsWith(`${envelope.covers}-`)))) {
      throw new LedgerHistoryReadError("Stored row belongs to another ledger or period");
    }
    if (envelope.tier === "raw" && (identity.unit_id !== envelope.unit_id
      || identity.run_id !== writer.run_id || identity.attempt !== writer.attempt
      || identity.job !== writer.job || identity.pipeline_name !== writer.pipeline_name
      || identity.task_name !== writer.task_name || identity.shard !== writer.shard)) {
      throw new LedgerHistoryReadError("Raw row identity differs from its writer envelope");
    }
    const storedRow = projectionContract === undefined
      ? storedSchema.parse(Object.fromEntries(rowFields.map(key => [key, record[key]]))) : undefined;
    const projectedRow = projectionContract !== undefined
      ? Object.fromEntries(projectionContract.projectedFields.map(key => [key, record[key]]))
      : storedRow;
    if (projectedRow === undefined) throw new Error("Ledger projection did not produce a row");
    if (projectionContract === undefined && storedRow === undefined) throw new Error("Stored ledger row was not parsed");
    const row = projectionContract !== undefined ? projectionContract.schema.parse(projectedRow)
      : contract.schema.parse(legacy === undefined ? storedRow : legacy.migrate(storedRow!));
    return { identity, row };
  });
  return { envelope, rows, bytes: bytes.byteLength };
}
