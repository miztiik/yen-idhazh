/** Which current failures, paused coverage and evidence gaps need operator attention? */
import { HarvestArticleFailureReasonSchema } from "@idhazh/common-contracts";
import type { FeedHealthStateRow, PlanRunRow } from "@idhazh/common-contracts";
import type { z } from "zod";
import type { FeedAvailabilitySnapshotSchema } from "../api/feed-health-state.schema";
import { escapeMarkdown } from "./markdown-format";
import { describeReason } from "./selection-exclusions-markdown";

type AttentionRow = { scope: string; problem: string; impact: string; period: string; next: string };

export function renderFailureEvidence(
  feeds: readonly FeedHealthStateRow[] | undefined,
  availability?: z.infer<typeof FeedAvailabilitySnapshotSchema>,
  run?: PlanRunRow,
  gaps: readonly [string, string, string][] = [],
) {
  const rows: AttentionRow[] = [];
  const addGap = (scope: string, problem: string, impact: string) =>
    rows.push({ scope, problem, impact,
      period: scope === "Historical evidence" ? "Earlier evidence: closed UTC days" : "This run",
      next: "Not recorded" });
  for (const [scope, problem, impact] of gaps) addGap(scope, problem, impact);
  if (run?.failure_code) addGap("Run", run.failure_code, `Planning ${run.status}; completion not established`);
  if (feeds === undefined) addGap("Run", "Feed work evidence unavailable", "Checks, failures and article totals cannot be established");
  const failures = new Map<string, AttentionRow & { count: number; dates: Set<string> }>();
  for (const feed of feeds ?? []) {
    for (const failure of feed.rejection_counts) {
      if (failure.attribution === null || (failure.subject === "article"
        && !HarvestArticleFailureReasonSchema.safeParse(failure.reason_code).success)) continue;
      const status = failure.subject === "feed" && failure.reason_code === feed.last_failure_code ? feed.status : null;
      const problem = `${describeReason(failure.reason_code)}${status === null ? "" : ` (HTTP ${status})`}`;
      const key = JSON.stringify([feed.feed_id, failure.subject, problem, failure.attribution]);
      const group = failures.get(key) ?? {
        scope: feed.feed_id, problem, impact: "", period: "", next: "Not recorded",
        count: 0, dates: new Set<string>(),
      };
      group.count += failure.count;
      group.dates.add(feed.date);
      group.impact = `${group.count} recorded ${failure.subject} failures; underlying cause unavailable`;
      if (failure.subject === "article" && failure.reason_code === "FETCH_FAILED_HTTP") {
        group.impact += "; response status unavailable in report input";
      }
      failures.set(key, group);
    }
  }
  for (const group of failures.values()) {
    rows.push({ ...group, period: `This run: ${[...group.dates].sort().join(", ")} UTC` });
  }
  if (availability === undefined) addGap("Run", "Feed availability evidence unavailable", "Paused coverage and next checks cannot be established");
  for (const feed of availability?.feeds ?? []) {
    if (feed.availability === "eligible" && feed.availability_complete) continue;
    const paused = feed.availability === "resting" || feed.availability === "retired";
    rows.push({
      scope: feed.feed_id,
      problem: paused ? `Coverage paused: ${feed.availability}; historical cause unavailable`
        : "Availability evidence incomplete",
      impact: paused ? "No new feed check while paused; not a new HTTP failure"
        : "Earlier history incomplete; supported deadlines retained",
      period: feed.availability_updated_at === null ? "Earlier evidence: time unavailable"
        : `Saved state at ${feed.availability_updated_at} UTC`,
      next: feed.rest_until ?? (feed.availability === "retired" ? "None: retired" : "Not recorded"),
    });
  }
  const missing = [...new Set(feeds?.filter(feed => feed.article_candidates === null).map(feed => feed.feed_id))].sort();
  if (missing.length) addGap(missing.join(", "), "Technical admission totals unavailable", "Known subtotal is not an exact run total");
  rows.sort((a, b) => a.scope.localeCompare(b.scope) || a.problem.localeCompare(b.problem));
  return {
    markdown: [
      "## Table B - Needs attention", "",
      ...(rows.length ? [
        "| Id | Feed or scope | Problem | Observed impact | Evidence period | Next eligible check (UTC) |",
        "| --- | --- | --- | --- | --- | --- |",
        ...rows.map((item, index) => `| B${index + 1} | ${[item.scope, item.problem, item.impact, item.period, item.next].map(escapeMarkdown).join(" | ")} |`),
        "", "An eligible check is not a scheduled request. A saved HTTP status is a response, not an underlying cause.",
      ] : ["No recorded problems in the supplied run and availability evidence."]),
    ].join("\n"),
    notice: `${rows.length} attention items in saved evidence.`,
  };
}
