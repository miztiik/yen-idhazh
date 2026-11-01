/** How are completed ledgers, a run report and the article handoff finalized despite independent failures? */
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { z } from "zod";
import { CommitShaSchema, WriterIdentitySchema } from "../../../packages/common-contracts/src/index";
import { describePlanError, PlanError } from "../src/api/plan-request";
import { deliverWorkflowMetadataHttp } from "./safe-persist-http-client";
import { writeWorkflowReport } from "./feed-ingest-plan-report";
import { prepareWorkflowArtifacts } from "./feed-ingest-plan-artifacts";
import { parseRawDocumentDumpControl } from "../src/config/service-settings";
import { writeJsonLine } from "../src/logging/structured-logger";
import { publishWorkflowUploadInventories } from "./feed-ingest-plan-upload-inventory";
import { writeGitHubOutputs } from "./feed-ingest-plan-outputs";

const FinalizationOperationSchema = z.enum(["all", "commit-ledgers", "write-report", "prepare-artifacts"]);

export async function finalizeRunOutput(input: {
  root: string; directory: string; currentRunFiles?: string; runNumber: string; attempt: number;
  gitSha: string;
  cancelled: boolean; summaryPath?: string; outputPath?: string;
  dumpRawDocumentContents?: boolean; runId?: string; signal?: AbortSignal;
  operation?: z.infer<typeof FinalizationOperationSchema>; reportFilename?: string;
}) {
  const runNumber = z.string().regex(/^\d+$/).parse(input.runNumber);
  const attempt = WriterIdentitySchema.shape.attempt.parse(input.attempt);
  const gitSha = CommitShaSchema.parse(input.gitSha);
  await mkdir(input.directory, { recursive: true });
  const failures: unknown[] = [];
  const operation = FinalizationOperationSchema.parse(input.operation ?? "all");
  let reportFilename = input.reportFilename;
  const operations: readonly (readonly [string, () => Promise<unknown>])[] = [
    ["commit-ledgers", async () => {
      if (input.cancelled) {
        writeJsonLine({ event: "workflow_ledger_commit_skipped", reason: "cancelled" });
        return;
      }
      if (!input.currentRunFiles) {
        throw new PlanError("COMPLETED_PATHS_MISSING", "Collection did not supply its exact completed ledger paths");
      }
      return deliverWorkflowMetadataHttp({ ...input, runNumber, attempt, gitSha, currentRunFiles: input.currentRunFiles },
        input.signal === undefined ? {} : { signal: input.signal });
    }],
    ["write-report", async () => {
      const report = await writeWorkflowReport({ ...input, runNumber });
      if (report.status === "written") {
        reportFilename = report.filename;
        if (input.outputPath !== undefined) {
          await writeGitHubOutputs(input.outputPath, { report_filename: report.filename });
        }
      }
    }],
    ["prepare-artifacts", () => prepareWorkflowArtifacts({ ...input, runNumber, attempt, gitSha,
      ...(reportFilename === undefined ? {} : { reportFilename }) })],
    ["list-upload-files", () => publishWorkflowUploadInventories({ directory: input.directory, runNumber })],
  ];
  for (const [name, execute] of operations) {
    if (operation !== "all" && operation !== name
      && !(operation === "prepare-artifacts" && name === "list-upload-files")) continue;
    try { await execute(); }
    catch (error) {
      failures.push(error);
      writeJsonLine({
        event: "workflow_finalization_failed", operation: name,
        code: error instanceof Error && "code" in error && typeof error.code === "string"
          ? error.code : describePlanError(error, input.root).code,
        reason: error instanceof PlanError ? error.message : error instanceof Error ? error.name : "UnknownError",
      });
    }
  }
  if (failures.length) throw new AggregateError(failures, "Run finalization failed; completed output remains available");
}

if (import.meta.main) {
  const cancellation = new AbortController();
  const cancel = () => cancellation.abort(new Error("Workflow finalization cancelled"));
  process.on("SIGINT", cancel);
  process.on("SIGTERM", cancel);
  try {
    const { RUNNER_TEMP, GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT, GITHUB_STEP_SUMMARY, GITHUB_OUTPUT,
      CURRENT_RUN_FILES, RUN_CANCELLED, DUMP_RAW_DOCUMENT_CONTENTS, RUN_ID, GITHUB_SHA,
      FINALIZATION_OPERATION, REPORT_FILENAME } = process.env;
    if (!RUNNER_TEMP || !GITHUB_RUN_ID || !GITHUB_RUN_ATTEMPT || !GITHUB_OUTPUT || !GITHUB_SHA) {
      throw new Error("Workflow finalization controls are missing");
    }
    await finalizeRunOutput({
      root: process.cwd(), directory: join(RUNNER_TEMP, "feed-ingest-plan"),
      ...(CURRENT_RUN_FILES === undefined ? {} : { currentRunFiles: CURRENT_RUN_FILES }),
      runNumber: GITHUB_RUN_ID, attempt: Number(GITHUB_RUN_ATTEMPT),
      gitSha: GITHUB_SHA,
      cancelled: z.enum(["true", "false"]).parse(RUN_CANCELLED) === "true",
      ...(GITHUB_STEP_SUMMARY === undefined ? {} : { summaryPath: GITHUB_STEP_SUMMARY }),
      outputPath: GITHUB_OUTPUT,
      dumpRawDocumentContents: DUMP_RAW_DOCUMENT_CONTENTS === undefined ? false : parseRawDocumentDumpControl(DUMP_RAW_DOCUMENT_CONTENTS),
      ...(RUN_ID === undefined || RUN_ID === "" ? {} : { runId: RUN_ID }),
      signal: cancellation.signal,
      operation: FinalizationOperationSchema.parse(FINALIZATION_OPERATION ?? "all"),
      ...(REPORT_FILENAME === undefined || REPORT_FILENAME === "" ? {} : { reportFilename: REPORT_FILENAME }),
    });
  } catch (error) {
    writeJsonLine({ event: "workflow_finalization_incomplete",
      code: describePlanError(error, process.cwd()).code });
    process.exitCode = 2;
  } finally {
    process.off("SIGINT", cancel);
    process.off("SIGTERM", cancel);
  }
}
