/** Which single captured UTC instant and writer identity belong to this run? */
import { createRootContext, OperationMetadataSchema, RecordedInstantSchema, WriterIdentitySchema } from "@idhazh/common-contracts";
import type { OperationMetadata } from "@idhazh/common-contracts";
import type { ServiceSettings } from "./config/service-settings";
import { selectedArtifactPath } from "./selected-artifact-path";

export const FIRST_RUN_ATTEMPT = 1;
export const DEFAULT_PLANNER_PRODUCER = "feed-ingest-plan.runner";

export function resolveRunContext(
  settings: ServiceSettings, gitSha: string, now: Date,
  runNumber?: string,
  operation: OperationMetadata = createRootContext(),
  capturedAt?: string,
  attempt = FIRST_RUN_ATTEMPT,
  producer = DEFAULT_PLANNER_PRODUCER,
) {
  if (!Number.isFinite(now.getTime())) throw new Error("run.now must be a valid UTC instant");
  const occurred_at = now.toISOString().replace(/\.\d{3}Z$/, "Z");
  const captured_at = RecordedInstantSchema.parse(capturedAt ?? now.toISOString());
  if (Date.parse(captured_at) !== now.getTime()) throw new Error("run.captured_at differs from its original clock");
  const date = occurred_at.slice(0, 10);
  const metadata = OperationMetadataSchema.parse(operation);
  const run_id = `${date}-${runNumber ?? BigInt(`0x${metadata.traceId}`).toString()}`;
  const writer = WriterIdentitySchema.parse({
    run_id, attempt, job: null, pipeline_name: "feed-ingest-plan",
    task_name: "plan", shard: 0, producer, git_sha: gitSha,
  });
  selectedArtifactPath(settings.inputs.artifact_root, { run_id, writer });
  return {
    now: occurred_at, captured_at, date, run_id, writer, ...metadata,
  };
}
export type RunContext = ReturnType<typeof resolveRunContext>;
