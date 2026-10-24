/** Prove that real HTTP commands profile an external PID throughout controlled CPU and RAM work. */
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import { z } from "../../services/host-probes/node_modules/zod";
import { loadConfig, ProbeConfigSchema } from "../../services/host-probes/src/config";
import { serveSamples, START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH } from "../../services/host-probes/src/api/server";
import {
  StartTaskProfileResponseSchema, StopTaskProfileResponseSchema,
} from "../../services/host-probes/src/api/task-command-schema";
import { OwnedProcessSchema, TaskProfileSchema } from "../../services/host-probes/src/task-profile/profile-schema";
import { readPinnedProcess, readProcessIdentity } from "../../services/host-probes/src/task-profile/process-stat";

// These are time and Linux memory-unit conversions, not sampling controls.
const MILLISECONDS_PER_SECOND = 1000;
const BYTES_PER_LINUX_KB = 1024;
const ControlsSchema = z.strictObject({
  cpu_work_ms: z.number().finite().positive(), buffer_bytes: z.int().positive(),
  minimum_periodic_samples: z.int().positive(),
});
const WorkResultSchema = z.strictObject({
  type: z.literal("complete"), allocated_bytes: z.int().positive(),
  elapsed_ms: z.number().finite().positive(), batches: z.int().positive(), digest: z.string().regex(/^[a-f0-9]{64}$/),
});
const ChildMessageSchema = z.union([
  z.strictObject({ type: z.literal("ready"), pid: z.int().positive() }), WorkResultSchema,
]);
export const TaskProfileProofSchema = z.strictObject({
  scope: z.literal("controlled_cpu_task"), handle: z.uuid(), expires_at: z.iso.datetime(),
  target: OwnedProcessSchema, server: OwnedProcessSchema, target_alive_at_stop: z.literal(true),
  work: WorkResultSchema, profile: TaskProfileSchema,
});

export async function verifyTaskProfileHttp(identity: { run_id: string; correlation_id: string }) {
  if (process.platform !== "linux") throw new Error("Live PID CPU proof requires Linux");
  const controls = ControlsSchema.parse(await Bun.file(
    new URL("../../tests/fixtures/host-probes/controlled-task.json", import.meta.url),
  ).json());
  const defaults = await loadConfig();
  const config = ProbeConfigSchema.parse({ ...defaults, task_profile: {
    ...defaults.task_profile, enabled: true, memory_enabled: true,
  } });
  if (config.task_profile.poll_interval_ms !== MILLISECONDS_PER_SECOND) {
    throw new Error("Controlled task proof requires the configured one-second polling cadence");
  }
  type ChildMessage = z.infer<typeof ChildMessageSchema>;
  type Result = { message: ChildMessage } | { error: Error };
  let ready: (result: Result) => void;
  let done: (result: Result) => void;
  const opening = new Promise<Result>(resolve => { ready = resolve; });
  const completed = new Promise<Result>(resolve => { done = resolve; });
  const fail = (error: Error) => { ready({ error }); done({ error }); };
  let closing = false;
  const server = serveSamples(config);
  let child: ReturnType<typeof Bun.spawn> | undefined;
  let timeout: ReturnType<typeof setTimeout> | undefined;
  const pin = (pid: number) => {
    const stat = readProcessIdentity(pid, config.max_proc_bytes, {});
    if (stat.reason !== null) throw new Error(`Actual controlled process identity is unavailable: ${stat.reason}`);
    return OwnedProcessSchema.parse({ pid: stat.value.pid, start_ticks: stat.value.start_ticks });
  };
  const post = (path: string, body: unknown) => fetch(new URL(path, server.url), {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    signal: AbortSignal.timeout(config.task_profile.lifecycle_timeout_ms),
  });
  try {
    child = Bun.spawn({
      cmd: [process.execPath, fileURLToPath(new URL("../../tests/fixtures/host-probes/controlled-task.ts", import.meta.url))],
      stdin: "ignore", stdout: "ignore", stderr: "inherit", serialization: "json",
      ipc(raw: unknown) {
        const result = ChildMessageSchema.safeParse(raw);
        if (!result.success) { fail(new Error("Controlled task returned invalid IPC metadata")); return; }
        if (result.data.type === "ready") ready({ message: result.data });
        else done({ message: result.data });
      },
      onExit(_child, code) {
        if (!closing) fail(new Error(`Controlled task exited before profile stop (${code})`));
      },
    });
    timeout = setTimeout(() => fail(new Error("Controlled task exceeded lifecycle_timeout_ms")),
      config.task_profile.lifecycle_timeout_ms);
    const opened = await opening;
    if ("error" in opened) throw opened.error;
    if (opened.message.type !== "ready" || opened.message.pid !== child.pid || child.pid === process.pid) {
      throw new Error("Task CPU proof must target the actual separate child PID");
    }
    const target = pin(child.pid);
    const serverPin = pin(process.pid);
    const response = await post(START_TASK_PROFILE_PATH, {
      identity: { pipeline_name: "host-probes", task_name: "controlled-cpu-task", run_id: identity.run_id,
        correlation_id: identity.correlation_id, request_id: randomUUID() },
      target, server: serverPin,
    });
    if (response.status !== 200) throw new Error("Actual task profile HTTP start failed");
    const started = StartTaskProfileResponseSchema.parse(await response.json());
    if (started.status !== "started" || JSON.stringify(started.target) !== JSON.stringify(target)) {
      throw new Error("HTTP start did not return the requested process identity");
    }
    child.send({ command: "work" });
    const worked = await completed;
    if ("error" in worked) throw worked.error;
    const work = WorkResultSchema.parse(worked.message);
    const stoppedResponse = await post(STOP_TASK_PROFILE_PATH, { handle: started.handle, outcome: "success" });
    if (stoppedResponse.status !== 200) throw new Error("Actual task profile HTTP stop failed");
    const stopped = StopTaskProfileResponseSchema.parse(await stoppedResponse.json());
    if (stopped.status !== "stopped") throw new Error("Enabled task CPU proof did not return its profile");
    const profile = stopped.profile;
    const worker = profile.processes.worker;
    const clock = profile.process_clock_ticks_per_second;
    if (profile.identity.task_name !== "controlled-cpu-task" || profile.outcome !== "success"
      || stopped.end_reason !== "explicit_stop" || profile.end_reason !== "explicit_stop"
      || worker.closing.pid !== target.pid || worker.closing.start_ticks !== target.start_ticks
      || profile.processes.server.closing.pid !== serverPin.pid
      || profile.processes.server.closing.start_ticks !== serverPin.start_ticks
      || clock.reason !== null || clock.value <= 0
      || worker.cpu.reason !== null || worker.cpu.value.cpu_time_ms <= 0 || worker.cpu.value.percent_one_core <= 0
      || worker.cpu_interval_ms < work.elapsed_ms || profile.elapsed_ms < work.elapsed_ms
      || work.elapsed_ms < controls.cpu_work_ms || work.allocated_bytes !== controls.buffer_bytes
      || profile.periodic_sample_count < controls.minimum_periodic_samples
      || !profile.samples.some(sample => sample.phase === "poll" && sample.processes.worker.cpu_window.full_window
        && sample.processes.worker.cpu_window.cpu.value !== null
        && sample.processes.worker.cpu_window.cpu.value.cpu_time_ms > 0)
      || !profile.samples.every((sample, index) => index === 0 || sample.elapsed_ms >= profile.samples[index - 1]!.elapsed_ms)
      || worker.closing.memory_kb.rss === null || worker.closing.memory_kb.rss < controls.buffer_bytes / BYTES_PER_LINUX_KB
      || profile.processes.server.closing.memory_kb.rss === null || profile.machine_available_min_kb === null) {
      throw new Error("Actual external PID CPU, identities, RAM or full-task intervals were not proved");
    }
    if (readPinnedProcess(target, config.max_proc_bytes, {}).reason !== null) {
      throw new Error("Controlled target must remain alive through the HTTP closing observation");
    }
    return TaskProfileProofSchema.parse({
      scope: "controlled_cpu_task", handle: started.handle, expires_at: started.expires_at,
      target, server: serverPin, target_alive_at_stop: true, work, profile,
    });
  } finally {
    clearTimeout(timeout);
    closing = true;
    try { await server.stop(true); }
    finally {
      if (child !== undefined) {
        const ownedChild = child;
        const cleanup = setTimeout(() => ownedChild.kill(), config.task_profile.lifecycle_timeout_ms);
        try {
          if (ownedChild.exitCode === null) ownedChild.send({ command: "close" });
          const code = await ownedChild.exited;
          if (code !== 0) throw new Error(`Controlled task cleanup failed (${code})`);
        } finally { clearTimeout(cleanup); }
      }
    }
  }
}
