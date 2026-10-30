/** What one planner Parquet file proves before a consumer validates its fields. */
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import { DataType, tableFromIPC } from "apache-arrow";
import type { Field } from "apache-arrow";
import initializeParquet, { readMetadata, readParquet } from "parquet-wasm/esm";
import {
  PlannerFileEnvelopeSchema, PlannerStoredFileEnvelopeSchema, PLANNER_FOOTER_METADATA_KEYS, PLANNER_OPTIONAL_FOOTER_METADATA_KEYS,
} from "@idhazh/common-contracts";
import type { PlannerStoredFileEnvelope } from "@idhazh/common-contracts";
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

function storedFields(fields: readonly Field[]): LogicalField[] {
  if (new Set(fields.map(field => field.name)).size !== fields.length) {
    throw new PlannerLedgerFileError("Planner Arrow columns repeat a name");
  }
  return fields.map(field => {
    const arrow = field.type;
    let type: LogicalType;
    if (DataType.isStruct(arrow)) {
      type = { kind: "struct", nullable: field.nullable, fields: storedFields(arrow.children) };
    } else if (DataType.isList(arrow) && arrow.children.length === 1) {
      const item = storedFields(arrow.children)[0]!;
      type = { kind: "list", nullable: field.nullable, itemType: item.type, itemNullable: item.nullable };
    } else {
      const scalar = DataType.isUtf8(arrow) ? "string"
        : DataType.isInt(arrow) ? "int64"
        : DataType.isFloat(arrow) ? "float64"
        : DataType.isBool(arrow) ? "bool" : null;
      if (scalar === null) throw new PlannerLedgerFileError(`Planner Arrow column has an unsupported stored type at ${field.name}`);
      type = { kind: "scalar", scalar, nullable: field.nullable };
    }
    return { name: field.name, nullable: field.nullable, type };
  });
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

async function loadStoredPlannerParquet(path: string, ledger: PlannerStoredFileEnvelope["ledger"]) {
  initialization ??= initializeParquet();
  await initialization;
  const bytes = await readFile(path);
  const metadata = parseContainer(() => readMetadata(bytes));
  const footer = metadata.fileMetadata();
  let envelope: PlannerStoredFileEnvelope;
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
    envelope = PlannerStoredFileEnvelopeSchema.parse({
      version: values.get("envelope_version"), row_schema_version: rowSchemaVersion,
      tier: values.get("tier"), ledger: footerLedger, covers: values.get("covers"),
      period: values.get("period") ?? null, file_id: values.get("file_id"),
      content_sha256: values.get("content_sha256"), writer: values.get("writer"),
      writer_version: values.get("writer_version"), compression: values.get("compression"),
      updated_at: values.get("updated_at") ?? null,
    });
  } finally { footer.free(); metadata.free(); }
  if (envelope.ledger !== ledger) {
    throw new PlannerLedgerFileError("Planner file does not match its registered ledger");
  }
  if (envelope.tier === "raw" && basename(path) !== `${envelope.file_id}.parquet`) {
    throw new PlannerLedgerFileError("Planner raw filename differs from its file identity");
  }
  const table = tableFromIPC(parseContainer(() => readParquet(bytes)).intoIPCStream());
  const columns = storedFields(table.schema.fields);
  const records = table.toArray().map(value => {
    const row = normalize(value);
    if (typeof row !== "object" || row === null || Array.isArray(row)) throw new PlannerLedgerFileError("Planner row must be an object");
    return row as Record<string, unknown>;
  });
  let digest: string;
  try { digest = digestRows(records, columns); }
  catch (error) {
    if (!(error instanceof TypeError)) throw error;
    throw new PlannerLedgerFileError("Planner stored values cannot reproduce their row digest", { cause: error });
  }
  if (digest !== envelope.content_sha256) {
    throw new PlannerLedgerFileError("Planner row digest differs from its footer");
  }
  return {
    envelope, rows: records, fields: table.schema.fields, bytes: bytes.byteLength,
    file_sha256: createHash("sha256").update(bytes).digest("hex"),
  };
}

export async function readStoredPlannerParquet(path: string, ledger: PlannerStoredFileEnvelope["ledger"]) {
  const { fields, ...stored } = await loadStoredPlannerParquet(path, ledger);
  return stored;
}

export async function readPlannerParquet<T extends object>(
  path: string, ledger: PlannerStoredFileEnvelope["ledger"], contract: LedgerRowContract<T>,
) {
  const { fields, ...stored } = await loadStoredPlannerParquet(path, ledger);
  const accepted = contract.acceptedSchemaVersions ?? [contract.schemaVersion];
  if (!accepted.includes(stored.envelope.row_schema_version)) {
    throw new PlannerLedgerFileError(
      `Planner ${ledger} uses an unsupported row schema; accepted ledger contract versions are ${accepted.join(", ")}`,
    );
  }
  const envelope = PlannerFileEnvelopeSchema.parse(stored.envelope);
  checkFields(fields, describeObjectSchema(contract.schema).fields);
  return { ...stored, envelope, rows: stored.rows.map(row => contract.schema.parse(row)) };
}
