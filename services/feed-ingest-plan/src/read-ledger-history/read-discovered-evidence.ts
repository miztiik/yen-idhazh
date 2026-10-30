/** Keep first discovery global by URL key across the named planner inputs. */
import { resolve } from "node:path";
import { DiscoveredArticleRowContract, DiscoveredArticleRowSchema } from "@idhazh/common-contracts";
import type { DiscoveredArticleRow } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, LedgerSettings } from "@idhazh/ledger-file-writer";
import { LedgerDayInputSchema, RelativePathSchema } from "../config/service-settings";
import type { LedgerDayInput } from "../config/service-settings";
import { requiredUtcDays } from "../utc-instant";
import type { RunContext } from "../resolve-run-context";
import type { StageLogger } from "../logging/structured-logger";
import { readPlannerDay, createPlannerHistoryCache } from "./read-planner-history";
import { readPlannerParquet } from "./read-planner-parquet";
import { mapPool } from "../harvest-feeds/harvest-pool";
import { defaultDayInput } from "./named-days";

export function parseDiscoveredDays(days: readonly LedgerDayInput[]): LedgerDayInput[] {
  const parsed = days.map(day => LedgerDayInputSchema.parse(day));
  if (parsed.some((day, index) => index > 0 && day.day <= parsed[index - 1]!.day)) {
    throw new Error("Discovery inputs must name distinct ascending UTC days");
  }
  return parsed;
}
export function foldDiscoveryHistory(rows: readonly DiscoveredArticleRow[]) {
  const known = new Map<string, DiscoveredArticleRow>();
  for (const candidate of rows) {
    const row = DiscoveredArticleRowSchema.parse(candidate);
    const prior = known.get(row.url_key);
    if (prior === undefined || row.first_seen_at < prior.first_seen_at) known.set(row.url_key, row);
  }
  return [...known.values()].sort((a, b) => a.url_key.localeCompare(b.url_key));
}
export async function readDiscoveredEvidence(input: {
  root: string; discovered_files: readonly string[]; discovered_days: readonly LedgerDayInput[];
  registration: LedgerRegistration; now: string; lookback_days: number; concurrency: number;
  own_rows?: readonly DiscoveredArticleRow[];
  log?: StageLogger;
}) {
  const required = requiredUtcDays(input.now, input.lookback_days);
  const named = parseDiscoveredDays(input.discovered_days);
  if (named.some(day => !required.includes(day.day))) throw new Error("Discovery day lies outside its configured UTC window");
  const byDay = new Map(named.map(day => [day.day, day]));
  const inventory = required.map(day => byDay.get(day) ?? defaultDayInput(input.registration.prefix, day));
  const cache = createPlannerHistoryCache<DiscoveredArticleRow>();
  const [files, days] = await Promise.all([
    mapPool(input.discovered_files, input.concurrency, path =>
      readPlannerParquet(resolve(input.root, RelativePathSchema.parse(path)), "discovered-articles", DiscoveredArticleRowContract)),
    mapPool(inventory, input.concurrency, day => readPlannerDay(
      input.root, input.registration, day, DiscoveredArticleRowContract, cache, input.log,
    )),
  ]);
  const rows = foldDiscoveryHistory([...files.flatMap(file => file.rows), ...days.flatMap(day => day.rows), ...(input.own_rows ?? [])]);
  const complete = required.every(day => days.find(value => value.day === day)?.complete === true);
  return {
    discovered: rows.length > 0 || named.length > 0 || input.discovered_files.length > 0
      ? { availability: "available" as const, rows } : { availability: "unavailable" as const },
    absence_proof: complete ? "within_configured_window" as const : "unavailable" as const,
    rows,
  };
}
export async function rememberDiscoveries(
  existing: readonly DiscoveredArticleRow[], sightings: readonly DiscoveredArticleRow[],
  context: RunContext, destination: { outputRoot: string; registryEntry: LedgerRegistration; ledgerSettings: LedgerSettings },
) {
  const known = new Map(existing.map(row => [row.url_key, row]));
  const rows = foldDiscoveryHistory(sightings).filter(row => {
    const prior = known.get(row.url_key);
    return prior === undefined || row.first_seen_at < prior.first_seen_at;
  });
  const result = await persistLedger({
    ...destination, ledger: "discovered-articles", rowContract: DiscoveredArticleRowContract,
    writerContext: context.writer, period: { tier: "raw", covers: context.date }, rows,
  });
  if (result.status === "skipped") throw new Error("Planner discovery write was refused");
  return { result, rows: foldDiscoveryHistory([...existing, ...rows]) };
}
