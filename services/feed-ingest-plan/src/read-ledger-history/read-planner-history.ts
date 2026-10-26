/** Read one named planner UTC day, merging raw and compact representations of its facts. */
import { readFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { createHash } from "node:crypto";
import { CompactIndexSchema, RawDayIndexSchema, PlannerLedgerNameSchema } from "@idhazh/common-contracts";
import type { LedgerRegistration, LedgerRowContract } from "@idhazh/ledger-file-writer";
import type { SeenDayInput } from "../config/service-settings";
import { readPlannerParquet } from "./read-planner-parquet";
import { LedgerHistoryReadError } from "./ledger-history-error";

function missing(error: unknown) { return error instanceof Error && "code" in error && error.code === "ENOENT"; }
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
) {
  const ledger = PlannerLedgerNameSchema.parse(registration.name);
  const files: Awaited<ReturnType<typeof readPlannerParquet<T>>>[] = [];
  let represented = false;
  let complete = true;
  for (const period of ["yearly", "monthly", "daily"] as const) {
    const named = day.indexes?.[period];
    if (named === undefined) continue;
    const indexPath = resolve(root, named);
    const raw = await index(indexPath);
    if (raw === null) continue;
    const compact = CompactIndexSchema.parse(raw);
    if (compact.ledger !== ledger || compact.period !== period) throw new LedgerHistoryReadError("Planner compact index belongs to another ledger");
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
    try {
      const held = await readPlannerParquet(path, ledger, contract);
      if (held.envelope.tier !== "compact" || held.envelope.period !== period || held.envelope.covers !== covers
        || held.bytes !== entry.bytes || held.rows.length !== entry.rows
        || (entry.file_sha256 != null && held.file_sha256 !== entry.file_sha256)) {
        throw new LedgerHistoryReadError("Planner compact file differs from its named index");
      }
      files.push(held);
    } catch (error) {
      if (!missing(error)) throw error;
      complete = false;
    }
    break;
  }
  let rawPaths = day.raw_files?.map(path => resolve(root, path));
  let sizes: readonly number[] | null = null;
  if (day.raw_index !== undefined) {
    const path = resolve(root, day.raw_index);
    const raw = await index(path);
    if (raw !== null) {
      const current = RawDayIndexSchema.parse(raw);
      if (current.ledger !== ledger || current.date !== day.day
        || createHash("sha256").update(current.files.join("\n")).digest("hex") !== current.content_sha256) {
        throw new LedgerHistoryReadError("Planner raw index identity or filename digest differs");
      }
      rawPaths = current.files.map(name => join(dirname(path), name));
      sizes = current.bytes;
    }
  }
  if (rawPaths !== undefined) {
    represented = true;
    if (new Set(rawPaths).size !== rawPaths.length) throw new LedgerHistoryReadError("Planner raw input repeats a file");
    for (const [position, path] of rawPaths.entries()) {
      try {
        const held = await readPlannerParquet(path, ledger, contract);
        if (held.envelope.tier !== "raw" || held.envelope.covers !== day.day
          || (sizes !== null && sizes[position] !== held.bytes)) {
          throw new LedgerHistoryReadError("Planner raw file differs from its named day or index");
        }
        files.push(held);
      } catch (error) {
        if (!missing(error)) throw error;
        complete = false;
      }
    }
  }
  return {
    day: day.day, complete: represented && complete,
    rows: files.flatMap(file => file.rows.filter(row => "date" in row && row.date === day.day)),
  };
}
