/** Which named raw files or compact periods does an existing ledger index declare? */
import { z } from "zod";
import { LedgerNameSchema, PeriodSchema } from "./envelope.schema";
import {
  CountSchema, DateStampSchema, MonthStampSchema, SchemaVersionSchema,
  Sha256Schema, TimestampSchema, YearStampSchema, reject,
} from "./primitives";

// These stamps identify existing persisted index formats, not runtime settings.
export const RAW_DAY_INDEX_VERSION = "2026-10-03";
export const COMPACT_INDEX_VERSION = "2026-11-25";
export const FileIdNameSchema = z.string().regex(
  /^[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.(parquet|json)$/,
);
export const EntryStateSchema = z.enum(["packed", "empty", "lost"]);
export const CoverageStateSchema = EntryStateSchema.exclude(["packed"]);
const CoversSchema = z.union([DateStampSchema, MonthStampSchema, YearStampSchema]);
const PeriodQuality = {
  lost_days: z.array(DateStampSchema).default([]), set_aside: CountSchema.default(0),
};
export const CompactEntrySchema = z.strictObject({
  covers: CoversSchema,
  rows: CountSchema, bytes: CountSchema, file_sha256: Sha256Schema.nullable().optional(),
  state: EntryStateSchema.default("packed"),
  ...PeriodQuality,
});
export const CompactCoverageSchema = z.strictObject({
  covers: CoversSchema, state: CoverageStateSchema, ...PeriodQuality,
});
function ascending(values: readonly string[]): boolean {
  return values.every((value, index) => index === 0 || values[index - 1]! < value);
}
function realDay(day: string): boolean {
  const instant = Date.parse(`${day}T00:00:00Z`);
  return Number.isFinite(instant) && new Date(instant).toISOString().slice(0, 10) === day;
}
export const RawDayIndexSchema = z.strictObject({
  version: SchemaVersionSchema, ledger: LedgerNameSchema, date: DateStampSchema,
  files: z.array(FileIdNameSchema), content_sha256: Sha256Schema,
  bytes: z.array(CountSchema).nullable().default(null), listed_at: TimestampSchema,
}).superRefine((value, ctx) => {
  if (!ascending(value.files)) reject(ctx, "raw filenames must ascend without repeats");
  if (value.bytes !== null && value.bytes.length !== value.files.length) reject(ctx, "bytes must match files one for one");
});
export const CompactIndexSchema = z.strictObject({
  version: SchemaVersionSchema, ledger: LedgerNameSchema, period: PeriodSchema,
  entries: z.array(CompactEntrySchema), coverage: z.array(CompactCoverageSchema),
  expired_through: YearStampSchema.nullable().default(null),
}).superRefine((value, ctx) => {
  if (value.version !== COMPACT_INDEX_VERSION) reject(ctx, `unsupported compact index version; expected ${COMPACT_INDEX_VERSION}`);
  if (value.entries.some(entry => entry.state !== "packed")) reject(ctx, "entries must name files");
  if (!ascending(value.entries.map(entry => entry.covers))) reject(ctx, "compact entries must ascend without repeats");
  if (!ascending(value.coverage.map(record => record.covers))) reject(ctx, "compact coverage must ascend without repeats");
  const periods = [...value.entries, ...value.coverage];
  if (new Set(periods.map(record => record.covers)).size !== periods.length) {
    reject(ctx, "a period cannot appear in both entries and coverage");
  }
  if (value.expired_through !== null && (value.period !== "yearly"
    || periods.some(record => record.covers <= value.expired_through!))) {
    reject(ctx, "only yearly indexes may expire years, and periods must follow expired_through");
  }
  const stamp = value.period === "yearly" ? YearStampSchema : value.period === "monthly" ? MonthStampSchema : DateStampSchema;
  for (const entry of periods) {
    if (!stamp.safeParse(entry.covers).success) {
      reject(ctx, "covers must match index period");
    }
    if (entry.state === "lost" && value.period !== "daily") reject(ctx, "only a daily entry can be lost");
    if (entry.lost_days.length > 0 && (value.period === "daily" || !ascending(entry.lost_days)
      || entry.lost_days.some(day => !realDay(day) || !day.startsWith(`${entry.covers}-`)))) {
      reject(ctx, "lost_days must ascend without repeats inside a month or year");
    }
  }
});
export type CompactIndex = z.infer<typeof CompactIndexSchema>;
export type CompactCoverage = z.infer<typeof CompactCoverageSchema>;
export type RawDayIndex = z.infer<typeof RawDayIndexSchema>;

/** Every checked period in order, whether it has a file or not. */
export function compactPeriods(index: CompactIndex): CompactIndex["entries"] {
  if (index.coverage.length === 0) return index.entries;
  return [...index.entries, ...index.coverage.map(record => ({ ...record, rows: 0, bytes: 0 }))]
    .sort((left, right) => left.covers.localeCompare(right.covers));
}
