/** Name each visible file in the prepared current-run upload directory, relative to the ZIP root. */
import { randomUUID } from "node:crypto";
import { join } from "node:path";
import type { FeedIngestEvent } from "@idhazh/common-contracts";
import { createStageLogger, writeJsonLine } from "../src/logging/structured-logger";

export async function publishUploadInventory(input: {
  directory: string; runNumber: string; now?: Date; write?: (event: FeedIngestEvent) => void;
}) {
  const now = input.now ?? new Date();
  const emit = createStageLogger({
    run_id: `${now.toISOString().slice(0, 10)}-${input.runNumber}`, correlation_id: randomUUID(),
  }, event => {
    (input.write ?? writeJsonLine)(event);
    if (event.details._compliance !== undefined) throw new Error("Upload inventory event was refused by the publisher");
  });
  emit("artifact-upload", "started");
  let count = 0;
  try {
    // This directory is built by this run, not a repository-wide discovery input.
    for await (const path of new Bun.Glob("**/*").scan({
      cwd: input.directory, dot: false, onlyFiles: true, followSymlinks: true,
    })) {
      const file = path.replaceAll("\\", "/");
      if (file.split("/").some(part => part.startsWith("."))) continue;
      emit("artifact-upload", "started", { file }, ["file"]);
      count++;
    }
    if (count === 0) throw new Error("Prepared artifact directory contains no upload files");
    emit("artifact-upload", "completed", { file_count: count });
    return count;
  } catch (error) {
    emit("artifact-upload", "failed", { failure_code: "ARTIFACT_INVENTORY_FAILED", file_count: count });
    throw error;
  }
}

if (import.meta.main) {
  const { RUNNER_TEMP, GITHUB_RUN_ID, ARTIFACT_DIRECTORY } = process.env;
  if (!RUNNER_TEMP || !GITHUB_RUN_ID || !ARTIFACT_DIRECTORY) throw new Error("Artifact inventory controls are missing");
  await publishUploadInventory({
    directory: join(RUNNER_TEMP, "feed-ingest-plan", ARTIFACT_DIRECTORY), runNumber: GITHUB_RUN_ID,
  });
}
