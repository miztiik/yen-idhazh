/** Render a body-free planner outcome without claiming summary quality or publication. */
import { appendFile, readFile } from "node:fs/promises";
import { join } from "node:path";
import {
  FeedIngestConfigSchema, PlanRunRowSchema, readFeedIngestEvent,
} from "../../packages/common-contracts/src/index";
import { PlanResponseSchema } from "../../services/feed-ingest-plan/src/api/plan-response.schema";
import { FeedHealthStateUpdateResponseSchema } from "../../services/feed-ingest-plan/src/api/feed-health-state.schema";
import { escapeCommand, escapeMarkdown, escapeParameter } from "./feed-ingest-plan-report-format";

export type PlannerReport = { annotations: readonly string[]; summary: string };
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
export function formatExecutionReport(input: { response: unknown; health?: unknown; historyStagingMs?: unknown }): string {
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
  const known = (value: number | null, unit: string) => value === null ? "Unavailable" : `${value} ${unit}`;
  return [
    "# Feed planner run", "", `**Status: ${row.status}.** ${row.failure_code === null ? "The requested planning stages finished." : `Cause: ${escapeMarkdown(row.failure_code)}.`}`,
    "", "This is planning output, not proof of summarization or publication. Article bodies are kept only in the selected text artifact.", "",
    "## Table A - Run facts", "", "| Id | Fact | Recorded value |", "| --- | --- | --- |",
    `| A1 | Run and attempt | ${escapeMarkdown(row.run_id)}; attempt ${row.attempt} |`,
    `| A2 | Chosen articles | ${row.selected_count} articles |`,
    `| A3 | Worker assignment | ${row.dispatch_count} partitions; ${row.strategy} |`,
    `| A4 | Elapsed planning time | ${known(row.duration_ms, "milliseconds")} |`,
    `| A5 | Age evaluation clock | ${row.evaluated_at} UTC |`,
    `| A6 | Selection start clock | ${row.selection_started_at_utc === null ? "Selection did not run" : `${row.selection_started_at_utc} UTC`} |`,
    `| A7 | Lifecycle history | ${row.lifecycle_window_days} represented UTC days |`,
    `| A8 | Feed-read reliability | ${row.reliability_window_days} represented UTC days; minimum factor ${row.reliability_floor}; ${row.reliability_penalty_enabled ? "enabled when measured" : "disabled"} |`,
    `| A9 | Request report | ${row.request_report_closed_days} closed UTC calendar days, excluding the selection-start day |`,
    `| A10 | History staging time | ${staging === undefined ? "Unavailable" : `${staging} milliseconds`} |`,
    "", "## Table B - Measured operations", "", "| Id | Operation | Duration | State |", "| --- | --- | --- | --- |",
    ...row.api_timings.map((span, index) => `| B${index + 1} | ${span.operation} | ${span.duration_ms} milliseconds | ${span.status} |`),
    "", "Concurrent spans can overlap. Do not add them to estimate elapsed run time.",
    "", "## Table C - This run's feed work", "",
    "| Id | Feed | UTC work day | Feed checks | Admitted articles | Chosen articles | Feed / article / robots requests | Outcome |",
    "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ...feedRows.map((feed, index) => `| C${index + 1} | ${escapeMarkdown(feed.feed_id)} | ${feed.date} | ${known(feed.feed_reads, "checks")} | ${known(feed.article_candidates, "articles")} | ${known(feed.articles_selected, "articles")} | ${[feed.feed_requests, feed.article_requests, feed.robots_requests].map(value => known(value, "requests")).join(" / ")} | ${feed.outcome ?? "Unavailable"} |`),
    ...(feedRows.length ? [] : ["", health === null ? "Feed work is unavailable." : "The supplied run has zero recorded feed rows."]),
    "", "## Table D - Closed-day request spend", "",
    requests === undefined ? "Request evidence is unavailable." : `Window: ${requests.from_day} through ${requests.through_day} UTC. Coverage: ${requests.complete ? "complete" : "incomplete"}. This is spend, not waste or a ranking penalty.`,
    "", "| Id | Feed | Feed requests | Article requests | Robots requests | Accounting |", "| --- | --- | --- | --- | --- | --- |",
    ...(requests?.feeds ?? []).map((feed, index) => `| D${index + 1} | ${escapeMarkdown(feed.feed_id)} | ${known(feed.feed_requests, "requests")} | ${known(feed.article_requests, "requests")} | ${known(feed.robots_requests, "requests")} | ${feed.counts_complete ? "Complete" : "Incomplete"} |`),
    "", "## Table E - Grouped exclusions", "", "| Id | Feed | UTC day | Subject / stage | Reason | Count | Attribution |",
    "| --- | --- | --- | --- | --- | --- | --- |",
    ...causes.map((cause, index) => `| E${index + 1} | ${escapeMarkdown(cause.feed_id)} | ${cause.date} | ${escapeMarkdown(`${cause.subject} / ${cause.stage}`)} | ${escapeMarkdown(cause.reason_code)} | ${cause.count} decisions | ${cause.attribution ?? "Not a failure"} |`),
    ...(causes.length ? [] : ["", health === null ? "Exclusion evidence is unavailable." : "No exclusions were recorded."]), "",
  ].join("\n");
}
export async function writePlannerReport(input: {
  config: unknown; evidence?: Parameters<typeof formatExecutionReport>[0]; events?: unknown;
  summary_path?: string; annotate?: (line: string) => void;
}) {
  if (!FeedIngestConfigSchema.parse(input.config).workflow_reporting.enabled) return { status: "disabled" as const };
  if (!input.summary_path) throw new Error("Enabled reporting requires a summary output path");
  const report = input.evidence === undefined ? formatPlannerReport(input.events) : { annotations: [], summary: formatExecutionReport(input.evidence) };
  await appendFile(input.summary_path, report.summary, "utf8");
  for (const annotation of report.annotations) (input.annotate ?? console.log)(annotation);
  return { status: "written" as const, annotations: report.annotations.length };
}
export async function readExecutionReport(directory: string) {
  const response: unknown = JSON.parse(await readFile(join(directory, "response.json"), "utf8"));
  const healthPath = join(directory, "health.json");
  const stagingPath = join(directory, "history-staging-ms.json");
  return formatExecutionReport({
    response,
    ...(await Bun.file(healthPath).exists() ? { health: await Bun.file(healthPath).json() } : {}),
    ...(await Bun.file(stagingPath).exists() ? { historyStagingMs: await Bun.file(stagingPath).json() } : {}),
  });
}
