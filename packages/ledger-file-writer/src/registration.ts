/** Validates registry, period, contract, and writer settings before a ledger write. */
import {
  DateStampSchema, DiscoveredArticleRowContract, FeedHealthStateRowContract,
  LedgerNameSchema, PlanRunRowContract, PlannerLedgerNameSchema,
  SelectedArticleRowContract, RejectedArticleRowContract, WriterIdentitySchema,
} from "@idhazh/common-contracts";
import type { WriterIdentity } from "@idhazh/common-contracts";
import { resolve } from "node:path";
import { z } from "zod";
import { appendIdentityColumns, describeObjectSchema } from "./row-schema";
import type {
  LedgerPeriod,
  LedgerRegistration,
  LedgerRowContract,
  PersistLedgerInput,
  ValidatedLedgerWrite,
} from "./ledger-types";

export const PLANNER_CONTRACTS = {
  "discovered-articles": DiscoveredArticleRowContract,
  "selected-articles": SelectedArticleRowContract,
  "rejected-articles": RejectedArticleRowContract,
  "feed-health-state": FeedHealthStateRowContract,
  "plan-runs": PlanRunRowContract,
} as const;

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function validateRegistration(ledger: string, entry: LedgerRegistration): void {
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
  const isFlatPrefix = entry.prefix.length === 1 && entry.prefix[0] === ledger;
  const isNestedPrefix =
    entry.prefix.length >= 2 &&
    entry.prefix[0] === entry.family &&
    entry.prefix.at(-1) === ledger;
  if (!isFlatPrefix && !isNestedPrefix) {
    throw new Error(`${ledger} has an invalid trusted registry prefix`);
  }
  for (const segment of entry.prefix) {
    if (!segment || segment === "." || segment === ".." || /[\\/:]/.test(segment)) {
      throw new Error(`${ledger} registry prefix contains an unsafe path segment`);
    }
  }
}

export function validatePeriod(period: LedgerPeriod): void {
  if (!isObject(period)) throw new TypeError("ledger period must be an object");
  if (period.tier === "raw") {
    DateStampSchema.parse(period.covers);
    return;
  }
  if (period.tier !== "compact") throw new Error("ledger period tier must be raw or compact");
  if (!["daily", "monthly", "yearly"].includes(period.period)) {
    throw new Error("compact ledger period must be daily, monthly, or yearly");
  }
  if (!Number.isSafeInteger(period.builtFrom) || period.builtFrom < 0) {
    throw new RangeError("built_from must be a nonnegative safe integer");
  }
  const pattern = period.period === "daily" ? /^\d{4}-\d{2}-\d{2}$/ :
    period.period === "monthly" ? /^\d{4}-\d{2}$/ : /^\d{4}$/;
  if (!pattern.test(period.covers)) throw new Error(`covers does not match compact ${period.period} period`);
  if (period.period === "daily") DateStampSchema.parse(period.covers);
}

export function isMaintenanceJob(job: WriterIdentity["job"]): boolean {
  return job === "migrate" || job === "run-tasks" || job === "history";
}

export function validateLedgerInput<T extends object>(
  input: PersistLedgerInput<T>,
): ValidatedLedgerWrite<T> {
  validateRegistration(input.ledger, input.registryEntry);
  validatePeriod(input.period);
  if ("partition_date" in input && input.partition_date !== undefined) DateStampSchema.parse(input.partition_date);
  const ledger = LedgerNameSchema.parse(input.ledger);
  const plannerName = PlannerLedgerNameSchema.safeParse(ledger);
  const planner = plannerName.success;
  const writerContext = planner ? null : WriterIdentitySchema.parse(input.writerContext);
  let rowSchema: z.ZodType<object> = input.rowContract.schema;
  if (plannerName.success) {
    const declared: LedgerRowContract<object> = PLANNER_CONTRACTS[plannerName.data];
    rowSchema = declared.schema;
    if (input.registryEntry.family !== "feed-ingest-plan"
      || input.registryEntry.prefix.join("/") !== `feed-ingest-plan/${ledger}`) {
      throw new Error(`${ledger} requires its registered planner family prefix`);
    }
    const writableVersions = (declared.acceptedSchemaVersions ?? [declared.schemaVersion])
      .filter(version => declared.historicalSchemas?.[version] === undefined);
    if (!writableVersions.includes(input.rowContract.schemaVersion)
      || JSON.stringify(z.toJSONSchema(input.rowContract.schema)) !== JSON.stringify(z.toJSONSchema(declared.schema))) {
      throw new Error(`${ledger} requires its declared current planner row contract`);
    }
  }
  if (!/^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?)?$/.test(input.rowContract.schemaVersion)) {
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
  const { fields } = describeObjectSchema(rowSchema);
  const columns = planner ? fields : appendIdentityColumns(fields);
  if (!input.outputRoot || input.outputRoot.includes("\0")) throw new Error("outputRoot must be a valid path");
  return {
    input,
    ledger,
    writerContext,
    planner,
    rowSchema,
    outputRoot: resolve(input.outputRoot),
    columns,
  };
}
