/** Which exact run receipts can be retained without copying private stage or article populations? */
import { copyFile, mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { z } from "zod";
import { WriterIdentitySchema } from "../../../packages/common-contracts/src/index";
import { collectWorkflowFiles, readWorkflowDeliveryContext } from "./feed-ingest-plan-current-files";
import type { ExecutionIdentity, MetadataRegistrations } from "./feed-ingest-plan-metadata";
import { MetadataDeliveryResultSchema } from "./feed-ingest-plan-delivery-result";
import { writeGitHubOutputs } from "./feed-ingest-plan-outputs";

export async function prepareWorkflowArtifacts(input: {
  root: string; directory: string; runNumber: string; attempt: number; outputPath?: string;
  identity?: ExecutionIdentity; registrations?: MetadataRegistrations;
}) {
  // Actions run numbers and attempt numbers form filenames, never fetched text.
  const run = z.string().regex(/^\d+$/).parse(input.runNumber);
  const attempt = WriterIdentitySchema.shape.attempt.parse(input.attempt);
  const outputs: Record<string, string> = {};
  async function writeOutput(key: string, path: string) {
    outputs[key] = path;
    if (input.outputPath !== undefined) await writeGitHubOutputs(input.outputPath, { [key]: path });
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
    ["response", "response.json"], ["health", "health.json"], ["history", "history-staging-ms.json"],
    ["delivery", "delivery-result.json"], ["runtime_log", "runtime.log"], ["delivery_log", "delivery.log"],
    ["policy", "workflow-policy.json"], ["resources", "resources.json"], ["report", "report.md"],
  ] as const) await retain(key, join(input.directory, name), name);
  await retain("independent", join(input.root, "test-results", "host-probes", "resource-proof.json"), "controlled-host-proof.json");
  const responsePath = join(input.directory, "response.json");
  if (!await Bun.file(responsePath).exists() && !await Bun.file(join(input.directory, "resources.json")).exists()) return outputs;
  const context = input.identity !== undefined && input.registrations !== undefined
    ? { identity: input.identity, registrations: input.registrations } : await readWorkflowDeliveryContext(input);
  const { paths, response, failures } = await collectWorkflowFiles({ ...input, ...context });
  const deliveryFile = Bun.file(join(input.directory, "delivery-result.json"));
  let delivery: ReturnType<typeof MetadataDeliveryResultSchema.parse> | null = null;
  try { if (await deliveryFile.exists()) delivery = MetadataDeliveryResultSchema.parse(await deliveryFile.json()); }
  catch (error) { failures.push(error); }
  const confirmed = delivery !== null && delivery.files === paths.length
    && [...delivery.paths].sort().join("\n") === [...paths].sort().join("\n")
    && (delivery.status === "landed" || delivery.status === "already-on-main") && delivery.commit !== null;
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
  const { RUNNER_TEMP, GITHUB_OUTPUT, GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT } = process.env;
  if (!RUNNER_TEMP || !GITHUB_OUTPUT || !GITHUB_RUN_ID || !GITHUB_RUN_ATTEMPT) throw new Error("Artifact execution controls are missing");
  await prepareWorkflowArtifacts({
    root: process.cwd(), directory: join(RUNNER_TEMP, "feed-ingest-plan"),
    runNumber: GITHUB_RUN_ID, attempt: Number(GITHUB_RUN_ATTEMPT), outputPath: GITHUB_OUTPUT,
  });
}
