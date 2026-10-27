/** Read one named planner UTC day, merging raw and compact representations of its facts. */
import { readFile, realpath } from "node:fs/promises";
import { dirname, join, resolve, relative } from "node:path";
import { COMPACT_INDEX_VERSION, CompactIndexSchema, PlannerLedgerNameSchema } from "@idhazh/common-contracts";
import type { LedgerRegistration, LedgerRowContract } from "@idhazh/ledger-file-writer";
import type { SeenDayInput } from "../config/service-settings";
import { readPlannerParquet } from "./read-planner-parquet";
import { LedgerHistoryReadError } from "./ledger-history-error";
import { classifyPlannerHistoryGap } from "./planner-history-gap";
import { fixedHistoryRevision, listExactRawDayMembers, rawDayDirectory, verifyRawDayMember } from "./raw-day-members";

function missing(error: unknown) { return error instanceof Error && "code" in error && error.code === "ENOENT"; }
export type PlannerHistoryCache<T extends object> = {
  indexes: Map<string, Promise<unknown | null>>;
  files: Map<string, Promise<Awaited<ReturnType<typeof readPlannerParquet<T>>>>>;
  revision?: Promise<string>;
  trees: Map<string, Promise<string>>;
};
export function createPlannerHistoryCache<T extends object>(): PlannerHistoryCache<T> {
  return { indexes: new Map(), files: new Map(), trees: new Map() };
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
  if (day.raw_index !== undefined) throw new LedgerHistoryReadError("Planner raw days do not accept raw_index");
  rawDayDirectory(registration, day.day);
  const ledger = PlannerLedgerNameSchema.parse(registration.name);
  const files: Awaited<ReturnType<typeof readPlannerParquet<T>>>[] = [];
  let represented: boolean | null = null;
  let covered = false;
  let selectedCompact = false;
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
    // Match native held_days: a nonempty month/year represents even its row-free days.
    // Known-empty entries prove request coverage, not lifecycle/reliability membership.
    represented = (represented ?? false) || entry.rows > 0;
    if (selectedCompact) continue;
    selectedCompact = true;
    covered = true;
    if (entry.state === "lost" || entry.lost_days.includes(day.day)) { complete = false; continue; }
    if (entry.set_aside > 0) complete = false;
    if (entry.state === "empty") continue;
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
  }
  let rawPaths = day.raw_files?.map(path => resolve(root, path));
  const committedDigests = new Map<string, string>();
  if (rawPaths === undefined || day.raw_revision !== undefined) {
    const discovered = await attempt(resolve(root, `state/raw/${registration.prefix.join("/")}`), async () => {
      const revision = await (cache.revision ??= day.raw_revision === undefined
        ? fixedHistoryRevision(root) : Promise.resolve(day.raw_revision));
      if (day.raw_revision !== undefined && day.raw_revision !== revision) {
        throw new LedgerHistoryReadError("Raw history revisions differ within one capture");
      }
      const listing = await listExactRawDayMembers(root, registration, day.day, revision, cache.trees);
      const expected = listing.members.map(member => resolve(root, member.path));
      if (rawPaths !== undefined && [...rawPaths].sort().join("\n") !== [...expected].sort().join("\n")) {
        throw new LedgerHistoryReadError("Supplied raw members differ from the complete named Git day");
      }
      for (const member of listing.members) {
        committedDigests.set(resolve(root, member.path), (await verifyRawDayMember(root, member)).file_sha256);
      }
      return expected;
    });
    rawPaths = discovered;
  }
  if (rawPaths !== undefined) {
    covered = true;
    represented = rawPaths.length > 0 ? true : represented ?? (complete ? false : null);
    if (new Set(rawPaths).size !== rawPaths.length) throw new LedgerHistoryReadError("Planner raw input repeats a file");
    for (const path of rawPaths) {
      await attempt(path, async () => {
        const local = relative(root, path).replaceAll("\\", "/");
        const suffix = `raw/${registration.prefix.join("/")}/${day.day.replaceAll("-", "/")}/`;
        if (local.startsWith("../") || (local !== `${suffix}${local.split("/").at(-1)}`
          && local !== `state/${suffix}${local.split("/").at(-1)}`)) {
          throw new LedgerHistoryReadError("Planner raw file lies outside its registered UTC day");
        }
        const actual = await realpath(path);
        const expected = resolve(await realpath(root), local);
        if (actual !== expected) throw new LedgerHistoryReadError("Planner raw file crosses a linked directory");
        const held = await readParquet(path);
        const digest = committedDigests.get(path);
        if (digest !== undefined && held.file_sha256 !== digest) {
          throw new LedgerHistoryReadError("Raw history bytes changed during the named revision read");
        }
        if (held.envelope.tier !== "raw" || held.envelope.covers !== day.day) {
          throw new LedgerHistoryReadError("Planner raw file differs from its named day");
        }
        files.push(held);
      });
    }
  }
  for (const [code, path] of gaps) console.error(JSON.stringify({ event: "planner_history_gap", ledger, day: day.day, code, path }));
  return {
    day: day.day, represented, complete: covered && complete,
    rows: files.flatMap(file => file.rows.filter(row => "date" in row && row.date === day.day)),
    gaps: [...gaps.keys()],
  };
}
