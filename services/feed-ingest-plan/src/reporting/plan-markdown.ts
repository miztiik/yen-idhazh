/** How does one validated plan result become reusable Markdown and notices? */
import {
  PlanRunRowSchema, readFeedIngestEvent,
} from "../../../../packages/common-contracts/src/index";
import type { FeedHealthStateRow } from "../../../../packages/common-contracts/src/index";
import { PlanResponseSchema } from "../api/plan-response.schema";
import { FeedHealthStateUpdateResponseSchema } from "../api/feed-health-state.schema";
import { escapeMarkdown } from "./markdown-format";

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
    case null: return "Unavailable (download outcome not recorded)";
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
    if (left.article_candidates === null && right.article_candidates !== null) return 1;
    if (left.article_candidates !== null && right.article_candidates === null) return -1;
    if (left.article_candidates !== null && right.article_candidates !== null
      && left.article_candidates !== right.article_candidates) {
      return right.article_candidates - left.article_candidates;
    }
    return left.feed_id.localeCompare(right.feed_id) || left.date.localeCompare(right.date);
  });
  const causes = feedRows.flatMap(feed => feed.rejection_counts.map(cause =>
    ({ ...cause, feed_id: feed.feed_id, date: feed.date })));
  const requests = health?.request_report;
  const known = (value: number | null, unit: string) => value === null ? "Unavailable"
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
    `| A2 | Chosen articles | ${row.selected_count} articles |`,
    `| A3 | Worker assignment | ${row.dispatch_count} worker groups; ${strategy} |`,
    `| A4 | Elapsed planning time | ${known(row.duration_ms, "milliseconds")} |`,
    `| A5 | Age evaluation clock | ${row.evaluated_at} UTC |`,
    `| A6 | Selection start clock | ${row.selection_started_at_utc === null ? "Selection did not run" : `${row.selection_started_at_utc} UTC`} |`,
    `| A7 | Lifecycle history | ${row.lifecycle_window_days} represented UTC days |`,
    `| A8 | Feed-read reliability | ${row.reliability_window_days} represented UTC days; retains at least ${row.reliability_floor * 100} percent of feed authority; ${row.reliability_penalty_enabled ? "applied when measured" : "not applied"} |`,
    `| A9 | Request report | ${row.request_report_closed_days} closed UTC calendar days, excluding the selection-start day |`,
    "", "## Table B - Measured operations", "", "| Id | Operation | Duration | State |", "| --- | --- | --- | --- |",
    ...row.api_timings.map((span, index) =>
      `| B${index + 1} | ${operationName(span.operation)} | ${span.duration_ms} milliseconds | ${span.status} |`),
    "", "Concurrent spans can overlap. Do not add them to estimate elapsed run time.",
    "", "## Table C - This run's feed work", "",
    "| Id | Feed | UTC work day | Feed checks | Admitted articles | Chosen articles | Feed / article / robots requests | Feed read result |",
    "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ...tableFeedRows.map((feed, index) =>
      `| C${index + 1} | ${escapeMarkdown(feed.feed_id)} | ${feed.date} | ${known(feed.feed_reads, "checks")} | ${known(feed.article_candidates, "articles")} | ${known(feed.articles_selected, "articles")} | ${[feed.feed_requests, feed.article_requests, feed.robots_requests].map(value => known(value, "requests")).join(" / ")} | ${escapeMarkdown(describeFeedRead(feed))} |`),
    ...(feedRows.length ? [] : ["", health === null ? "Feed work is unavailable." : "The supplied run has zero recorded feed rows."]),
    "", "Feed read results combine the recorded download result, usable URL count and failure code. The saved download outcome is unchanged.",
    "", "## Table D - Closed-day request spend", "",
    requests === undefined ? "Request evidence is unavailable." : `Window: ${requests.from_day} through ${requests.through_day} UTC. Coverage: ${requests.complete ? "complete" : "incomplete"}. This is spend, not waste or a ranking penalty.`,
    "", "| Id | Feed | Feed requests | Article requests | Robots requests | Accounting |", "| --- | --- | --- | --- | --- | --- |",
    ...(requests?.feeds ?? []).map((feed, index) =>
      `| D${index + 1} | ${escapeMarkdown(feed.feed_id)} | ${known(feed.feed_requests, "requests")} | ${known(feed.article_requests, "requests")} | ${known(feed.robots_requests, "requests")} | ${feed.counts_complete ? "Complete" : "Incomplete"} |`),
    "", "## Table E - Grouped exclusions", "", "| Id | Feed | UTC day | Subject / stage | Reason | Count | Attribution |",
    "| --- | --- | --- | --- | --- | --- | --- |",
    ...causes.map((cause, index) =>
      `| E${index + 1} | ${escapeMarkdown(cause.feed_id)} | ${cause.date} | ${escapeMarkdown(`${cause.subject} / ${cause.stage}`)} | ${escapeMarkdown(cause.reason_code)} | ${known(cause.count, "decisions")} | ${cause.attribution ?? "Not a failure"} |`),
    ...(causes.length ? [] : ["", health === null ? "Exclusion evidence is unavailable." : "No exclusions were recorded."]),
    ...(causes.some(cause => cause.reason_code === "MISSING_REQUIRED_FIELDS") ? ["", missingFields] : []),
    ...(input.policy === undefined ? [] : ["", input.policy.markdown]),
    ...(input.host === undefined ? [] : ["", input.host.markdown]),
  ].join("\n");
  function total<T>(rows: readonly T[], value: (row: T) => number | null) {
    const values = rows.map(value);
    return values.some(value => value === null) ? null : values.reduce<number>((sum, value) => sum + value!, 0);
  }
  const feedWork = health === null ? "Feed work is unavailable; no health result was saved."
    : feedRows.length === 0 ? "There are zero recorded feed rows; work totals and accounting are unavailable."
    : `${known(new Set(feedRows.map(feed => feed.feed_id)).size, "feeds")}; `
      + `${known(total(feedRows, feed => feed.feed_reads), "feed checks")}; `
      + `${known(total(feedRows, feed => feed.article_candidates), "admitted articles")}; `
      + `${known(total(feedRows, feed => feed.articles_selected), "chosen articles")}; `
      + `feed / article / robots requests: ${[total(feedRows, feed => feed.feed_requests),
        total(feedRows, feed => feed.article_requests), total(feedRows, feed => feed.robots_requests)]
        .map(value => known(value, "requests")).join(" / ")}. `
      + `Accounting ${feedRows.every(feed => feed.counts_complete) ? "complete" : "incomplete; missing counts are unavailable"}.`;
  const requestSpend = requests === undefined ? "Closed-day request evidence is unavailable."
    : `${requests.from_day} through ${requests.through_day} UTC; coverage ${requests.complete ? "complete" : "incomplete"}. `
      + `Feed / article / robots requests: ${[total(requests.feeds, feed => feed.feed_requests),
        total(requests.feeds, feed => feed.article_requests), total(requests.feeds, feed => feed.robots_requests)]
        .map(value => known(value, "requests")).join(" / ")}. This is spend, not waste or a ranking penalty.`;
  const grouped = new Map<string, number>();
  for (const cause of causes) grouped.set(cause.reason_code, (grouped.get(cause.reason_code) ?? 0) + cause.count);
  const exclusions = health === null ? "Exclusion evidence is unavailable."
    : grouped.size === 0 ? "No exclusions were recorded."
    : [...grouped].sort(([left], [right]) => left.localeCompare(right))
      .map(([reason, count]) => `${reason}: ${known(count, "decisions")}`).join("; ")
      + (grouped.has("MISSING_REQUIRED_FIELDS") ? `. ${missingFields}` : ".");
  const notices: PlannerMarkdownNotice[] = [
    ...(input.host === undefined ? [] : [
      { level: "notice" as const, title: "Host fingerprint", message: input.host.notice },
    ]),
    { level: "notice", title: "This run's feed work", message: feedWork },
    { level: "notice", title: "Closed-day request spend", message: requestSpend },
    { level: "notice", title: "Grouped exclusions", message: exclusions },
    ...(input.policy === undefined ? [] : [
      { level: "notice" as const, title: "Policy used", message: input.policy.notice },
    ]),
  ];
  if (row.failure_code !== null) notices.push({
    level: "warning", title: "Feed planner outcome",
    message: `Planning ${row.status}: ${row.failure_code}. Saved evidence does not certify completion.`,
  });
  return { markdown: summary, notices };
}

export function renderUnavailablePlanMarkdown(input: { host?: MarkdownSection } = {}): PlannerMarkdown {
  const message = "No planner HTTP result was saved. Planning completion, feed work, request spend and exclusions are unavailable.";
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
