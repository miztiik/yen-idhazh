/** Which explicit files and compact indexes serve a named list of UTC days? */
import { resolve } from "node:path";
import type { LedgerRegistration, StoredLedgerRow } from "@idhazh/ledger-file-writer";
import { LedgerNameSchema } from "@idhazh/common-contracts";
import { SeenDayInputSchema } from "../config/service-settings";
import type { SeenDayInput } from "../config/service-settings";
import { readLedgerDay } from "./read-period";
import type { NamedDayInput, LedgerDay } from "./read-period";
import type { ReadLedgerFile } from "./read-parquet";

export function defaultDayInput(prefix: readonly string[], day: string): SeenDayInput {
  const base = prefix.join("/");
  return SeenDayInputSchema.parse({
    day, ...(prefix[0] === "feed-ingest-plan" ? {} : {
      indexes: Object.fromEntries(["yearly", "monthly", "daily"].map(period =>
        [period, `state/compact/${base}/index/${period}.json`])),
    }),
    ...(prefix[0] === "feed-ingest-plan" ? {} : {
      raw_index: `state/raw/${base}/${day.replaceAll("-", "/")}/index.json`,
    }),
  });
}

export async function readNamedDays<T extends object>(
  root: string, registration: LedgerRegistration, days: readonly SeenDayInput[],
  contract: NamedDayInput<T>["contract"],
  fileCache = new Map<string, Promise<ReadLedgerFile<T>>>(),
) {
  const parsed = days.map(day => SeenDayInputSchema.parse(day));
  if (parsed.some((day, index) => index > 0 && day.day <= parsed[index - 1]!.day)) {
    throw new Error(`${registration.name}: history must name distinct ascending UTC days`);
  }
  const held = [];
  for (const input of parsed) {
    const day = await readLedgerDay({
      ledger: LedgerNameSchema.parse(registration.name), day: input.day, contract, fileCache,
      ...(input.indexes === undefined ? {} : { indexes: Object.fromEntries(
        Object.entries(input.indexes).flatMap(([period, path]) => path === undefined ? [] : [[period, resolve(root, path)]]),
      ) }),
      ...(input.raw_files === undefined ? {} : { rawFiles: input.raw_files.map(path => resolve(root, path)) }),
      ...(input.raw_index === undefined ? {} : { rawIndex: resolve(root, input.raw_index) }),
    });
    held.push(day);
  }
  return held;
}

export function usableDay(day: LedgerDay<object>): boolean {
  return (day.status === "rows" || day.status === "empty")
    && !day.notices.some(notice => notice === "period-expired" || notice.startsWith("files-set-aside:"));
}

export function latestNativeRows<T extends object>(rows: readonly StoredLedgerRow<T>[]): T[] {
  const attempts = new Map<string, number>();
  for (const { identity } of rows) attempts.set(identity.unit_id, Math.max(identity.attempt, attempts.get(identity.unit_id) ?? 0));
  return rows.filter(({ identity }) => identity.attempt === attempts.get(identity.unit_id)).map(held => held.row);
}

export function historyCoverage(days: readonly LedgerDay<object>[]) {
  return {
    availability: days.length > 0 && days.every(usableDay) ? "available" as const : "unavailable" as const,
    days: days.map(day => ({
      day: day.day, status: day.status, notices: day.notices,
      files: day.files.map(file => ({
        file_id: file.envelope.file_id, content_sha256: file.envelope.content_sha256, row_count: file.rows.length,
      })),
    })),
  };
}
