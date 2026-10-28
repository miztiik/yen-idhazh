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
import { describePlanError } from "../src/api/plan-request";
import { RelativePathSchema } from "../src/config/service-settings";
import { z } from "zod";

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

export async function deliverWorkflowMetadata(input: {
  root: string; directory: string; currentRunFiles: string; runNumber: string; attempt: number;
}) {
  const paths = z.array(RelativePathSchema).parse(JSON.parse(input.currentRunFiles));
  try {
    const context = await readWorkflowDeliveryContext({
      ...input,
    });
    const completed = await collectWorkflowFiles({ ...input, ...context });
    if ([...paths].sort().join("\n") !== [...completed.paths].sort().join("\n")) {
      throw new Error("Delivery paths differ from the validated completed API output");
    }
    if (completed.failures.length) console.error(JSON.stringify({
      event: "planner_metadata_producers_failed",
      failures: completed.failures.length,
    }));
    const result = MetadataDeliveryResultSchema.parse(await deliverPlannerFiles({
      repository: input.root,
      stateRoot: join(input.directory, "state"),
      paths,
      ...context,
      message: "Record feed planner and host outcomes",
      retry: await Bun.file(join(input.root, "config", "push-retry.json")).json(),
      committer: SafePersistDataCommitterSchema.parse(await Bun.file(join(input.root, "config", "data-delivery.json")).json()),
    }));
    await writeFile(join(input.directory, "delivery-result.json"), JSON.stringify(result));
    console.log(JSON.stringify(result));
    return result;
  } catch (error) {
    const result = MetadataDeliveryResultSchema.parse({ status: "failed", commit: null, files: paths.length, paths });
    await writeFile(join(input.directory, "delivery-result.json"), JSON.stringify(result));
    console.error(JSON.stringify({
      event: "planner_metadata_delivery_failed",
      ...result,
      code: error instanceof Error ? error.name : "UnknownError",
      reason: error instanceof Error
        ? error.message.replaceAll(input.directory, "feed-ingest-plan").replaceAll(input.root, ".").replaceAll("\\", "/")
        : "Unknown delivery failure",
    }));
    throw error;
  }
}

if (import.meta.main) {
  try {
    const { RUNNER_TEMP, CURRENT_RUN_FILES, GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT } = process.env;
    if (!RUNNER_TEMP || !CURRENT_RUN_FILES || !GITHUB_RUN_ID || !GITHUB_RUN_ATTEMPT) {
      throw new Error("Delivery requires exact output paths and the executed run and attempt");
    }
    await deliverWorkflowMetadata({
      root: process.cwd(), directory: join(RUNNER_TEMP, "feed-ingest-plan"),
      currentRunFiles: CURRENT_RUN_FILES, runNumber: GITHUB_RUN_ID, attempt: Number(GITHUB_RUN_ATTEMPT),
    });
  } catch (error) {
    console.error(JSON.stringify({ event: "planner_metadata_delivery_cli_failed",
      code: describePlanError(error, process.cwd()).code }));
    process.exitCode = 2;
  }
}
