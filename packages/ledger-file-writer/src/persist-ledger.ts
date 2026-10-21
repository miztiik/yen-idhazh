/** Validates ledger rows, renders their files and writes each file atomically. */
import { randomUUID } from "node:crypto";
import { mkdir, realpath, rename, rm, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { z } from "zod";
import {
  DateStampSchema,
  LedgerNameSchema,
  RowIdentitySchema,
  WriterIdentitySchema,
} from "@idhazh/common-contracts";
import type { WriterIdentity } from "@idhazh/common-contracts";
import { buildArrowTable } from "./parquet/arrow-builder";
import type { ArrowColumn } from "./parquet/arrow-builder";
import { buildEnvelopeMetadata } from "./parquet/envelope-footer";
import { digestRows } from "./parquet/row-digest";
import type { LogicalType } from "./parquet/row-digest";
import { readParquetEngineVersion, serializeParquet } from "./parquet/wasm-serializer";
import { createFileId } from "./uuid/file-id";
import { createUnitId } from "./uuid/unit-id";

export type LedgerRowContract<T extends object> = {
  schema: z.ZodType<T>;
  schemaVersion: string;
};

export type LedgerRegistration = {
  name: string;
  family: string;
  grain: "raw-and-compact";
  lifecycle_status: "active" | "paused" | "retired";
  prefix: readonly string[];
};

export type LedgerSettings = {
  format: "parquet" | "json";
  compression_raw: "snappy" | "zstd" | "none";
  compression_compact: "snappy" | "zstd" | "none";
};

export type LedgerPeriod =
  | { tier: "raw"; covers: string }
  | { tier: "compact"; period: "daily" | "monthly" | "yearly"; covers: string; builtFrom: number };

export type StoredLedgerRow<T extends object> = {
  identity: z.input<typeof RowIdentitySchema>;
  row: T;
};

type LedgerWriteContext<T extends object> = {
  ledger: string;
  rowContract: LedgerRowContract<T>;
  outputRoot: string;
  writerContext: WriterIdentity;
  registryEntry: LedgerRegistration;
  ledgerSettings: LedgerSettings;
};

export type PersistLedgerInput<T extends object> = LedgerWriteContext<T> & (
  | { period: Extract<LedgerPeriod, { tier: "raw" }>; rows: readonly T[] }
  | { period: Extract<LedgerPeriod, { tier: "compact" }>; rows: readonly StoredLedgerRow<T>[] }
);

export type PersistedLedgerFile = {
  path: string;
  file_id: string;
  unit_id: string;
  covers: string;
  content_sha256: string;
  row_count: number;
};

export type PersistLedgerResult =
  | { status: "written"; files: PersistedLedgerFile[] }
  | { status: "empty"; files: [] }
  | { status: "skipped"; reason: "ledger_not_active"; files: [] };

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

function describeObjectSchema(schema: z.ZodType): { root: JsonSchema; fields: ArrowColumn[] } {
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

function readIdentityColumns(): ArrowColumn[] {
  const { fields } = describeObjectSchema(RowIdentitySchema);
  return fields;
}

function appendIdentityColumns(contractFields: readonly ArrowColumn[]): ArrowColumn[] {
  const columns = [...contractFields];
  const byName = new Map(columns.map((column) => [column.name, column]));
  for (const identity of readIdentityColumns()) {
    const present = byName.get(identity.name);
    if (present === undefined) {
      columns.push(identity);
      byName.set(identity.name, identity);
      continue;
    }
    if (present.nullable !== identity.nullable || JSON.stringify(present.type) !== JSON.stringify(identity.type)) {
      throw new TypeError(`row contract identity field ${identity.name} has a different logical type`);
    }
  }
  return columns;
}

function validateRegistration(ledger: string, entry: LedgerRegistration): void {
  LedgerNameSchema.parse(ledger);
  if (!isObject(entry)) throw new TypeError("ledger registration must be an object");
  if (typeof entry.name !== "string" || typeof entry.family !== "string" || !entry.family) {
    throw new TypeError("ledger registration must name its ledger and family");
  }
  if (!["active", "paused", "retired"].includes(entry.lifecycle_status)) {
    throw new Error(`${ledger} has an unsupported lifecycle status`);
  }
  if (!Array.isArray(entry.prefix) || entry.prefix.some((segment) => typeof segment !== "string")) {
    throw new TypeError(`${ledger} registry prefix must be a list of path segments`);
  }
  if (entry.name !== ledger) throw new Error(`registry entry ${entry.name} does not match ledger ${ledger}`);
  if (entry.grain !== "raw-and-compact") throw new Error(`${ledger} is not registered as a raw-and-compact ledger`);
  if (entry.prefix.length < 2 || entry.prefix[0] !== entry.family || entry.prefix.at(-1) !== ledger) {
    throw new Error(`${ledger} has an invalid trusted registry prefix`);
  }
  for (const segment of entry.prefix) {
    if (!segment || segment === "." || segment === ".." || /[\\/:]/.test(segment)) {
      throw new Error(`${ledger} registry prefix contains an unsafe path segment`);
    }
  }
}

function validatePeriod(period: LedgerPeriod): void {
  if (period.tier === "raw") {
    DateStampSchema.parse(period.covers);
    return;
  }
  if (!Number.isSafeInteger(period.builtFrom) || period.builtFrom < 0) {
    throw new RangeError("built_from must be a nonnegative safe integer");
  }
  const pattern = period.period === "daily" ? /^\d{4}-\d{2}-\d{2}$/ :
    period.period === "monthly" ? /^\d{4}-\d{2}$/ : /^\d{4}$/;
  if (!pattern.test(period.covers)) throw new Error(`covers does not match compact ${period.period} period`);
  if (period.period === "daily") DateStampSchema.parse(period.covers);
}

function isInsidePeriod(day: string, period: Extract<LedgerPeriod, { tier: "compact" }>): boolean {
  return period.period === "daily"
    ? day === period.covers
    : period.period === "monthly"
      ? day.startsWith(`${period.covers}-`)
      : day.startsWith(`${period.covers}-`);
}

function buildIdentityCells(
  ledger: string,
  covers: string,
  identity: WriterIdentity,
  generatedUnitId: string,
): Record<string, unknown> {
  return {
    ledger,
    covers,
    run_id: identity.run_id,
    attempt: identity.attempt,
    job: identity.job,
    pipeline_name: identity.pipeline_name,
    task_name: identity.task_name,
    shard: identity.shard,
    unit_id: generatedUnitId,
  };
}

function refuseIdentityContradictions(
  row: Record<string, unknown>,
  identity: Record<string, unknown>,
): void {
  for (const key of Object.keys(identity)) {
    if (Object.hasOwn(row, key) && row[key] !== identity[key]) {
      throw new Error(`ledger row contradicts its writer identity at ${key}`);
    }
  }
}

function buildStoredRawRow(
  row: Record<string, unknown>,
  ledger: string,
  covers: string,
  identity: WriterIdentity,
  generatedUnitId: string,
): Record<string, unknown> {
  const stamped = buildIdentityCells(ledger, covers, identity, generatedUnitId);
  refuseIdentityContradictions(row, stamped);
  return { ...stamped, ...row };
}

function buildStoredCompactRow<T extends object>(
  input: StoredLedgerRow<T>,
  contract: z.ZodType<T>,
  ledger: string,
  period: Extract<LedgerPeriod, { tier: "compact" }>,
): Record<string, unknown> {
  const identity = RowIdentitySchema.parse(input.identity);
  const row = contract.parse(input.row);
  if (!isObject(row)) throw new TypeError("ledger row contract did not produce an object");
  if (identity.ledger !== ledger || !isInsidePeriod(identity.covers, period)) {
    throw new Error(`compact ${ledger} rows must belong to the requested period`);
  }
  const identityRecord = identity as Record<string, unknown>;
  refuseIdentityContradictions(row, identityRecord);
  return { ...identityRecord, ...row };
}

function toRelativePath(root: string, target: string): string {
  const path = relative(root, target);
  if (!path || path === ".." || path.startsWith(`..${sep}`) || isAbsolute(path)) {
    throw new Error(`ledger path escapes output root: ${target}`);
  }
  return path.split(sep).join("/");
}

async function checkTrustedParent(root: string, target: string): Promise<void> {
  await mkdir(dirname(target), { recursive: true });
  const [rootPath, parentPath] = await Promise.all([realpath(root), realpath(dirname(target))]);
  const fromRoot = relative(rootPath, parentPath);
  if (fromRoot === ".." || fromRoot.startsWith(`..${sep}`) || isAbsolute(fromRoot)) {
    throw new Error(`ledger path resolves outside output root: ${target}`);
  }
}

export async function writeAtomically(target: string, data: Uint8Array): Promise<void> {
  const temporary = join(dirname(target), `.${randomUUID()}.tmp`);
  try {
    await writeFile(temporary, data, { flag: "wx" });
    await rename(temporary, target);
  } catch (error) {
    try {
      await rm(temporary, { force: true });
    } catch (cleanupError) {
      throw new AggregateError([error, cleanupError], `could not complete or clean up ledger write ${target}`);
    }
    throw error;
  }
}

function buildRawPath(root: string, prefix: readonly string[], covers: string, file: string): string {
  return resolve(root, "raw", ...prefix, covers.slice(0, 4), covers.slice(5, 7), covers.slice(8, 10), `${file}.parquet`);
}

function buildCompactPath(
  root: string,
  prefix: readonly string[],
  period: Extract<LedgerPeriod, { tier: "compact" }>,
): string {
  const parts = period.period === "daily"
    ? [period.covers.slice(0, 4), period.covers.slice(5, 7), `${period.covers.slice(8, 10)}.parquet`]
    : period.period === "monthly"
      ? [period.covers.slice(0, 4), `${period.covers.slice(5, 7)}.parquet`]
      : [period.covers, `${period.covers}.parquet`];
  return resolve(root, "compact", ...prefix, period.period, ...parts);
}

async function renderFile<T extends object>(
  rows: readonly Record<string, unknown>[],
  columns: readonly ArrowColumn[],
  input: LedgerWriteContext<T> & { period: LedgerPeriod },
  covers: string,
  tier: "raw" | "compact",
): Promise<{ file: PersistedLedgerFile; data: Uint8Array }> {
  const writerContext = WriterIdentitySchema.parse(input.writerContext);
  const unit = createUnitId({
    ledger: input.ledger,
    covers,
    runId: writerContext.run_id,
    job: writerContext.job,
    pipelineName: writerContext.pipeline_name,
    taskName: writerContext.task_name,
    shard: writerContext.shard,
    producer: writerContext.producer,
  });
  const writtenAtMs = Date.now();
  const id = createFileId({ unit, attempt: writerContext.attempt, writtenAtMs });
  const digest = digestRows(rows, columns);
  const compactPeriod = input.period.tier === "compact" ? input.period : null;
  const compression = tier === "raw"
    ? input.ledgerSettings.compression_raw
    : input.ledgerSettings.compression_compact;
  const writerVersion = await readParquetEngineVersion();
  const metadata = buildEnvelopeMetadata({
    rowSchemaVersion: input.rowContract.schemaVersion,
    tier,
    ledger: input.ledger,
    covers,
    period: compactPeriod?.period ?? null,
    writtenAtMs,
    identity: writerContext,
    unitId: unit,
    fileId: id,
    contentSha256: digest,
    writerVersion,
    compression,
    builtFrom: compactPeriod?.builtFrom ?? null,
  });
  const table = buildArrowTable(columns, rows);
  const serialized = await serializeParquet(table, metadata, compression);
  let filePath: string;
  if (tier === "raw") {
    filePath = buildRawPath(input.outputRoot, input.registryEntry.prefix, covers, id);
  } else {
    if (input.period.tier !== "compact") throw new Error("compact file rendering requires a compact period");
    filePath = buildCompactPath(input.outputRoot, input.registryEntry.prefix, input.period);
  }
  toRelativePath(resolve(input.outputRoot), filePath);
  return {
    file: {
      path: toRelativePath(resolve(input.outputRoot), filePath),
      file_id: id,
      unit_id: unit,
      covers,
      content_sha256: digest,
      row_count: rows.length,
    },
    data: serialized.data,
  };
}

export async function persistLedger<T extends object>(
  input: PersistLedgerInput<T>,
): Promise<PersistLedgerResult> {
  validateRegistration(input.ledger, input.registryEntry);
  validatePeriod(input.period);
  const ledger = LedgerNameSchema.parse(input.ledger);
  const writerContext = WriterIdentitySchema.parse(input.writerContext);
  const fileEnvelope = {
    schema: input.rowContract.schema,
    schemaVersion: input.rowContract.schemaVersion,
  };
  if (!/^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?)?$/.test(fileEnvelope.schemaVersion)) {
    throw new Error("row schema version must be a date-stamp");
  }
  if (input.ledgerSettings.format !== "parquet") {
    throw new Error("ledger-file-writer writes typed Parquet only");
  }
  for (const compression of [input.ledgerSettings.compression_raw, input.ledgerSettings.compression_compact]) {
    if (!["snappy", "zstd", "none"].includes(compression)) {
      throw new Error(`unsupported ledger compression: ${compression}`);
    }
  }
  const { fields: rowFields } = describeObjectSchema(fileEnvelope.schema);
  const columns = appendIdentityColumns(rowFields);
  if (!input.outputRoot || input.outputRoot.includes("\0")) throw new Error("outputRoot must be a valid path");
  const outputRoot = resolve(input.outputRoot);

  if (input.period.tier === "raw") {
    if (input.rows.length === 0) return { status: "empty", files: [] };
    if (input.registryEntry.lifecycle_status !== "active") {
      return { status: "skipped", reason: "ledger_not_active", files: [] };
    }

    const validated = input.rows.map((candidate) => {
      const row = fileEnvelope.schema.parse(candidate);
      if (!isObject(row)) throw new TypeError("ledger row contract did not produce an object");
      return row;
    });
    const groups = new Map<string, Record<string, unknown>[]>();
    for (const row of validated) {
      const day = Object.hasOwn(row, "date") ? row.date : input.period.covers;
      const covers = DateStampSchema.parse(day);
      const unit = createUnitId({
        ledger,
        covers,
        runId: writerContext.run_id,
        job: writerContext.job,
        pipelineName: writerContext.pipeline_name,
        taskName: writerContext.task_name,
        shard: writerContext.shard,
        producer: writerContext.producer,
      });
      const stored = buildStoredRawRow(row, ledger, covers, writerContext, unit);
      groups.set(covers, [...(groups.get(covers) ?? []), stored]);
    }

    const rendered: { file: PersistedLedgerFile; data: Uint8Array; target: string }[] = [];
    for (const [covers, rows] of [...groups.entries()].sort(([left], [right]) => left.localeCompare(right))) {
      const result = await renderFile(rows, columns, { ...input, outputRoot }, covers, "raw");
      const target = resolve(outputRoot, ...result.file.path.split("/"));
      rendered.push({ ...result, target });
    }
    await mkdir(outputRoot, { recursive: true });
    await Promise.all(rendered.map(({ target }) => checkTrustedParent(outputRoot, target)));
    for (const { target, data } of rendered) await writeAtomically(target, data);
    return { status: "written", files: rendered.map(({ file }) => file) };
  }

  const compactPeriod = input.period;
  const compactRows = input.rows.map((candidate) => {
    if (!isObject(candidate) || !isObject(candidate.identity)) {
      throw new TypeError("compact rows require a row identity and contract row");
    }
    return buildStoredCompactRow(candidate, fileEnvelope.schema, ledger, compactPeriod);
  });
  const result = await renderFile(
    compactRows,
    columns,
    { ...input, outputRoot },
    compactPeriod.covers,
    "compact",
  );
  const target = resolve(outputRoot, ...result.file.path.split("/"));
  await mkdir(outputRoot, { recursive: true });
  await checkTrustedParent(outputRoot, target);
  await writeAtomically(target, result.data);
  return { status: "written", files: [result.file] };
}
