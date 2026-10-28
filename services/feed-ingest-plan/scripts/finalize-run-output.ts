/** How are completed ledgers, a run report and the article handoff finalized despite independent failures? */
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { z } from "zod";
import { WriterIdentitySchema } from "../../../packages/common-contracts/src/index";
import { describePlanError, PlanError } from "../src/api/plan-request";
import { deliverWorkflowMetadata } from "./feed-ingest-plan-deliver";
import { writeWorkflowReport } from "./feed-ingest-plan-report";
import { prepareWorkflowArtifacts } from "./feed-ingest-plan-artifacts";

export async function finalizeRunOutput(input: {
  root: string; directory: string; currentRunFiles?: string; runNumber: string; attempt: number;
  cancelled: boolean; summaryPath?: string; outputPath?: string;
}) {
  const runNumber = z.string().regex(/^\d+$/).parse(input.runNumber);
  const attempt = WriterIdentitySchema.shape.attempt.parse(input.attempt);
  await mkdir(input.directory, { recursive: true });
  const failures: unknown[] = [];
  const operations: readonly (readonly [string, () => Promise<unknown>])[] = [
    ["commit-ledgers", async () => {
      if (input.cancelled) {
        console.error(JSON.stringify({ event: "workflow_ledger_commit_skipped", reason: "cancelled" }));
        return;
      }
      if (!input.currentRunFiles) {
        throw new PlanError("COMPLETED_PATHS_MISSING", "Collection did not supply its exact completed ledger paths");
      }
      return deliverWorkflowMetadata({ ...input, runNumber, attempt, currentRunFiles: input.currentRunFiles });
    }],
    ["write-report", () => writeWorkflowReport(input)],
    ["prepare-artifacts", () => prepareWorkflowArtifacts({ ...input, runNumber, attempt })],
  ];
  for (const [operation, execute] of operations) {
    try { await execute(); }
    catch (error) {
      failures.push(error);
      console.error(JSON.stringify({
        event: "workflow_finalization_failed", operation,
        code: error instanceof Error && "code" in error && typeof error.code === "string"
          ? error.code : describePlanError(error, input.root).code,
        reason: error instanceof PlanError ? error.message : error instanceof Error ? error.name : "UnknownError",
      }));
    }
  }
  if (failures.length) throw new AggregateError(failures, "Run finalization failed; completed output remains available");
}

if (import.meta.main) {
  try {
    const { RUNNER_TEMP, GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT, GITHUB_STEP_SUMMARY, GITHUB_OUTPUT,
      CURRENT_RUN_FILES, RUN_CANCELLED } = process.env;
    if (!RUNNER_TEMP || !GITHUB_RUN_ID || !GITHUB_RUN_ATTEMPT || !GITHUB_OUTPUT) {
      throw new Error("Workflow finalization controls are missing");
    }
    await finalizeRunOutput({
      root: process.cwd(), directory: join(RUNNER_TEMP, "feed-ingest-plan"),
      ...(CURRENT_RUN_FILES === undefined ? {} : { currentRunFiles: CURRENT_RUN_FILES }),
      runNumber: GITHUB_RUN_ID, attempt: Number(GITHUB_RUN_ATTEMPT),
      cancelled: z.enum(["true", "false"]).parse(RUN_CANCELLED) === "true",
      ...(GITHUB_STEP_SUMMARY === undefined ? {} : { summaryPath: GITHUB_STEP_SUMMARY }),
      outputPath: GITHUB_OUTPUT,
    });
  } catch (error) {
    console.error(JSON.stringify({ event: "workflow_finalization_incomplete",
      code: describePlanError(error, process.cwd()).code }));
    process.exitCode = 2;
  }
}
