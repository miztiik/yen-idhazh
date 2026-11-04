/** How does one owned helper close shared whole-machine measurement before the API stops? */
import { z } from "../../../services/host-probes/node_modules/zod";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import type { Readable } from "node:stream";
import {
  loadConfig, ProbeConfigSchema,
} from "../../../services/host-probes/src/config";
import {
  startTaskProfile,
} from "../../../services/host-probes/src/task-profile/task-profiler";
import type {
  TaskProfileSession,
} from "../../../services/host-probes/src/task-profile/task-profiler";
import { TaskProfileSchema } from "../../../services/host-probes/src/task-profile/profile-schema";
import { captureHardware } from "./hardware";
import { projectMachineProfile } from "./project-profile";

const VERSION = "2026-11-02"; // Private workflow protocol identity.
const StartupSchema = z.strictObject({
  version: z.literal(VERSION), startup_id: z.uuidv4(),
  context: z.strictObject({
    run_id: z.string().min(1), pipeline_name: z.string().min(1), task_name: z.string().min(1),
  }),
  git_sha: z.string().regex(/^[0-9a-f]{40}$/), attempt: z.int().positive(),
  request_id: z.uuidv4(), correlation_id: z.uuidv4(),
});
const StopSchema = z.strictObject({
  kind: z.literal("stop"), outcome: z.enum(["success", "error"]),
});

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

async function main(): Promise<void> {
  const root = fileURLToPath(new URL("../../../", import.meta.url));
  const settings = z.object({
    control_max_bytes: z.int().positive(), output_directory: z.string().min(1),
  }).parse(await Bun.file(join(root, "config", "summary-eval-hhem.json")).json());
  const shared = await loadConfig(join(root, "config", "host-probes.json"));
  // Select this step's instruments; sampling and lifecycle bounds remain shared controls.
  const config = ProbeConfigSchema.parse({
    ...shared, task_profile: {
      ...shared.task_profile, enabled: true, memory_enabled: false, machine_memory_enabled: true,
    },
  });
  const packets = readPackets(process.stdin, settings.control_max_bytes);
  const first = await packets.next();
  const startup = StartupSchema.parse(first.value);
  let finished = false;
  let deadline: ReturnType<typeof setTimeout> | undefined;
  const abort = new AbortController();
  const closing = packets.next().then(result => {
    if (result.done) return { kind: "eof" as const };
    const value = StopSchema.safeParse(result.value);
    return value.success ? value.data : { kind: "invalid" as const };
  }, () => ({ kind: "invalid" as const })).then(command => {
    if (command.kind !== "stop" && !finished) {
      abort.abort();
      deadline = setTimeout(() => process.exit(1), config.task_profile.lifecycle_timeout_ms);
    }
    return command;
  });
  let session: TaskProfileSession | null = null;
  let profile: z.infer<typeof TaskProfileSchema> | null = null;
  let clean = true;
  try {
    const hardware = await captureHardware(root, join(root, settings.output_directory), {
      ...startup.context, git_sha: startup.git_sha, attempt: startup.attempt,
    });
    try {
      session = await startTaskProfile({ config, report: () => {} }, startup.context, {
        signal: abort.signal, expiresAfterMs: config.task_profile.profile_handle_ttl_ms,
      });
    } catch { clean = false; }
    emit({
      version: VERSION, kind: "ready", service: "host", startup_id: startup.startup_id,
      pid: process.pid, hardware, profile_started: session !== null,
      lifecycle_timeout_ms: config.task_profile.lifecycle_timeout_ms,
    });
    const command = await closing;
    if (command.kind === "invalid") clean = false;
    if (session !== null) {
      try {
        profile = TaskProfileSchema.parse(await session.close(
          command.kind === "stop" ? command.outcome : "cancelled",
          command.kind === "stop" ? "explicit_stop" : "service_stopped",
        ));
      } catch { clean = false; }
    }
  } finally {
    finished = true;
    clearTimeout(deadline);
    emit({
      version: VERSION, kind: "stopped", service: "host", startup_id: startup.startup_id,
      pid: process.pid, clean, worker_exit_confirmed: null,
      machine: profile === null ? null : projectMachineProfile(profile),
    });
    process.stdin.destroy();
    if (!clean) process.exitCode = 1;
  }
}

if (import.meta.main) {
  try { await main(); }
  catch {
    // No article text enters this helper, and no raw child exception leaves it.
    process.exitCode = 1;
  }
}
