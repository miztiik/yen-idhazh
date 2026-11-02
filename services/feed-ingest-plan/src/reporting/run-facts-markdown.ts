/** Which compact outcome can the saved response and feed rows establish? */
import type { FeedHealthStateRow, PlanRunRow } from "@idhazh/common-contracts";
import { escapeMarkdown } from "./markdown-format";
import { aggregateFeedResults, formatDuration } from "./aggregate-feed-results";

export function renderRunFacts(
  row: PlanRunRow, feeds: readonly FeedHealthStateRow[] | undefined,
  maximum?: string, paused?: number, decimalPlaces?: number,
) {
  const mean = row.selection_metrics?.mean_substance_score;
  const meanScore = mean == null ? "No selected articles"
    : decimalPlaces === undefined ? String(mean) : String(Number(mean.toFixed(decimalPlaces)));
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
    ["Selected website groups", row.selection_metrics === null ? "Selection not completed" : String(row.selection_metrics.selected_website_groups)],
    ["Selected feeds", row.selection_metrics === null ? "Selection not completed" : String(row.selection_metrics.selected_feeds)],
    ["Mean substance score (points)", row.selection_metrics === null ? "Selection not completed" : meanScore],
    ["Technically eligible articles", eligibility],
    ["Feeds checked", feeds === undefined ? "Not recorded" : `${checked.size}${unknownChecks ? "; exact total unavailable" : ""}`],
    ["Feeds paused", paused === undefined ? "Not recorded" : String(paused)],
    ["Elapsed planning time", formatDuration(row.duration_ms)],
  ];
  return {
    markdown: [
      "## Table A - Run outcome", "", "| Id | Measure | Result |", "| --- | --- | --- |",
      ...facts.map(([label, value], index) => `| A${index + 1} | ${label} | ${escapeMarkdown(value!)} |`),
      "", "Feed counts describe this selection, not historically new feeds. Substance points measure article shape, not factual accuracy.",
    ].join("\n"),
    notice: `${row.status}; ${row.selected_count} selected articles; technically eligible articles: ${eligibility}.`,
  };
}
