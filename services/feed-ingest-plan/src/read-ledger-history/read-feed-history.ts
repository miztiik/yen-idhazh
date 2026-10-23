/** Which native history says a feed must rest, has retired, or has delivered reliably? */
import { createHash } from "node:crypto";
import type { LedgerRegistration } from "@idhazh/ledger-file-writer";
import type { SourceSnapshot } from "@idhazh/common-contracts";
import { z } from "zod";
import { FeedHealthContract, FeedRetirementContract } from "@idhazh/common-contracts";
import type { FeedHealthRow, FeedRetirementRow } from "@idhazh/common-contracts";
import type { SeenDayInput } from "../config/service-settings";
import { readNamedDays, historyCoverage, latestNativeRows } from "./named-days";
import { readOwnFeedReceipts } from "./own-feed-receipts";
import type { OwnFeedReceipt } from "./own-feed-receipts";

// Matches ledger.rows.HEALTH_WINDOW_DAYS: the native availability reader's fixed cover.
export const HEALTH_RECORDED_DAYS = 31;
export const FeedHistoryPolicySchema = z.object({
  availability_strikes_before_rest: z.int().positive(),
  feed_http_410_runs_before_retirement: z.int().positive(),
  reliability_window_days: z.int().positive(), reliability_floor: z.number().finite().min(0).max(1),
});
export type FeedHistoryPolicy = z.infer<typeof FeedHistoryPolicySchema>;
export type SourceHistoryEvidence = Readonly<{
  lifecycle: "eligible" | "resting" | "retired";
  retirement_cause: "http_410" | "low_yield" | null;
  endpoint_key: string;
  strikes: number; rested_runs: number; gone_run_ids: readonly string[];
  reliability: {
    success_fraction: number; productive: number; attempted: number; window_days: number;
    from_day: string | null; through_day: string | null; production_factor: number;
  } | null;
}>;
export const endpointKey = (url: string) => createHash("sha256").update(url, "utf8").digest("hex");
const answered = (row: FeedHealthRow) => row.outcome === "ok" && row.items > 0;
const preserves = (row: FeedHealthRow) => row.outcome === "skipped" || row.outcome === "robots_denied";
const observationKey = (row: FeedHealthRow) => JSON.stringify([row.run_id, row.feed_id, row.checked_at]);

function settleFeedHealth(
  rows: readonly FeedHealthRow[], originalWrites: ReadonlyMap<string, number> = new Map(),
): FeedHealthRow[] {
  const settled = new Map<string, FeedHealthRow>();
  for (const row of rows) {
    const key = `${row.run_id}:${row.feed_id}`;
    const previous = settled.get(key);
    if (previous === undefined || (answered(row) && !answered(previous))
      || (answered(row) === answered(previous) && row.checked_at > previous.checked_at)) settled.set(key, row);
  }

  return [...settled.values()].sort((a, b) => {
    const runA = BigInt(a.run_id.split("-").at(-1)!);
    const runB = BigInt(b.run_id.split("-").at(-1)!);
    return a.date.localeCompare(b.date) || a.checked_at.localeCompare(b.checked_at)
      || ((originalWrites.get(observationKey(a)) ?? Date.parse(a.checked_at))
        - (originalWrites.get(observationKey(b)) ?? Date.parse(b.checked_at)))
      || (runA < runB ? -1 : runA > runB ? 1 : 0);
  });
}

function measuredReliability(
  rows: readonly FeedHealthRow[], days: readonly string[], source: string, policy: FeedHistoryPolicy,
): SourceHistoryEvidence["reliability"] {
  const attempts = rows.filter(row => row.feed_id === source && days.includes(row.date) && !preserves(row));
  if (attempts.length === 0) return null;
  const productive = attempts.filter(answered).length;
  return {
    success_fraction: productive / attempts.length, productive, attempted: attempts.length,
    window_days: policy.reliability_window_days,
    from_day: days[0] ?? null, through_day: days.at(-1) ?? null,
    production_factor: Math.max(policy.reliability_floor, productive / attempts.length),
  };
}

export async function readFeedHistory(input: {
  root: string; now: string; run_id: string; sources: readonly SourceSnapshot[]; policy: FeedHistoryPolicy;
  health: LedgerRegistration; retirements: LedgerRegistration;
  health_days: readonly SeenDayInput[]; retirement_days: readonly SeenDayInput[];
  own_receipts?: readonly OwnFeedReceipt[]; receipt_root?: string;
}) {
  const policy = FeedHistoryPolicySchema.parse(input.policy);
  const maxDays = Math.max(HEALTH_RECORDED_DAYS, policy.reliability_window_days);
  if (input.health_days.length > maxDays) throw new Error("feed_health_days exceeds its recorded-day cover");
  for (const day of [...input.health_days, ...input.retirement_days]) {
    if (day.day > input.now.slice(0, 10)) throw new Error("Feed history day exceeds the captured UTC clock");
  }
  const healthDays = await readNamedDays(input.root, input.health, input.health_days, FeedHealthContract);
  const retirementDays = await readNamedDays(input.root, input.retirements, input.retirement_days, FeedRetirementContract);
  const own = await readOwnFeedReceipts(input.receipt_root ?? input.root, input.own_receipts ?? [], input.now, input);
  for (const day of healthDays) for (const { row } of day.rows) {
    if (row.date !== day.day || row.checked_at > input.now) throw new Error("Feed health differs from its named UTC day or run clock");
  }
  for (const day of retirementDays) for (const { row } of day.rows) {
    if (row.retired_on !== day.day) throw new Error("Feed retirement differs from its named UTC day");
  }
  const ownHealth = own.filter(item => item.receipt.ledger === "feed-health")
    .flatMap(item => item.files.flatMap(file => file.rows.map(held => ({
      identity: held.identity, row: FeedHealthContract.schema.parse(held.row),
    }))));
  const ownRetirements = own.filter(item => item.receipt.ledger === "feed-retirements")
    .flatMap(item => item.files.flatMap(file => file.rows.map(held => ({
      identity: held.identity, row: FeedRetirementContract.schema.parse(held.row),
    }))));
  for (const { row } of ownHealth) {
    if (row.checked_at > input.now) throw new Error("Own feed health exceeds the captured UTC clock");
  }
  const originalWrites = new Map<string, number>();
  const healthFiles = [
    ...healthDays.flatMap(day => [...day.files]),
    ...own.filter(item => item.receipt.ledger === "feed-health").flatMap(item => item.files),
  ];
  for (const file of healthFiles) {
    if (file.envelope.tier !== "raw") continue;
    for (const { row: raw } of file.rows) {
      const row = FeedHealthContract.schema.parse(raw);
      const key = observationKey(row);
      originalWrites.set(key, Math.max(originalWrites.get(key) ?? 0, file.envelope.written_at_ms));
    }
  }
  const rows = settleFeedHealth(latestNativeRows([...healthDays.flatMap(day => [...day.rows]), ...ownHealth]), originalWrites);
  const representedDays = [...new Set([...input.health_days.map(day => day.day), ...ownHealth.map(({ row }) => row.date)])].sort();
  const recent = rows.filter(row => representedDays.slice(-HEALTH_RECORDED_DAYS).includes(row.date));
  const reliabilityDays = healthDays.slice(-policy.reliability_window_days);
  const reliabilityCoverage = historyCoverage(reliabilityDays);
  const retired = new Map<string, FeedRetirementRow["cause"]>();
  for (const row of latestNativeRows([...retirementDays.flatMap(day => [...day.rows]), ...ownRetirements])
    .toSorted((a, b) => a.retired_on.localeCompare(b.retired_on))) {
    if (!retired.has(row.endpoint_key)) retired.set(row.endpoint_key, row.cause);
  }
  const newRetirements: FeedRetirementRow[] = [];
  const sources = new Map<string, SourceHistoryEvidence>();
  for (const source of input.sources) {
    const key = endpointKey(source.feed_url);
    const feedRows = recent.filter(row => row.feed_id === source.source_id);
    let strikes = 0;
    for (const row of feedRows.toReversed()) {
      if (preserves(row)) continue;
      if (answered(row)) break;
      strikes++;
    }
    let rested = 0;
    for (const row of feedRows.toReversed()) {
      if (row.outcome !== "skipped") break;
      rested++;
    }
    const gone: string[] = [];
    for (const row of recent.filter(row => row.endpoint_key === key)) {
      if (answered(row)) gone.length = 0;
      else if (row.status === 410 && !gone.includes(row.run_id)) gone.push(row.run_id);
    }
    if (source.status === "active" && !retired.has(key) && gone.length >= policy.feed_http_410_runs_before_retirement) {
      retired.set(key, "http_410");
      newRetirements.push(FeedRetirementContract.schema.parse({
        version: FeedRetirementContract.schemaVersion, feed_id: source.source_id, endpoint_key: key,
        retired_on: input.now.slice(0, 10), decided_by_run: input.run_id, cause: "http_410",
        evidence_run_ids: gone, evidence_dates: [],
      }));
    }
    const reliability = measuredReliability(rows, representedDays.slice(-policy.reliability_window_days), source.source_id, policy);
    sources.set(source.source_id, {
      endpoint_key: key, lifecycle: retired.has(key) ? "retired"
        : strikes >= policy.availability_strikes_before_rest && rested < policy.availability_strikes_before_rest ? "resting" : "eligible",
      retirement_cause: retired.get(key) ?? null,
      strikes, rested_runs: rested, gone_run_ids: gone, reliability,
    });
  }
  return {
    sources, new_retirements: newRetirements, rows, represented_days: representedDays,
    history: {
      own_receipts: own.map(({ receipt, files }) => ({
        ...receipt, evidence: files.map(file => ({
          file_id: file.envelope.file_id, content_sha256: file.envelope.content_sha256, row_count: file.rows.length,
        })),
      })),
      health: {
        ...historyCoverage(healthDays), required_recorded_days: HEALTH_RECORDED_DAYS,
        represented_days: representedDays.slice(-HEALTH_RECORDED_DAYS),
        availability: healthDays.length >= HEALTH_RECORDED_DAYS
          ? historyCoverage(healthDays).availability : "unavailable" as const,
      },
      retirements: historyCoverage(retirementDays),
      reliability: {
        ...reliabilityCoverage, required_recorded_days: policy.reliability_window_days,
        represented_days: representedDays.slice(-policy.reliability_window_days),
        availability: reliabilityDays.length >= policy.reliability_window_days
          ? reliabilityCoverage.availability : "unavailable" as const,
      },
    },
  };
}
export type FeedHistory = Awaited<ReturnType<typeof readFeedHistory>>;

export function observeFeedReliability(history: FeedHistory, current: readonly FeedHealthRow[], policy: FeedHistoryPolicy): void {
  const currentKeys = new Set(current.map(row => `${row.run_id}:${row.feed_id}`));
  const rows = settleFeedHealth([
    ...history.rows.filter(row => !currentKeys.has(`${row.run_id}:${row.feed_id}`)), ...current,
  ]);
  const days = [...new Set([...history.represented_days, ...current.map(row => row.date)])].sort()
    .slice(-policy.reliability_window_days);
  history.history.reliability.represented_days = days;
  for (const [source, evidence] of history.sources) history.sources.set(source, {
    ...evidence, reliability: measuredReliability(rows, days, source, policy),
  });
}
