/** Which compact outcome can the saved response and feed rows establish? */
import type { FeedHealthStateRow, PlanRunRow } from "@idhazh/common-contracts";
import { escapeMarkdown } from "./markdown-format";
import { aggregateFeedResults, formatDuration } from "./aggregate-feed-results";

export function renderRunFacts(
  row: PlanRunRow, feeds: readonly FeedHealthStateRow[] | undefined,
  maximum?: string, paused?: number,
) {
  const results = feeds === undefined ? undefined : aggregateFeedResults(feeds);
  const unavailable = results?.filter(feed => feed.article_candidates === null) ?? [];
  const known = feeds?.flatMap(feed => feed.article_candidates === null ? [] : [feed.article_candidates]);
  const subtotal = known === undefined || (known.length === 0 && feeds!.length > 0)
    ? null : known.reduce((sum, value) => sum + value, 0);
  const checked = new Set(feeds?.filter(feed => feed.feed_reads !== null && feed.feed_reads > 0).map(feed => feed.feed_id));
  const unknownChecks = feeds?.some(feed => feed.feed_reads === null && !checked.has(feed.feed_id));
  const eligibility = `${subtotal === null ? "Not recorded" : subtotal}${unavailable.length
    ? `${subtotal === null ? "" : " known"}; exact total unavailable for ${unavailable.length} ${unavailable.length === 1 ? "feed" : "feeds"}` : ""}`;
  const facts = [
    ["Result", `${row.status}${row.failure_code === null ? "" : `: ${row.failure_code}`}`],
    ["Selected / configured maximum", `${row.selected_count} / ${maximum ?? "Not recorded"}`],
    ["Technically eligible articles", eligibility],
    ["Feeds checked", feeds === undefined ? "Not recorded" : `${checked.size}${unknownChecks ? "; exact total unavailable" : ""}`],
    ["Feeds paused", paused === undefined ? "Not recorded" : String(paused)],
    ["Elapsed planning time", formatDuration(row.duration_ms)],
  ];
  return {
    markdown: [
      "## Table A - Run outcome", "", "| Id | Measure | Result |", "| --- | --- | --- |",
      ...facts.map(([label, value], index) => `| A${index + 1} | ${label} | ${escapeMarkdown(value!)} |`),
    ].join("\n"),
    notice: `${row.status}; ${row.selected_count} selected articles; technically eligible articles: ${eligibility}.`,
  };
}
