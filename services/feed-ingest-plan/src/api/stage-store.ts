/** How is one immutable planner batch saved and read by its own identity? */
import { mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { randomUUID } from "node:crypto";
import { RequestIdSchema } from "@idhazh/common-contracts";
import { z } from "zod";
import { PlanError } from "./plan-request";

export type BatchStage = "parsed" | "selected" | "partitioned";

function batchPath(outputRoot: string, stage: BatchStage, batchId: string) {
  // The directory and suffix identify this storage protocol, not a tuning control.
  return join(outputRoot, "planner-batches", stage, `${RequestIdSchema.parse(batchId)}.json`);
}

export async function writeStageBatch<T extends { batch_id: string }>(
  outputRoot: string, stage: BatchStage, schema: z.ZodType<T>, raw: unknown,
): Promise<T> {
  const batch = schema.parse(raw);
  const path = batchPath(outputRoot, stage, batch.batch_id);
  const temporary = `${path}.${randomUUID()}.tmp`;
  await mkdir(join(outputRoot, "planner-batches", stage), { recursive: true });
  try {
    await writeFile(temporary, JSON.stringify(batch), { flag: "wx" });
    await rename(temporary, path);
  } finally {
    await rm(temporary, { force: true });
  }
  return batch;
}

export async function readStageBatch<T extends { batch_id: string }>(
  outputRoot: string, stage: BatchStage, batchId: string, schema: z.ZodType<T>,
  read: (raw: unknown) => T = raw => schema.parse(raw),
): Promise<T> {
  const path = batchPath(outputRoot, stage, batchId);
  let content: string;
  try {
    content = await readFile(path, "utf8");
  } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") {
      throw new PlanError("ARTIFACT_NOT_FOUND", "No completed batch exists for this stage and identity", "batch_id");
    }
    throw error;
  }
  try {
    const batch = read(JSON.parse(content));
    if (batch.batch_id !== batchId) {
      throw new PlanError("ARTIFACT_INVALID", "Stored batch identity differs from the requested identity", "batch_id");
    }
    return batch;
  } catch (error) {
    if (error instanceof SyntaxError || error instanceof z.ZodError) {
      throw new PlanError("ARTIFACT_INVALID", "Stored batch does not match its declared stage contract", "batch_id");
    }
    throw error;
  }
}
