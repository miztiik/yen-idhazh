/** Which settled first-sight observations exist in the caller's named files? */
import { resolve } from "node:path";
import { readLedgerParquet } from "./read-parquet";
import { readLedgerDay } from "./read-period";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, LedgerSettings } from "@idhazh/ledger-file-writer";
import type { FeedIngestCandidate } from "@idhazh/common-contracts";
import { SeenDayInputSchema, RelativePathSchema } from "../config/service-settings";
import type { SeenDayInput } from "../config/service-settings";
import { SeenRowSchema, UtcInstantSchema } from "../screen-article-candidates/seen-evidence";
import type { SeenEvidence, SeenRow } from "../screen-article-candidates/seen-evidence";
import type { RunContext } from "../resolve-run-context";

// The recorded SeenRow wire version, not a planning or retention control.
const seenSchemaVersion = "2026-08-31";
const millisecondsPerDay = 86_400_000;
const seenContract = { schema: SeenRowSchema, schemaVersion: seenSchemaVersion };
export type OwnSeenReceipt = Readonly<{ day: string; files: readonly string[] }>;

export function parseSeenDays(days: readonly SeenDayInput[]): SeenDayInput[] {
  const parsed = days.map(day => SeenDayInputSchema.parse(day));
  for (const [index, day] of parsed.entries()) {
    if (index > 0 && day.day <= parsed[index - 1]!.day) {
      throw new Error("seen_days must have distinct UTC days in ascending order");
    }
  }
  return parsed;
}

export function requiredSeenDays(now: string, lookbackDays: number): string[] {
  UtcInstantSchema.parse(now);
  if (!Number.isSafeInteger(lookbackDays) || lookbackDays < 0) throw new Error("seen_window_days must be a nonnegative safe integer");
  const midnight = Date.parse(`${now.slice(0, 10)}T00:00:00Z`);
  if (!Number.isFinite(new Date(midnight - lookbackDays * millisecondsPerDay).getTime())) {
    throw new Error("seen_window_days exceeds the UTC calendar range");
  }
  return Array.from({ length: lookbackDays + 1 }, (_, index) =>
    new Date(midnight - (lookbackDays - index) * millisecondsPerDay).toISOString().slice(0, 10));
}

function foldSeen(rows: readonly SeenRow[], now?: string): SeenRow[] {
  const settled = new Map<string, SeenRow>();
  for (const row of rows) {
    const parsed = SeenRowSchema.parse(row);
    const instant = Date.parse(parsed.first_seen_at);
    if (now !== undefined && instant > Date.parse(now)) throw new Error("seen.first_seen_at exceeds the captured run clock");
    const previous = settled.get(parsed.url_key);
    if (previous === undefined || instant < Date.parse(previous.first_seen_at)
      || (instant === Date.parse(previous.first_seen_at) && parsed.first_seen_run < previous.first_seen_run)) {
      settled.set(parsed.url_key, parsed);
    }
  }
  return [...settled.values()].sort((a, b) => a.url_key.localeCompare(b.url_key));
}

export async function readSeenEvidence(
  root: string, files: readonly string[],
  window?: {
    now: string; lookback_days: number; days: readonly SeenDayInput[];
    own_receipts?: readonly OwnSeenReceipt[];
  },
) {
  files.forEach(file => RelativePathSchema.parse(file));
  if (new Set(files).size !== files.length) throw new Error("seen_files must name distinct files");
  const required = window === undefined ? [] : requiredSeenDays(window.now, window.lookback_days);
  const namedDays = parseSeenDays(window?.days ?? []);
  for (const [index, day] of namedDays.entries()) {
    if (!required.includes(day.day)) throw new Error(`seen_days.${index}.day is outside the required UTC window`);
  }
  const ownReceipts = window?.own_receipts ?? [];
  if (new Set(ownReceipts.map(receipt => receipt.day)).size !== ownReceipts.length) {
    throw new Error("own seen receipts must have distinct UTC days");
  }
  for (const receipt of ownReceipts) {
    if (!required.includes(receipt.day)) throw new Error("own seen receipt is outside the required UTC window");
    if (new Set(receipt.files).size !== receipt.files.length) throw new Error("own seen receipts must name distinct files");
    receipt.files.forEach(file => RelativePathSchema.parse(file));
  }
  const loaded = await Promise.all(files.map(file => readLedgerParquet(
    resolve(root, file), "seen", seenContract,
  )));
  const own = await Promise.all(ownReceipts.flatMap(receipt => receipt.files.map(async path => {
    const file = await readLedgerParquet(resolve(root, path), "seen", seenContract);
    if (file.envelope.tier !== "raw" || file.envelope.covers !== receipt.day) {
      throw new Error("own seen receipt does not match its actual raw file day");
    }
    return file;
  })));
  const named = new Map(namedDays.map(day => [day.day, day]));
  const days = [];
  for (const day of required) {
    const input = named.get(day);
    const held = await readLedgerDay({
      ledger: "seen", day, contract: seenContract,
      ...(input?.indexes === undefined ? {} : {
        indexes: Object.fromEntries(Object.entries(input.indexes).flatMap(([period, path]) =>
          path === undefined ? [] : [[period, resolve(root, path)]])),
      }),
      ...(input?.raw_files === undefined ? {} : { rawFiles: input.raw_files.map(path => resolve(root, path)) }),
      ...(input?.raw_index === undefined ? {} : { rawIndex: resolve(root, input.raw_index) }),
    });
    days.push({ input: input ?? { day }, held });
  }
  const rows = foldSeen([
    ...loaded.flatMap(file => file.rows.map(row => row.row)),
    ...own.flatMap(file => file.rows.map(row => row.row)),
    ...days.flatMap(day => day.held.rows.map(row => row.row)),
  ], window?.now);
  const complete = required.length > 0 && days.every(day =>
    (day.held.status === "rows" || day.held.status === "empty")
      && !day.held.notices.some(notice => notice.startsWith("files-set-aside:") || notice === "period-expired"));
  const evidence: SeenEvidence = files.length > 0 || namedDays.length > 0 || ownReceipts.length > 0
    ? { availability: "available", rows } : { availability: "unavailable" };
  return {
    evidence, global_absence: "unavailable" as const,
    absence_proof: complete ? "within_configured_window" as const : "unavailable" as const,
    files, own_receipts: ownReceipts,
    window: window === undefined ? null : {
      from_day: required[0]!, through_day: required[required.length - 1]!,
      lookback_days: window.lookback_days, required_day_count: required.length,
      days: days.map(({ input, held }) => ({
        input, status: held.status, tier: held.tier, notices: held.notices,
        file_evidence: held.files.map(file => ({
          file_id: file.envelope.file_id, content_sha256: file.envelope.content_sha256, row_count: file.rows.length,
        })),
      })),
    },
  };
}
export type SettledSeenEvidence = Awaited<ReturnType<typeof readSeenEvidence>>;

export async function rememberFirstSight(
  seen: SettledSeenEvidence, candidates: readonly FeedIngestCandidate[], context: RunContext,
  destination: { outputRoot: string; registryEntry: LedgerRegistration; ledgerSettings: LedgerSettings },
) {
  const rows = seen.evidence.availability === "available" ? seen.evidence.rows : [];
  const known = new Set(rows.map(row => row.url_key));
  const newRows: SeenRow[] = [];
  for (const candidate of candidates) {
    if (known.has(candidate.url_key)) continue;
    known.add(candidate.url_key);
    newRows.push(SeenRowSchema.parse({
      version: seenSchemaVersion, url_key: candidate.url_key,
      first_seen_at: context.now, first_seen_run: context.run_id,
    }));
  }
  const sealing = await persistLedger({
    ...destination, ledger: "seen", rowContract: seenContract, writerContext: context.writer,
    period: { tier: "raw", covers: context.date }, rows: newRows,
  });
  if (sealing.status === "skipped") throw new Error("seen: first-sight ledger write was skipped");
  return {
    ...seen, new_rows: newRows, sealing,
    evidence: newRows.length === 0 ? seen.evidence : {
      availability: "available" as const, rows: foldSeen([...rows, ...newRows], context.now),
    },
  };
}
