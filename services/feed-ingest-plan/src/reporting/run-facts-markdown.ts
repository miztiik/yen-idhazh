/** Which run facts and partial counts can the saved response and feed rows establish? */
import type { FeedHealthStateRow, PlanRunRow } from "@idhazh/common-contracts";
import { escapeMarkdown } from "./markdown-format";

export function renderRunFacts(row: PlanRunRow, feeds: readonly FeedHealthStateRow[] | undefined) {
  const recorded = (value: number | null) => value === null ? "Not recorded" : String(value);
  const total = (field: "feed_requests" | "article_requests" | "robots_requests") => {
    if (feeds === undefined || feeds.some(feed => feed[field] === null)) return null;
    return feeds.reduce((sum, feed) => sum + feed[field]!, 0);
  };
  const checked = new Set(feeds?.filter(feed => feed.feed_reads !== null && feed.feed_reads > 0)
    .map(feed => feed.feed_id));
  const unknownChecks = feeds?.some(feed => feed.feed_reads === null && !checked.has(feed.feed_id)) ?? false;
  const unavailableAdmissions = new Set(feeds?.filter(feed => feed.article_candidates === null).map(feed => feed.feed_id));
  const knownAdmissions = feeds === undefined || (feeds.length > 0 && feeds.every(feed => feed.article_candidates === null))
    ? null : feeds.reduce((sum, feed) => sum + (feed.article_candidates ?? 0), 0);
  const partialAdmissions = unavailableAdmissions.size > 0;
  const facts: [string, string][] = [
    ["Status", row.status],
    ["Run", row.run_id],
    ["Attempt", String(row.attempt)],
    ...(row.failure_code === null ? [] : [["Failure code", row.failure_code] satisfies [string, string]]),
    ["Feeds with saved run rows", feeds === undefined ? "Not recorded" : String(new Set(feeds.map(feed => feed.feed_id)).size)],
    ["Feeds checked", feeds === undefined ? "Not recorded" : `${checked.size}${unknownChecks ? "*" : ""}`],
    [partialAdmissions ? "Known admitted articles" : "Admitted articles", recorded(knownAdmissions)],
    ["Feeds with unavailable admission totals", feeds === undefined ? "Not recorded" : String(unavailableAdmissions.size)],
    ["Chosen articles", String(row.selected_count)],
    ["Article assignments", String(row.dispatch_count)],
    ["Assignment strategy", row.strategy],
    ["Elapsed planning time (ms)", recorded(row.duration_ms)],
    ["Age evaluated at (UTC)", row.evaluated_at],
    ["Selection started", String(row.selection_started_at_utc !== null)],
    ...(row.selection_started_at_utc === null ? []
      : [["Selection began at (UTC)", row.selection_started_at_utc] satisfies [string, string]]),
  ];
  const admissionNote = partialAdmissions
    ? `${knownAdmissions === null ? "Admission subtotal unavailable" : `${knownAdmissions} known admitted articles`}; exact total unavailable. `
      + `Feeds with unavailable totals: ${[...unavailableAdmissions].sort().map(escapeMarkdown).join(", ")}. `
      + "An unresolved article capture can make its feed total unavailable; it does not mean zero admissions."
    : "";
  const requests = [total("feed_requests"), total("article_requests"), total("robots_requests")];
  return {
    markdown: [
      "## Table A - Run facts", "", "| Id | Fact | Recorded value |", "| --- | --- | --- |",
      ...facts.map(([label, value], index) =>
        `| A${index + 1} | ${label} | ${escapeMarkdown(value)} |`),
      ...(admissionNote ? ["", admissionNote] : []),
      ...(unknownChecks ? ["", "\\* Feeds checked counts only feeds with recorded checks; some check counts are unavailable."] : []),
      "", "Article assignments group selected articles for downstream work; they are not fetch or parser workers.",
    ].join("\n"),
    notice: feeds === undefined ? "No feed-health result was saved for this run."
      : feeds.length === 0 ? "Zero feed rows were recorded for this run."
      : `${new Set(feeds.map(feed => feed.feed_id)).size} feeds with run rows; `
        + `${checked.size} feeds checked${unknownChecks ? " (known subtotal)" : ""}; `
        + `${knownAdmissions === null ? "Admission subtotal unavailable" : `${knownAdmissions} ${partialAdmissions ? "known " : ""}admitted articles`}`
        + `${partialAdmissions ? ` (${unavailableAdmissions.size} ${unavailableAdmissions.size === 1 ? "feed total" : "feed totals"} unavailable)` : ""}; `
        + `${row.selected_count} chosen articles; feed / article / robots requests: ${requests.map(recorded).join(" / ")}. `
        + `Request counts ${requests.every(value => value !== null) ? "complete" : "incomplete; some counts were not recorded"}.`,
  };
}
