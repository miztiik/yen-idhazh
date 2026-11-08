/** Run one real HTTP task and retain observed child outcomes even when startup fails. */
import { mkdir, rename, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import type { z } from "zod";
import { PIPELINE_API_EVENT_SOURCE } from "./declare-event-source";
import { superviseHttpChild } from "./supervise-http-child";
import { ApiHostStartupSchema } from "./api-startup";
import type { ApiHostStartup, ApiReady, ApiReadiness } from "./api-startup";
import type { HttpChildFailure, HttpChildFailurePolicy, HttpChildKind } from "./http-child-failure";
import type { SupervisionSettings } from "./load-settings";
import { SERVER_EVIDENCE_VERSION, serverEvidenceFilename, serverLogFilename } from "./server-evidence";
import type { CurrentServerEvidence, ServerEvidence } from "./server-evidence";
import { createServerEventWriter } from "./write-server-event";
import type { ApiDiagnostic } from "./write-server-event";
import type { ApiGroup } from "./server-evidence";

export async function superviseApiTask<T, Profile, Failure extends HttpChildFailure, NativeData = never>(input: {
  root: string; startup: ApiHostStartup & { group: ApiGroup }; kind: HttpChildKind;
  failure: HttpChildFailurePolicy<Failure>; serverEntry: string; signal?: AbortSignal;
  supervision: SupervisionSettings; maxControlBytes: number;
  evidenceSchema: z.ZodType<ServerEvidence<Profile>>;
  decodeDiagnostic: (raw: unknown) => ApiDiagnostic<Profile, NativeData>;
  ready: (message: unknown, pid: number, signal: AbortSignal) => Promise<ApiReadiness>;
  request: (origin: string, signal: AbortSignal, identity: ApiReady) => Promise<T>;
}): Promise<T> {
  const startup = ApiHostStartupSchema.parse(input.startup);
  const directory = resolve(input.root, startup.directory);
  await mkdir(directory, { recursive: true });
  const logger = createServerEventWriter({
    directory, source: PIPELINE_API_EVENT_SOURCE, group: input.startup.group, run: startup.run,
    decode: input.decodeDiagnostic,
  });
  const started = performance.now();
  const evidence: CurrentServerEvidence<Profile> = {
    version: SERVER_EVIDENCE_VERSION, server_name: "hono-server", group: input.startup.group,
    run_id: startup.run.run_id, attempt: startup.run.attempt, started_at: startup.run.started_at,
    pid: null, startup: "not_started", startup_ms: null, shutdown: "not_started", exit_code: null,
    log_filename: serverLogFilename(input.startup.group, startup.run), log_available: logger.available,
    listener: { hostname: startup.server.hostname, port: startup.server.port }, identity: null,
    error_code: null, cleanup_error_code: null, reported_profiles: [],
  };
  let original: unknown;
  let failed = false;
  const destination = join(directory, serverEvidenceFilename(input.startup.group));
  async function saveEvidence() {
    await writeFile(`${destination}.tmp`, JSON.stringify(input.evidenceSchema.parse(evidence)));
    await rename(`${destination}.tmp`, destination);
  }
  try {
    await saveEvidence();
    logger.write({ phase: "starting" });
    return await superviseHttpChild({
      root: input.root, kind: input.kind, startup: input.startup,
      maxControlBytes: input.maxControlBytes, supervision: input.supervision, failure: input.failure,
      ...(input.signal === undefined ? {} : { signal: input.signal }),
      serverEntry: input.serverEntry,
      diagnostics: line => logger.acceptModuleLine(line),
      observe: event => {
        evidence.pid = event.pid;
        if (event.phase === "ready") {
          if (event.identity === undefined) throw new Error("Ready server observation has no verified identity");
          evidence.identity = event.identity;
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
      ready: input.ready,
      request: input.request,
    });
  } catch (error) {
    original = error;
    failed = true;
    const failure = input.failure.capture(error);
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
