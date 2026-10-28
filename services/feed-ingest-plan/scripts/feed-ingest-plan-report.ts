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
  return renderPlanMarkdown({
    response, health: input.health,
    policy: { markdown: policy.summary, notice: policy.notice },
    host: { markdown: host.summary, notice: host.notice },
  });
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

if (import.meta.main) {
  const { RUNNER_TEMP, GITHUB_STEP_SUMMARY } = process.env;
  const config = FeedIngestConfigSchema.parse(await Bun.file("config/feed-ingest-plan.json").json());
  if (config.workflow_reporting.enabled) {
    if (!RUNNER_TEMP || !GITHUB_STEP_SUMMARY) throw new Error("Workflow report controls are missing");
    const directory = join(RUNNER_TEMP, "feed-ingest-plan");
    await mkdir(directory, { recursive: true });
    const response = Bun.file(join(directory, "response.json"));
    if (!await response.exists()) {
      const hostFile = Bun.file(join(directory, "host-fingerprint.json"));
      const host = formatHostFingerprintSummary(await hostFile.exists() ? await hostFile.json() : undefined);
      const report = renderUnavailablePlanMarkdown({
        host: { markdown: host.summary, notice: host.notice },
      });
      await appendFile(GITHUB_STEP_SUMMARY, report.markdown, "utf8");
      await writeFile(join(directory, "report.md"), report.markdown);
      for (const notice of report.notices) console.log(formatWorkflowAnnotation(notice));
    } else {
      const report = await writePlannerReport({
        config, evidence: await readExecutionEvidence(directory), summary_path: GITHUB_STEP_SUMMARY,
      });
      if (report.status !== "written") throw new Error("Enabled workflow reporting did not write a report");
      await writeFile(join(directory, "report.md"), report.markdown);
    }
  }
}
