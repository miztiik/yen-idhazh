/** Write the reusable planner Markdown into the workflow run summary. */
import { appendFile, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { FeedIngestConfigSchema, WriterIdentitySchema, PlannerSavedResponseSchema } from "../../../packages/common-contracts/src/index";
import { z } from "zod";
import { renderExclusionDiagnostics } from "../src/reporting/selection-exclusions-markdown";
import {
  renderPlanMarkdown, renderPlannerProgressMarkdown, renderUnavailablePlanMarkdown,
} from "../src/reporting";
import type { PlannerMarkdown } from "../src/reporting";
import { formatHostFingerprintSummary } from "./feed-ingest-plan-host-summary";
import { formatPolicyTable } from "./feed-ingest-plan-policy-report";
import { formatWorkflowAnnotation } from "./feed-ingest-plan-report-format";
import { readReportFailureEvidence } from "./feed-ingest-plan-report-evidence";
import type { ReportFailureEvidence } from "../src/reporting/failure-evidence-markdown";
import { verifyParquetFiles } from "./feed-ingest-plan-verification";
import { ServiceSettingsSchema } from "../src/config/service-settings";
import { articleEntitiesFilename, articleEntitiesPath } from "../src/selected-artifact-path";
import { readMachineServerEvidence } from "@idhazh/host-probes/machine-evidence";
import { renderServerEvidence } from "./feed-ingest-plan-server-report";
import type { MachineServerEvidence } from "@idhazh/host-probes/machine-evidence";
import type { ReportDiagnosticIdentity } from "../src/reporting/article-failure-evidence";

export type WorkflowReportEvidence = {
  response: unknown; selected?: unknown; policy?: unknown; host?: unknown;
  failures?: ReportFailureEvidence;
};

export function renderWorkflowPlanMarkdown(
  input: WorkflowReportEvidence, documentationUrl = resolveWorkflowGuideUrl(process.env),
): PlannerMarkdown {
  const response = input.response === undefined ? undefined : PlannerSavedResponseSchema.parse(input.response);
  if (response === undefined || !("planning_complete" in response)) {
    const host = formatHostFingerprintSummary(input.host);
    return renderUnavailablePlanMarkdown({
      failure: response?.failure ?? null, host: { markdown: host.cells, notice: host.notice },
      ...(input.failures === undefined ? {} : { failures: input.failures }),
    });
  }
  const policy = formatPolicyTable(input.policy, response.selection_started_at_utc !== null, documentationUrl);
  const host = formatHostFingerprintSummary(input.host);
  return renderPlanMarkdown({
    response, selected: input.selected, policy: { markdown: policy.summary, notice: policy.notice },
    ...(policy.score_decimal_places === undefined ? {} : { score_decimal_places: policy.score_decimal_places }),
    host: { markdown: host.cells, notice: host.notice },
    maximum: policy.maximum,
    ...(input.failures === undefined ? {} : { failures: input.failures }),
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

export async function readExecutionEvidence(directory: string, root?: string, options: {
  execution?: ReportDiagnosticIdentity; servers?: readonly MachineServerEvidence[];
} = {}): Promise<WorkflowReportEvidence> {
  const responseFile = Bun.file(join(directory, "response.json"));
  const response: unknown = await responseFile.exists() ? await responseFile.json() : undefined;
  const evidence: WorkflowReportEvidence = { response };
  for (const [key, name] of [
    ["policy", "workflow-policy.json"],
    ["host", "host-fingerprint.json"],
  ] as const) {
    const file = Bun.file(join(directory, name));
    if (await file.exists()) evidence[key] = await file.json();
  }
  evidence.failures = await readReportFailureEvidence({
    directory, ...(root === undefined ? {} : { root }), response,
    ...options,
  });
  const saved = response === undefined ? undefined : PlannerSavedResponseSchema.parse(response);
  if (saved === undefined || !("planning_complete" in saved)) return evidence;
  const selected = saved.files.selected_articles;
  if (selected !== undefined) {
    try {
      const saved = await verifyParquetFiles(join(directory, "state"), "selected-articles", selected, {
        name: "selected-articles", family: "feed-ingest-plan", lifecycle_status: "active",
        grain: "raw-and-compact", prefix: ["feed-ingest-plan", "selected-articles"],
      });
      evidence.selected = saved.rows;
    } catch (error) {
      if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error;
      evidence.failures = { ...evidence.failures, gaps: [
        ...(evidence.failures.gaps ?? []),
        ["Run", "Selected metadata file missing", "Saved totals retained; measured counts and scores unavailable"],
      ] };
    }
  }
  return evidence;
}

export async function readExecutionReport(directory: string) {
  return renderWorkflowPlanMarkdown(await readExecutionEvidence(directory)).markdown;
}

export async function writeWorkflowReport(input: {
  root: string; directory: string; summaryPath?: string; runNumber: string; runId?: string;
  attempt?: number;
}) {
  const config = FeedIngestConfigSchema.parse(await Bun.file(join(input.root, "config", "feed-ingest-plan.json")).json());
  if (!config.workflow_reporting.enabled) return { status: "disabled" as const };
  if (!input.summaryPath) throw new Error("Enabled reporting requires a summary output path");
  await mkdir(input.directory, { recursive: true });
  const servers = await readMachineServerEvidence(input.directory);
  const evidence = await readExecutionEvidence(input.directory, input.root, {
    execution: {
      ...(input.runId === undefined ? {} : { run_id: input.runId }),
      ...(input.attempt === undefined ? {} : { attempt: input.attempt }),
    }, servers,
  });
  const report = renderWorkflowPlanMarkdown(evidence);
  let diagnostics = "";
  const response = evidence.response === undefined ? undefined : PlannerSavedResponseSchema.parse(evidence.response);
  if (response !== undefined && "planning_complete" in response && response.health?.status === "summarized") {
    diagnostics = renderExclusionDiagnostics(response.health.rows);
  }
  let entityEvidence = "Entity output could not be checked because execution identity was not recorded.";
  const runId = input.runId ?? (response !== undefined && "planning_complete" in response
    ? response.run_id : response?.failure?.execution.run_id ?? undefined);
  if (runId !== undefined) {
    const settingsFile = Bun.file(join(input.root, "config", "feed-ingest-plan-service.json"));
    const attempt = input.attempt ?? (response !== undefined && "planning_complete" in response
      ? response.attempt : response?.failure?.execution.attempt);
    if (!await settingsFile.exists()) {
      entityEvidence = "Entity output could not be checked because service settings were not recorded.";
    } else if (attempt != null) {
      const settings = ServiceSettingsSchema.parse(await settingsFile.json());
      const context = { run_id: runId, writer: { attempt } };
      entityEvidence = "No entity file was written for this run. Missing output is not a successful empty entity set.";
      if (await Bun.file(join(input.root, articleEntitiesPath(settings.inputs.artifact_root, context))).exists()) {
        entityEvidence = `Available private file: \`${articleEntitiesFilename(context)}\`. Each JSONL line is one article record and states incomplete or truncated evidence. Entity names are not included in this report or in progress logs.`;
      }
    }
  }
  const expectedAttempt = input.attempt ?? (response !== undefined && "planning_complete" in response
    ? response.attempt : response?.failure?.execution.attempt);
  if (servers.some(server => server.run_id !== input.runNumber
    || (expectedAttempt != null && server.attempt !== expectedAttempt))) {
    throw new Error("Report server evidence belongs to another run or attempt");
  }
  const markdown = `${report.markdown}\n\n${renderServerEvidence(servers)}\n## Per-run named entities\n\nPeople, places and organizations are recognized from the original title and full sanitized extracted article, not downloaded HTML. These names do not change scores or checks that decide whether an article is eligible.\n\n${entityEvidence}\n`;
  const filename = workflowReportFilename({ ...input, ...(runId === undefined ? {} : { runId }) });
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
  const { RUNNER_TEMP, GITHUB_STEP_SUMMARY, GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT, RUN_ID } = process.env;
  if (!RUNNER_TEMP || !GITHUB_RUN_ID) throw new Error("Workflow report controls are missing");
  await writeWorkflowReport({
    root: process.cwd(), directory: join(RUNNER_TEMP, "feed-ingest-plan"),
    runNumber: GITHUB_RUN_ID,
    ...(GITHUB_RUN_ATTEMPT === undefined ? {} : { attempt: WriterIdentitySchema.shape.attempt.parse(Number(GITHUB_RUN_ATTEMPT)) }),
    ...(RUN_ID === undefined || RUN_ID === "" ? {} : { runId: RUN_ID }),
    ...(GITHUB_STEP_SUMMARY === undefined ? {} : { summaryPath: GITHUB_STEP_SUMMARY }),
  });
}
