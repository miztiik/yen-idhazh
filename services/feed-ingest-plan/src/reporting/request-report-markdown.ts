/** How are complete, partial and absent request totals shown without changing source order? */
import type { PlannerRequestReport } from "@idhazh/common-contracts";
import { escapeMarkdown } from "./markdown-format";

type RequestFeed = PlannerRequestReport["feeds"][number];
type RequestField = keyof RequestFeed["coverage"];
const fields = ["feed_requests", "article_requests", "robots_requests"] as const;
function formatCounter(value: number | null, status: string) {
  return value === null ? "No recorded data" : `${value} ${value === 1 ? "request" : "requests"}${status === "partial" ? "*" : ""}`;
}
function compareCount(left: number | null, right: number | null) {
  if (left === null) return right === null ? 0 : 1;
  return right === null ? -1 : right - left;
}
function describeCoverage(feed: RequestFeed, field: RequestField, periodDays: number) {
  const cell = feed.coverage[field];
  return `${field.replaceAll("_", " ")}: recorded UTC days: ${cell.recorded_days.join(", ") || "none"}; `
    + `${cell.complete_days.length} of ${periodDays} days complete; ${cell.known_records} known records; `
    + `${cell.unknown_records} ${cell.unknown_records === 1 ? "record" : "records"} with missing or invalid counts`;
}
export function renderRequestReport(requests: PlannerRequestReport | undefined) {
  if (requests === undefined) return {
    markdown: "## Table D - Closed-day request spend\n\nNo recorded data.",
    notice: "Closed-day requests: No recorded data.",
  };
  const periodDays = (Date.parse(requests.through_day) - Date.parse(requests.from_day)) / 86_400_000 + 1;
  const coverage = `Window: ${requests.from_day} through ${requests.through_day} UTC (${periodDays} closed days). `
    + `Coverage: ${requests.complete ? "complete" : "not full data"}.`;
  const note = requests.complete ? [] : [
    "", "\\* Not full data: marked totals include only recorded counts, not estimates for missing records.",
    `Missing or incomplete day files: ${requests.missing_days.join(", ") || "none"}. `
      + `Days with records that cannot be attributed: ${requests.unattributed_days.join(", ") || "none"}. `
      + `Staged history inputs: ${requests.input_complete ? "complete" : "incomplete; missing records may affect any day"}.`,
    ...requests.feeds.filter(feed => !feed.counts_complete).flatMap(feed => ["",
      `${escapeMarkdown(feed.feed_id)} - ${fields.filter(field => feed.coverage[field].status !== "complete")
        .map(field => describeCoverage(feed, field, periodDays)).join("; ")}.`]),
  ];
  const sorted = [...requests.feeds].sort((left, right) =>
    compareCount(left.feed_requests, right.feed_requests) || compareCount(left.article_requests, right.article_requests)
    || left.feed_id.localeCompare(right.feed_id));
  const totals = fields.map(field => {
    const known = requests.feeds.flatMap(feed => feed[field] === null ? [] : [feed[field]]);
    const complete = requests.input_complete && requests.missing_days.length === 0 && requests.unattributed_days.length === 0
      && requests.feeds.every(feed => feed.coverage[field].status === "complete");
    const value = known.length === 0 && !complete ? null : known.reduce((sum, count) => sum + count, 0);
    return formatCounter(value, complete ? "complete" : "partial");
  });
  return {
    markdown: [
      "## Table D - Closed-day request spend", "", `${coverage} This is spend, not waste or a ranking penalty.`,
      "", "| Id | Feed | Feed requests | Article requests | Robots requests | Accounting |",
      "| --- | --- | --- | --- | --- | --- |",
      ...sorted.map((feed, index) =>
        `| D${index + 1} | ${escapeMarkdown(feed.feed_id)} | ${fields.map(field => formatCounter(feed[field], feed.coverage[field].status)).join(" | ")} | ${feed.counts_complete ? "Complete" : fields.some(field => feed[field] !== null) ? "Partial*" : "No recorded data"} |`),
      ...note,
    ].join("\n"),
    notice: `${coverage} Feed / article / robots requests: ${totals.join(" / ")}. `
      + (requests.complete ? "" : "* Not full data; only known counts are added. See Table D for day and record coverage. ")
      + "This is spend, not waste or a ranking penalty.",
  };
}
