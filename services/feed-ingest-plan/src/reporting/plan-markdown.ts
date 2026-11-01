/** How does one validated plan result become reusable Markdown and notices? */
import {
  PlanRunRowSchema, RejectedArticleRowSchema, FeedHealthRestFieldsSchema, readFeedIngestEvent,
} from "../../../../packages/common-contracts/src/index";
import { PlanResponseSchema } from "../api/plan-response.schema";
import { FeedHealthStateUpdateResponseSchema } from "../api/feed-health-state.schema";
import { escapeMarkdown } from "./markdown-format";
import { renderRequestReport } from "./request-report-markdown";
import { renderRunFacts } from "./run-facts-markdown";
import { renderFailureEvidence } from "./failure-evidence-markdown";
import type { ReportFailureEvidence } from "./failure-evidence-markdown";
import { aggregateFeedResults, compareKnownDescending, formatDuration } from "./aggregate-feed-results";
import { renderSelectionExclusions } from "./selection-exclusions-markdown";

export type MarkdownSection = Readonly<{ markdown: string; notice: string }>;
export type PlannerMarkdownNotice = Readonly<{
  level: "notice" | "warning"; title: string; message: string;
}>;
export type PlannerMarkdown = Readonly<{
  markdown: string; notices: readonly PlannerMarkdownNotice[];
}>;
export type PlanMarkdownEvidence = Readonly<{
  response: unknown; health?: unknown; policy?: MarkdownSection; host?: MarkdownSection;
  maximum?: string;
  failures?: ReportFailureEvidence;
}>;

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
  const failures = input.failures === undefined ? undefined : {
    ...input.failures,
    ...(input.failures.articles === undefined ? {}
      : { articles: RejectedArticleRowSchema.array().parse(input.failures.articles) }),
    ...(input.failures.earlier_checks === undefined ? {}
      : { earlier_checks: FeedHealthRestFieldsSchema.array().parse(input.failures.earlier_checks) }),
  };
  if (failures?.articles?.some(article => article.run_id !== row.run_id || article.attempt !== row.attempt)) {
    throw new Error("Article failure report belongs to another execution");
  }
  const feedRows = health?.rows ?? [];
  const tableFeedRows = aggregateFeedResults(feedRows).sort((left, right) =>
    compareKnownDescending(left.articles_selected, right.articles_selected)
      || compareKnownDescending(left.article_candidates, right.article_candidates)
      || left.feed_id.localeCompare(right.feed_id));
  const requestReport = renderRequestReport(health?.request_report, health?.rows);
  const facts = renderRunFacts(row, health?.rows, input.maximum,
    health?.availability?.feeds.filter(feed => feed.availability === "resting" || feed.availability === "retired").length);
  const gaps: [string, string, string][] = [];
  if (health?.request_report.complete !== true) gaps.push([
    "Historical evidence", "Request history incomplete or unavailable", "Exact historical totals unavailable; see Request counts and coverage",
  ]);
  if (input.policy === undefined || input.maximum === "Not recorded") gaps.push([
    "Run", "Effective settings evidence unavailable", "Configured maximum and applied controls cannot be established",
  ]);
  const failureEvidence = renderFailureEvidence(health?.rows, health?.availability, row, gaps, failures);
  const operationName = (operation: typeof row.api_timings[number]["operation"]) => ({
    "feed-health-before-fetch": "Feed health before requests",
    "feed-health-for-selection": "Fresh feed health for selection",
    "feed-health-summary": "Legacy feed-health capture (purpose not recorded)",
    fetch: "Fetch and article work", parse: "HTML parsing", select: "Article selection",
    partition: "Worker assignment", persist: "Selected output",
  })[operation];
  const summary = [
    "# Feed planner run", "", facts.markdown, "", failureEvidence.markdown,
    "", "<details>", "<summary>Per-feed article results</summary>", "",
    "## Table C - Per-feed article results", "",
    "| Id | Feed | Selected articles | Technically eligible articles | Feed checks |",
    "| --- | --- | --- | --- | --- |",
    ...tableFeedRows.map((feed, index) =>
      `| C${index + 1} | ${escapeMarkdown(feed.feed_id)} | ${feed.articles_selected ?? "Not recorded"} | ${feed.article_candidates ?? "Not recorded"} | ${feed.feed_reads ?? "Not recorded"} |`),
    ...(feedRows.length ? [] : ["", health === null ? "Feed work was not recorded." : "Zero feed rows were recorded."]),
    "", "Technically eligible means original captures passing technical admission, not later screening. Each feed combines this run's UTC work days; one unknown constituent makes its exact total unavailable.",
    "", "</details>", "", requestReport.markdown,
    "", renderSelectionExclusions(health?.rows),
    ...(input.policy === undefined ? [
      "", "<details>", "<summary>Effective settings</summary>", "",
      "## Table G - Effective settings", "", "| Id | Setting | Effective value | Source |",
      "| --- | --- | --- | --- |", "| G1 | Effective settings | Not recorded | Captured policy unavailable |",
      "", "</details>",
    ] : ["", input.policy.markdown]),
    "", "<details>", "<summary>Execution measurements</summary>", "",
    "## Table H - Execution measurements", "", "| Id | Measure | Recorded value |", "| --- | --- | --- |",
    ...(input.host === undefined ? ["| H1 | Machine | Not recorded |"] : [input.host.markdown]),
    `| H${(input.host?.markdown.split("\n").filter(line => /^\| H\d+ \|/.test(line)).length ?? 1) + 1} | Run / attempt | ${escapeMarkdown(row.run_id)} / ${row.attempt} |`,
    ...row.api_timings.map((span, index) =>
      `| H${(input.host?.markdown.split("\n").filter(line => /^\| H\d+ \|/.test(line)).length ?? 1) + index + 2} | ${operationName(span.operation)} (${span.status}) | ${formatDuration(span.duration_ms)} |`),
    "", "Concurrent operation durations can overlap. Do not add them to estimate elapsed run time.",
    "", "</details>",
  ].join("\n");
  const notices: PlannerMarkdownNotice[] = [];
  if (row.failure_code !== null) notices.push({
    level: "warning", title: "Feed planner outcome",
    message: `Planning ${row.status}: ${row.failure_code}. Saved evidence does not certify completion.`,
  });
  return { markdown: summary, notices };
}

export function renderUnavailablePlanMarkdown(input: { host?: MarkdownSection } = {}): PlannerMarkdown {
  const message = "No planner HTTP result was saved, so planning completion, feed work, request counts and exclusions were not recorded.";
  return {
    markdown: `# Feed planner run\n\n## Table A - Run outcome\n\n**Planning result unavailable.**\n\n## Table B - Needs attention\n\n${message}${input.host === undefined ? "" : `\n\n<details>\n<summary>Execution measurements</summary>\n\n## Table H - Execution measurements\n\n| Id | Measure | Recorded value |\n| --- | --- | --- |\n${input.host.markdown}\n\n</details>`}`,
    notices: [
      { level: "warning", title: "Feed planner outcome", message },
    ],
  };
}
