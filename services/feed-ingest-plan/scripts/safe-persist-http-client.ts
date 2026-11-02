/** Deliver the finalizer's completed metadata over HTTP and reap its separate safe-persist child. */
import { randomUUID } from "node:crypto";
import { writeFile } from "node:fs/promises";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { CommitShaSchema, PLANNER_API_PREFIX } from "@idhazh/common-contracts";
import { z } from "zod";
import { PlanError } from "../src/api/plan-request";
import { ServiceSettingsSchema } from "../src/config/service-settings";
import { writeJsonLine } from "../src/logging/structured-logger";
import {
  isMetadataDeliveryConfirmed, MetadataDeliveryResultSchema, SafePersistHttpReadySchema,
  SafePersistHttpRequestSchema, SafePersistHttpStartupFailureSchema, SafePersistHttpStartupSchema,
} from "./feed-ingest-plan-delivery-result";
import { superviseHttpChild } from "./http-child-lifetime";
import { readPlannerResponseError, withPlannerFailure } from "../src/api/plan-failure";
import { retainFailureThroughCleanup } from "../src/api/retain-failure-through-cleanup";

export async function deliverWorkflowMetadataHttp(input: {
  root: string; directory: string; currentRunFiles: string; runNumber: string; attempt: number; gitSha: string;
}, options: { signal?: AbortSignal; serverEntry?: string } = {}) {
  const gitSha = CommitShaSchema.parse(input.gitSha);
  const request = SafePersistHttpRequestSchema.parse({
    runNumber: input.runNumber, attempt: input.attempt, paths: JSON.parse(input.currentRunFiles),
  });
  const capture = { operation: "commit-ledgers" as const,
    execution: { run_id: null, attempt: request.attempt, correlation_id: null, git_sha: gitSha } };
  try {
    const settings = ServiceSettingsSchema.parse(await Bun.file(join(input.root, "config", "feed-ingest-plan-service.json")).json());
    const startup = SafePersistHttpStartupSchema.parse({
      nonce: randomUUID(), settings, git_sha: gitSha,
      output_root: relative(input.root, input.directory).replaceAll("\\", "/"),
    });
    return await superviseHttpChild({
      root: input.root, kind: "SAFE_PERSIST", settings, startup,
      capture: { ...capture, limits: settings.diagnostics.failure },
      serverEntry: options.serverEntry ?? fileURLToPath(new URL("./safe-persist-http-server.ts", import.meta.url)),
      ...(options.signal === undefined ? {} : { signal: options.signal }),
      ready: async (message, pid, signal) => {
        const ready = z.union([SafePersistHttpReadySchema, SafePersistHttpStartupFailureSchema]).parse(message);
        if (ready.event === "safe_persist_startup_failed") throw new PlanError(ready.code, ready.message, null, { failure: ready.failure });
        if (ready.pid !== pid || ready.nonce !== startup.nonce || ready.port !== settings.listener.port) {
          throw new PlanError("SAFE_PERSIST_READY_IDENTITY", "Readiness does not match the owned safe-persist child");
        }
        const hostname = settings.listener.hostname;
        const base = `http://${hostname === "::1" ? "[::1]" : hostname}:${ready.port}${PLANNER_API_PREFIX}`;
        const response = await fetch(`${base}/health`, { signal });
        const health = z.strictObject({ identity: SafePersistHttpReadySchema }).parse(await response.json());
        if (response.status !== 200 || JSON.stringify(health.identity) !== JSON.stringify(ready)) {
          throw new PlanError("SAFE_PERSIST_READY_IDENTITY", "HTTP readiness does not match the owned safe-persist child");
        }
        return base;
      },
      request: async (base, signal) => {
        const response = await fetch(`${base}/safe-persist-data`, {
          method: "POST", headers: { "content-type": "application/json" },
          body: JSON.stringify(request), signal, timeout: false,
        });
        const body: unknown = await response.json();
        if (response.status !== 200) {
          throw readPlannerResponseError(body, { ...capture, limits: settings.diagnostics.failure });
        }
        const result = MetadataDeliveryResultSchema.parse(body);
        if (!isMetadataDeliveryConfirmed(result, request.paths)) {
          throw new PlanError("SAFE_PERSIST_HTTP_RESULT", "Safe-persist did not confirm the exact completed metadata paths");
        }
        return result;
      },
    });
  } catch (error) {
    const failure = withPlannerFailure(error, capture);
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
