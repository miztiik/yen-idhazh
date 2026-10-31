/** Which exact run receipts can be retained without copying private stage or article populations? */
import { copyFile, mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { z } from "zod";
import { WriterIdentitySchema } from "../../../packages/common-contracts/src/index";
import { collectWorkflowFiles, readWorkflowDeliveryContext } from "./feed-ingest-plan-current-files";
import type { ExecutionIdentity, MetadataRegistrations } from "./feed-ingest-plan-metadata";
import { isMetadataDeliveryConfirmed, MetadataDeliveryResultSchema } from "./feed-ingest-plan-delivery-result";
import { writeGitHubOutputs } from "./feed-ingest-plan-outputs";
import { safe_persist_data } from "@idhazh/data-delivery";
import { parseRawDocumentDumpControl, ServiceSettingsSchema } from "../src/config/service-settings";
import { rawDocumentContentsPath, RAW_DOCUMENT_CONTENTS_FILENAME } from "../src/selected-artifact-path";

// This separate upload directory is an artifact packaging protocol, not a content or retention setting.
export const RAW_DOCUMENT_ARTIFACT_DIRECTORY = "raw-document-artifacts";

async function prepareRawDocumentArtifact(input: {
  root: string; directory: string; runNumber: string; attempt: number;
  dumpRawDocumentContents?: boolean; runId?: string;
}) {
  if (input.dumpRawDocumentContents !== true || !input.runId) return undefined;
  const runId = WriterIdentitySchema.shape.run_id.parse(input.runId);
  if (runId.slice(11) !== input.runNumber) throw new Error("Raw document artifact run differs from the executed workflow");
  const settings = ServiceSettingsSchema.parse(await Bun.file(join(input.root, "config", "feed-ingest-plan-service.json")).json());
  const sourcePath = rawDocumentContentsPath(settings.inputs.artifact_root, {
    run_id: runId, writer: { attempt: input.attempt },
  });
  if (!await Bun.file(join(input.root, sourcePath)).exists()) return undefined;
  await safe_persist_data({
    sourceRoot: input.root,
    files: [{ sourcePath, targetPath: RAW_DOCUMENT_CONTENTS_FILENAME }],
    permittedPaths: [RAW_DOCUMENT_CONTENTS_FILENAME],
    destination: { kind: "artifact-directory", directory: join(input.directory, RAW_DOCUMENT_ARTIFACT_DIRECTORY) },
  });
  return `${RAW_DOCUMENT_ARTIFACT_DIRECTORY}/${RAW_DOCUMENT_CONTENTS_FILENAME}`;
}

export async function prepareWorkflowArtifacts(input: {
  root: string; directory: string; runNumber: string; attempt: number; outputPath?: string;
  identity?: ExecutionIdentity; registrations?: MetadataRegistrations;
  dumpRawDocumentContents?: boolean; runId?: string;
}) {
  // Actions run numbers and attempt numbers form filenames, never fetched text.
  const run = z.string().regex(/^\d+$/).parse(input.runNumber);
  const attempt = WriterIdentitySchema.shape.attempt.parse(input.attempt);
  const outputs: Record<string, string> = {};
  const failures: unknown[] = [];
  try {
    const path = await prepareRawDocumentArtifact({ ...input, runNumber: run, attempt });
    if (path !== undefined) {
      outputs.raw_document_contents = path;
      if (input.outputPath !== undefined) await writeGitHubOutputs(input.outputPath, { raw_document_contents: path });
    }
  } catch (error) {
    failures.push(error);
    console.error(JSON.stringify({ event: "planner_raw_document_artifact_failed",
      code: error instanceof Error ? error.name : "UnknownError" }));
  }
  async function writeOutput(key: string, path: string) {
    outputs[key] = path;
    outputs.artifact_directory = "artifacts";
    if (input.outputPath !== undefined) await writeGitHubOutputs(input.outputPath, {
      [key]: path, artifact_directory: outputs.artifact_directory,
    });
  }
  async function retain(key: string, source: string, filename: string) {
    if (!await Bun.file(source).exists()) {
      console.error(JSON.stringify({ event: "planner_evidence_unavailable", file: filename }));
      return;
    }
    const path = `artifacts/${run}-${attempt}-${filename}`;
    await mkdir(dirname(join(input.directory, path)), { recursive: true });
    await copyFile(source, join(input.directory, path));
    await writeOutput(key, path);
  }
  for (const [key, name] of [
    ["delivery", "delivery-result.json"], ["report", "report.md"],
  ] as const) await retain(key, join(input.directory, name), name);
  const responsePath = join(input.directory, "response.json");
  if (!await Bun.file(responsePath).exists()
    && !await Bun.file(join(input.directory, "host-fingerprint.json")).exists()) {
    if (failures.length) throw new AggregateError(failures, "Raw document artifact preparation failed");
    return outputs;
  }
  const context = input.identity !== undefined && input.registrations !== undefined
    ? { identity: input.identity, registrations: input.registrations } : await readWorkflowDeliveryContext(input);
  const { paths, response, failures: metadataFailures } = await collectWorkflowFiles({ ...input, ...context });
  failures.push(...metadataFailures);
  const deliveryFile = Bun.file(join(input.directory, "delivery-result.json"));
  let delivery: ReturnType<typeof MetadataDeliveryResultSchema.parse> | null = null;
  try { if (await deliveryFile.exists()) delivery = MetadataDeliveryResultSchema.parse(await deliveryFile.json()); }
  catch (error) { failures.push(error); }
  const confirmed = isMetadataDeliveryConfirmed(delivery, paths);
  if (!confirmed && paths.length > 0) {
    const recovery = `artifacts/uncommitted-metadata-${run}-${attempt}`;
    for (const path of paths) {
      const destination = join(input.directory, recovery, path);
      await mkdir(dirname(destination), { recursive: true });
      await copyFile(join(input.directory, "state", path), destination);
    }
    await writeFile(join(input.directory, recovery, "current-run-files.json"), JSON.stringify(paths));
    await writeOutput("metadata_recovery", recovery);
    console.error(JSON.stringify({ event: "planner_uncommitted_metadata_retained", files: paths.length,
      delivery_status: delivery?.status ?? "not_recorded" }));
  }
  if (response !== undefined && response.selected_articles_artifact !== null) {
    await retain("selected", join(input.root, response.selected_articles_artifact), "selected-articles.json");
  }
  if (failures.length) throw new AggregateError(failures, "Workflow metadata validation failed; valid completed files retained");
  return outputs;
}

if (import.meta.main) {
  const { RUNNER_TEMP, GITHUB_OUTPUT, GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT, DUMP_RAW_DOCUMENT_CONTENTS, RUN_ID } = process.env;
  if (!RUNNER_TEMP || !GITHUB_OUTPUT || !GITHUB_RUN_ID || !GITHUB_RUN_ATTEMPT) throw new Error("Artifact execution controls are missing");
  await prepareWorkflowArtifacts({
    root: process.cwd(), directory: join(RUNNER_TEMP, "feed-ingest-plan"),
    runNumber: GITHUB_RUN_ID, attempt: Number(GITHUB_RUN_ATTEMPT), outputPath: GITHUB_OUTPUT,
    dumpRawDocumentContents: DUMP_RAW_DOCUMENT_CONTENTS === undefined ? false : parseRawDocumentDumpControl(DUMP_RAW_DOCUMENT_CONTENTS),
    ...(RUN_ID === undefined || RUN_ID === "" ? {} : { runId: RUN_ID }),
  });
}
