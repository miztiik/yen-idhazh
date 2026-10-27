/** How does the manual planner workflow deliver its exact verified metadata files? */
import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import {
  safe_persist_data,
  SafePersistDataCommitterSchema,
  SafePersistDataInputSchema,
} from "@idhazh/data-delivery";
import type { SafePersistDataCommitter } from "@idhazh/data-delivery";
import { verifyMetadataFile } from "./feed-ingest-plan-metadata";
import type { ExecutionIdentity, MetadataRegistrations } from "./feed-ingest-plan-metadata";
import { collectWorkflowFiles, readWorkflowDeliveryContext } from "./feed-ingest-plan-current-files";
import { MetadataDeliveryResultSchema } from "./feed-ingest-plan-delivery-result";

export function metadataWritePermissions(registrations: MetadataRegistrations): string[] {
  return Object.values(registrations).map(({ prefix }) => `state/raw/${prefix.join("/")}`);
}

export async function deliverPlannerFiles(input: Readonly<{
  repository: string;
  stateRoot: string;
  paths: readonly string[];
  message: string;
  retry: unknown;
  committer: SafePersistDataCommitter;
  identity: ExecutionIdentity;
  registrations: MetadataRegistrations;
}>) {
  if (new Set(input.paths).size !== input.paths.length) {
    throw new Error("delivery: duplicate output paths");
  }
  const completed: { sourcePath: string; targetPath: string; sha256: string }[] = [];
  for (const path of input.paths) {
    const metadata = await verifyMetadataFile(input.stateRoot, path, input.registrations, input.identity);
    completed.push({
      sourcePath: path,
      targetPath: `state/${path}`,
      sha256: metadata.file_sha256,
    });
  }
  const request = SafePersistDataInputSchema.parse({
    sourceRoot: input.stateRoot,
    files: completed.map(({ sourcePath, targetPath, sha256 }) => ({ sourcePath, targetPath, sha256 })),
    permittedPaths: metadataWritePermissions(input.registrations),
    destination: { kind: "git", repository: input.repository },
    committer: input.committer,
    message: input.message,
    retry: input.retry,
  });
  const result = await safe_persist_data(request);
  if (result.destination !== "git") {
    throw new Error("delivery: metadata requires a Git destination");
  }
  return MetadataDeliveryResultSchema.parse({
    status: result.status,
    commit: result.commit,
    files: result.files,
    paths: input.paths,
  });
}

if (import.meta.main) {
  const { RUNNER_TEMP, CURRENT_RUN_FILES, GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT } = process.env;
  if (!RUNNER_TEMP || !CURRENT_RUN_FILES) throw new Error("Delivery requires exact planner output paths");
  const parsedPaths: unknown = JSON.parse(CURRENT_RUN_FILES);
  if (!Array.isArray(parsedPaths) || !parsedPaths.every((path): path is string => typeof path === "string")) {
    throw new Error("Delivery output list is invalid");
  }
  const paths = parsedPaths;
  const root = join(RUNNER_TEMP, "feed-ingest-plan");
  try {
    if (!GITHUB_RUN_ID || !GITHUB_RUN_ATTEMPT) throw new Error("Delivery requires the executed run and attempt");
    const context = await readWorkflowDeliveryContext({
      root: process.cwd(),
      directory: root,
      runNumber: GITHUB_RUN_ID,
      attempt: Number(GITHUB_RUN_ATTEMPT),
    });
    const completed = await collectWorkflowFiles({ root: process.cwd(), directory: root, ...context });
    if ([...paths].sort().join("\n") !== [...completed.paths].sort().join("\n")) {
      throw new Error("Delivery paths differ from the validated completed API output");
    }
    if (completed.failures.length) console.error(JSON.stringify({
      event: "planner_metadata_producers_failed",
      failures: completed.failures.length,
    }));
    const result = MetadataDeliveryResultSchema.parse(await deliverPlannerFiles({
      repository: process.cwd(),
      stateRoot: join(root, "state"),
      paths,
      ...context,
      message: "Record feed planner and host outcomes",
      retry: await Bun.file("config/push-retry.json").json(),
      committer: SafePersistDataCommitterSchema.parse(await Bun.file("config/data-delivery.json").json()),
    }));
    await writeFile(join(root, "delivery-result.json"), JSON.stringify(result));
    console.log(JSON.stringify(result));
  } catch (error) {
    const result = MetadataDeliveryResultSchema.parse({ status: "failed", commit: null, files: paths.length, paths });
    await writeFile(join(root, "delivery-result.json"), JSON.stringify(result));
    console.error(JSON.stringify({
      event: "planner_metadata_delivery_failed",
      ...result,
      code: error instanceof Error ? error.name : "UnknownError",
      reason: error instanceof Error
        ? error.message.replaceAll(root, "feed-ingest-plan").replaceAll(process.cwd(), ".").replaceAll("\\", "/")
        : "Unknown delivery failure",
    }));
    process.exitCode = 2;
  }
}
