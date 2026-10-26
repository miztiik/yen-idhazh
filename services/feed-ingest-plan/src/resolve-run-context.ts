/** Which single captured UTC instant and writer identity belong to this run? */
import { RecordedInstantSchema, WriterIdentitySchema } from "@idhazh/common-contracts";
import { randomUUID } from "node:crypto";
import { z } from "zod";
import type { ServiceSettings } from "./config/service-settings";
import { selectedArtifactPath } from "./selected-artifact-path";

export function resolveRunContext(
  settings: ServiceSettings, gitSha: string, now: Date,
  runNumber = BigInt(`0x${randomUUID().replaceAll("-", "")}`).toString(),
  correlationId: string = randomUUID(),
  capturedAt?: string,
) {
  if (!Number.isFinite(now.getTime())) throw new Error("run.now must be a valid UTC instant");
  const occurred_at = now.toISOString().replace(/\.\d{3}Z$/, "Z");
  const captured_at = RecordedInstantSchema.parse(capturedAt ?? now.toISOString());
  if (Date.parse(captured_at) !== now.getTime()) throw new Error("run.captured_at differs from its original clock");
  const date = occurred_at.slice(0, 10);
  const run_id = `${date}-${runNumber}`;
  const writer = WriterIdentitySchema.parse({
    run_id, attempt: settings.run.attempt, job: null, pipeline_name: "feed-ingest-plan",
    task_name: "plan", shard: 0, producer: settings.run.producer, git_sha: gitSha,
  });
  selectedArtifactPath(settings.inputs.artifact_root, { run_id, writer });
  return {
    now: occurred_at, captured_at, date, run_id, correlation_id: z.uuid({ version: "v4" }).parse(correlationId),
    writer,
  };
}
export type RunContext = ReturnType<typeof resolveRunContext>;
