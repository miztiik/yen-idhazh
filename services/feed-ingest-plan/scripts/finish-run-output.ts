/** When may one run remove temporary output without hiding a failed collection, commit or upload? */
import { lstat, realpath, rm } from "node:fs/promises";
import { isAbsolute, join, relative, resolve, sep } from "node:path";
import { z } from "zod";
import { describePlanError, PlanError } from "../src/api/plan-request";
import { collectWorkflowFiles, readWorkflowDeliveryContext } from "./feed-ingest-plan-current-files";
import { isMetadataDeliveryConfirmed, MetadataDeliveryResultSchema } from "./feed-ingest-plan-delivery-result";

const OutcomeSchema = z.enum(["success", "failure", "cancelled", "skipped"]);

function contains(parent: string, child: string): boolean {
  const path = relative(parent, child);
  return path === "" || (path !== ".." && !path.startsWith(`..${sep}`) && !isAbsolute(path));
}

async function ownedRunDirectory(root: string, temporaryRoot: string) {
  const directory = join(await realpath(temporaryRoot), "feed-ingest-plan");
  const repository = await realpath(root);
  const info = await lstat(directory);
  if (!info.isDirectory() || info.isSymbolicLink() || resolve(await realpath(directory)) !== resolve(directory)
    || contains(repository, directory) || contains(directory, repository)) {
    throw new PlanError("CLEANUP_DIRECTORY_REFUSED", "Cleanup requires the workflow's separate temporary run directory");
  }
  return directory;
}

export async function finishRunOutput(input: {
  root: string; temporaryRoot: string; runNumber: string; attempt: number;
  collectionOutcome: unknown; planningComplete: unknown; finalizationOutcome: unknown;
  uploadOutcome: unknown; artifactId?: string;
}) {
  const collection = OutcomeSchema.parse(input.collectionOutcome);
  const finalization = OutcomeSchema.parse(input.finalizationOutcome);
  const upload = OutcomeSchema.parse(input.uploadOutcome);
  const failures: unknown[] = [];
  if (collection !== "success" || input.planningComplete !== "true") {
    failures.push(new Error("Article collection did not complete"));
  }
  if (finalization !== "success") failures.push(new Error("Ledger commit, report or handoff preparation failed"));
  const uploaded = upload === "success" && z.string().regex(/^\d+$/).safeParse(input.artifactId).success;
  if (!uploaded) failures.push(new Error("The run artifact upload was not confirmed"));
  let cleaned = false;
  if (finalization === "success" && uploaded) {
    let operation = "check-directory";
    try {
      const directory = await ownedRunDirectory(input.root, input.temporaryRoot);
      operation = "verify-metadata";
      const context = await readWorkflowDeliveryContext({ ...input, directory });
      const completed = await collectWorkflowFiles({ ...input, directory, ...context });
      if (completed.failures.length) throw new AggregateError(completed.failures, "Cleanup found invalid completed output");
      operation = "confirm-delivery";
      const delivery = MetadataDeliveryResultSchema.parse(await Bun.file(join(directory, "delivery-result.json")).json());
      if (!isMetadataDeliveryConfirmed(delivery, completed.paths)) {
        throw new PlanError("DELIVERY_UNCONFIRMED", "Cleanup requires confirmed ledger delivery");
      }
      if (collection === "success" && input.planningComplete === "true" && completed.response?.planning_complete !== true) {
        failures.push(new Error("The completed planning control differs from the saved result"));
      }
      operation = "remove-temporary-output";
      await rm(directory, { recursive: true });
      cleaned = true;
    } catch (error) {
      const code = error instanceof Error && "code" in error && typeof error.code === "string"
        ? error.code : describePlanError(error, input.root).code;
      const reason = error instanceof PlanError ? error.message : `Temporary output cleanup failed during ${operation}`;
      failures.push(new Error(reason, { cause: error }));
      console.error(JSON.stringify({ event: "workflow_cleanup_refused", operation, code, reason }));
    }
  }
  console.error(JSON.stringify({
    event: "workflow_output_finished", collection, finalization, upload,
    cleanup: cleaned ? "removed" : "retained", status: failures.length ? "failed" : "completed",
    failures: failures.map(error => error instanceof Error ? error.message : "Unknown completion failure"),
  }));
  if (failures.length) throw new AggregateError(failures, "Run output is incomplete; confirmed commits and artifacts are retained");
}

if (import.meta.main) {
  try {
    const { RUNNER_TEMP, GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT, COLLECTION_OUTCOME, PLANNING_COMPLETE,
      FINALIZATION_OUTCOME, UPLOAD_OUTCOME, UPLOAD_ARTIFACT_ID } = process.env;
    if (!RUNNER_TEMP || !GITHUB_RUN_ID || !GITHUB_RUN_ATTEMPT) throw new Error("Workflow completion controls are missing");
    await finishRunOutput({
      root: process.cwd(), temporaryRoot: RUNNER_TEMP, runNumber: GITHUB_RUN_ID, attempt: Number(GITHUB_RUN_ATTEMPT),
      collectionOutcome: COLLECTION_OUTCOME, planningComplete: PLANNING_COMPLETE,
      finalizationOutcome: FINALIZATION_OUTCOME, uploadOutcome: UPLOAD_OUTCOME,
      ...(UPLOAD_ARTIFACT_ID === undefined ? {} : { artifactId: UPLOAD_ARTIFACT_ID }),
    });
  } catch (error) {
    console.error(JSON.stringify({ event: "workflow_output_incomplete", code: describePlanError(error, process.cwd()).code }));
    process.exitCode = 2;
  }
}
