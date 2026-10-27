/** What one current planner Parquet file proves about its rows and writer. */
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import { DataType, tableFromIPC } from "apache-arrow";
import type { Field } from "apache-arrow";
import initializeParquet, { readMetadata, readParquet } from "parquet-wasm/esm";
import {
  PlannerFileEnvelopeSchema, PLANNER_FOOTER_METADATA_KEYS, PLANNER_OPTIONAL_FOOTER_METADATA_KEYS,
} from "@idhazh/common-contracts";
import type { PlannerFileEnvelope } from "@idhazh/common-contracts";
import { describeObjectSchema } from "./row-schema";
import { digestRows } from "./parquet/row-digest";
import type { LedgerRowContract } from "./ledger-types";
import type { LogicalField, LogicalType } from "./parquet/row-digest";

let initialization: ReturnType<typeof initializeParquet> | undefined;

export class PlannerLedgerFileError extends Error {
  override readonly name = "PlannerLedgerFileError";
}

function normalize(value: unknown): unknown {
  if (typeof value === "bigint") {
    const number = Number(value);
    if (!Number.isSafeInteger(number)) throw new PlannerLedgerFileError("Planner Parquet integer exceeds the safe numeric range");
    return number;
  }
  if (Array.isArray(value)) return value.map(normalize);
  if (typeof value !== "object" || value === null) return value;
  if ("toJSON" in value && typeof value.toJSON === "function") return normalize(value.toJSON());
  return Object.fromEntries(Object.entries(value).map(([key, cell]) => [key, normalize(cell)]));
}

function checkType(field: Field, expected: LogicalType): void {
  const type = field.type;
  if (field.nullable !== expected.nullable) throw new PlannerLedgerFileError(`Planner Arrow nullability differs at ${field.name}`);
  if (expected.kind === "struct" && DataType.isStruct(type) && expected.fields !== undefined) {
    checkFields(type.children, expected.fields);
  } else if (expected.kind === "list" && DataType.isList(type) && expected.itemType !== undefined) {
    checkType(type.children[0]!, { ...expected.itemType, nullable: expected.itemNullable ?? false });
  } else if (!(expected.kind === "scalar" && (
    (expected.scalar === "string" && DataType.isUtf8(type))
    || (expected.scalar === "int64" && DataType.isInt(type) && type.bitWidth === 64 && type.isSigned)
    || (expected.scalar === "float64" && DataType.isFloat(type) && type.precision === 2)
    || (expected.scalar === "bool" && DataType.isBool(type))
  ))) throw new PlannerLedgerFileError(`Planner Arrow type differs at ${field.name}`);
}

function checkFields(fields: readonly Field[], expected: readonly LogicalField[]): void {
  if (fields.length !== expected.length || new Set(fields.map(field => field.name)).size !== fields.length) {
    throw new PlannerLedgerFileError("Planner Arrow columns differ from the declared row schema");
  }
  for (const column of expected) {
    const field = fields.find(candidate => candidate.name === column.name);
    if (field === undefined) throw new PlannerLedgerFileError(`Planner Arrow column is missing ${column.name}`);
    checkType(field, column.type);
  }
}

function parseContainer<T>(read: () => T): T {
  try { return read(); }
  catch (error) {
    if (error instanceof Error && (error.message.startsWith("Parquet error:") || error.message.startsWith("EOF:"))) {
      throw new PlannerLedgerFileError("Planner Parquet container is malformed", { cause: error });
    }
    throw error;
  }
}

export async function readPlannerParquet<T extends object>(
  path: string, ledger: PlannerFileEnvelope["ledger"], contract: LedgerRowContract<T>,
) {
  initialization ??= initializeParquet();
  await initialization;
  const bytes = await readFile(path);
  const metadata = parseContainer(() => readMetadata(bytes));
  const footer = metadata.fileMetadata();
  let envelope: PlannerFileEnvelope;
  try {
    const values = footer.keyValueMetadata();
    const permitted = new Set<string>([...PLANNER_FOOTER_METADATA_KEYS, "ARROW:schema"]);
    if ([...values].some(([key, value]) => typeof key !== "string" || typeof value !== "string" || !permitted.has(key))) {
      throw new PlannerLedgerFileError("Planner footer contains an undeclared key or value");
    }
    for (const key of PLANNER_FOOTER_METADATA_KEYS) {
      if (!(PLANNER_OPTIONAL_FOOTER_METADATA_KEYS as readonly string[]).includes(key) && !values.has(key)) {
        throw new PlannerLedgerFileError(`Planner footer is missing ${key}`);
      }
    }
    const footerLedger = values.get("ledger");
    const rowSchemaVersion = values.get("schema_version");
    if (footerLedger === ledger && rowSchemaVersion !== contract.schemaVersion) {
      throw new PlannerLedgerFileError(
        `Planner ${ledger} uses an unsupported row schema; current ledger contract requires ${contract.schemaVersion}`,
      );
    }
    envelope = PlannerFileEnvelopeSchema.parse({
      version: values.get("envelope_version"), row_schema_version: rowSchemaVersion,
      tier: values.get("tier"), ledger: footerLedger, covers: values.get("covers"),
      period: values.get("period") ?? null, file_id: values.get("file_id"),
      content_sha256: values.get("content_sha256"), writer: values.get("writer"),
      writer_version: values.get("writer_version"), compression: values.get("compression"),
      updated_at: values.get("updated_at") ?? null,
    });
  } finally { footer.free(); metadata.free(); }
  if (envelope.ledger !== ledger || envelope.row_schema_version !== contract.schemaVersion) {
    throw new PlannerLedgerFileError("Planner file does not match its current ledger contract");
  }
  if (envelope.tier === "raw" && basename(path) !== `${envelope.file_id}.parquet`) {
    throw new PlannerLedgerFileError("Planner raw filename differs from its file identity");
  }
  const table = tableFromIPC(parseContainer(() => readParquet(bytes)).intoIPCStream());
  const columns = describeObjectSchema(contract.schema).fields;
  checkFields(table.schema.fields, columns);
  const records = table.toArray().map(value => {
    const row = normalize(value);
    if (typeof row !== "object" || row === null || Array.isArray(row)) throw new PlannerLedgerFileError("Planner row must be an object");
    return row as Record<string, unknown>;
  });
  if (digestRows(records, columns) !== envelope.content_sha256) {
    throw new PlannerLedgerFileError("Planner row digest differs from its footer");
  }
  const rows = records.map(record => contract.schema.parse(record));
  return {
    envelope, rows, bytes: bytes.byteLength,
    file_sha256: createHash("sha256").update(bytes).digest("hex"),
  };
}
