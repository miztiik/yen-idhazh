/** How does one validated plan result become reusable Markdown and notices? */
import {
  PlanRunRowSchema, readFeedIngestEvent,
} from "../../../../packages/common-contracts/src/index";
import type { FeedHealthStateRow } from "../../../../packages/common-contracts/src/index";
import { PlanResponseSchema } from "../api/plan-response.schema";
import { FeedHealthStateUpdateResponseSchema } from "../api/feed-health-state.schema";
import { escapeMarkdown } from "./markdown-format";
import { renderRequestReport } from "./request-report-markdown";

export type MarkdownSection = Readonly<{ markdown: string; notice: string }>;
export type PlannerMarkdownNotice = Readonly<{
  level: "notice" | "warning"; title: string; message: string;
}>;
export type PlannerMarkdown = Readonly<{
  markdown: string; notices: readonly PlannerMarkdownNotice[];
}>;
export type PlanMarkdownEvidence = Readonly<{
  response: unknown; health?: unknown; policy?: MarkdownSection; host?: MarkdownSection;
}>;

function describeFeedRead(feed: Pick<FeedHealthStateRow, "outcome" | "items" | "last_failure_code">): string {
  if (feed.last_failure_code === "FEED_PARSE_FAILED") return "Feed parsing failed";
  switch (feed.outcome) {
    case "ok":
      return feed.items === null ? "Download succeeded; parsing not recorded"
        : feed.items === 0 ? "No usable feed URLs" : "Feed read succeeded";
    case "robots_denied": return "Robots permission denied or unknown";
    case "blocked": return "Request blocked by URL safety checks";
    case "permanent": return "HTTP request failed (outside retry list)";
    case "transient": return "Download failed (retryable or network failure)";
    case "skipped": return "Feed download skipped";
    case null: return "Not recorded (download result missing)";
  }
}

export function renderPlannerProgressMarkdown(input: unknown): PlannerMarkdown {
  if (!Array.isArray(input)) throw new Error("Progress must be an explicit array");
  const events = input.map(readFeedIngestEvent);
  const first = events[0];
  if (events.some(event => event.run_id !== first!.run_id || event.correlation_id !== first!.correlation_id)) {
    throw new Error("Progress belongs to more than one run");
  }
  const notices = events.flatMap(event => [
    ...(event.phase === "failed" ? [{
      level: "warning" as const, title: "Planner operation failed",
      message: `${event.operation}: ${typeof event.details.failure_code === "string" ? event.details.failure_code : "Cause unavailable"}`,
    }] : []),
    ...(typeof event.details._compliance === "object" && event.details._compliance !== null
      && !Array.isArray(event.details._compliance)
      && event.details._compliance.status === "NON_COMPLIANT" ? [{
        level: "warning" as const, title: "Non-compliant progress event",
        message: `${event.operation} event details did not meet the publisher's requested fields or safety limits.`,
      }] : []),
  ]);
  return {
    notices,
    markdown: [
      "# Feed planner progress", "", "Progress does not prove saved output or publication.", "",
      "## Table A - Observed work", "", "| Id | Operation | State | Details |",
      "| --- | --- | --- | --- |",
      ...events.map((event, index) =>
        `| A${index + 1} | ${event.operation} | ${event.phase} | ${escapeMarkdown(JSON.stringify(event.details))} |`),
      ...(events.some(event => typeof event.details._compliance === "object" && event.details._compliance !== null)
        ? ["", "One or more events are marked NON_COMPLIANT by the publisher."]
        : []),
      ...(events.length ? [] : ["", "No progress was supplied. The result is unavailable."]), "",
    ].join("\n"),
  };
}

export function renderPlanMarkdown(input: PlanMarkdownEvidence): PlannerMarkdown {
  const response = PlanResponseSchema.parse(input.response);
  const row = PlanRunRowSchema.parse(Object.fromEntries(Object.keys(PlanRunRowSchema.shape).map(key =>
    [key, response[key as keyof typeof response]])));
  const health = input.health == null ? null : FeedHealthStateUpdateResponseSchema.parse(input.health);
  if (health !== null && health.rows.some(feed => feed.run_id !== row.run_id || feed.attempt !== row.attempt)) {
    throw new Error("Health report belongs to another execution");
  }
  const feedRows = health?.rows ?? [];
  const tableFeedRows = [...feedRows].sort((left, right) => {
    return compareKnownDescending(left.articles_selected, right.articles_selected)
      || compareKnownDescending(left.article_candidates, right.article_candidates)
      || left.feed_id.localeCompare(right.feed_id) || left.date.localeCompare(right.date);
  });
  const causes = feedRows.flatMap(feed => feed.rejection_counts.map(cause =>
    ({ ...cause, feed_id: feed.feed_id, date: feed.date })))
    .sort((left, right) => right.count - left.count || left.reason_code.localeCompare(right.reason_code)
      || left.feed_id.localeCompare(right.feed_id) || left.date.localeCompare(right.date));
  const requestReport = renderRequestReport(health?.request_report);
  const known = (value: number | null, unit: string) => value === null ? "Not recorded"
    : `${value} ${value === 1 && unit.endsWith("s") ? unit.slice(0, -1) : unit}`;
  const operationName = (operation: typeof row.api_timings[number]["operation"]) => ({
    "feed-health-before-fetch": "Feed health before requests",
    "feed-health-for-selection": "Fresh feed health for selection",
    "feed-health-summary": "Legacy feed-health capture (purpose not recorded)",
    fetch: "Fetch and article work", parse: "HTML parsing", select: "Article selection",
    partition: "Worker assignment", persist: "Selected output",
  })[operation];
  const strategy = { "bin-pack": "work-balanced", "round-robin": "in order", none: "one worker" }[row.strategy];
  const missingFields = "MISSING_REQUIRED_FIELDS rejects an article with a missing or invalid offered URL or identity, or no usable title after extraction. "
    + "The grouped count cannot identify which field failed. It does not mean a feed configuration field is missing.";
  const summary = [
    "# Feed planner run", "", `**Status: ${row.status}.** ${row.failure_code === null ? "The requested planning stages finished." : `Cause: ${escapeMarkdown(row.failure_code)}.`}`,
    "", "This is planning output, not proof of summarization or publication. Article bodies are kept only in the selected text artifact.", "",
    "## Table A - Run facts", "", "| Id | Fact | Recorded value |", "| --- | --- | --- |",
    `| A1 | Run and attempt | ${escapeMarkdown(row.run_id)}; attempt ${row.attempt} |`,
    `| A2 | Feeds with saved run rows | ${health === null ? "Not recorded" : known(new Set(feedRows.map(feed => feed.feed_id)).size, "feeds")} |`,
    `| A3 | Feed checks | ${health === null ? "Not recorded" : known(total(feedRows, feed => feed.feed_reads), "checks")} |`,
    `| A4 | Admitted articles | ${health === null ? "Not recorded" : known(total(feedRows, feed => feed.article_candidates), "articles")} |`,
    `| A5 | Chosen articles | ${row.selected_count} articles |`,
    `| A6 | Worker groups | ${row.dispatch_count} groups; ${strategy} |`,
    `| A7 | Elapsed planning time | ${known(row.duration_ms, "milliseconds")} |`,
    `| A8 | Age evaluated at | ${escapeMarkdown(row.evaluated_at)} UTC |`,
    `| A9 | Selection began at | ${row.selection_started_at_utc === null ? "Selection did not run" : `${escapeMarkdown(row.selection_started_at_utc)} UTC`} |`,
    ...(input.policy === undefined
      ? ["", "## Table B - Applied policy", "", "| Id | Setting | What it controls | Effective value |", "| --- | --- | --- | --- |",
        "| B1 | Effective settings | Values used by this run | Not recorded; policy evidence was not supplied |"]
      : ["", input.policy.markdown]),
    "", "## Table C - Measured operations", "", "| Id | Operation | Duration | State |", "| --- | --- | --- | --- |",
    ...row.api_timings.map((span, index) =>
      `| C${index + 1} | ${operationName(span.operation)} | ${span.duration_ms} milliseconds | ${span.status} |`),
    "", "Concurrent spans can overlap. Do not add them to estimate elapsed run time.",
    "", "<details>", "<summary>Per-feed article results</summary>", "",
    "## Table D - Per-feed article results", "",
    "| Id | Feed | UTC work day | Chosen articles | Admitted articles | Feed checks | Feed / article / robots requests | Feed read result |",
    "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ...tableFeedRows.map((feed, index) =>
      `| D${index + 1} | ${escapeMarkdown(feed.feed_id)} | ${feed.date} | ${known(feed.articles_selected, "articles")} | ${known(feed.article_candidates, "articles")} | ${known(feed.feed_reads, "checks")} | ${[feed.feed_requests, feed.article_requests, feed.robots_requests].map(value => known(value, "requests")).join(" / ")} | ${escapeMarkdown(describeFeedRead(feed))} |`),
    ...(feedRows.length ? [] : ["", health === null ? "Feed work was not recorded." : "Zero feed rows were recorded."]),
    "", "Feed read results combine the recorded download result, usable URL count and failure code. The saved download outcome is unchanged.",
    "", "</details>", "", requestReport.markdown,
    "", "<details>", "<summary>Grouped exclusions</summary>", "",
    "## Table G - Grouped exclusions", "", "| Id | Feed | UTC day | Subject / stage | Reason | Count | Attribution |",
    "| --- | --- | --- | --- | --- | --- | --- |",
    ...causes.map((cause, index) =>
      `| G${index + 1} | ${escapeMarkdown(cause.feed_id)} | ${cause.date} | ${escapeMarkdown(`${cause.subject} / ${cause.stage}`)} | ${escapeMarkdown(cause.reason_code)} | ${known(cause.count, "decisions")} | ${cause.attribution ?? "Not a failure"} |`),
    ...(causes.length ? [] : ["", health === null ? "Exclusion evidence was not recorded." : "No exclusions were recorded."]),
    ...(causes.some(cause => cause.reason_code === "MISSING_REQUIRED_FIELDS") ? ["", missingFields] : []),
    "", "</details>",
    ...(input.host === undefined ? [] : ["", input.host.markdown]),
  ].join("\n");
  function total<T>(rows: readonly T[], value: (row: T) => number | null) {
    const values = rows.map(value);
    return values.some(value => value === null) ? null : values.reduce<number>((sum, value) => sum + value!, 0);
  }
  const feedWork = health === null ? "No feed-health result was saved for this run."
    : feedRows.length === 0 ? "Zero feed rows were recorded for this run."
    : `${known(new Set(feedRows.map(feed => feed.feed_id)).size, "feeds with run rows")}; `
      + `${known(total(feedRows, feed => feed.feed_reads), "feed checks")}; `
      + `${known(total(feedRows, feed => feed.article_candidates), "admitted articles")}; `
      + `${known(total(feedRows, feed => feed.articles_selected), "chosen articles")}; `
      + `feed / article / robots requests: ${[total(feedRows, feed => feed.feed_requests),
        total(feedRows, feed => feed.article_requests), total(feedRows, feed => feed.robots_requests)]
        .map(value => known(value, "requests")).join(" / ")}. `
      + `Request counts ${feedRows.every(feed => feed.counts_complete) ? "complete" : "incomplete; some counts were not recorded"}.`;
  const grouped = new Map<string, number>();
  for (const cause of causes) grouped.set(cause.reason_code, (grouped.get(cause.reason_code) ?? 0) + cause.count);
  const exclusions = health === null ? "Exclusion evidence was not recorded."
    : grouped.size === 0 ? "No exclusions were recorded."
    : [...grouped].sort(([leftReason, leftCount], [rightReason, rightCount]) =>
      rightCount - leftCount || leftReason.localeCompare(rightReason))
      .map(([reason, count]) => `${reason}: ${known(count, "decisions")}`).join("; ")
      + (grouped.has("MISSING_REQUIRED_FIELDS") ? `. ${missingFields}` : ".");
  const notices: PlannerMarkdownNotice[] = [
    ...(input.host === undefined ? [] : [
      { level: "notice" as const, title: "Host fingerprint", message: input.host.notice },
    ]),
    { level: "notice", title: "Feed work", message: feedWork },
    { level: "notice", title: "Request counts", message: requestReport.notice },
    { level: "notice", title: "Grouped exclusions", message: exclusions },
    ...(input.policy === undefined ? [] : [{ level: "notice" as const, title: "Applied policy", message: input.policy.notice }]),
  ];
  if (row.failure_code !== null) notices.push({
    level: "warning", title: "Feed planner outcome",
    message: `Planning ${row.status}: ${row.failure_code}. Saved evidence does not certify completion.`,
  });
  return { markdown: summary, notices };
}

export function renderUnavailablePlanMarkdown(input: { host?: MarkdownSection } = {}): PlannerMarkdown {
  const message = "No planner HTTP result was saved, so planning completion, feed work, request counts and exclusions were not recorded.";
  return {
    markdown: `# Feed planner run\n\n**Planning result unavailable.** ${message}${input.host === undefined ? "" : `\n\n${input.host.markdown}`}`,
    notices: [
      { level: "warning", title: "Feed planner outcome", message },
      ...(input.host === undefined ? [] : [
        { level: "notice" as const, title: "Host fingerprint", message: input.host.notice },
      ]),
    ],
  };
}

function compareKnownDescending(left: number | null, right: number | null) {
  if (left === null) return right === null ? 0 : 1;
  return right === null ? -1 : right - left;
}
