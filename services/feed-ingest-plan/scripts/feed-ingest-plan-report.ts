/** Render a body-free planner outcome without claiming summary quality or publication. */
import { appendFile, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import {
  FeedIngestConfigSchema, PlanRunRowSchema, readFeedIngestEvent,
} from "../../../packages/common-contracts/src/index";
import type { FeedHealthStateRow } from "../../../packages/common-contracts/src/index";
import { PlanResponseSchema } from "../src/api/plan-response.schema";
import { FeedHealthStateUpdateResponseSchema } from "../src/api/feed-health-state.schema";
import { escapeCommand, escapeMarkdown, escapeParameter } from "./feed-ingest-plan-report-format";
import { formatPolicyTable } from "./feed-ingest-plan-policy-report";
import { formatResourceSummary } from "./feed-ingest-plan-resource-summary";

export type PlannerReport = { annotations: readonly string[]; summary: string };
export type ExecutionReportEvidence = {
  response: unknown; health?: unknown; historyStagingMs?: unknown;
  policy?: unknown; resources?: unknown; independent?: unknown; profileRequested?: boolean;
};
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
export function formatPlannerReport(input: unknown): PlannerReport {
  if (!Array.isArray(input)) throw new Error("Progress must be an explicit array");
  const events = input.map(readFeedIngestEvent);
  const first = events[0];
  if (events.some(event => event.run_id !== first!.run_id || event.correlation_id !== first!.correlation_id)) {
    throw new Error("Progress belongs to more than one run");
  }
  const annotations = events.filter(event => event.phase === "failed").map(event =>
    `::warning title=${escapeParameter("Planner operation failed")}::${escapeCommand(`${event.operation}: ${event.failure_code ?? "Cause unavailable"}`)}`);
  return {
    annotations, summary: [
      "# Feed planner progress", "", "Progress does not prove saved output or publication.", "",
      "## Table A - Observed work", "", "| Id | Operation | State | Feed | Measured duration |",
      "| --- | --- | --- | --- | --- |",
      ...events.map((event, index) => `| A${index + 1} | ${event.operation} | ${event.phase} | ${escapeMarkdown(event.feed_id ?? "Unavailable")} | ${event.duration_ms === null ? "Unavailable" : `${event.duration_ms} milliseconds`} |`),
      ...(events.length ? [] : ["", "No progress was supplied. The result is unavailable."]), "",
    ].join("\n"),
  };
}
export function formatExecutionOutcome(input: ExecutionReportEvidence): PlannerReport {
  const response = PlanResponseSchema.parse(input.response);
  const row = PlanRunRowSchema.parse(Object.fromEntries(Object.keys(PlanRunRowSchema.shape).map(key =>
    [key, response[key as keyof typeof response]])));
  const health = input.health == null ? null : FeedHealthStateUpdateResponseSchema.parse(input.health);
  if (health !== null && health.rows.some(feed => feed.run_id !== row.run_id || feed.attempt !== row.attempt)) throw new Error("Health report belongs to another execution");
  const staging = input.historyStagingMs;
  if (staging !== undefined && (typeof staging !== "number" || !Number.isSafeInteger(staging) || staging < 0)) throw new Error("History staging duration must be a measured nonnegative integer");
  const feedRows = health?.rows ?? [];
  const causes = feedRows.flatMap(feed => feed.rejection_counts.map(cause => ({ ...cause, feed_id: feed.feed_id, date: feed.date })));
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
  const policy = formatPolicyTable(input.policy, row.selection_started_at_utc !== null);
  const resources = formatResourceSummary(input.resources, input.independent, input.profileRequested);
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
    `| A10 | History staging time | ${staging === undefined ? "Unavailable" : `${staging} milliseconds`} |`,
    "", "## Table B - Measured operations", "", "| Id | Operation | Duration | State |", "| --- | --- | --- | --- |",
    ...row.api_timings.map((span, index) => `| B${index + 1} | ${operationName(span.operation)} | ${span.duration_ms} milliseconds | ${span.status} |`),
    "", "Concurrent spans can overlap. Do not add them to estimate elapsed run time.",
    "", "## Table C - This run's feed work", "",
    "| Id | Feed | UTC work day | Feed checks | Admitted articles | Chosen articles | Feed / article / robots requests | Feed read result |",
    "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ...feedRows.map((feed, index) => `| C${index + 1} | ${escapeMarkdown(feed.feed_id)} | ${feed.date} | ${known(feed.feed_reads, "checks")} | ${known(feed.article_candidates, "articles")} | ${known(feed.articles_selected, "articles")} | ${[feed.feed_requests, feed.article_requests, feed.robots_requests].map(value => known(value, "requests")).join(" / ")} | ${escapeMarkdown(describeFeedRead(feed))} |`),
    ...(feedRows.length ? [] : ["", health === null ? "Feed work is unavailable." : "The supplied run has zero recorded feed rows."]),
    "", "Feed read results combine the recorded download result, usable URL count and failure code. The saved download outcome is unchanged.",
    "", "## Table D - Closed-day request spend", "",
    requests === undefined ? "Request evidence is unavailable." : `Window: ${requests.from_day} through ${requests.through_day} UTC. Coverage: ${requests.complete ? "complete" : "incomplete"}. This is spend, not waste or a ranking penalty.`,
    "", "| Id | Feed | Feed requests | Article requests | Robots requests | Accounting |", "| --- | --- | --- | --- | --- | --- |",
    ...(requests?.feeds ?? []).map((feed, index) => `| D${index + 1} | ${escapeMarkdown(feed.feed_id)} | ${known(feed.feed_requests, "requests")} | ${known(feed.article_requests, "requests")} | ${known(feed.robots_requests, "requests")} | ${feed.counts_complete ? "Complete" : "Incomplete"} |`),
    "", "## Table E - Grouped exclusions", "", "| Id | Feed | UTC day | Subject / stage | Reason | Count | Attribution |",
    "| --- | --- | --- | --- | --- | --- | --- |",
    ...causes.map((cause, index) => `| E${index + 1} | ${escapeMarkdown(cause.feed_id)} | ${cause.date} | ${escapeMarkdown(`${cause.subject} / ${cause.stage}`)} | ${escapeMarkdown(cause.reason_code)} | ${known(cause.count, "decisions")} | ${cause.attribution ?? "Not a failure"} |`),
    ...(causes.length ? [] : ["", health === null ? "Exclusion evidence is unavailable." : "No exclusions were recorded."]),
    ...(causes.some(cause => cause.reason_code === "MISSING_REQUIRED_FIELDS") ? ["", missingFields] : []),
    "", policy.summary, resources.summary,
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
  const notices = [
    ["Resources", resources.notice],
    ["This run's feed work", feedWork],
    ["Closed-day request spend", requestSpend],
    ["Grouped exclusions", exclusions],
    ["Policy used", policy.notice],
  ].map(([title, text]) => `::notice title=${escapeParameter(title!)}::${escapeCommand(`${text} Full details are in the public job summary.`)}`);
  if (row.failure_code !== null) notices.push(
    `::warning title=${escapeParameter("Feed planner outcome")}::${escapeCommand(`Planning ${row.status}: ${row.failure_code}. Saved evidence does not certify completion.`)}`);
  return { summary, annotations: notices };
}
export function formatExecutionReport(input: ExecutionReportEvidence): string {
  return formatExecutionOutcome(input).summary;
}
export async function writePlannerReport(input: {
  config: unknown; evidence?: Parameters<typeof formatExecutionReport>[0]; events?: unknown;
  summary_path?: string; annotate?: (line: string) => void;
}) {
  if (!FeedIngestConfigSchema.parse(input.config).workflow_reporting.enabled) return { status: "disabled" as const };
  if (!input.summary_path) throw new Error("Enabled reporting requires a summary output path");
  const report = input.evidence === undefined ? formatPlannerReport(input.events) : formatExecutionOutcome(input.evidence);
  await appendFile(input.summary_path, report.summary, "utf8");
  for (const annotation of report.annotations) (input.annotate ?? console.log)(annotation);
  return { status: "written" as const, annotations: report.annotations.length };
}
export async function readExecutionEvidence(directory: string): Promise<ExecutionReportEvidence> {
  const response: unknown = JSON.parse(await readFile(join(directory, "response.json"), "utf8"));
  const evidence: ExecutionReportEvidence = { response };
  for (const [key, name] of [
    ["health", "health.json"], ["historyStagingMs", "history-staging-ms.json"],
    ["policy", "workflow-policy.json"], ["resources", "resources.json"],
  ] as const) {
    const file = Bun.file(join(directory, name));
    if (await file.exists()) evidence[key] = await file.json();
  }
  return evidence;
}
export async function readExecutionReport(directory: string) {
  return formatExecutionReport(await readExecutionEvidence(directory));
}
if (import.meta.main) {
  const { RUNNER_TEMP, GITHUB_STEP_SUMMARY } = process.env;
  const config = FeedIngestConfigSchema.parse(await Bun.file("config/feed-ingest-plan.json").json());
  if (config.workflow_reporting.enabled) {
    if (!RUNNER_TEMP || !GITHUB_STEP_SUMMARY) throw new Error("Workflow report controls are missing");
    const directory = join(RUNNER_TEMP, "feed-ingest-plan");
    const response = Bun.file(join(directory, "response.json"));
    if (!await response.exists()) {
      const message = "No planner HTTP result was saved. Planning completion, feed work, request spend and exclusions are unavailable; see the retained runtime log.";
      const summary = `# Feed planner run\n\n**Planning result unavailable.** ${message}\n`;
      await appendFile(GITHUB_STEP_SUMMARY, summary, "utf8");
      await writeFile(join(directory, "report.md"), summary);
      console.log(`::warning title=${escapeParameter("Feed planner outcome")}::${escapeCommand(message)}`);
    } else {
      const evidence = await readExecutionEvidence(directory);
      const independent = Bun.file(join("test-results", "host-probes", "resource-proof.json"));
      if (await independent.exists()) evidence.independent = await independent.json();
      await writePlannerReport({ config, evidence, summary_path: GITHUB_STEP_SUMMARY });
      await writeFile(join(directory, "report.md"), formatExecutionReport(evidence));
    }
  }
}
