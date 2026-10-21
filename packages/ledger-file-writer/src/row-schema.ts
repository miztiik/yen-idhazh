/** Derives the stored Arrow columns from a row contract's declared JSON Schema. */
import { RowIdentitySchema } from "@idhazh/common-contracts";
import { z } from "zod";
import type { ArrowColumn } from "./parquet/arrow-builder";
import type { LogicalType } from "./parquet/row-digest";

type JsonSchema = { [key: string]: unknown };

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function resolveReference(schema: JsonSchema, root: JsonSchema): JsonSchema {
  if (typeof schema.$ref !== "string") return schema;
  const segments = schema.$ref.replace(/^#\//, "").split("/").map((segment) =>
    segment.replaceAll("~1", "/").replaceAll("~0", "~"),
  );
  let current: unknown = root;
  for (const segment of segments) {
    if (!isObject(current) || !(segment in current)) {
      throw new TypeError(`row contract contains an unresolved schema reference ${schema.$ref}`);
    }
    current = current[segment];
  }
  if (!isObject(current)) throw new TypeError(`row contract schema reference ${schema.$ref} is not an object`);
  return current;
}

function normalizeSchema(schema: JsonSchema, root: JsonSchema): { node: JsonSchema; nullable: boolean } {
  const resolved = resolveReference(schema, root);
  const choices = Array.isArray(resolved.anyOf) ? resolved.anyOf : resolved.oneOf;
  if (Array.isArray(choices)) {
    const nonNull = choices.filter((choice) =>
      isObject(choice) && choice.type !== "null",
    );
    const allowsNull = nonNull.length !== choices.length;
    if (nonNull.length !== 1 || !isObject(nonNull[0])) {
      throw new TypeError("row contract contains a union that has no single Arrow type");
    }
    const child = normalizeSchema(nonNull[0], root);
    return { node: child.node, nullable: allowsNull || child.nullable };
  }
  if (Array.isArray(resolved.type)) {
    const typeNames = resolved.type.filter((entry): entry is string => typeof entry === "string");
    const nonNull = typeNames.filter((entry) => entry !== "null");
    if (nonNull.length !== 1) throw new TypeError("row contract contains a union that has no single Arrow type");
    return { node: { ...resolved, type: nonNull[0] }, nullable: nonNull.length !== typeNames.length };
  }
  return { node: resolved, nullable: resolved.type === "null" };
}

function inferLogicalType(schema: JsonSchema, root: JsonSchema, fieldName: string): LogicalType {
  const resolved = resolveReference(schema, root);
  const choices = Array.isArray(resolved.anyOf) ? resolved.anyOf : resolved.oneOf;
  if (Array.isArray(choices)) {
    const nonNull = choices.filter((choice) => isObject(choice) && choice.type !== "null");
    if (nonNull.length === 0 || nonNull.some((choice) => !isObject(choice))) {
      throw new TypeError(`${fieldName} has a union with no declared Arrow type`);
    }
    const branchTypes = nonNull.map((choice) => inferLogicalType(choice, root, fieldName));
    const first = branchTypes[0];
    if (first === undefined || branchTypes.some((candidate) => JSON.stringify(candidate) !== JSON.stringify(first))) {
      throw new TypeError(`${fieldName} has a union that does not reduce to one Arrow type`);
    }
    return {
      ...first,
      nullable: choices.some((choice) => isObject(choice) && choice.type === "null") || first.nullable,
    };
  }
  const normalized = normalizeSchema(schema, root);
  const node = normalized.node;
  if (node.type === "object") {
    const properties = node.properties;
    if (!isObject(properties)) throw new TypeError(`${fieldName} has no declared object fields`);
    const fields = Object.entries(properties).map(([name, child]) => {
      if (!isObject(child)) throw new TypeError(`${fieldName}.${name} has an invalid schema`);
      const type = inferLogicalType(child, root, `${fieldName}.${name}`);
      return { name, type, nullable: type.nullable };
    });
    return { kind: "struct", nullable: normalized.nullable, fields };
  }
  if (node.type === "array") {
    if (!isObject(node.items)) throw new TypeError(`${fieldName} has no declared list item type`);
    const itemType = inferLogicalType(node.items, root, `${fieldName}[]`);
    return {
      kind: "list",
      nullable: normalized.nullable,
      itemType,
      itemNullable: itemType.nullable,
    };
  }
  const literals = Array.isArray(node.enum)
    ? node.enum
    : Object.hasOwn(node, "const")
      ? [node.const]
      : null;
  if (literals !== null && literals.length > 0) {
    const literalTypes = new Set(literals.map((value) =>
      typeof value === "number" && Number.isInteger(value) ? "integer" : typeof value,
    ));
    if (literalTypes.size === 1) {
      const literalType = [...literalTypes][0];
      if (literalType === "string") return { kind: "scalar", scalar: "string", nullable: normalized.nullable };
      if (literalType === "integer") return { kind: "scalar", scalar: "int64", nullable: normalized.nullable };
      if (literalType === "boolean") return { kind: "scalar", scalar: "bool", nullable: normalized.nullable };
    }
  }
  const typeByJson: Record<string, LogicalType["scalar"]> = {
    string: "string",
    integer: "int64",
    number: "float64",
    boolean: "bool",
  };
  if (typeof node.type !== "string" || typeByJson[node.type] === undefined) {
    throw new TypeError(`${fieldName} has an unsupported declared Arrow type`);
  }
  const scalar = typeByJson[node.type];
  if (scalar === undefined) throw new TypeError(`${fieldName} has an unsupported declared Arrow type`);
  return { kind: "scalar", scalar, nullable: normalized.nullable };
}

export function describeObjectSchema(schema: z.ZodType): { root: JsonSchema; fields: ArrowColumn[] } {
  const rootValue = z.toJSONSchema(schema);
  if (!isObject(rootValue) || rootValue.type !== "object" || !isObject(rootValue.properties)) {
    throw new TypeError("ledger row contract must declare a top-level object");
  }
  const fields = Object.entries(rootValue.properties).map(([name, child]) => {
    if (!isObject(child)) throw new TypeError(`row contract field ${name} has an invalid schema`);
    const type = inferLogicalType(child, rootValue, name);
    return { name, type, nullable: type.nullable };
  });
  return { root: rootValue, fields };
}

export function appendIdentityColumns(contractFields: readonly ArrowColumn[]): ArrowColumn[] {
  const columns = [...contractFields];
  const byName = new Set(columns.map((column) => column.name));
  const identityFields = describeObjectSchema(RowIdentitySchema).fields;
  for (const identity of identityFields) {
    if (!byName.has(identity.name)) {
      columns.push(identity);
      byName.add(identity.name);
    }
  }
  return columns;
}
