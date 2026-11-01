/** Write the reusable planner Markdown into the workflow run summary. */
import { appendFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { FeedIngestConfigSchema, WriterIdentitySchema } from "../../../packages/common-contracts/src/index";
import { z } from "zod";
import { PlanResponseSchema } from "../src/api/plan-response.schema";
import { FeedHealthStateUpdateResponseSchema } from "../src/api/feed-health-state.schema";
import { renderExclusionDiagnostics } from "../src/reporting/selection-exclusions-markdown";
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

export function renderWorkflowPlanMarkdown(
  input: WorkflowReportEvidence, documentationUrl = resolveWorkflowGuideUrl(process.env),
): PlannerMarkdown {
  const response = PlanResponseSchema.parse(input.response);
  const policy = formatPolicyTable(input.policy, response.selection_started_at_utc !== null, documentationUrl);
  const host = formatHostFingerprintSummary(input.host);
  return renderPlanMarkdown({
    response, health: input.health, policy: { markdown: policy.summary, notice: policy.notice },
    host: { markdown: host.cells, notice: host.notice },
    maximum: policy.maximum,
  });
}

export function resolveWorkflowGuideUrl(context: NodeJS.ProcessEnv): string | undefined {
  const { GITHUB_REPOSITORY, GITHUB_SERVER_URL, GITHUB_SHA } = context;
  if (GITHUB_REPOSITORY === undefined) return undefined;
  if (!GITHUB_SERVER_URL || !GITHUB_SHA) throw new Error("Workflow documentation link requires server URL and commit SHA");
  return new URL(
    `${GITHUB_REPOSITORY}/blob/${GITHUB_SHA}/docs/how-to/run-feed-ingest-plan-test.md`,
    `${GITHUB_SERVER_URL}/`,
  ).href;
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
  root: string; directory: string; summaryPath?: string; runNumber: string; runId?: string;
}) {
  const config = FeedIngestConfigSchema.parse(await Bun.file(join(input.root, "config", "feed-ingest-plan.json")).json());
  if (!config.workflow_reporting.enabled) return { status: "disabled" as const };
  if (!input.summaryPath) throw new Error("Enabled reporting requires a summary output path");
  await mkdir(input.directory, { recursive: true });
  let report: PlannerMarkdown;
  let diagnostics = "";
  if (await Bun.file(join(input.directory, "response.json")).exists()) {
    const evidence = await readExecutionEvidence(input.directory);
    report = renderWorkflowPlanMarkdown(evidence);
    if (evidence.health !== undefined) {
      diagnostics = renderExclusionDiagnostics(FeedHealthStateUpdateResponseSchema.parse(evidence.health).rows);
    }
  } else {
    const hostFile = Bun.file(join(input.directory, "host-fingerprint.json"));
    const host = formatHostFingerprintSummary(await hostFile.exists() ? await hostFile.json() : undefined);
    report = renderUnavailablePlanMarkdown({ host: { markdown: host.cells, notice: host.notice } });
  }
  const markdown = report.markdown;
  const filename = workflowReportFilename(input);
  await writeFile(join(input.directory, filename), markdown + diagnostics, "utf8");
  await appendFile(input.summaryPath, markdown, "utf8");
  for (const notice of report.notices) console.log(formatWorkflowAnnotation(notice));
  return { status: "written" as const, markdown, filename };
}

export function workflowReportFilename(input: { runNumber: string; runId?: string }): string {
  const run = z.string().regex(/^\d+$/).parse(input.runNumber);
  const runId = input.runId === undefined ? undefined : WriterIdentitySchema.shape.run_id.parse(input.runId);
  if (runId !== undefined && runId.slice(11) !== run) throw new Error("Report run differs from the executed workflow");
  const day = runId?.slice(0, 10) ?? new Date().toISOString().slice(0, 10);
  return `feed-ingest-report-${day}-${run}.md`;
}

if (import.meta.main) {
  const { RUNNER_TEMP, GITHUB_STEP_SUMMARY, GITHUB_RUN_ID, RUN_ID } = process.env;
  if (!RUNNER_TEMP || !GITHUB_RUN_ID) throw new Error("Workflow report controls are missing");
  await writeWorkflowReport({
    root: process.cwd(), directory: join(RUNNER_TEMP, "feed-ingest-plan"),
    runNumber: GITHUB_RUN_ID,
    ...(RUN_ID === undefined || RUN_ID === "" ? {} : { runId: RUN_ID }),
    ...(GITHUB_STEP_SUMMARY === undefined ? {} : { summaryPath: GITHUB_STEP_SUMMARY }),
  });
}
