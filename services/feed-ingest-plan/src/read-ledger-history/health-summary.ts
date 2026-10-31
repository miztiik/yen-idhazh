/** Derive feed-read reliability and article admission from their own required fields. */
import { FeedHealthStateRowSchema, SourceArticleRefusalReasonSchema } from "@idhazh/common-contracts";
import type { FeedHealthStateRow, SourceSnapshot, FeedLifecyclePolicy } from "@idhazh/common-contracts";
import type { SourceHistoryEvidence, FeedHistoryPolicy } from "./read-feed-history";
import type { HealthCapture } from "./read-health-capture";
import { reuseFeedLifecycle, updateFeedLifecycle } from "./feed-lifecycle-history";
import { reuseFeedReliability } from "./feed-reliability-history";
import { projectLifecycleFields } from "../health-row";
import type { StageLogger } from "../logging/structured-logger";
import { projectFeedHealthFields } from "./read-feed-health-fields";
import { resolveFeedEligibility } from "../availability/feed-lifecycle";

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
  lifecycle_window_days: number; lifecycle_policy: FeedLifecyclePolicy;
  current_rows?: readonly FeedHealthStateRow[]; log?: StageLogger;
  saved_sources?: ReadonlyMap<string, SourceHistoryEvidence>;
}) {
  const now = Date.parse(input.now);
  if (!Number.isFinite(now)) throw new Error("Health summary needs a valid UTC clock");
  const current = input.current_rows ?? [];
  const currentAdmission = current.flatMap(row => projectFeedHealthFields(row.date, [row]).article_admission.rows);
  const represented = [...new Set([
    ...input.days.filter(day => day.day <= input.now.slice(0, 10)).map(day => day.day),
    ...current.filter(row => row.checked_at !== null).map(row => row.date),
  ])].sort();
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
    const onGap = (reason: string) => input.log?.("history", "failed", {
      source: "feed-health-calculation", failed_check: reason, reason, feed_id: source.feed_id,
    });
    const lifecycleDays = represented.slice(-input.lifecycle_window_days);
    const lifecycleRows = [...input.uses.feed_rest.rows, ...input.uses.feed_rest.partial_rows]
      .filter(row => row.feed_id !== undefined && row.endpoint_key !== undefined && matches({
        feed_id: row.feed_id, endpoint_key: row.endpoint_key,
      }) && row.date !== undefined && lifecycleDays.includes(row.date));
    const reliabilityRows = [...input.uses.feed_reliability.rows, ...input.uses.feed_reliability.partial_rows]
      .filter(row => row.feed_id !== undefined && row.endpoint_key !== undefined && matches({
        feed_id: row.feed_id, endpoint_key: row.endpoint_key,
      }));
    const work = current.filter(matches);
    const saved = input.saved_sources?.get(source.feed_id);
    if (saved !== undefined && !matches({ feed_id: source.feed_id, endpoint_key: saved.endpoint_key })) {
      throw new Error("Saved planning calculation belongs to a different endpoint");
    }
    const supported = updateFeedLifecycle(
      saved === undefined ? reuseFeedLifecycle(lifecycleRows, input.now, input.lifecycle_policy, onGap)
        : projectLifecycleFields(saved), work, input.lifecycle_policy,
    );
    supported.availability = resolveFeedEligibility(supported, input.now);
    const { availability, ...lifecycle } = supported;
    const conflicting = (use: keyof typeof input.uses) => input.uses[use].gaps.some(gap =>
      gap.code === "conflict" && (gap.identity === null || matches(gap.identity)));
    if (conflicting("feed_rest")) lifecycle.availability_complete = false;
    const reliability = reuseFeedReliability({
      rows: reliabilityRows, current: work, days: reliabilityDays, history_days: represented, now: input.now,
      ...(saved?.reliability == null ? {} : { saved: saved.reliability }),
      floor: input.policy.reliability_floor, window: input.policy.reliability_window_days, onGap,
      knownDay: day => input.days.find(value => value.day === day)?.complete === true
        && !input.uses.feed_reliability.gaps.some(gap => gap.day === day
          && (gap.identity === null || matches(gap.identity))
          && (gap.identity === null || gap.code === "conflict"
            || ["checked_at", "outcome", "items", "check_request_id"].includes(gap.field))),
    });
    if (conflicting("feed_reliability")) reliability.complete = false;
    const articleRows = [...input.uses.article_admission.rows, ...currentAdmission].filter(row => row.feed_id === source.feed_id
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
      ...lifecycle, lifecycle: source.status === "retired" ? "retired" : availability,
      article_pass_rate: articleKnown && admitted + refused > 0 ? admitted / (admitted + refused) : null,
      reliability,
    });
  }
  return { sources, represented_days: represented };
}

export function captureHealthRows(rows: readonly FeedHealthStateRow[], sources: ReadonlyMap<string, SourceHistoryEvidence>) {
  return rows.map(row => {
    const observed = sources.get(row.feed_id);
    if (observed === undefined || observed.endpoint_key !== row.endpoint_key) throw new Error("Health capture does not match its configured feed endpoint");
    return FeedHealthStateRowSchema.parse({
      ...row, ...projectLifecycleFields(observed),
      reliability: observed.reliability,
    });
  });
}

import { createHash } from "node:crypto";
export function inputEndpointKey(url: string) {
  return createHash("sha256").update(url, "utf8").digest("hex");
}
