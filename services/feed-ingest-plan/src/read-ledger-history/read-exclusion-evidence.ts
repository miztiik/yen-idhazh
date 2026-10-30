/** Which named published and settled-failure rows exclude an article before page fetch? */
import { resolve } from "node:path";
import { ItemHealthFailureCodeSchema } from "@idhazh/common-contracts";
import type { ItemHealthFailureCode } from "@idhazh/common-contracts";
import type { PublishedRow } from "../metrics/publication-evidence";
import { readLedgerDay } from "./read-period";
import { ItemHealthFailureProjectionContract } from "./item-health-failure";
import type { ItemHealthFailureProjection } from "./item-health-failure";
import { PublishedRowProjectionContract } from "./published-row";
import { LedgerDayInputSchema } from "../config/service-settings";
import type { LedgerDayInput } from "../config/service-settings";
import type { LedgerRegistration } from "@idhazh/ledger-file-writer";
import { requiredUtcDays, UtcInstantSchema } from "../utc-instant";
import type { LedgerDay } from "./read-period";
import type { ReadLedgerFile } from "./read-parquet";
import { mapPool } from "../harvest-feeds/harvest-pool";

function defaultInput(prefix: readonly string[], day: string): LedgerDayInput {
  const base = prefix.join("/");
  return LedgerDayInputSchema.parse({
    day,
    indexes: {
      yearly: `state/compact/${base}/index/yearly.json`,
      monthly: `state/compact/${base}/index/monthly.json`,
      daily: `state/compact/${base}/index/daily.json`,
    },
    raw_index: `state/raw/${base}/${day.replaceAll("-", "/")}/index.json`,
  });
}

function namedDays(
  prefix: readonly string[], required: readonly string[], authored: readonly LedgerDayInput[],
  name: string,
) {
  const parsed = authored.map(input => LedgerDayInputSchema.parse(input));
  const byDay = new Map<string, LedgerDayInput>();
  for (const [index, input] of parsed.entries()) {
    if (index > 0 && input.day <= parsed[index - 1]!.day) throw new Error(`${name} must name distinct ascending UTC days`);
    if (!required.includes(input.day)) throw new Error(`${name}.${index}.day is outside the configured UTC window`);
    byDay.set(input.day, input);
  }
  return required.map(day => {
    const input = byDay.get(day) ?? defaultInput(prefix, day);
    return { input };
  });
}

function coverage(days: readonly {
  input: LedgerDayInput; held: LedgerDay<PublishedRow>;
}[]) {
  const missing = days.filter(({ held }) => (held.status !== "rows" && held.status !== "empty")
    || held.notices.some(notice => notice === "period-expired" || notice.startsWith("files-set-aside:")));
  return {
    from_day: days[0]?.input.day ?? null, through_day: days.at(-1)?.input.day ?? null,
    required_day_count: days.length, known_day_count: days.length - missing.length,
    missing_days: missing.map(({ input }) => input.day),
  };
}

function folderInputs(
  root: string, input: LedgerDayInput,
) {
  return {
    ...(input.indexes === undefined ? {} : {
      indexes: Object.fromEntries(Object.entries(input.indexes).flatMap(([period, path]) =>
        path === undefined ? [] : [[period, resolve(root, path)]])),
    }),
    ...(input.raw_files === undefined ? {} : { rawFiles: input.raw_files.map(path => resolve(root, path)) }),
    ...(input.raw_index === undefined ? {} : { rawIndex: resolve(root, input.raw_index) }),
  };
}

export async function readExclusionEvidence(input: {
  root: string; now: string; publishedWindowDays: number; settledFailureCodes: readonly ItemHealthFailureCode[];
  publishedRegistration: LedgerRegistration; itemHealthRegistration: LedgerRegistration;
  publishedDays: readonly LedgerDayInput[]; settledFailureDays: readonly LedgerDayInput[];
  concurrency?: number;
}) {
  const now = UtcInstantSchema.parse(input.now);
  if (!Number.isSafeInteger(input.publishedWindowDays) || input.publishedWindowDays < 0) {
    throw new Error("collect.published_window_days must be a finite nonnegative integer in the TypeScript planner");
  }
  const publishedDays = requiredUtcDays(now, input.publishedWindowDays);
  const publishedNamed = namedDays(input.publishedRegistration.prefix, publishedDays,
    input.publishedDays, "published_days");
  const publishedFileCache = new Map<string, Promise<ReadLedgerFile<PublishedRow>>>();
  const indexCache = new Map<string, Promise<unknown | undefined>>();
  const publishedHeld = await mapPool(publishedNamed, input.concurrency ?? publishedNamed.length, async ({ input: day }) => ({
    input: day,
    held: await readLedgerDay({
      ...folderInputs(input.root, day), ledger: "published", day: day.day, contract: PublishedRowProjectionContract,
      fileCache: publishedFileCache, indexCache,
    }),
  }));
  const publishedOn = new Map<string, string>();
  const publishedRows = publishedHeld.flatMap(({ held }) => held.rows.map(({ row }) => row));
  for (const { input: day, held } of publishedHeld) {
    for (const { row } of held.rows) {
      if (row.published_on !== day.day) throw new Error("published row date differs from its named UTC day");
      const previous = publishedOn.get(row.url_key);
      if (previous === undefined || row.published_on < previous) publishedOn.set(row.url_key, row.published_on);
    }
  }

  const codes = input.settledFailureCodes.map(code => ItemHealthFailureCodeSchema.parse(code));
  const wantedCodes = new Set(codes);
  if (codes.length !== wantedCodes.size) throw new Error("collect.settled_failure_codes must be distinct");
  if (wantedCodes.size === 0) return {
    published_on: publishedOn,
    published_rows: publishedRows,
    settled_failure_codes: new Map<string, ItemHealthFailureCode>(),
    history: { published: coverage(publishedHeld), settled_failures: null },
  };
  const settledDays = namedDays(input.itemHealthRegistration.prefix, [now.slice(0, 10)],
    input.settledFailureDays, "settled_failure_days");
  const settledFileCache = new Map<string, Promise<ReadLedgerFile<ItemHealthFailureProjection>>>();
  const settledHeld = await mapPool(settledDays, input.concurrency ?? settledDays.length, async ({ input: day }) => ({
    input: day,
    held: await readLedgerDay({
      ...folderInputs(input.root, day), ledger: "item-health", day: day.day,
      contract: ItemHealthFailureProjectionContract,
      fileCache: settledFileCache, indexCache,
    }),
  }));
  const settledCodes = new Map<string, ItemHealthFailureCode>();
  for (const { input: day, held } of settledHeld) {
    for (const { row: raw } of held.rows) {
      const row: ItemHealthFailureProjection = ItemHealthFailureProjectionContract.schema.parse(raw);
      if (row.date !== day.day) throw new Error("item-health row date differs from its named UTC day");
      if (row.outcome !== "failed" || row.code === null || !wantedCodes.has(row.code)) continue;
      const previous = settledCodes.get(row.url_key);
      if (previous === undefined || row.code < previous) settledCodes.set(row.url_key, row.code);
    }
  }
  return {
    published_on: publishedOn, published_rows: publishedRows, settled_failure_codes: settledCodes,
    history: {
      published: coverage(publishedHeld),
      settled_failures: {
        from_day: now.slice(0, 10), through_day: now.slice(0, 10), required_day_count: 1,
        known_day_count: settledHeld.filter(({ held }) => held.status === "rows" || held.status === "empty").length,
        missing_days: settledHeld.filter(({ held }) => held.status !== "rows" && held.status !== "empty")
          .map(({ input: day }) => day.day),
      },
    },
  };
}
