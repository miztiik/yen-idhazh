/** Which native history says a feed must rest, has retired, or has delivered reliably? */
import { createHash } from "node:crypto";
import type { LedgerRegistration } from "@idhazh/ledger-file-writer";
import type { SourceSnapshot } from "@idhazh/common-contracts";
import { z } from "zod";
import {
  FeedHealthContract, RecordedInstantSchema,
  availabilityEvidence, definitelyAfter, observationGroups,
} from "@idhazh/common-contracts";
import type { FeedHealthRow } from "@idhazh/common-contracts";
import type { SeenDayInput } from "../config/service-settings";
import { readNamedDays, historyCoverage, latestNativeRows } from "./named-days";
import { readOwnFeedReceipts } from "./own-feed-receipts";
import type { OwnFeedReceipt } from "./own-feed-receipts";

export const FeedHistoryPolicySchema = z.object({
  availability_strikes_before_rest: z.int().positive(),
  reliability_window_days: z.int().positive(), reliability_floor: z.number().finite().min(0).max(1),
});
export type FeedHistoryPolicy = z.infer<typeof FeedHistoryPolicySchema>;
export type SourceHistoryEvidence = Readonly<{
  lifecycle: "eligible" | "resting" | "retired" | "unknown";
  endpoint_key: string;
  strikes: number | null; rested_runs: number | null;
  reliability: {
    success_fraction: number; productive: number; attempted: number; window_days: number;
    from_day: string | null; through_day: string | null; production_factor: number;
  } | null;
}>;
export const endpointKey = (url: string) => createHash("sha256").update(url, "utf8").digest("hex");
const answered = (row: FeedHealthRow) => row.outcome === "ok" && row.items > 0;
const preserves = (row: FeedHealthRow) => row.outcome === "skipped" || row.outcome === "robots_denied";
function settleFeedHealth(rows: readonly FeedHealthRow[]): FeedHealthRow[] {
  const settled = new Map<string, FeedHealthRow>();
  for (const row of rows) {
    const key = `${row.run_id}:${row.feed_id}`;
    const previous = settled.get(key);
    if (previous === undefined || (answered(row) && !answered(previous))
      || (answered(row) === answered(previous) && definitelyAfter(row.checked_at, previous.checked_at))) settled.set(key, row);
  }

  return observationGroups([...settled.values()]).flat();
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
  lifecycle_window_days: number;
  health: LedgerRegistration;
  health_days: readonly SeenDayInput[];
  own_receipts?: readonly OwnFeedReceipt[]; receipt_root?: string;
}) {
  const policy = FeedHistoryPolicySchema.parse(input.policy);
  RecordedInstantSchema.parse(input.now);
  if (!Number.isSafeInteger(input.lifecycle_window_days) || input.lifecycle_window_days < 1) {
    throw new Error("feed health lifecycle window must be a positive represented-day count");
  }
  const maxDays = Math.max(input.lifecycle_window_days, policy.reliability_window_days);
  if (input.health_days.length > maxDays) throw new Error("feed_health_days exceeds its recorded-day cover");
  for (const day of input.health_days) {
    if (day.day > input.now.slice(0, 10)) throw new Error("Feed history day exceeds the captured UTC clock");
  }
  const healthDays = await readNamedDays(input.root, input.health, input.health_days, FeedHealthContract);
  const own = await readOwnFeedReceipts(input.receipt_root ?? input.root, input.own_receipts ?? [], input.now, input.health);
  for (const day of healthDays) for (const { row } of day.rows) {
    if (row.date !== day.day || definitelyAfter(row.checked_at, input.now)) throw new Error("Feed health differs from its named UTC day or run clock");
  }
  const ownHealth = own.filter(item => item.receipt.ledger === "feed-health")
    .flatMap(item => item.files.flatMap(file => file.rows.map(held => ({
      identity: held.identity, row: FeedHealthContract.schema.parse(held.row),
    }))));
  for (const { row } of ownHealth) {
    if (definitelyAfter(row.checked_at, input.now)) throw new Error("Own feed health exceeds the captured UTC clock");
  }
  const rows = settleFeedHealth(latestNativeRows([...healthDays.flatMap(day => [...day.rows]), ...ownHealth]));
  const representedDays = [...new Set([...input.health_days.map(day => day.day), ...ownHealth.map(({ row }) => row.date)])].sort();
  const recent = rows.filter(row => representedDays.slice(-input.lifecycle_window_days).includes(row.date));
  const reliabilityDays = healthDays.slice(-policy.reliability_window_days);
  const reliabilityCoverage = historyCoverage(reliabilityDays);
  const sources = new Map<string, SourceHistoryEvidence>();
  for (const source of input.sources) {
    const key = endpointKey(source.feed_url);
    const feedRows = recent.filter(row => row.feed_id === source.source_id);
    const availability = availabilityEvidence(feedRows, policy.availability_strikes_before_rest);
    const reliability = measuredReliability(rows, representedDays.slice(-policy.reliability_window_days), source.source_id, policy);
    sources.set(source.source_id, {
      endpoint_key: key, lifecycle: source.status === "retired" ? "retired"
        : availability.resting === true ? "resting" : availability.resting === null ? "unknown" : "eligible",
      strikes: availability.strikes, rested_runs: availability.rested_runs,
      reliability,
    });
  }
  return {
    sources, rows, represented_days: representedDays,
    history: {
      own_receipts: own.map(({ receipt, files }) => ({
        ...receipt, evidence: files.map(file => ({
          file_id: file.envelope.file_id, content_sha256: file.envelope.content_sha256, row_count: file.rows.length,
        })),
      })),
      health: {
        ...historyCoverage(healthDays), required_recorded_days: input.lifecycle_window_days,
        represented_days: representedDays.slice(-input.lifecycle_window_days),
        availability: healthDays.length >= input.lifecycle_window_days
          ? historyCoverage(healthDays).availability : "unavailable" as const,
      },
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
