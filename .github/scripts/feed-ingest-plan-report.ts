/** Which source and stage outcomes can validated planner events actually prove? */
import { appendFile, readFile } from "node:fs/promises";
import { FeedIngestConfigSchema, FeedIngestEventSchema } from "../../packages/common-contracts/src/index";
import type { FeedIngestEvent } from "../../packages/common-contracts/src/index";

export type PlannerReport = Readonly<{ annotations: readonly string[]; summary: string }>;

function escapeCommand(value: string): string {
  return value.replaceAll("%", "%25").replaceAll("\r", "%0D").replaceAll("\n", "%0A");
}

function escapeParameter(value: string): string {
  return escapeCommand(value).replaceAll(":", "%3A").replaceAll(",", "%2C");
}

function escapeMarkdown(value: string): string {
  return value.replace(/[\u0000-\u0020\u007f-\u009f\u2028\u2029]/g, " ")
    .replace(/[&<>"'\\`*_{}[\]()#+.!|:=-]/g, character => `&#${character.charCodeAt(0)};`);
}

function validateEvents(input: unknown): FeedIngestEvent[] {
  const events = FeedIngestEventSchema.array().parse(input);
  const first = events[0];
  const identities = new Set<string>();
  let sequence = -1;
  for (const event of events) {
    if (event.run_id !== first?.run_id || event.attempt !== first.attempt
      || event.correlation_id !== first.correlation_id) {
      throw new Error("events.run_id, attempt and correlation_id must identify one planning attempt");
    }
    if (event.sequence <= sequence || identities.has(event.event_id)) {
      throw new Error("events.sequence and event_id must be unique and ordered");
    }
    identities.add(event.event_id);
    sequence = event.sequence;
  }
  return events;
}

export function formatPlannerReport(input: unknown): PlannerReport {
  const events = validateEvents(input);
  const first = events[0];
  const annotations: string[] = [];
  const sourceRows: string[] = [];
  const stageRows: string[] = [];
  const decisions = new Map<string, number>();
  for (const event of events) {
    const payload = event.payload;
    if (payload.kind === "feed_outcome") {
      const outcome = `${payload.fetch_status} / ${payload.parse_status}`;
      annotations.push(`::notice title=${escapeParameter("Feed ingest source outcome")}::${escapeCommand(
        `${payload.source.source_id}: ${outcome}; harvested ${payload.harvested_count ?? "unavailable"} articles`,
      )}`);
      sourceRows.push(`| A${sourceRows.length + 1} | ${escapeMarkdown(payload.source.source_id)} | ${escapeMarkdown(payload.source.title)} | ${escapeMarkdown(outcome)} | ${payload.parsed_count ?? "Unavailable"} | ${payload.harvested_count ?? "Unavailable"} | ${payload.rejection_reason ?? "None recorded"} |`);
    } else if (payload.kind === "stage_completion") {
      stageRows.push(`| B${stageRows.length + 1} | ${escapeMarkdown(payload.stage)} | ${payload.input_count} | ${payload.output_count} | ${payload.terminal_rejection_count} | ${event.step_elapsed_ms} |`);
    } else if (payload.kind === "candidate_decision") {
      const assessment = payload.assessment;
      const key = `${assessment.stage}: ${assessment.decision} / ${assessment.reason ?? "no rejection reason"}`;
      decisions.set(key, (decisions.get(key) ?? 0) + 1);
    }
  }
  const summary = [
    "# Feed ingest test evidence",
    "",
    first === undefined ? "No events supplied. Source and stage evidence is unavailable."
      : `Run: ${escapeMarkdown(first.run_id)}. Attempt: ${first.attempt}. First observation: ${escapeMarkdown(first.occurred_at)} (UTC).`,
    "",
    "**Audit completion: unavailable.** These stage events do not prove that required audit files were written. This report does not certify a complete plan or publication.",
    "",
    "## Table A - Source outcomes",
    "",
    "| Id | Source | Title | Fetch / parse | Parsed articles | Harvested articles | Rejection reason |",
    "| --- | --- | --- | --- | --- | --- | --- |",
    ...sourceRows,
    ...(sourceRows.length === 0 ? ["", "Source outcomes unavailable."] : []),
    "",
    "## Table B - Observed stage completions",
    "",
    "| Id | Stage | Input count | Output count | Terminal rejections | Step time (ms) |",
    "| --- | --- | --- | --- | --- | --- |",
    ...stageRows,
    ...(stageRows.length === 0 ? ["", "Stage completion evidence unavailable."] : []),
    "",
    "## Candidate decisions",
    "",
    ...[...decisions].map(([decision, count]) => `- ${escapeMarkdown(decision)}: ${count} observations.`),
    ...(decisions.size === 0 ? ["Candidate decision evidence unavailable."] : []),
    "",
    "Counts describe only supplied events, not a reconciled audit. Article text, source URLs, request headers and full event payloads are not included.",
    "",
  ].join("\n");
  return { annotations, summary };
}

export async function writePlannerReport(input: Readonly<{
  enabled: boolean; events: unknown; summaryPath?: string; annotate: (line: string) => void;
}>): Promise<void> {
  if (!input.enabled) return;
  const report = formatPlannerReport(input.events);
  if (input.summaryPath === undefined || input.summaryPath.length === 0) {
    throw new Error("GITHUB_STEP_SUMMARY is required when workflow reporting is enabled");
  }
  await appendFile(input.summaryPath, report.summary, "utf8");
  for (const line of report.annotations) input.annotate(line);
}

if (import.meta.main) {
  const configPath = process.argv[2];
  if (configPath === undefined) throw new Error("config path is required");
  const config = FeedIngestConfigSchema.parse(JSON.parse(await readFile(configPath, "utf8")));
  if (config.workflow_reporting.enabled) {
    const eventsPath = process.argv[3];
    if (eventsPath === undefined) throw new Error("events path is required when workflow reporting is enabled");
    await writePlannerReport({
      enabled: true, events: JSON.parse(await readFile(eventsPath, "utf8")),
      ...(process.env.GITHUB_STEP_SUMMARY === undefined ? {} : { summaryPath: process.env.GITHUB_STEP_SUMMARY }),
      annotate: line => console.log(line),
    });
  }
}
