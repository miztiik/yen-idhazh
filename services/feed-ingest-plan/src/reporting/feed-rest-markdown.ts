/** Which recorded feed states explain rest and retry without inventing a schedule? */
import type { FeedHealthStateRow } from "@idhazh/common-contracts";
import { escapeMarkdown } from "./markdown-format";

export function renderFeedRest(feeds: readonly FeedHealthStateRow[]) {
  const rows = [...feeds].sort((a, b) => a.feed_id.localeCompare(b.feed_id) || a.date.localeCompare(b.date));
  return [
    "<details>", "<summary>Feed rest and retry</summary>", "",
    "## Table I - Feed rest and retry", "",
    "| Id | Feed | UTC work day | Availability | Failing checks | Rested runs |",
    "| --- | --- | --- | --- | --- | --- |",
    ...rows.map((feed, index) =>
      `| I${index + 1} | ${escapeMarkdown(feed.feed_id)} | ${feed.date} | ${feed.availability} | ${feed.strikes ?? "Not recorded"} | ${feed.rested_runs ?? "Not recorded"} |`),
    ...(rows.length ? [] : ["", "Feed rest evidence was not recorded."]),
    "", "Rested runs count skipped logical runs, not elapsed time. No rest-entry or next-retry UTC timestamp is recorded.",
    ...(rows.some(feed => feed.availability === "unknown") ? [
      "", "Unknown availability means the saved history did not establish a rest decision. Missing counters are not zero.",
    ] : []),
    "", "</details>",
  ].join("\n");
}
