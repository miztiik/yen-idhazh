/** Deliver the finalizer's completed metadata over HTTP and reap its separate safe-persist child. */
import { randomUUID } from "node:crypto";
import { writeFile } from "node:fs/promises";
import { join, relative } from "node:path";
import { CommitShaSchema, createRootContext, DELIVERY_API_PATHS, PLANNER_API_PREFIX, writeTraceContext } from "@idhazh/common-contracts";
import { PlanError } from "../src/api/plan-request";
import { ServiceSettingsSchema } from "../src/config/service-settings";
import { writeJsonLine } from "../src/logging/structured-logger";
import {
  isMetadataDeliveryConfirmed, MetadataDeliveryResultSchema,
  SafePersistHttpRequestSchema, SafePersistHttpStartupSchema,
} from "./feed-ingest-plan-delivery-result";
import { superviseFeedApiTask } from "./supervise-feed-api-task";
import { loadHonoSettings } from "../../serve-pipeline-apis/src/load-settings";
import { readMachineServerEvidence } from "@idhazh/host-probes/machine-evidence";
import { readPlannerResponseError, withPlannerFailure } from "../src/api/plan-failure";
import { retainFailureThroughCleanup } from "../src/api/retain-failure-through-cleanup";

export async function deliverWorkflowMetadataHttp(input: {
  root: string; directory: string; currentRunFiles: string; runNumber: string; attempt: number; gitSha: string;
}, options: { signal?: AbortSignal; serverEntry?: string } = {}) {
  const gitSha = CommitShaSchema.parse(input.gitSha);
  const request = SafePersistHttpRequestSchema.parse({
    runNumber: input.runNumber, attempt: input.attempt, paths: JSON.parse(input.currentRunFiles),
  });
  const context = createRootContext();
  const capture = { operation: "commit-ledgers" as const,
    execution: { run_id: null, attempt: request.attempt, traceId: context.traceId, spanId: context.spanId, git_sha: gitSha } };
  try {
    const settings = ServiceSettingsSchema.parse(await Bun.file(join(input.root, "config", "feed-ingest-plan-service.json")).json());
    const startup = SafePersistHttpStartupSchema.parse({
      nonce: randomUUID(), settings, git_sha: gitSha,
      output_root: relative(input.root, input.directory).replaceAll("\\", "/"),
    });
    const earlier = await readMachineServerEvidence(input.directory, { run_id: input.runNumber, attempt: input.attempt });
    return await superviseFeedApiTask({
      root: input.root,
      startup: {
        group: "delivery", delivery: startup, server: await loadHonoSettings(input.root),
        directory: relative(input.root, input.directory).replaceAll("\\", "/"),
        run: { run_id: input.runNumber, attempt: input.attempt, context,
          started_at: earlier[0]?.started_at ?? new Date().toISOString() },
      },
      capture: { ...capture, limits: settings.diagnostics.failure },
      ...(options.serverEntry === undefined ? {} : { serverEntry: options.serverEntry }),
      ...(options.signal === undefined ? {} : { signal: options.signal }),
      request: async (origin, signal) => {
        const response = await fetch(`${origin}${PLANNER_API_PREFIX}${DELIVERY_API_PATHS.persistData}`, {
          method: "POST", headers: { "content-type": "application/json", ...writeTraceContext(context) },
          body: JSON.stringify(request), signal, timeout: false,
        });
        const body: unknown = await response.json();
        if (response.status !== 200) {
          throw readPlannerResponseError(body, {
            ...capture, execution: { ...capture.execution, spanId: null }, limits: settings.diagnostics.failure,
          });
        }
        const result = MetadataDeliveryResultSchema.parse(body);
        if (!isMetadataDeliveryConfirmed(result, request.paths)) {
          throw new PlanError("SAFE_PERSIST_HTTP_RESULT", "Safe-persist did not confirm the exact completed metadata paths");
        }
        return result;
      },
    });
  } catch (error) {
    const failure = withPlannerFailure(error, { ...capture,
      cancelled: options.signal?.aborted === true && error === options.signal.reason });
    const result = MetadataDeliveryResultSchema.parse({
      status: "failed", commit: null, files: request.paths.length, paths: request.paths,
    });
    writeJsonLine({
      event: "safe_persist_http_client_failed", run_number: request.runNumber, attempt: request.attempt,
      status: result.status, commit: result.commit, files: result.files,
      code: failure.code, failure: failure.failure,
    });
    throw await retainFailureThroughCleanup(failure, capture, [{
      operation: "record-run", execute: () => writeFile(join(input.directory, "delivery-result.json"), JSON.stringify(result)),
    }]);
  }
}
