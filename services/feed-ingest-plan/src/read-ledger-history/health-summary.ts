/** Derive feed-read reliability and article admission from their own required fields. */
import { definitelyAfter } from "@idhazh/common-contracts";
import { FeedHealthStateRowSchema, SourceArticleRefusalReasonSchema } from "@idhazh/common-contracts";
import type { FeedHealthStateRow, SourceSnapshot } from "@idhazh/common-contracts";
import type { SourceHistoryEvidence, FeedHistoryPolicy } from "./read-feed-history";
import type { HealthCapture } from "./read-health-capture";

export function settleHealthRows(rows: readonly FeedHealthStateRow[]): FeedHealthStateRow[] {
  const facts = new Map<string, FeedHealthStateRow>();
  for (const row of rows) {
    const key = JSON.stringify([row.date, row.run_id, row.attempt, row.feed_id, row.endpoint_key]);
    const previous = facts.get(key);
    if (previous !== undefined && JSON.stringify(previous) !== JSON.stringify(row)) {
      throw new Error("Conflicting copies of one finalized planner health fact");
    }
    facts.set(key, row);
  }
  return [...facts.values()];
}

export function summarizePlanningHealth(input: {
  uses: Pick<HealthCapture["uses"], "feed_rest" | "feed_reliability" | "article_admission">;
  days: readonly { day: string; complete: boolean }[];
  sources: readonly SourceSnapshot[]; now: string; policy: FeedHistoryPolicy;
  lifecycle_window_days: number;
}) {
  const now = Date.parse(input.now);
  if (!Number.isFinite(now)) throw new Error("Health summary needs a valid UTC clock");
  const represented = [...new Set(input.days.filter(day => day.day <= input.now.slice(0, 10)).map(day => day.day))].sort();
  const reliabilityDays = represented.slice(-input.policy.reliability_window_days);
  const complete = (days: readonly string[], required: number) => days.length >= required
    && days.every(day => input.days.find(value => value.day === day)?.complete === true);
  const sources = new Map<string, SourceHistoryEvidence>();
  for (const source of input.sources) {
    const endpoint = source.feed_url;
    const matches = (row: { feed_id: string; endpoint_key: string }) =>
      row.feed_id === source.feed_id && row.endpoint_key === inputEndpointKey(endpoint);
    const fieldsComplete = (use: keyof typeof input.uses, days: readonly string[], required: number) =>
      complete(days, required) && !input.uses[use].gaps.some(gap => days.includes(gap.day)
        && (gap.identity === null || matches(gap.identity)));
    const logical = (use: "feed_rest" | "feed_reliability") => {
      const matching = input.uses[use].rows.filter(row => matches(row)
        && row.date <= input.now.slice(0, 10) && row.checked_at !== null && Date.parse(row.checked_at) <= now
        && row.outcome !== null && row.items !== null);
      const reads = new Map<string, typeof matching[number]>();
      for (const row of matching) {
        const key = `${row.run_id}:${row.feed_id}`;
        const previous = reads.get(key);
        const productive = row.outcome === "ok" && row.items! > 0;
        const priorProductive = previous?.outcome === "ok" && previous.items! > 0;
        if (previous === undefined || (productive && !priorProductive)
          || (productive === priorProductive && definitelyAfter(row.checked_at!, previous.checked_at!))) reads.set(key, row);
      }
      return [...reads.values()].map(row => ({
        date: row.date, run_id: row.run_id, checked_at: row.checked_at!, outcome: row.outcome!, items: row.items!,
      }));
    };
    const measured = logical("feed_reliability").filter(row => reliabilityDays.includes(row.date)
      && row.outcome !== "skipped" && row.outcome !== "robots_denied");
    const productive = measured.filter(row => row.outcome === "ok" && row.items > 0).length;
    const articleRows = input.uses.article_admission.rows.filter(row => row.feed_id === source.feed_id
      && row.endpoint_key === inputEndpointKey(endpoint) && reliabilityDays.includes(row.date));
    const articleKnown = fieldsComplete("article_admission", reliabilityDays, input.policy.reliability_window_days)
      && articleRows.every(row => row.counts_complete && row.article_candidates !== null);
    const admitted = articleRows.reduce((total, row) => total + (row.article_candidates ?? 0), 0);
    const refused = articleRows.reduce((total, row) => total + row.rejection_counts
      .filter(reason => reason.subject === "article" && reason.attribution === "feed"
        && SourceArticleRefusalReasonSchema.safeParse(reason.reason_code).success)
      .reduce((count, reason) => count + reason.count, 0), 0);
    sources.set(source.feed_id, {
      endpoint_key: inputEndpointKey(endpoint),
      lifecycle: source.status === "retired" ? "retired" : "unknown",
      strikes: null, rested_runs: null,
      article_pass_rate: articleKnown && admitted + refused > 0 ? admitted / (admitted + refused) : null,
      reliability: measured.length === 0 ? null : {
        productive, attempted: measured.length, success_fraction: productive / measured.length,
        from_day: reliabilityDays[0] ?? null, through_day: reliabilityDays.at(-1) ?? null,
        production_factor: Math.max(input.policy.reliability_floor, productive / measured.length),
        complete: fieldsComplete("feed_reliability", reliabilityDays, input.policy.reliability_window_days),
      },
    });
  }
  return { sources, represented_days: represented };
}

export function captureHealthRows(rows: readonly FeedHealthStateRow[], sources: ReadonlyMap<string, SourceHistoryEvidence>) {
  return rows.map(row => {
    const observed = sources.get(row.feed_id);
    if (observed === undefined || observed.endpoint_key !== row.endpoint_key) throw new Error("Health capture does not match its configured feed endpoint");
    return FeedHealthStateRowSchema.parse({
      ...row, availability: observed.lifecycle, strikes: observed.strikes, rested_runs: observed.rested_runs,
      reliability: observed.reliability,
    });
  });
}

import { createHash } from "node:crypto";
export function inputEndpointKey(url: string) {
  return createHash("sha256").update(url, "utf8").digest("hex");
}
