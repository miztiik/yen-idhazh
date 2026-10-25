/** Which named source serves one UTC day, with yearly-to-raw precedence? */
import { createHash } from "node:crypto";
import { readFile as readFileFromDisk, stat } from "node:fs/promises";
import { dirname, join, basename } from "node:path";
import {
  COMPACT_INDEX_VERSION, RAW_DAY_INDEX_VERSION,
  CompactIndexSchema, DateStampSchema, LedgerNameSchema, RawDayIndexSchema,
} from "@idhazh/common-contracts";
import type { CompactIndex } from "@idhazh/common-contracts";
import type { LedgerRowContract, StoredLedgerRow } from "@idhazh/ledger-file-writer";
import { readLedgerParquet } from "./read-parquet";
import type { LedgerRowProjectionContract, ReadLedgerFile } from "./read-parquet";
import { LedgerHistoryReadError } from "./ledger-history-error";

type Period = CompactIndex["period"];
export type LedgerDay<T extends object> = Readonly<{
  ledger: ReturnType<typeof LedgerNameSchema.parse>;
  day: string; status: "rows" | "empty" | "lost" | "missing";
  tier: "raw" | Period | null;
  rows: readonly StoredLedgerRow<T>[];
  files: readonly ReadLedgerFile<T>[];
  notices: readonly string[];
}>;
export type NamedDayInput<T extends object> = Readonly<{
  ledger: ReturnType<typeof LedgerNameSchema.parse>;
  day: string;
  contract: LedgerRowContract<T> | LedgerRowProjectionContract<T>;
  indexes?: Readonly<Partial<Record<Period, string>>>;
  rawFiles?: readonly string[];
  rawIndex?: string;
  preservedRawFiles?: readonly Readonly<{
    path: string; file_id: string; content_sha256: string; bytes: number; row_count: number;
  }>[];
  fileCache?: Map<string, Promise<ReadLedgerFile<T>>>;
}>;

function missing(error: unknown): boolean {
  return error instanceof Error && "code" in error && error.code === "ENOENT";
}
function sourceRunPartitionDay(row: object): string | undefined {
  if (!("date" in row) || typeof row.date !== "string"
    || !("run_id" in row) || typeof row.run_id !== "string"
    || !("observed_at" in row) || typeof row.observed_at !== "string"
    || !("observation_phase" in row)) return undefined;
  if (row.observation_phase === "plan_complete") return row.run_id.slice(0, 10);
  if (row.observation_phase === "publication_complete") return row.observed_at.slice(0, 10);
  return undefined;
}
async function readIndex(path: string): Promise<unknown | undefined> {
  try {
    return JSON.parse(await readFileFromDisk(path, "utf8")) as unknown;
  } catch (error) {
    if (missing(error)) return undefined;
    if (error instanceof SyntaxError) throw new LedgerHistoryReadError("Invalid history index JSON", { cause: error });
    throw error;
  }
}
async function readFile<T extends object>(input: NamedDayInput<T>, path: string): Promise<ReadLedgerFile<T>> {
  if (input.fileCache === undefined) return readLedgerParquet(path, input.ledger, input.contract);
  let pending = input.fileCache.get(path);
  if (pending === undefined) {
    pending = readLedgerParquet(path, input.ledger, input.contract);
    input.fileCache.set(path, pending);
  }
  return pending;
}
async function readPreservedRawFiles<T extends object>(
  input: NamedDayInput<T>, day: string, notices: string[],
): Promise<readonly ReadLedgerFile<T>[] | undefined> {
  const references = input.preservedRawFiles ?? [];
  if (new Set(references.map(reference => reference.path)).size !== references.length
    || new Set(references.map(reference => reference.file_id)).size !== references.length) {
    throw new LedgerHistoryReadError("Preserved raw snapshot references must name distinct files");
  }
  const files: ReadLedgerFile<T>[] = [];
  for (const reference of references) {
    let file: ReadLedgerFile<T>;
    try {
      file = await readFile(input, reference.path);
    } catch (error) {
      if (!missing(error)) throw error;
      notices.push(`preserved-file-missing:${basename(reference.path)}`);
      return undefined;
    }
    if (file.envelope.tier !== "raw" || file.envelope.covers !== day) {
      throw new LedgerHistoryReadError("Preserved raw snapshot belongs to another day or tier");
    }
    if (file.envelope.file_id !== reference.file_id
      || file.envelope.content_sha256 !== reference.content_sha256
      || file.bytes !== reference.bytes || file.rows.length !== reference.row_count) {
      throw new LedgerHistoryReadError("Preserved raw snapshot differs from its head reference");
    }
    files.push(file);
  }
  return files;
}
export async function readLedgerDay<T extends object>(input: NamedDayInput<T>): Promise<LedgerDay<T>> {
  const day = DateStampSchema.parse(input.day);
  if (new Date(`${day}T00:00:00Z`).toISOString().slice(0, 10) !== day) throw new Error("Requested UTC day is not a calendar date");
  const ledger = LedgerNameSchema.parse(input.ledger);
  const notices: string[] = [];
  const matches: { period: Period; entry: CompactIndex["entries"][number]; indexPath: string }[] = [];
  let expired = false;
  for (const period of ["yearly", "monthly", "daily"] as const) {
    const path = input.indexes?.[period];
    if (path === undefined) continue;
    const value = await readIndex(path);
    if (value === undefined) {
      notices.push(`index-missing:${period}`);
      continue;
    }
    const index = CompactIndexSchema.parse(value);
    if (index.version > COMPACT_INDEX_VERSION) throw new LedgerHistoryReadError("Compact index schema is newer than the declared reader");
    if (index.ledger !== ledger || index.period !== period) throw new LedgerHistoryReadError("Named compact index belongs to another ledger or period");
    if (period === "yearly" && index.expired_through !== null && day.slice(0, 4) <= index.expired_through) expired = true;
    const covers = period === "yearly" ? day.slice(0, 4) : period === "monthly" ? day.slice(0, 7) : day;
    const entry = index.entries.find(entry => entry.covers === covers);
    if (entry !== undefined) matches.push({ period, entry, indexPath: path });
  }
  const result = (
    status: LedgerDay<T>["status"], tier: LedgerDay<T>["tier"],
    files: readonly ReadLedgerFile<T>[] = [],
  ): LedgerDay<T> => ({
    ledger, day, status, tier, files, notices,
    rows: files.flatMap(file => file.rows.filter(held => held.identity.covers === day)),
  });
  const verifySourcePartition = (files: readonly ReadLedgerFile<T>[]) => {
    if (ledger !== "source-runs" && ledger !== "feed-runs") return;
    for (const file of files) for (const held of file.rows) {
      if (held.identity.covers !== day) continue;
      const partitionDay = sourceRunPartitionDay(held.row);
      if (partitionDay === undefined) throw new Error("Source-run row lacks its run or observation partition basis");
      if (held.identity.covers !== partitionDay) throw new Error("Source-run partition differs from its observation phase");
    }
  };
  if (expired) {
    notices.push("period-expired");
    const preserved = await readPreservedRawFiles(input, day, notices);
    if (preserved === undefined) return result("missing", "raw");
    if (preserved.length > 0) {
      verifySourcePartition(preserved);
      return result(preserved.some(file => file.rows.some(row => row.identity.covers === day)) ? "rows" : "empty", "raw", preserved);
    }
    return result("missing", "yearly");
  }
  if (matches.length > 1) notices.push(`overlapping-periods:${matches.map(match => match.period).join(",")}`);
  const match = matches[0];
  if (match !== undefined) {
    const { entry, period, indexPath } = match;
    const pieces = entry.covers.split("-");
    const path = join(dirname(dirname(indexPath)), period,
      ...pieces.slice(0, -1), `${pieces[pieces.length - 1]}.parquet`);
    // Year files live in their own year folder, unlike daily and monthly files.
    const filePath = period === "yearly" ? join(dirname(dirname(indexPath)), period, entry.covers, `${entry.covers}.parquet`) : path;
    if (entry.state !== "packed") {
      try {
        await stat(filePath);
      } catch (error) {
        if (!missing(error)) throw error;
        const preserved = await readPreservedRawFiles(input, day, notices);
        if (preserved === undefined) return result("missing", "raw");
        verifySourcePartition(preserved);
        const status = entry.state === "lost" ? "lost"
          : preserved.some(file => file.rows.some(row => row.identity.covers === day)) ? "rows" : "empty";
        return result(status, preserved.length > 0 ? "raw" : period, preserved);
      }
      throw new LedgerHistoryReadError("Compact index declares no file but its named file exists");
    }
    if (entry.lost_days.includes(day)) {
      const preserved = await readPreservedRawFiles(input, day, notices);
      if (preserved === undefined) return result("missing", "raw");
      verifySourcePartition(preserved);
      return result("lost", preserved.length > 0 ? "raw" : period, preserved);
    }
    if (entry.set_aside > 0) notices.push(`files-set-aside:${entry.set_aside}`);
    let file: ReadLedgerFile<T>;
    try {
      file = await readFile(input, filePath);
    } catch (error) {
      if (!missing(error)) throw error;
      notices.push(`file-missing:${period}:${entry.covers}`);
      return result("missing", period);
    }
    if (file.envelope.tier !== "compact" || file.envelope.period !== period || file.envelope.covers !== entry.covers) {
      throw new LedgerHistoryReadError("Indexed compact file belongs to another period");
    }
    if (file.bytes !== entry.bytes || file.rows.length !== entry.rows
      || (entry.file_sha256 !== undefined && entry.file_sha256 !== null
        && file.file_sha256 !== entry.file_sha256)) {
      throw new LedgerHistoryReadError("Compact index row count, byte size or file digest differs from its file");
    }
    const preserved = await readPreservedRawFiles(input, day, notices);
    if (preserved === undefined) return result("missing", "raw");
    const compactIdentities = new Set(file.rows.map(row => JSON.stringify(row.identity)));
    if (preserved.some(raw => raw.rows.some(row => compactIdentities.has(JSON.stringify(row.identity))))) {
      throw new LedgerHistoryReadError("Preserved raw snapshot is already represented in the compact file");
    }
    const files = [file, ...preserved];
    verifySourcePartition(files);
    const held = result("rows", period, files);
    return { ...held, status: held.rows.length === 0 ? "empty" : "rows" };
  }
  if (input.preservedRawFiles !== undefined && input.preservedRawFiles.length > 0) {
    if (input.rawFiles !== undefined || input.rawIndex !== undefined) {
      throw new LedgerHistoryReadError("Name preserved snapshots or ordinary raw files, not both");
    }
    const preserved = await readPreservedRawFiles(input, day, notices);
    if (preserved === undefined) return result("missing", "raw");
    verifySourcePartition(preserved);
    return result(preserved.some(file => file.rows.some(row => row.identity.covers === day)) ? "rows" : "empty", "raw", preserved);
  }
  let rawFiles = input.rawFiles;
  let sizes: number[] | null = null;
  if (input.rawIndex !== undefined) {
    if (rawFiles !== undefined) throw new Error("Name raw files or a raw index, not both");
    const value = await readIndex(input.rawIndex);
    if (value === undefined) {
      notices.push("raw-index-missing");
      return result("missing", "raw");
    }
    const index = RawDayIndexSchema.parse(value);
    if (index.version > RAW_DAY_INDEX_VERSION) throw new LedgerHistoryReadError("Raw index schema is newer than the declared reader");
    if (index.ledger !== ledger || index.date !== day) throw new LedgerHistoryReadError("Raw index belongs to another ledger or day");
    const digest = createHash("sha256").update(index.files.join("\n"), "utf8").digest("hex");
    if (digest !== index.content_sha256) throw new LedgerHistoryReadError("Raw index filename digest differs from its list");
    rawFiles = index.files.map(name => join(dirname(input.rawIndex!), name));
    sizes = index.bytes;
  }
  if (rawFiles === undefined) return result("missing", null);
  if (new Set(rawFiles).size !== rawFiles.length) throw new LedgerHistoryReadError("Raw input names a file twice");
  const files: ReadLedgerFile<T>[] = [];
  for (const [index, path] of rawFiles.entries()) {
    let file: ReadLedgerFile<T>;
    try {
      file = await readFile(input, path);
    } catch (error) {
      if (!missing(error)) throw error;
      notices.push(`file-missing:${basename(path)}`);
      return result("missing", "raw");
    }
    if (file.envelope.tier !== "raw" || file.envelope.covers !== day) throw new LedgerHistoryReadError("Raw file belongs to another day or tier");
    if (sizes !== null && sizes[index] !== file.bytes) throw new LedgerHistoryReadError("Raw index byte size differs from its file");
    if (files.some(held => held.envelope.file_id === file.envelope.file_id)) throw new LedgerHistoryReadError("Raw input repeats a file identifier");
    files.push(file);
  }
  verifySourcePartition(files);
  files.sort((left, right) => left.envelope.written_at_ms - right.envelope.written_at_ms
    || (left.envelope.file_id < right.envelope.file_id ? -1 : left.envelope.file_id > right.envelope.file_id ? 1 : 0));
  return result(files.some(file => file.rows.length > 0) ? "rows" : "empty", "raw", files);
}
