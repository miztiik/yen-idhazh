/** What do the decoded Parquet columns and their row digest prove? */
import { DataType, tableFromIPC } from "apache-arrow";
import type { Field } from "apache-arrow";
import { readMetadata, readParquet } from "parquet-wasm/esm";
import { digestRows } from "./row-digest";
import type { LogicalField, LogicalType } from "./row-digest";

type FileError = (message: string, cause?: unknown) => Error;

function normalize(value: unknown, failure: FileError): unknown {
  if (typeof value === "bigint") {
    const number = Number(value);
    if (!Number.isSafeInteger(number)) throw failure("Parquet integer exceeds the safe numeric range");
    return number;
  }
  if (Array.isArray(value)) return value.map(cell => normalize(cell, failure));
  if (typeof value !== "object" || value === null) return value;
  if ("toJSON" in value && typeof value.toJSON === "function") return normalize(value.toJSON(), failure);
  return Object.fromEntries(Object.entries(value).map(([key, cell]) => [key, normalize(cell, failure)]));
}

function checkType(field: Field, expected: LogicalType, failure: FileError): void {
  const type = field.type;
  if (field.nullable !== expected.nullable) throw failure(`Arrow nullability differs at ${field.name}`);
  if (expected.kind === "struct" && DataType.isStruct(type) && expected.fields !== undefined) {
    checkParquetFields(type.children, expected.fields, failure);
  } else if (expected.kind === "list" && DataType.isList(type) && expected.itemType !== undefined) {
    checkType(type.children[0]!, { ...expected.itemType, nullable: expected.itemNullable ?? false }, failure);
  } else if (!(expected.kind === "scalar" && (
    (expected.scalar === "string" && DataType.isUtf8(type))
    || (expected.scalar === "int64" && DataType.isInt(type) && type.bitWidth === 64 && type.isSigned)
    || (expected.scalar === "float64" && DataType.isFloat(type) && type.precision === 2)
    || (expected.scalar === "bool" && DataType.isBool(type))
  ))) throw failure(`Arrow type differs at ${field.name}`);
}

export function checkParquetFields(fields: readonly Field[], expected: readonly LogicalField[], failure: FileError): void {
  if (fields.length !== expected.length || new Set(fields.map(field => field.name)).size !== fields.length) {
    throw failure("Arrow columns differ from the declared row schema");
  }
  for (const column of expected) {
    const field = fields.find(candidate => candidate.name === column.name);
    if (field === undefined) throw failure(`Arrow column is missing ${column.name}`);
    checkType(field, column.type, failure);
  }
}

function storedFields(fields: readonly Field[], failure: FileError): LogicalField[] {
  if (new Set(fields.map(field => field.name)).size !== fields.length) throw failure("Arrow columns repeat a name");
  return fields.map(field => {
    const arrow = field.type;
    let type: LogicalType;
    if (DataType.isStruct(arrow)) {
      type = { kind: "struct", nullable: field.nullable, fields: storedFields(arrow.children, failure) };
    } else if (DataType.isList(arrow) && arrow.children.length === 1) {
      const item = storedFields(arrow.children, failure)[0]!;
      type = { kind: "list", nullable: field.nullable, itemType: item.type, itemNullable: item.nullable };
    } else {
      const scalar = DataType.isUtf8(arrow) ? "string"
        : DataType.isInt(arrow) ? "int64"
        : DataType.isFloat(arrow) ? "float64"
        : DataType.isBool(arrow) ? "bool" : null;
      if (scalar === null) throw failure(`Arrow column has an unsupported stored type at ${field.name}`);
      type = { kind: "scalar", scalar, nullable: field.nullable };
    }
    return { name: field.name, nullable: field.nullable, type };
  });
}

function parseContainer<T>(read: () => T, failure: FileError): T {
  try { return read(); }
  catch (error) {
    if (error instanceof Error && (error.message.startsWith("Parquet error:") || error.message.startsWith("EOF:"))) {
      throw failure("Parquet container is malformed", error);
    }
    throw error;
  }
}

export function readParquetFooter(bytes: Uint8Array, required: readonly string[], optional: readonly string[], failure: FileError) {
  const metadata = parseContainer(() => readMetadata(bytes), failure);
  const footer = metadata.fileMetadata();
  try {
    const values = footer.keyValueMetadata();
    const permitted = new Set([...required, "ARROW:schema"]);
    for (const [key, value] of values) {
      if (typeof key !== "string" || typeof value !== "string" || !permitted.has(key)) {
        throw failure("footer contains an undeclared key or value");
      }
    }
    for (const key of required) {
      if (!optional.includes(key) && !values.has(key)) throw failure(`footer is missing ${key}`);
    }
    return values;
  } finally { footer.free(); metadata.free(); }
}

export function readVerifiedParquetRows(bytes: Uint8Array, expectedDigest: string, failure: FileError) {
  const table = tableFromIPC(parseContainer(() => readParquet(bytes), failure).intoIPCStream());
  const columns = storedFields(table.schema.fields, failure);
  const records = table.toArray().map(value => {
    const row = normalize(value, failure);
    if (typeof row !== "object" || row === null || Array.isArray(row)) throw failure("row must be an object");
    return row as Record<string, unknown>;
  });
  let digest: string;
  try { digest = digestRows(records, columns); }
  catch (error) {
    if (!(error instanceof TypeError)) throw error;
    throw failure("stored values cannot reproduce their row digest", error);
  }
  if (digest !== expectedDigest) throw failure("row digest differs from its footer");
  return { fields: table.schema.fields, rows: records };
}
