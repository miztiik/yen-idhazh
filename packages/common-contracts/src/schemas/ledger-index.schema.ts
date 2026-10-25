/** Which named raw files or compact periods does an existing ledger index declare? */
import { z } from "zod";
import { LedgerNameSchema, PeriodSchema } from "./envelope.schema";
import {
  CountSchema, DateStampSchema, MonthStampSchema, SchemaVersionSchema,
  Sha256Schema, TimestampSchema, YearStampSchema, reject,
} from "./primitives";

// These stamps identify existing persisted index formats, not runtime settings.
export const RAW_DAY_INDEX_VERSION = "2026-10-03";
export const COMPACT_INDEX_VERSION = "2026-10-25";
export const FileIdNameSchema = z.string().regex(
  /^[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.(parquet|json)$/,
);
export const EntryStateSchema = z.enum(["packed", "empty", "lost"]);
export const CompactEntrySchema = z.strictObject({
  covers: z.union([DateStampSchema, MonthStampSchema, YearStampSchema]),
  rows: CountSchema, bytes: CountSchema, file_sha256: Sha256Schema.nullable().optional(),
  state: EntryStateSchema.default("packed"),
  lost_days: z.array(DateStampSchema).default([]), set_aside: CountSchema.default(0),
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
  entries: z.array(CompactEntrySchema), expired_through: YearStampSchema.nullable().default(null),
}).superRefine((value, ctx) => {
  if (!ascending(value.entries.map(entry => entry.covers))) reject(ctx, "compact entries must ascend without repeats");
  if (value.expired_through !== null && (value.period !== "yearly"
    || value.entries.some(entry => entry.covers <= value.expired_through!))) {
    reject(ctx, "only yearly indexes may expire years, and entries must follow expired_through");
  }
  const stamp = value.period === "yearly" ? YearStampSchema : value.period === "monthly" ? MonthStampSchema : DateStampSchema;
  for (const entry of value.entries) {
    if (!stamp.safeParse(entry.covers).success) reject(ctx, "covers must match index period");
    if (entry.state !== "packed" && (entry.rows !== 0 || entry.bytes !== 0 || entry.file_sha256 != null)) {
      reject(ctx, "an entry without a file counts no rows or bytes or digest");
    }
    if (entry.state === "lost" && value.period !== "daily") reject(ctx, "only a daily entry can be lost");
    if (entry.lost_days.length > 0 && (value.period === "daily" || !ascending(entry.lost_days)
      || entry.lost_days.some(day => !realDay(day) || !day.startsWith(`${entry.covers}-`)))) {
      reject(ctx, "lost_days must ascend without repeats inside a month or year");
    }
  }
});
export type CompactIndex = z.infer<typeof CompactIndexSchema>;
export type RawDayIndex = z.infer<typeof RawDayIndexSchema>;
