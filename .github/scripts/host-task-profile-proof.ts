/** Prove that real HTTP commands profile an external PID throughout controlled CPU and RAM work. */
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import { z } from "../../services/host-probes/node_modules/zod";
import { loadConfig, ProbeConfigSchema } from "../../services/host-probes/src/config";
import type { ProbeConfig } from "../../services/host-probes/src/config";
import { serveSamples, START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH } from "../../services/host-probes/src/api/server";
import {
  StartTaskProfileResponseSchema, StopTaskProfileResponseSchema,
} from "../../services/host-probes/src/api/task-command-schema";
import { OwnedProcessSchema } from "../../services/host-probes/src/task-profile/profile-schema";
import { readPinnedProcess, readProcessIdentity } from "../../services/host-probes/src/task-profile/process-stat";
import {
  CONTROLLED_POLL_INTERVAL_MS, CONTROLLED_TASK_NAME, ControlledWorkResultSchema, TaskProfileProofSchema,
} from "./feed-ingest-plan-profile-schema";
export { TaskProfileProofSchema } from "./feed-ingest-plan-profile-schema";

const ControlsSchema = z.strictObject({
  minimum_elapsed_work_ms: z.number().finite().positive(), buffer_bytes: z.int().positive(),
  minimum_periodic_samples: z.int().positive(),
});
const ChildMessageSchema = z.union([
  z.strictObject({ type: z.literal("ready"), pid: z.int().positive() }), ControlledWorkResultSchema,
]);

export async function verifyTaskProfileHttp(identity: { run_id: string; correlation_id: string }, settings?: ProbeConfig) {
  if (process.platform !== "linux") throw new Error("Live PID CPU proof requires Linux");
  const controls = ControlsSchema.parse(await Bun.file(
    new URL("../../tests/fixtures/host-probes/controlled-task.json", import.meta.url),
  ).json());
  const defaults = settings ?? await loadConfig();
  const config = ProbeConfigSchema.parse({ ...defaults, task_profile: {
    ...defaults.task_profile, enabled: true, memory_enabled: true, machine_memory_enabled: true,
  } });
  if (config.task_profile.poll_interval_ms !== CONTROLLED_POLL_INTERVAL_MS) {
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
    const input = {
      identity: { pipeline_name: "host-probes", task_name: CONTROLLED_TASK_NAME, run_id: identity.run_id,
        correlation_id: identity.correlation_id, request_id: randomUUID() },
      target, server: serverPin,
    };
    const refused = await post(START_TASK_PROFILE_PATH, { ...input, padding: "x".repeat(config.max_request_body_bytes) });
    if (refused.status !== 413) throw new Error("Actual task HTTP ingress did not enforce max_request_body_bytes");
    await refused.body?.cancel();
    const response = await post(START_TASK_PROFILE_PATH, input);
    if (response.status !== 200 || response.headers.get("cache-control") !== "no-store") {
      throw new Error("Actual task profile HTTP start failed");
    }
    const started = StartTaskProfileResponseSchema.parse(await response.json());
    if (started.status !== "started" || started.target.pid !== target.pid || started.target.start_ticks !== target.start_ticks) {
      throw new Error("HTTP start did not return the requested process identity");
    }
    child.send({ command: "work" });
    const worked = await completed;
    if ("error" in worked) throw worked.error;
    const work = ControlledWorkResultSchema.parse(worked.message);
    const stoppedResponse = await post(STOP_TASK_PROFILE_PATH, { handle: started.handle, outcome: "success" });
    if (stoppedResponse.status !== 200 || stoppedResponse.headers.get("cache-control") !== "no-store") {
      throw new Error("Actual task profile HTTP stop failed");
    }
    const stoppedBytes = await stoppedResponse.text();
    const stopped = StopTaskProfileResponseSchema.parse(JSON.parse(stoppedBytes));
    if (stopped.status !== "stopped" || stopped.end_reason !== "explicit_stop") {
      throw new Error("Enabled task CPU proof did not return its explicit stop");
    }
    const profile = stopped.profile;
    if (work.elapsed_ms < controls.minimum_elapsed_work_ms || work.allocated_bytes !== controls.buffer_bytes
      || profile.periodic_sample_count < controls.minimum_periodic_samples) {
      throw new Error("Controlled task did not meet its declared CPU/RAM work inputs");
    }
    if (readPinnedProcess(target, config.max_proc_bytes, {}).reason !== null) {
      throw new Error("Controlled target must remain alive through the HTTP closing observation");
    }
    const repeated = await post(STOP_TASK_PROFILE_PATH, { handle: started.handle, outcome: "error" });
    if (repeated.status !== 200 || await repeated.text() !== stoppedBytes) {
      throw new Error("Repeated task and cache stop did not preserve the original response");
    }
    return TaskProfileProofSchema.parse({
      scope: "controlled_cpu_task", handle: started.handle, expires_at: started.expires_at,
      target, server: serverPin, target_alive_at_stop: true, work, profile,
      cache_counters_start: started.cache_counters, cache_counters: stopped.cache_counters, repeat_stop_identical: true,
    });
  } finally {
    clearTimeout(timeout);
    closing = true;
    try { await server.stop(true); }
    finally {
      if (child !== undefined) {
        const ownedChild = child;
        // Only this fixture's maintainer can end its child; the profiling API never signals the target.
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
