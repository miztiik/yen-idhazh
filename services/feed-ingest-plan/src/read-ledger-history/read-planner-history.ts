/** Read one named planner UTC day, merging raw and compact representations of its facts. */
import { readFile } from "node:fs/promises";
import { dirname, join, resolve, relative } from "node:path";
import { createHash } from "node:crypto";
import { COMPACT_INDEX_VERSION, RAW_DAY_INDEX_VERSION, CompactIndexSchema, RawDayIndexSchema, PlannerLedgerNameSchema } from "@idhazh/common-contracts";
import type { LedgerRegistration, LedgerRowContract } from "@idhazh/ledger-file-writer";
import type { SeenDayInput } from "../config/service-settings";
import { readPlannerParquet } from "./read-planner-parquet";
import { LedgerHistoryReadError } from "./ledger-history-error";
import { classifyPlannerHistoryGap } from "./planner-history-gap";

function missing(error: unknown) { return error instanceof Error && "code" in error && error.code === "ENOENT"; }
export type PlannerHistoryCache<T extends object> = {
  indexes: Map<string, Promise<unknown | null>>;
  files: Map<string, Promise<Awaited<ReturnType<typeof readPlannerParquet<T>>>>>;
};
export function createPlannerHistoryCache<T extends object>(): PlannerHistoryCache<T> {
  return { indexes: new Map(), files: new Map() };
}
async function index(path: string): Promise<unknown | null> {
  try { return JSON.parse(await readFile(path, "utf8")); }
  catch (error) {
    if (missing(error)) return null;
    if (error instanceof SyntaxError) throw new LedgerHistoryReadError("Planner index is not valid JSON", { cause: error });
    throw error;
  }
}
export async function readPlannerDay<T extends object>(
  root: string, registration: LedgerRegistration, day: SeenDayInput, contract: LedgerRowContract<T>,
  cache: PlannerHistoryCache<T> = createPlannerHistoryCache<T>(),
) {
  const ledger = PlannerLedgerNameSchema.parse(registration.name);
  const files: Awaited<ReturnType<typeof readPlannerParquet<T>>>[] = [];
  let represented = false;
  let complete = true;
  const gaps = new Map<string, string>();
  function readIndex(path: string) {
    let pending = cache.indexes.get(path);
    if (pending === undefined) { pending = index(path); cache.indexes.set(path, pending); }
    return pending;
  }
  function readParquet(path: string) {
    let pending = cache.files.get(path);
    if (pending === undefined) { pending = readPlannerParquet(path, ledger, contract); cache.files.set(path, pending); }
    return pending;
  }
  async function attempt<R>(path: string, read: () => Promise<R>): Promise<R | undefined> {
    try { return await read(); }
    catch (error) {
      const code = classifyPlannerHistoryGap(error);
      if (code === null) throw error;
      complete = false;
      if (!gaps.has(code)) gaps.set(code, relative(root, path).replaceAll("\\", "/"));
      return undefined;
    }
  }
  for (const period of ["yearly", "monthly", "daily"] as const) {
    const named = day.indexes?.[period];
    if (named === undefined) continue;
    const indexPath = resolve(root, named);
    const compact = await attempt(indexPath, async () => {
      const raw = await readIndex(indexPath);
      if (raw === null) return null;
      const parsed = CompactIndexSchema.parse(raw);
      if (parsed.ledger !== ledger || parsed.period !== period || parsed.version > COMPACT_INDEX_VERSION) throw new LedgerHistoryReadError("Planner compact index identity or version was refused");
      return parsed;
    });
    if (compact == null) continue;
    const covers = period === "yearly" ? day.day.slice(0, 4) : period === "monthly" ? day.day.slice(0, 7) : day.day;
    const entry = compact.entries.find(entry => entry.covers === covers);
    if (entry === undefined) continue;
    represented = true;
    if (entry.state === "lost" || entry.lost_days.includes(day.day)) { complete = false; break; }
    if (entry.set_aside > 0) complete = false;
    if (entry.state === "empty") break;
    const base = dirname(dirname(indexPath));
    const parts = covers.split("-");
    const path = period === "yearly" ? join(base, period, covers, `${covers}.parquet`)
      : join(base, period, ...parts.slice(0, -1), `${parts.at(-1)!}.parquet`);
    await attempt(path, async () => {
      const held = await readParquet(path);
      if (held.envelope.tier !== "compact" || held.envelope.period !== period || held.envelope.covers !== covers
        || held.bytes !== entry.bytes || held.rows.length !== entry.rows
        || (entry.file_sha256 != null && held.file_sha256 !== entry.file_sha256)) {
        throw new LedgerHistoryReadError("Planner compact file differs from its named index");
      }
      files.push(held);
    });
    break;
  }
  let rawPaths = day.raw_files?.map(path => resolve(root, path));
  let sizes: readonly number[] | null = null;
  if (day.raw_index !== undefined) {
    const path = resolve(root, day.raw_index);
    const current = await attempt(path, async () => {
      const raw = await readIndex(path);
      if (raw === null) return null;
      const parsed = RawDayIndexSchema.parse(raw);
      if (parsed.ledger !== ledger || parsed.date !== day.day || parsed.version > RAW_DAY_INDEX_VERSION
        || createHash("sha256").update(parsed.files.join("\n")).digest("hex") !== parsed.content_sha256) {
        throw new LedgerHistoryReadError("Planner raw index identity or filename digest differs");
      }
      return parsed;
    });
    if (current != null) {
      rawPaths = current.files.map(name => join(dirname(path), name));
      sizes = current.bytes;
    }
  }
  if (rawPaths !== undefined) {
    represented = true;
    if (new Set(rawPaths).size !== rawPaths.length) throw new LedgerHistoryReadError("Planner raw input repeats a file");
    for (const [position, path] of rawPaths.entries()) {
      await attempt(path, async () => {
        const held = await readParquet(path);
        if (held.envelope.tier !== "raw" || held.envelope.covers !== day.day
          || (sizes !== null && sizes[position] !== held.bytes)) {
          throw new LedgerHistoryReadError("Planner raw file differs from its named day or index");
        }
        files.push(held);
      });
    }
  }
  for (const [code, path] of gaps) console.error(JSON.stringify({ event: "planner_history_gap", ledger, day: day.day, code, path }));
  return {
    day: day.day, complete: represented && complete,
    rows: files.flatMap(file => file.rows.filter(row => "date" in row && row.date === day.day)),
    gaps: [...gaps.keys()],
  };
}
