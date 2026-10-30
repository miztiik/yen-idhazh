/** Resolve bounded represented planner days from existing native inventory and period files. */
import {
  CompactIndexSchema, DateStampSchema, PublicationInventoryInputSchema,
} from "../../../packages/common-contracts/src/index";
import type { CompactIndex, FeedHealthStateRow } from "../../../packages/common-contracts/src/index";
import type { LedgerDayInput } from "../src/config/service-settings";
import { createHistoryDayInputs, resolveHistoryInventory } from "./feed-ingest-plan-outputs";
import { closedRequestDays } from "../src/read-ledger-history/request-summary";
import { classifyPlannerHistoryGap } from "../src/read-ledger-history/planner-history-gap";
import { LedgerHistoryReadError } from "../src/read-ledger-history/ledger-history-error";

function representedPeriodDays(period: CompactIndex["period"], covers: string, today: string) {
  const first = period === "yearly" ? `${covers}-01-01` : period === "monthly" ? `${covers}-01` : covers;
  const start = new Date(`${first}T00:00:00Z`);
  if (!Number.isFinite(start.getTime()) || start.getUTCFullYear() < 1 || start.toISOString().slice(0, 10) !== first) {
    throw new LedgerHistoryReadError("Health cover is not a valid UTC period");
  }
  const end = new Date(start);
  if (period === "yearly") end.setUTCFullYear(end.getUTCFullYear() + 1);
  else if (period === "monthly") end.setUTCMonth(end.getUTCMonth() + 1);
  else end.setUTCDate(end.getUTCDate() + 1);
  const days: string[] = [];
  for (const at = new Date(start); at < end; at.setUTCDate(at.getUTCDate() + 1)) {
    const day = at.toISOString().slice(0, 10);
    if (day > today) break;
    days.push(day);
  }
  return days;
}

export async function stageFeedHistory(input: {
  ledger: "feed-health-state"; prefix: readonly string[]; now: string;
  health_window_days: number; request_report_closed_days: number; period_limit: number;
  authored: readonly LedgerDayInput[];
  read: (path: string) => Promise<unknown | undefined>;
  read_period: (path: string) => Promise<readonly FeedHealthStateRow[]>;
  raw_files: (day: string) => Promise<readonly string[]>;
}) {
  if (!Number.isSafeInteger(input.period_limit) || input.period_limit < 1) throw new Error("Health period limit must be positive");
  const base = input.prefix.join("/");
  if (base !== "feed-ingest-plan/feed-health-state") throw new Error("Health history requires its current planner registration");
  const defaults = createHistoryDayInputs(input.prefix, [input.now.slice(0, 10)])[0]!;
  const compact: CompactIndex[] = [];
  const files = new Set<string>(["frontend/public/publication.json", ...Object.values(defaults.indexes)]);
  const notices: string[] = [];
  for (const period of ["yearly", "monthly", "daily"] as const) {
    try {
      const raw = await input.read(defaults.indexes[period]);
      if (raw === undefined) continue;
      const index = CompactIndexSchema.parse(raw);
      if (index.ledger !== input.ledger || index.period !== period) throw new LedgerHistoryReadError("Health index belongs to another registered output");
      compact.push(index);
    } catch (error) {
      const code = classifyPlannerHistoryGap(error);
      if (code === null) throw error;
      notices.push(`health_index_refused:${period}`);
    }
  }
  const days = new Map<string, LedgerDayInput>();
  const rawDays = new Map<string, readonly string[]>();
  async function rawFiles(day: string) {
    let files = rawDays.get(day);
    if (files === undefined) { files = await input.raw_files(day); rawDays.set(day, files); }
    return files;
  }
  let entries: ReturnType<typeof PublicationInventoryInputSchema.parse>["entries"] = [];
  try {
    const inventory = await input.read("frontend/public/publication.json");
    if (inventory === undefined) notices.push("publication_inventory_missing");
    else entries = PublicationInventoryInputSchema.parse(inventory).entries;
  } catch (error) {
    if (classifyPlannerHistoryGap(error) === null) throw error;
    notices.push("health_inventory_refused");
  }
  for (const entry of entries) {
    const prefix = `raw/${base}/`;
    if (entry.root !== "state" || !entry.path.startsWith(prefix)) continue;
    const parts = entry.path.slice(prefix.length).split("/");
    if (parts.length !== 4 || !/^[0-9a-f-]{36}\.parquet$/.test(parts[3]!)) continue;
    const day = DateStampSchema.parse(parts.slice(0, 3).join("-"));
    if (day > input.now.slice(0, 10)) continue;
    const held: LedgerDayInput = days.get(day) ?? createHistoryDayInputs(input.prefix, [day])[0]!;
    const rawFiles = [...new Set([...(held.raw_files ?? []), `state/${entry.path}`])];
    days.set(day, { day, indexes: defaults.indexes, raw_files: rawFiles });
  }
  const periods = compact.flatMap(index => index.entries.filter(entry => entry.state === "packed" && entry.rows > 0).map(entry => ({
    period: index.period, covers: entry.covers,
    path: `state/compact/${base}/${index.period}/${index.period === "yearly"
      ? `${entry.covers}/${entry.covers}` : entry.covers.replaceAll("-", "/")}.parquet`,
  }))).sort((a, b) => b.covers.localeCompare(a.covers) || a.period.localeCompare(b.period));
  let inspected = 0;
  for (const period of periods) {
    const chosen = [...days.keys()].sort().slice(-input.health_window_days);
    const end = period.period === "daily" ? period.covers : period.period === "monthly"
      ? `${period.covers}-31` : `${period.covers}-12-31`;
    if (chosen.length >= input.health_window_days && end < chosen[0]!) break;
    if (inspected >= input.period_limit) { notices.push("health_period_limit_reached"); break; }
    inspected++;
    files.add(period.path);
    try {
      for (const day of representedPeriodDays(period.period, period.covers, input.now.slice(0, 10))) {
        if (!days.has(day)) days.set(day, createHistoryDayInputs(input.prefix, [day])[0]!);
      }
      await input.read_period(period.path);
    } catch (error) {
      const code = classifyPlannerHistoryGap(error);
      if (code === null) throw error;
      notices.push(`health_period_refused:${period.covers}`);
    }
  }
  for (const day of [...closedRequestDays(input.now, input.request_report_closed_days), input.now.slice(0, 10)]) {
    const named = createHistoryDayInputs(input.prefix, [day])[0]!;
    if (!days.has(day) && (await rawFiles(day)).length > 0) days.set(day, named);
  }
  for (const named of input.authored) {
    if (named.day > input.now.slice(0, 10)) throw new Error("Authored health day exceeds the captured UTC clock");
    days.set(named.day, named);
  }
  const selected = [...days.values()].sort((a, b) => a.day.localeCompare(b.day)).slice(-input.health_window_days);
  const from = selected[0]?.day;
  if (from !== undefined && compact.some(index => index.entries.some(entry =>
    (entry.state === "lost" && entry.covers >= from && entry.covers <= input.now.slice(0, 10))
      || entry.lost_days.some(day => day >= from && day <= input.now.slice(0, 10))
      || (entry.set_aside > 0 && entry.covers >= from.slice(0, entry.covers.length)
        && entry.covers <= input.now.slice(0, entry.covers.length))))) {
    notices.push("health_coverage_gap");
  }
  for (const [position, day] of selected.entries()) {
    const members = [...await rawFiles(day.day)];
    const authored = input.authored.find(value => value.day === day.day);
    if (authored?.raw_files !== undefined && [...authored.raw_files].sort().join("\n") !== [...members].sort().join("\n")) {
      throw new LedgerHistoryReadError("Supplied health members differ from the selected Git day");
    }
    selected[position] = { ...day, raw_files: members };
    try {
      for (const path of resolveHistoryInventory({
        ledger: input.ledger, prefix: input.prefix, days: [day.day], compact, rawFiles: members,
        ...(day.indexes === undefined ? {} : { indexes: day.indexes }),
      })) files.add(path);
    } catch (error) {
      if (classifyPlannerHistoryGap(error) === null) throw error;
      notices.push(`health_history_refused:${day.day}`);
    }
  }
  return { inputs: selected, files: [...files].sort(), represented_days: selected.map(day => day.day), notices };
}
