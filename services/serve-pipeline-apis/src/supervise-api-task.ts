/** Run one real HTTP task and retain observed child outcomes even when startup fails. */
import { mkdir, rename, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { PIPELINE_API_EVENT_SOURCE } from "./declare-event-source";
import { superviseHttpChild } from "@idhazh/feed-ingest-plan/http-child-lifetime";
import { withPlannerFailure } from "@idhazh/feed-ingest-plan/plan-failure";
import { loadConfig as loadProbeConfig } from "@idhazh/host-probes/config";
import type { FailureCaptureOptions } from "@idhazh/feed-ingest-plan/plan-failure";
import { ApiStartupSchema, startupSupervision } from "./api-startup";
import type { ApiStartup } from "./api-startup";
import { ServerEvidenceSchema, serverEvidenceFilename, serverLogFilename } from "./server-evidence";
import type { ServerEvidence } from "./server-evidence";
import { createServerEventWriter } from "./write-server-event";
import { readApiReadiness } from "./read-api-readiness";

export async function superviseApiTask<T>(input: {
  root: string; startup: ApiStartup; kind: Parameters<typeof superviseHttpChild>[0]["kind"];
  capture?: FailureCaptureOptions; serverEntry?: string; signal?: AbortSignal;
  request: (origin: string, signal: AbortSignal) => Promise<T>;
}): Promise<T> {
  const startup = ApiStartupSchema.parse(input.startup);
  const directory = resolve(input.root, startup.directory);
  await mkdir(directory, { recursive: true });
  const maxControlBytes = startup.group === "machine"
    ? (await loadProbeConfig(join(input.root, "config", "host-probes.json"))).max_request_body_bytes
    : startup.group === "planning" ? startup.planner.settings.listener.max_body_bytes
    : startup.delivery.settings.listener.max_body_bytes;
  const logger = createServerEventWriter({ directory, source: PIPELINE_API_EVENT_SOURCE, group: startup.group, run: startup.run });
  const started = performance.now();
  const evidence: ServerEvidence = {
    version: "2026-11-04", server_name: "hono-server", group: startup.group,
    run_id: startup.run.run_id, attempt: startup.run.attempt, started_at: startup.run.started_at,
    pid: null, startup: "not_started", startup_ms: null, shutdown: "not_started", exit_code: null,
    log_filename: serverLogFilename(startup.run), log_available: logger.available,
    error_code: null, cleanup_error_code: null, reported_profiles: [],
  };
  let original: unknown;
  let failed = false;
  const destination = join(directory, serverEvidenceFilename(startup.group));
  async function saveEvidence() {
    await writeFile(`${destination}.tmp`, JSON.stringify(ServerEvidenceSchema.parse(evidence)));
    await rename(`${destination}.tmp`, destination);
  }
  try {
    await saveEvidence();
    logger.write({ phase: "starting" });
    return await superviseHttpChild({
      root: input.root, kind: input.kind, startup,
      settings: {
        listener: { max_body_bytes: maxControlBytes },
        supervision: startupSupervision(startup),
      },
      ...(input.capture === undefined ? {} : { capture: input.capture }),
      ...(input.signal === undefined ? {} : { signal: input.signal }),
      serverEntry: input.serverEntry ?? fileURLToPath(new URL("./index.ts", import.meta.url)),
      diagnostics: line => logger.acceptModuleLine(line),
      observe: event => {
        evidence.pid = event.pid;
        if (event.phase === "ready") {
          evidence.startup = "ready";
          evidence.startup_ms = performance.now() - started;
        } else if (event.phase === "startup_failed") {
          evidence.startup = "failed";
          evidence.startup_ms = performance.now() - started;
        } else if (event.phase === "forced") evidence.shutdown = "forced";
        else if (event.phase === "stopped") {
          if (evidence.shutdown !== "forced") evidence.shutdown = "stopped";
          evidence.exit_code = event.exit_code ?? null;
        } else if (event.phase === "cleanup_failed") {
          if (evidence.shutdown !== "forced") evidence.shutdown = "failed";
          evidence.cleanup_error_code = `${input.kind}_CLEANUP_FAILED`;
        }
        if (event.phase !== "started" && event.phase !== "startup_failed") logger.write({
          phase: event.phase === "cleanup_failed" ? "failed" : event.phase,
          severity: event.phase === "cleanup_failed" || event.phase === "forced" ? "error" : "info",
          duration_ms: event.phase === "ready" ? evidence.startup_ms : null,
          exit_code: event.exit_code ?? null,
        });
      },
      ready: (message, pid, signal) => readApiReadiness({ message, pid, signal, startup, kind: input.kind }),
      request: input.request,
    });
  } catch (error) {
    original = error;
    failed = true;
    const failure = withPlannerFailure(error, input.capture ?? { operation: "workflow" });
    evidence.error_code = failure.code;
    if (evidence.startup !== "ready") {
      evidence.startup = "failed";
      evidence.startup_ms ??= performance.now() - started;
    }
    logger.write({ phase: "failed", severity: "error", code: failure.code });
    throw error;
  } finally {
    logger.close();
    evidence.log_available = logger.available;
    evidence.reported_profiles = logger.reportedProfiles;
    try {
      await saveEvidence();
    } catch (error) {
      if (failed) throw new AggregateError([original, error], "API task failed and its server evidence could not be saved");
      throw error;
    }
  }
}
