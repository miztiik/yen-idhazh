/** Read one named planner UTC day, merging raw and compact representations of its facts. */
import { resolve, relative } from "node:path";
import { DateStampSchema, PlannerLedgerNameSchema, FEED_HEALTH_STATE_VERSION } from "@idhazh/common-contracts";
import type { PlannerStoredFileEnvelope } from "@idhazh/common-contracts";
import {
  readStoredPlannerParquet, compactPeriodFile, rawDayDirectory,
  readPlannerDayFiles, readPlannerCompactFile, regularPlannerPath,
} from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, LedgerRowContract, PlannerRawDayFiles } from "@idhazh/ledger-file-writer";
import type { LedgerDayInput } from "../config/service-settings";
import { PlannerDayInputSchema } from "../config/service-settings";
import { readPlannerParquet } from "./read-planner-parquet";
import { LedgerHistoryReadError } from "./ledger-history-error";
import { classifyPlannerHistoryGap } from "./planner-history-gap";
import type { StageLogger } from "../logging/structured-logger";
type PlannerHistoryFile<T extends object> = {
  envelope: PlannerStoredFileEnvelope; rows: T[]; bytes: number; file_sha256: string;
};
export type PlannerHistoryCache<T extends object> = {
  files: Map<string, Promise<PlannerHistoryFile<T>>>;
  days: Map<string, Promise<PlannerRawDayFiles>>;
  compact: Map<string, Promise<string | undefined>>;
};
export function createPlannerHistoryCache<T extends object>(): PlannerHistoryCache<T> {
  return { files: new Map(), days: new Map(), compact: new Map() };
}
export async function readPlannerDay<T extends object>(
  root: string, registration: LedgerRegistration, day: LedgerDayInput, contract: LedgerRowContract<T>,
  cache: PlannerHistoryCache<T> = createPlannerHistoryCache<T>(),
  log?: StageLogger,
) {
  return readPlannerDayUsing(root, registration, day, cache, "strict", log,
    (path, ledger) => readPlannerParquet(path, ledger, contract),
    row => "date" in row && row.date === day.day);
}

export async function readStoredPlannerDay(
  root: string, registration: LedgerRegistration, day: LedgerDayInput,
  cache: PlannerHistoryCache<Record<string, unknown>> = createPlannerHistoryCache(),
  log?: StageLogger,
) {
  return readPlannerDayUsing(root, registration, day, cache, "stored", log, async (path, ledger) => {
    const stored = await readStoredPlannerParquet(path, ledger);
    if (ledger === "feed-health-state" && stored.envelope.row_schema_version !== FEED_HEALTH_STATE_VERSION) {
      throw new LedgerHistoryReadError("Feed health history requires the current row schema");
    }
    return stored;
  },
    (row, envelope) => envelope.tier === "raw"
      || row.date === day.day || !DateStampSchema.safeParse(row.date).success);
}

async function readPlannerDayUsing<T extends object>(
  root: string, registration: LedgerRegistration, day: LedgerDayInput, cache: PlannerHistoryCache<T>,
  mode: "stored" | "strict", log: StageLogger | undefined,
  readFile: (path: string, ledger: PlannerStoredFileEnvelope["ledger"]) => Promise<PlannerHistoryFile<T>>,
  includesRow: (row: T, envelope: PlannerStoredFileEnvelope) => boolean,
) {
  PlannerDayInputSchema.parse(day);
  const directory = rawDayDirectory(registration, day.day);
  if (day.raw_files !== undefined && new Set(day.raw_files).size !== day.raw_files.length) {
    throw new LedgerHistoryReadError("Planner raw input repeats a file");
  }
  const ledger = PlannerLedgerNameSchema.parse(registration.name);
  const files: PlannerHistoryFile<T>[] = [];
  let represented: boolean | null = null;
  let covered = false;
  let complete = true;
  const gaps = new Map<string, string>();
  function readParquet(path: string) {
    const key = `${mode}:${path}`;
    let pending = cache.files.get(key);
    if (pending === undefined) {
      pending = regularPlannerPath(root, relative(root, path).replaceAll("\\", "/"))
        .then(() => readFile(path, ledger));
      cache.files.set(key, pending);
    }
    return pending;
  }
  async function attempt<R>(path: string, read: () => Promise<R>): Promise<R | undefined> {
    try { return await read(); }
    catch (error) {
      const code = classifyPlannerHistoryGap(error);
      if (code === null) throw error;
      complete = false;
      if (!gaps.has(code)) gaps.set(code, relative(root, path).replaceAll("\\", "/") || ".");
      return undefined;
    }
  }
  for (const period of ["yearly", "monthly", "daily"] as const) {
    const covers = period === "yearly" ? day.day.slice(0, 4) : period === "monthly" ? day.day.slice(0, 7) : day.day;
    const path = compactPeriodFile(registration, period, covers);
    const before = gaps.size;
    const member = await attempt(resolve(root, path), () => {
      let pending = cache.compact.get(path);
      if (pending === undefined) {
        pending = readPlannerCompactFile(root, registration, period, covers);
        cache.compact.set(path, pending);
      }
      return pending;
    });
    if (member === undefined) { if (gaps.size > before) break; continue; }
    covered = true;
    const held = await attempt(resolve(root, path), async () => {
      const held = await readParquet(resolve(root, path));
      if (held.envelope.tier !== "compact" || held.envelope.period !== period
        || held.envelope.covers !== covers || held.rows.length === 0) {
        throw new LedgerHistoryReadError("Planner compact file differs from its named period");
      }
      return held;
    });
    if (held !== undefined) {
      represented = true;
      files.push(held);
    }
    break;
  }
  const listing = await attempt(resolve(root, directory), () => {
    let pending = cache.days.get(directory);
    if (pending === undefined) {
      pending = readPlannerDayFiles(root, registration, day.day);
      cache.days.set(directory, pending);
    }
    return pending;
  });
  if (listing !== undefined) {
    for (const refusal of listing.refused) {
      complete = false;
      gaps.set(refusal.reason, refusal.path);
    }
    if (day.raw_files !== undefined
      && [...day.raw_files].sort().join("\n") !== listing.members.join("\n")) {
      complete = false;
      gaps.set("membership_refused", directory);
    }
    covered = true;
    const paths = [...new Set([...listing.members, ...day.raw_files ?? []])];
    represented = paths.length > 0 ? true : represented ?? (covered && complete ? false : null);
    for (const local of paths) {
      const path = resolve(root, local);
      await attempt(path, async () => {
        if (local !== `${directory}/${local.split("/").at(-1)}`) {
          throw new LedgerHistoryReadError("Planner raw file lies outside its registered UTC day");
        }
        const held = await readParquet(path);
        if (held.envelope.tier !== "raw" || held.envelope.covers !== day.day) {
          throw new LedgerHistoryReadError("Planner raw file differs from its named day");
        }
        files.push(held);
      });
    }
  }
  if (!covered && gaps.size === 0) gaps.set("missing", directory);
  if (log !== undefined) {
    for (const [code, path] of gaps) log("history", "failed", {
      source: "planner-ledger", failed_check: "named-day-read", reason: code, ledger, day: day.day, path,
    });
  }
  return {
    day: day.day, represented, complete: covered && complete,
    rows: files.flatMap(file => file.rows.filter(row => includesRow(row, file.envelope))),
    gaps: [...gaps.keys()],
  };
}
