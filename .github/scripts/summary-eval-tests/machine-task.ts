/** How does one phase call the real shared machine APIs and close their owned server? */
import { z } from "../../../services/typescript-api/node_modules/zod";
import { join, resolve } from "node:path";
import { randomUUID } from "node:crypto";
import { unlink } from "node:fs/promises";
import type { Readable } from "node:stream";
import { createRootContext, OperationMetadataSchema, writeTraceContext } from "../../../packages/common-contracts/src";
import { superviseApiTask } from "../../../services/typescript-api/src/supervise-api-task";
import { HonoServerSettingsSchema } from "../../../services/typescript-api/src/load-settings";
import { ServerEvidenceSchema } from "../../../services/typescript-api/src/server-evidence";
import { ServiceSettingsSchema } from "../../../services/feed-ingest-plan/src/config/service-settings";
import { loadConfig } from "../../../services/host-probes/src/config";
import { readProcessIdentity } from "../../../services/host-probes/src/task-profile/process-stat";
import { TaskProfileSchema } from "../../../services/host-probes/src/task-profile/profile-schema";
import { FINGERPRINT_PATH } from "../../../services/host-fingerprints/src/api/server";
import { FingerprintResponseSchema } from "../../../services/host-fingerprints/src/api/fingerprint-response";
import { START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH } from "../../../services/host-probes/src/api/server";
import { StartTaskProfileResponseSchema, StopTaskProfileResponseSchema } from "../../../services/host-probes/src/api/task-command-schema";
import { HardwareSchema, projectMachineProfile } from "./machine-results";

const VERSION = "2026-11-04"; // Disposable workflow control version.
const StartupSchema = z.strictObject({
  version: z.literal(VERSION), startup_id: z.uuidv4(),
  context: z.strictObject({
    run_id: z.string(), pipeline_name: z.string(), task_name: z.string(),
  }),
  git_sha: z.string().regex(/^[0-9a-f]{40}$/), attempt: z.int().positive(),
  request_id: z.uuidv4().nullable(), correlation_id: z.uuidv4().nullable(),
  phase: z.enum(["generation", "evaluation"]),
  run: z.strictObject({
    run_id: z.string(), attempt: z.int().positive(), git_sha: z.string(),
    started_at: z.iso.datetime(),
  }),
});
const StopSchema = z.strictObject({ kind: z.literal("stop"), outcome: z.enum(["success", "error"]) });

export async function* readPackets(stream: Readable, limit: number): AsyncGenerator<unknown> {
  let pending = Buffer.alloc(0);
  for await (const chunk of stream) {
    pending = Buffer.concat([pending, Buffer.from(chunk)]);
    let end: number;
    while ((end = pending.indexOf("\n")) !== -1) {
      if (end + 1 > limit) throw new Error("Private packet exceeded its byte allowance");
      const line = pending.subarray(0, end);
      pending = pending.subarray(end + 1);
      yield JSON.parse(line.toString("utf8"));
    }
    if (pending.length > limit) throw new Error("Private packet exceeded its byte allowance");
  }
  if (pending.length !== 0) throw new Error("Private packet ended before its newline");
}

function emit(value: unknown): void { process.stdout.write(JSON.stringify(value) + "\n"); }

async function main() {
  const root = resolve(Bun.argv[2]!);
  const pipeline = z.object({
    output_directory: z.string(), control_max_bytes: z.int().positive(),
    max_response_bytes: z.int().positive(), http_connect_timeout_ms: z.int().positive(),
  }).parse(await Bun.file(join(root, "config", "summary-eval-tests.json")).json());
  const runtime = join(root, pipeline.output_directory);
  const packets = readPackets(process.stdin, pipeline.control_max_bytes);
  const startup = StartupSchema.parse((await packets.next()).value);
  const probes = await loadConfig(join(runtime, "config", "host-probes.json"));
  const service = ServiceSettingsSchema.parse(await Bun.file(join(runtime, "config", "feed-ingest-plan-service.json")).json());
  const cancellation = new AbortController();
  const abort = () => cancellation.abort(new Error("Machine task parent stopped"));
  process.once("SIGINT", abort);
  process.once("SIGTERM", abort);
  const closing = packets.next().then(value => {
    if (value.done) { abort(); return null; }
    const command = StopSchema.parse(value.value);
    return command;
  }).catch(() => { abort(); return null; });
  let profile: z.infer<typeof TaskProfileSchema> | null = null;
  let clean = true;
  let server: z.infer<typeof ServerEvidenceSchema> | null = null;
  const context = createRootContext();
  try {
    // The native evidence filename is reused; a failed restart must not read the previous phase.
    await unlink(join(runtime, "logs", "hono-server-machine.json")).catch(error => {
      if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error;
    });
    await superviseApiTask({
      root: runtime, kind: "TYPESCRIPT_API", signal: cancellation.signal,
      startup: {
        group: "machine", nonce: randomUUID(), state_root: "host", directory: "logs",
        server: HonoServerSettingsSchema.parse(await Bun.file(join(runtime, "config", "hono-server.json")).json()),
        supervision: service.supervision, run: { ...startup.run, context },
      },
      request: async (origin, signal) => {
        async function call<T>(path: string, body: unknown, schema: z.ZodType<T>): Promise<T> {
          const response = await fetch(origin + path, {
            method: "POST", redirect: "error",
            signal: AbortSignal.any([signal, AbortSignal.timeout(
              Math.max(pipeline.http_connect_timeout_ms, probes.task_profile.lifecycle_timeout_ms),
            )]),
            headers: { "Content-Type": "application/json", ...writeTraceContext(context) },
            body: JSON.stringify(body),
          });
          if (response.status !== 200 || response.body === null) throw new Error("Machine API failed");
          const reader = response.body.getReader();
          let size = 0;
          const chunks: Uint8Array[] = [];
          try {
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;
              size += value.byteLength;
              if (size > pipeline.max_response_bytes) {
                await reader.cancel();
                throw new Error("Machine response exceeded its byte allowance");
              }
              chunks.push(value);
            }
          } finally { reader.releaseLock(); }
          return schema.parse(JSON.parse(Buffer.concat(chunks).toString("utf8")));
        }
        const hardware = await call(FINGERPRINT_PATH, {
          date: startup.run.started_at.slice(0, 10),
          writer: {
            ...startup.context, git_sha: startup.git_sha, attempt: startup.attempt,
            job: null, shard: 0, producer: "telemetry.silicon",
          },
        }, FingerprintResponseSchema);
        const target = readProcessIdentity(process.pid, probes.max_proc_bytes, {});
        if (target.reason !== null) throw new Error("Owned machine-task identity is unavailable");
        const started = await call(START_TASK_PROFILE_PATH, {
          identity: startup.context,
          target: { pid: target.value.pid, start_ticks: target.value.start_ticks },
        }, StartTaskProfileResponseSchema);
        if (started.status !== "started") throw new Error("Required task profile is disabled");
        emit({
          version: VERSION, kind: "ready", service: "host", startup_id: startup.startup_id,
          pid: process.pid, profile_started: true,
          lifecycle_timeout_ms: probes.task_profile.lifecycle_timeout_ms + service.supervision.shutdown_timeout_ms,
          hardware: HardwareSchema.parse({
            cpu_model: null, cpu_logical_processors: null, cpu_physical_cores: null,
            machine_memory_total_mib: null,
            ...(hardware.status === "written" ? hardware.row : {}),
            status: hardware.status === "written" ? "collected" : "disabled",
            unavailable: hardware.unavailable,
            reason: hardware.status === "written" ? null : "configured_off",
          }),
        });
        const command = await closing;
        if (command === null) throw new Error("Explicit profile close was not received");
        const result = await call(STOP_TASK_PROFILE_PATH, {
          handle: started.handle, outcome: command.outcome,
        }, StopTaskProfileResponseSchema);
        if (result.status !== "stopped" || result.handle !== started.handle
          || JSON.stringify(OperationMetadataSchema.strip().parse(started))
          !== JSON.stringify(OperationMetadataSchema.strip().parse(result.profile))) {
          throw new Error("Closed profile does not match the admitted operation");
        }
        profile = result.profile;
      },
    });
  } catch { clean = false; }
  finally {
    try {
      const file = Bun.file(join(runtime, "logs", "hono-server-machine.json"));
      if (file.size > pipeline.max_response_bytes) throw new Error("Oversized server evidence");
      server = ServerEvidenceSchema.parse(await file.json());
      if (server.run_id !== startup.run.run_id || server.attempt !== startup.run.attempt
        || server.started_at !== startup.run.started_at) throw new Error("Stale machine evidence");
      profile ??= server.reported_profiles.at(-1) ?? null;
    } catch { clean = false; server = null; }
    emit({
      version: VERSION, kind: "stopped", service: "host", startup_id: startup.startup_id,
      pid: process.pid, clean, worker_exit_confirmed: null,
      machine: profile === null ? null : projectMachineProfile(profile),
      server: server === null ? null : {
        server_name: server.server_name, startup: server.startup, startup_ms: server.startup_ms,
        shutdown: server.shutdown, exit_code: server.exit_code,
        log_filename: server.log_filename, log_available: server.log_available,
        error_code: server.error_code, cleanup_error_code: server.cleanup_error_code,
      },
    });
    process.off("SIGINT", abort);
    process.off("SIGTERM", abort);
    process.stdin.destroy();
    if (!clean) process.exitCode = 1;
  }
}

if (import.meta.main) {
  try { await main(); }
  catch { process.exitCode = 1; }
}
