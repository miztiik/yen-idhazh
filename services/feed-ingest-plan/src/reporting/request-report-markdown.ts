/** How are complete, partial and absent request totals shown with their coverage? */
import type { PlannerRequestReport } from "@idhazh/common-contracts";
import { escapeMarkdown } from "./markdown-format";

type RequestFeed = PlannerRequestReport["feeds"][number];
type RequestField = keyof RequestFeed["coverage"];
const fields = ["article_requests", "feed_requests", "robots_requests"] as const;
const fieldLabel: Record<RequestField, string> = {
  article_requests: "Article requests", feed_requests: "Feed requests", robots_requests: "Robots requests",
};
function formatCounter(value: number | null, status: string) {
  return value === null ? "Not recorded" : `${value} ${value === 1 ? "request" : "requests"}${status === "partial" ? "*" : ""}`;
}
function compareCount(left: number | null, right: number | null) {
  if (left === null) return right === null ? 0 : 1;
  return right === null ? -1 : right - left;
}
function describeCoverage(feed: RequestFeed, field: RequestField, periodDays: number) {
  const cell = feed.coverage[field];
  return `${fieldLabel[field]}: recorded UTC days: ${cell.recorded_days.join(", ") || "none"}; `
    + `${cell.complete_days.length} of ${periodDays} days complete; ${cell.known_records} known records; `
    + `${cell.unknown_records} ${cell.unknown_records === 1 ? "record" : "records"} with missing or invalid counts`;
}
export function renderRequestReport(requests: PlannerRequestReport | undefined) {
  if (requests === undefined) return {
    markdown: "## Table E - Request coverage\n\nRequest history was not recorded.",
    notice: "Request history was not recorded.",
  };
  const periodDays = (Date.parse(requests.through_day) - Date.parse(requests.from_day)) / 86_400_000 + 1;
  const completeFiles = periodDays - requests.missing_days.length;
  const coverageText = `Request history: ${periodDays} closed UTC days expected; ${completeFiles}/${periodDays} day files complete; `
    + `${requests.feeds.length} feeds listed; coverage ${requests.complete ? "complete" : "partial"}.`;
  const note = requests.complete ? [] : [
    "", "\\* Partial totals include recorded counts only; missing counts are not estimates.",
    `Missing or incomplete day files: ${requests.missing_days.join(", ") || "none"}. `
      + `Days with records that cannot be attributed: ${requests.unattributed_days.join(", ") || "none"}. `
      + `Staged history inputs: ${requests.input_complete ? "complete" : "incomplete; missing records may affect any day"}.`,
    ...requests.feeds.filter(feed => !feed.counts_complete).flatMap(feed => ["",
      `${escapeMarkdown(feed.feed_id)} - ${fields.filter(field => feed.coverage[field].status !== "complete")
        .map(field => describeCoverage(feed, field, periodDays)).join("; ")}.`]),
  ];
  const sorted = [...requests.feeds].sort((left, right) =>
    compareCount(left.article_requests, right.article_requests) || compareCount(left.feed_requests, right.feed_requests)
    || left.feed_id.localeCompare(right.feed_id));
  const totals = fields.map(field => {
    const known = requests.feeds.flatMap(feed => feed[field] === null ? [] : [feed[field]]);
    const complete = requests.input_complete && requests.missing_days.length === 0 && requests.unattributed_days.length === 0
      && requests.feeds.every(feed => feed.coverage[field].status === "complete");
    const value = known.length === 0 && !complete ? null : known.reduce((sum, count) => sum + count, 0);
    return formatCounter(value, complete ? "complete" : "partial");
  });
  const completeFeeds = (field: RequestField) =>
    requests.feeds.filter(feed => feed.coverage[field].status === "complete").length;
  const feedsWithCounts = (field: RequestField) =>
    requests.feeds.filter(feed => feed.coverage[field].known_records > 0).length;
  const recordedDays = (field: RequestField) => new Set(requests.feeds.flatMap(feed =>
    feed.coverage[field].recorded_days)).size;
  const coverageRows = fields.map((field, index) =>
    `| E${index + 5} | ${fieldLabel[field]} | ${recordedDays(field)}/${periodDays} days with records; `
      + `${feedsWithCounts(field)}/${requests.feeds.length} feeds with counts; `
      + `${completeFeeds(field)}/${requests.feeds.length} feeds complete |`);
  const feedCoverage = (feed: RequestFeed) => feed.counts_complete ? "Complete"
    : fields.some(field => feed.coverage[field].known_records > 0) ? "Partial" : "No recorded counts";
  return {
    markdown: [
      "<details>", `<summary>Request counts and coverage (${periodDays} closed UTC days)</summary>`, "",
      "## Table E - Request coverage", "",
      "| Id | Measure | Result |", "| --- | --- | --- |",
      `| E1 | Window | ${requests.from_day} through ${requests.through_day} UTC |`,
      `| E2 | Expected closed days | ${periodDays} |`,
      `| E3 | Complete day files | ${completeFiles}/${periodDays} |`,
      `| E4 | Feeds listed | ${requests.feeds.length} |`,
      ...coverageRows,
      `| E${fields.length + 5} | Unattributed days | ${requests.unattributed_days.length} |`,
      `| E${fields.length + 6} | History inputs | ${requests.input_complete ? "Complete" : "Incomplete"} |`,
      "", "## Table F - Request counts by feed", "",
      "| Id | Feed | Article requests | Feed requests | Robots requests | Coverage |",
      "| --- | --- | --- | --- | --- | --- |",
      ...sorted.map((feed, index) =>
        `| F${index + 1} | ${escapeMarkdown(feed.feed_id)} | ${fields.map(field => formatCounter(feed[field], feed.coverage[field].status)).join(" | ")} | ${feedCoverage(feed)} |`),
      ...note,
      "", "</details>",
    ].join("\n"),
    notice: `${coverageText} Article / feed / robots requests: ${totals.join(" / ")}.`
      + (requests.complete ? "" : " Partial totals include recorded counts only; see the summary for missing days and counts."),
  };
}
