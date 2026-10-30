/** How are complete, partial and absent request totals shown with their coverage? */
import type { FeedHealthStateRow, PlannerRequestReport } from "@idhazh/common-contracts";
import { escapeMarkdown } from "./markdown-format";

type RequestFeed = PlannerRequestReport["feeds"][number];
type RequestField = keyof RequestFeed["coverage"];
const fields = ["article_requests", "feed_requests", "robots_requests"] as const;
const fieldLabel: Record<RequestField, string> = {
  article_requests: "Article requests", feed_requests: "Feed requests", robots_requests: "Robots requests",
};
function formatCounter(value: number | null, status: string) {
  return value === null ? "Not recorded" : `${value}${status === "partial" ? "*" : ""}`;
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
export function renderRequestReport(requests: PlannerRequestReport | undefined, health: readonly FeedHealthStateRow[] = []) {
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
  const coverageRows = [
    ["Window (UTC)", `${requests.from_day} through ${requests.through_day}`],
    ["Expected closed UTC days", String(periodDays)],
    ["Complete day files / expected", `${completeFiles} / ${periodDays}`],
    ["Feeds listed", String(requests.feeds.length)],
    ...fields.flatMap(field => [
      [`${fieldLabel[field]}: recorded days / expected`, `${recordedDays(field)} / ${periodDays}`],
      [`${fieldLabel[field]}: feeds with counts / listed`, `${feedsWithCounts(field)} / ${requests.feeds.length}`],
      [`${fieldLabel[field]}: complete feeds / listed`, `${completeFeeds(field)} / ${requests.feeds.length}`],
    ]),
    ["Unattributed days", String(requests.unattributed_days.length)],
    ["History inputs complete", String(requests.input_complete)],
  ];
  const feedCoverage = (feed: RequestFeed) => feed.counts_complete ? "Complete"
    : fields.some(field => feed.coverage[field].known_records > 0) ? "Partial" : "No recorded counts";
  const latestHealth = new Map<string, FeedHealthStateRow>();
  for (const row of health) {
    const previous = latestHealth.get(row.feed_id);
    if (previous === undefined || row.date > previous.date) latestHealth.set(row.feed_id, row);
  }
  const reliabilityCells = (feedId: string) => {
    const value = latestHealth.get(feedId)?.reliability;
    return value == null ? "Not recorded | Not recorded | Not recorded"
      : `${value.success_fraction ?? "Not recorded"} | ${value.complete} | `
        + `${value.from_day === null ? "Not recorded" : `${value.from_day} through ${value.through_day}`}`;
  };
  return {
    markdown: [
      "<details>", "<summary>Request counts and coverage</summary>", "",
      "## Table E - Request coverage", "",
      "| Id | Measure | Result |", "| --- | --- | --- |",
      ...coverageRows.map(([label, value], index) => `| E${index + 1} | ${label} | ${value} |`),
      "", "## Table F - Request counts by feed", "",
      "| Id | Feed | Article requests | Feed requests | Robots requests | Request coverage | Feed-read reliability (fraction) | Reliability complete | Reliability window (UTC) |",
      "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
      ...sorted.map((feed, index) =>
        `| F${index + 1} | ${escapeMarkdown(feed.feed_id)} | ${fields.map(field => formatCounter(feed[field], feed.coverage[field].status)).join(" | ")} | ${feedCoverage(feed)} | ${reliabilityCells(feed.feed_id)} |`),
      "", "Feed-read reliability is productive checks / attempted checks, from 0 to 1. A productive check returns at least one usable URL.",
      "Reliability comes from the current run's latest saved health row per feed. Its represented-day window is separate from the closed request window.",
      "Incomplete reliability is an observed fraction, not a complete-history score. Missing reliability is not zero. Feed-read reliability does not score article selection.",
      ...note,
      "", "</details>",
    ].join("\n"),
    notice: `${coverageText} Article / feed / robots requests: ${totals.join(" / ")}.`
      + (requests.complete ? "" : " Partial totals include recorded counts only; see the summary for missing days and counts."),
  };
}
