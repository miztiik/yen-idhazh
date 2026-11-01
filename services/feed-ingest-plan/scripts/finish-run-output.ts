/** When may one run remove temporary output without hiding a failed collection, commit or upload? */
import { lstat, realpath, rm } from "node:fs/promises";
import { isAbsolute, join, relative, resolve, sep } from "node:path";
import { z } from "zod";
import { CommitShaSchema } from "@idhazh/common-contracts";
import { describePlanError, PlanError } from "../src/api/plan-request";
import { collectWorkflowFiles, readWorkflowDeliveryContext } from "./feed-ingest-plan-current-files";
import { isMetadataDeliveryConfirmed, MetadataDeliveryResultSchema } from "./feed-ingest-plan-delivery-result";
import { parseRawDocumentDumpControl } from "../src/config/service-settings";
import { RAW_DOCUMENT_CONTENTS_FILENAME } from "../src/selected-artifact-path";
import { RAW_DOCUMENT_ARTIFACT_DIRECTORY } from "./feed-ingest-plan-artifacts";

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
  gitSha: string;
  collectionOutcome: unknown; planningComplete: unknown; finalizationOutcome: unknown;
  uploadOutcome: unknown; artifactId?: string;
  dumpRawDocumentContents?: boolean; rawDocumentContents?: string;
  rawUploadOutcome?: unknown; rawArtifactId?: string;
  commitOutcome?: unknown; reportOutcome?: unknown; writeReport?: boolean;
}) {
  const gitSha = CommitShaSchema.parse(input.gitSha);
  const collection = OutcomeSchema.parse(input.collectionOutcome);
  const finalization = OutcomeSchema.parse(input.finalizationOutcome);
  const upload = OutcomeSchema.parse(input.uploadOutcome);
  const commit = input.commitOutcome === undefined ? finalization : OutcomeSchema.parse(input.commitOutcome);
  const report = input.reportOutcome === undefined ? finalization : OutcomeSchema.parse(input.reportOutcome);
  const failures: unknown[] = [];
  if (collection !== "success" || input.planningComplete !== "true") {
    failures.push(new Error("Article collection did not complete"));
  }
  if (commit !== "success") failures.push(new Error("Ledger commit failed"));
  const reportComplete = report === "success" || (input.writeReport === false && report === "skipped");
  if (!reportComplete) failures.push(new Error("Run report failed"));
  if (finalization !== "success") failures.push(new Error("Artifact preparation failed"));
  const uploaded = upload === "success" && z.string().regex(/^\d+$/).safeParse(input.artifactId).success;
  if (!uploaded) failures.push(new Error("The run artifact upload was not confirmed"));
  const rawPath = input.rawDocumentContents === undefined || input.rawDocumentContents === "" ? undefined
    : z.literal(`${RAW_DOCUMENT_ARTIFACT_DIRECTORY}/${RAW_DOCUMENT_CONTENTS_FILENAME}`).parse(input.rawDocumentContents);
  const rawRequired = input.dumpRawDocumentContents === true && rawPath !== undefined;
  const rawUploaded = !rawRequired || (OutcomeSchema.parse(input.rawUploadOutcome) === "success"
    && z.string().regex(/^\d+$/).safeParse(input.rawArtifactId).success);
  if (!rawUploaded) failures.push(new Error("The raw document artifact upload was not confirmed"));
  let cleaned = false;
  if (commit === "success" && reportComplete && finalization === "success"
    && uploaded && rawUploaded && collection !== "cancelled") {
    let operation = "check-directory";
    try {
      const directory = await ownedRunDirectory(input.root, input.temporaryRoot);
      operation = "verify-metadata";
      const context = await readWorkflowDeliveryContext({ ...input, directory, gitSha });
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
    event: "workflow_output_finished", collection, commit, report, finalization, upload,
    cleanup: cleaned ? "removed" : "retained", status: failures.length ? "failed" : "completed",
    failures: failures.map(error => error instanceof Error ? error.message : "Unknown completion failure"),
  }));
  if (failures.length) throw new AggregateError(failures, "Run output is incomplete; confirmed commits and artifacts are retained");
}

if (import.meta.main) {
  try {
    const { RUNNER_TEMP, GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT, COLLECTION_OUTCOME, PLANNING_COMPLETE,
      FINALIZATION_OUTCOME, UPLOAD_OUTCOME, UPLOAD_ARTIFACT_ID,
      DUMP_RAW_DOCUMENT_CONTENTS, RAW_DOCUMENT_CONTENTS, RAW_UPLOAD_OUTCOME, RAW_UPLOAD_ARTIFACT_ID, GITHUB_SHA,
      COMMIT_OUTCOME, REPORT_OUTCOME, WRITE_REPORT } = process.env;
    if (!RUNNER_TEMP || !GITHUB_RUN_ID || !GITHUB_RUN_ATTEMPT || !GITHUB_SHA) throw new Error("Workflow completion controls are missing");
    await finishRunOutput({
      root: process.cwd(), temporaryRoot: RUNNER_TEMP, runNumber: GITHUB_RUN_ID, attempt: Number(GITHUB_RUN_ATTEMPT),
      gitSha: GITHUB_SHA,
      collectionOutcome: COLLECTION_OUTCOME, planningComplete: PLANNING_COMPLETE,
      finalizationOutcome: FINALIZATION_OUTCOME, uploadOutcome: UPLOAD_OUTCOME,
      ...(COMMIT_OUTCOME === undefined ? {} : { commitOutcome: COMMIT_OUTCOME }),
      ...(REPORT_OUTCOME === undefined ? {} : { reportOutcome: REPORT_OUTCOME }),
      ...(WRITE_REPORT === undefined ? {} : { writeReport: z.enum(["true", "false"]).parse(WRITE_REPORT) === "true" }),
      ...(UPLOAD_ARTIFACT_ID === undefined ? {} : { artifactId: UPLOAD_ARTIFACT_ID }),
      dumpRawDocumentContents: DUMP_RAW_DOCUMENT_CONTENTS === undefined ? false : parseRawDocumentDumpControl(DUMP_RAW_DOCUMENT_CONTENTS),
      ...(RAW_DOCUMENT_CONTENTS === undefined ? {} : { rawDocumentContents: RAW_DOCUMENT_CONTENTS }),
      ...(RAW_UPLOAD_OUTCOME === undefined ? {} : { rawUploadOutcome: RAW_UPLOAD_OUTCOME }),
      ...(RAW_UPLOAD_ARTIFACT_ID === undefined ? {} : { rawArtifactId: RAW_UPLOAD_ARTIFACT_ID }),
    });
  } catch (error) {
    console.error(JSON.stringify({ event: "workflow_output_incomplete", code: describePlanError(error, process.cwd()).code }));
    process.exitCode = 2;
  }
}
