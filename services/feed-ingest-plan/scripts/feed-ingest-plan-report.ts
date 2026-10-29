/** Write the reusable planner Markdown into the workflow run summary. */
import { appendFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { FeedIngestConfigSchema } from "../../../packages/common-contracts/src/index";
import { PlanResponseSchema } from "../src/api/plan-response.schema";
import {
  renderPlanMarkdown, renderPlannerProgressMarkdown, renderUnavailablePlanMarkdown,
} from "../src/reporting";
import type { PlannerMarkdown } from "../src/reporting";
import { formatHostFingerprintSummary } from "./feed-ingest-plan-host-summary";
import { formatPolicyTable } from "./feed-ingest-plan-policy-report";
import { formatWorkflowAnnotation } from "./feed-ingest-plan-report-format";

export type WorkflowReportEvidence = {
  response: unknown; health?: unknown; policy?: unknown; host?: unknown;
};

export function renderWorkflowPlanMarkdown(input: WorkflowReportEvidence): PlannerMarkdown {
  const response = PlanResponseSchema.parse(input.response);
  const policy = formatPolicyTable(input.policy, response.selection_started_at_utc !== null);
  const host = formatHostFingerprintSummary(input.host);
  const report = renderPlanMarkdown({
    response, health: input.health, policy: { markdown: policy.summary, notice: policy.notice },
  });
  return {
    markdown: placeHostFingerprintFirst(report.markdown, host.summary),
    notices: [{ level: "notice", title: "Host fingerprint", message: host.notice }, ...report.notices],
  };
}

function placeHostFingerprintFirst(markdown: string, hostSummary: string): string {
  const title = "# Feed planner run\n\n";
  if (!markdown.startsWith(title)) throw new Error("Planner report is missing its title");
  return `${title}${hostSummary}\n\n${markdown.slice(title.length)}`;
}

export async function writePlannerReport(input: {
  config: unknown; evidence?: WorkflowReportEvidence; events?: unknown;
  summary_path?: string; annotate?: (line: string) => void;
}) {
  if (!FeedIngestConfigSchema.parse(input.config).workflow_reporting.enabled) return { status: "disabled" as const };
  if (!input.summary_path) throw new Error("Enabled reporting requires a summary output path");
  const report = input.evidence === undefined
    ? renderPlannerProgressMarkdown(input.events) : renderWorkflowPlanMarkdown(input.evidence);
  await appendFile(input.summary_path, report.markdown, "utf8");
  for (const notice of report.notices) {
    (input.annotate ?? console.log)(formatWorkflowAnnotation(notice));
  }
  return { status: "written" as const, annotations: report.notices.length, markdown: report.markdown };
}

export async function readExecutionEvidence(directory: string): Promise<WorkflowReportEvidence> {
  const response: unknown = JSON.parse(await readFile(join(directory, "response.json"), "utf8"));
  const evidence: WorkflowReportEvidence = { response };
  for (const [key, name] of [
    ["health", "health.json"], ["policy", "workflow-policy.json"],
    ["host", "host-fingerprint.json"],
  ] as const) {
    const file = Bun.file(join(directory, name));
    if (await file.exists()) evidence[key] = await file.json();
  }
  return evidence;
}

export async function readExecutionReport(directory: string) {
  return renderWorkflowPlanMarkdown(await readExecutionEvidence(directory)).markdown;
}

export async function writeWorkflowReport(input: {
  root: string; directory: string; summaryPath?: string;
}) {
  const config = FeedIngestConfigSchema.parse(await Bun.file(join(input.root, "config", "feed-ingest-plan.json")).json());
  if (!config.workflow_reporting.enabled) return { status: "disabled" as const };
  if (!input.summaryPath) throw new Error("Enabled reporting requires a summary output path");
  await mkdir(input.directory, { recursive: true });
  let report: PlannerMarkdown;
  if (await Bun.file(join(input.directory, "response.json")).exists()) {
    report = renderWorkflowPlanMarkdown(await readExecutionEvidence(input.directory));
  } else {
    const hostFile = Bun.file(join(input.directory, "host-fingerprint.json"));
    const host = formatHostFingerprintSummary(await hostFile.exists() ? await hostFile.json() : undefined);
    const unavailable = renderUnavailablePlanMarkdown();
    report = {
      markdown: placeHostFingerprintFirst(unavailable.markdown, host.summary),
      notices: [...unavailable.notices, { level: "notice", title: "Host fingerprint", message: host.notice }],
    };
  }
  const markdown = report.markdown;
  await writeFile(join(input.directory, "report.md"), markdown, "utf8");
  await appendFile(input.summaryPath, markdown, "utf8");
  for (const notice of report.notices) console.log(formatWorkflowAnnotation(notice));
  return { status: "written" as const, markdown };
}

if (import.meta.main) {
  const { RUNNER_TEMP, GITHUB_STEP_SUMMARY } = process.env;
  if (!RUNNER_TEMP) throw new Error("Workflow report controls are missing");
  await writeWorkflowReport({
    root: process.cwd(), directory: join(RUNNER_TEMP, "feed-ingest-plan"),
    ...(GITHUB_STEP_SUMMARY === undefined ? {} : { summaryPath: GITHUB_STEP_SUMMARY }),
  });
}
