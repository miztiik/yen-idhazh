/** Converts declared contract fields and stored rows into a typed Arrow table. */
import { Bool, BufferType, Field, Float64, Int64, List, RecordBatch, Schema, Struct, Table, Utf8, Vector, vectorFromArray } from "apache-arrow";
import type { Data, DataType } from "apache-arrow";
import type { LogicalField, LogicalType, ScalarKind } from "./row-digest.ts";

export type ArrowColumn = LogicalField;

function toScalarType(scalar: ScalarKind): DataType {
  switch (scalar) {
    case "string": return new Utf8();
    case "int64": return new Int64();
    case "float64": return new Float64();
    case "bool": return new Bool();
  }
}

function toArrowType(type: LogicalType, name: string): DataType {
  if (type.kind === "scalar") {
    if (type.scalar === undefined) throw new TypeError(`${name} has no scalar type`);
    return toScalarType(type.scalar);
  }
  if (type.kind === "list") {
    if (type.itemType === undefined) throw new TypeError(`${name} has no list item type`);
    return new List(new Field("item", toArrowType(type.itemType, `${name}[]`), type.itemNullable ?? false));
  }
  if (type.kind === "struct") {
    if (type.fields === undefined) throw new TypeError(`${name} has no struct fields`);
    return new Struct(type.fields.map((field) =>
      new Field(field.name, toArrowType(field.type, `${name}.${field.name}`), field.nullable),
    ));
  }
  throw new TypeError(`${name} has an unsupported Arrow type`);
}

function toArrowValue(value: unknown, type: LogicalType, name: string): unknown {
  if (value === null) return null;
  if (type.kind === "scalar") {
    if (type.scalar === "int64") {
      if (typeof value !== "number" || !Number.isSafeInteger(value)) {
        throw new TypeError(`${name} must be a safe integer for the Arrow int64 column`);
      }
      return BigInt(value);
    }
    return value;
  }
  if (type.kind === "list") {
    if (!Array.isArray(value) || type.itemType === undefined) throw new TypeError(`${name} is not a list`);
    return value.map((item, index) => toArrowValue(item, type.itemType!, `${name}[${index}]`));
  }
  if (type.kind === "struct") {
    if (typeof value !== "object" || value === null || Array.isArray(value) || type.fields === undefined) {
      throw new TypeError(`${name} is not an object`);
    }
    const record = value as Record<string, unknown>;
    return Object.fromEntries(type.fields.map((field) => [
      field.name,
      toArrowValue(record[field.name], field.type, `${name}.${field.name}`),
    ]));
  }
  throw new TypeError(`${name} has an unsupported Arrow value`);
}

function completeNullBitmaps(data: Data): Data {
  const buffers = data.buffers;
  buffers[BufferType.VALIDITY] ??= new Uint8Array(0);
  return data.clone(
    data.type,
    data.offset,
    data.length,
    data.nullCount,
    buffers,
    data.children.map(completeNullBitmaps),
  );
}

export function buildArrowTable(
  columns: readonly ArrowColumn[],
  rows: readonly Record<string, unknown>[],
): Table {
  const schema = new Schema(columns.map((column) =>
    new Field(column.name, toArrowType(column.type, column.name), column.nullable),
  ));
  const vectors: Record<string, Vector> = Object.fromEntries(columns.map((column) => {
    const type = toArrowType(column.type, column.name);
    const values = rows.map((row) => toArrowValue(row[column.name], column.type, column.name));
    return [column.name, vectorFromArray(values.length === 0 ? [null] : values, type).slice(0, values.length)];
  }));
  const data = Object.fromEntries(columns.map((column) => {
    const child = vectors[column.name]?.data[0];
    if (child === undefined) throw new TypeError(`${column.name} did not produce an Arrow data buffer`);
    return [column.name, completeNullBitmaps(child)];
  }));
  const inferred = new RecordBatch(data);
  return new Table(schema, new RecordBatch(schema, inferred.data));
}
