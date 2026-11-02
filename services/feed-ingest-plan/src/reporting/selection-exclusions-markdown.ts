/** Which routine decisions explain why articles were not selected without counting failures twice? */
import { HarvestArticleFailureReasonSchema } from "@idhazh/common-contracts";
import type { FeedHealthStateRow } from "@idhazh/common-contracts";
import { escapeMarkdown } from "./markdown-format";

const reasonLabels: Record<string, string> = {
  FETCH_FAILED_HTTP: "HTTP request failed", FETCH_TIMEOUT: "Request timed out",
  FETCH_FAILED: "Request failed", EXTRACT_EMPTY: "No article text extracted",
  EXTRACT_FAILED: "Article extraction failed", FEED_PARSE_FAILED: "Feed parsing failed",
  REJECTED_SCREENING_MIN_WORDS: "Article below minimum word count",
  MISSING_REQUIRED_FIELDS: "Usable URL, identity or title missing",
  PAYWALL_OR_BLOCKED: "Article blocked by screening rules",
  DUPLICATE: "Duplicate article", REJECTED_DUPLICATE: "Duplicate article",
  REJECTED_AGE: "Article outside the allowed age window",
  REJECTED_SCREENING_AGE_CEILING: "Article exceeds the maximum known age",
  REJECTED_DUPLICATE_CANONICAL_CARRIER: "Duplicate story already represented",
  REJECTED_GLOBAL_CAPACITY_REACHED: "Selected article maximum reached",
};
const stageLabels: Record<string, string> = {
  "harvest-feeds": "Technical admission",
  "screen-article-candidates": "Article screening",
  "curate-article-portfolio": "Article selection",
};
export function describeReason(reason: string) {
  return reasonLabels[reason] ?? reason.replaceAll("_", " ").toLowerCase();
}
export function renderSelectionExclusions(feeds: readonly FeedHealthStateRow[] | undefined) {
  const groups = new Map<string, { stage: string; reason: string; count: number; feeds: Set<string> }>();
  for (const feed of feeds ?? []) {
    for (const cause of feed.rejection_counts) {
      if (cause.subject !== "article" || (cause.attribution !== null
        && HarvestArticleFailureReasonSchema.safeParse(cause.reason_code).success)) continue;
      const key = JSON.stringify([cause.stage, cause.reason_code]);
      const group = groups.get(key) ?? { stage: cause.stage, reason: cause.reason_code, count: 0, feeds: new Set<string>() };
      group.count += cause.count;
      group.feeds.add(feed.feed_id);
      groups.set(key, group);
    }
  }
  const rows = [...groups.values()].sort((a, b) => b.count - a.count || a.reason.localeCompare(b.reason));
  return [
    "<details>", "<summary>Why articles were not selected</summary>", "",
    "## Table F - Selection exclusions", "",
    "| Id | Stage | Reason | Articles excluded | Feeds affected |", "| --- | --- | --- | --- | --- |",
    ...rows.map((row, index) => `| F${index + 1} | ${escapeMarkdown(stageLabels[row.stage] ?? row.stage.replaceAll("-", " "))} | ${escapeMarkdown(describeReason(row.reason))} | ${row.count} | ${row.feeds.size} |`),
    ...(rows.length ? [] : ["", feeds === undefined ? "Exclusion evidence was not recorded." : "No routine exclusions were recorded."]),
    "", "These are recorded decisions, not a subtractable funnel. Failed requests are shown only in Needs attention.",
    "Per-feed reasons are retained in the downloadable Markdown run artifact.",
    "", "</details>",
  ].join("\n");
}

export function renderExclusionDiagnostics(feeds: readonly FeedHealthStateRow[]) {
  const rows = feeds.flatMap(feed => feed.rejection_counts.map(cause => ({ ...cause, feed: feed.feed_id, date: feed.date })));
  return [
    "", "<details>", "<summary>Per-feed exclusion diagnostics (artifact only)</summary>", "",
    "## Table I - Per-feed exclusion diagnostics", "",
    "| Id | Feed | UTC day | Subject | Stage | Reason code | Recorded decisions | Attribution |",
    "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ...rows.map((row, index) => `| I${index + 1} | ${[row.feed, row.date, row.subject, row.stage, row.reason_code, String(row.count), row.attribution ?? "Not a failure"].map(escapeMarkdown).join(" | ")} |`),
    "", "</details>",
  ].join("\n");
}
