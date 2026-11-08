/** Do independently owned native applications preserve the sibling's real state through restart and pipe loss? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { createRootContext, PLANNER_API_PATHS, PLANNER_API_PREFIX, writeTraceContext } from "@idhazh/common-contracts";
import { ApiReadySchema, API_HEALTH_PATH } from "@idhazh/serve-pipeline-apis/startup";
import { loadHonoSettings } from "@idhazh/serve-pipeline-apis/settings";
import { FINGERPRINT_PATH } from "@idhazh/host-fingerprints/api";
import { FingerprintResponseSchema } from "@idhazh/host-fingerprints/response";
import { START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH } from "@idhazh/host-probes/api";
import { loadConfig } from "@idhazh/host-probes/config";
import { TaskProfileSchema } from "@idhazh/host-probes/profile";
import { OwnedProcessSchema } from "../../host-probes/src/task-profile/profile-schema";
import { readProcessIdentity } from "../../host-probes/src/task-profile/process-stat";
import { StartTaskProfileResponseSchema, StopTaskProfileResponseSchema } from "../../host-probes/src/api/task-command-schema";
import { recordedMachineTask } from "../../host-probes/test/machine-api-recordings";
import { FetchResponseSchema, ParseResponseSchema } from "../src/api/document-response.schema";
import { FeedApiStartupSchema } from "../scripts/read-feed-api-startup";
import type { FeedApiStartup } from "../scripts/read-feed-api-startup";
import type { MachineApiStartup } from "../../host-probes/src/api/read-machine-api-startup";
import { operationLink, operationMetadata } from "../src/api/operation-context";
import { recordedPlannerProcess } from "./planner-process-recordings";
import { NativeReplySchema, NativeRequestSchema } from "./run-api-task-owner";
import type { NativeReply } from "./run-api-task-owner";

async function beforeDeadline<T>(operation: Promise<T>, milliseconds: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([operation, new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new Error("Owned native operation exceeded its declared deadline")), milliseconds);
    })]);
  } finally { clearTimeout(timer); }
}

async function startNative(root: string, startup: FeedApiStartup | MachineApiStartup, maxBytes: number) {
  const pending = new Map<string, { resolve: (value: NativeReply) => void; reject: (error: Error) => void }>();
  const child = Bun.spawn({
    cmd: [process.execPath, fileURLToPath(new URL("./run-api-task-owner.ts", import.meta.url))],
    cwd: root, stdin: "pipe", stdout: "pipe", stderr: "pipe", serialization: "json",
    ipc(raw: unknown) {
      const result = NativeReplySchema.safeParse(raw);
      if (!result.success) {
        for (const operation of pending.values()) operation.reject(new Error("Native IPC reply failed validation"));
        return;
      }
      const operation = pending.get(result.data.request_id);
      if (operation === undefined) throw new Error("Native IPC reply belongs to no admitted request");
      operation.resolve(result.data);
    },
  });
  const errors = new Response(child.stderr).text();
  const exited = child.exited.then(code => {
    for (const operation of pending.values()) operation.reject(new Error(`Native child exited (${code})`));
    return code;
  });
  const reader = child.stdout.getReader();
  try {
    child.stdin.write(JSON.stringify(startup) + "\n");
    await child.stdin.flush();
    const ready = await beforeDeadline((async () => {
      let packet = "";
      let size = 0;
      const decoder = new TextDecoder();
      while (!packet.includes("\n")) {
        const { value, done } = await reader.read();
        if (done) throw new Error("Native child exited before readiness");
        size += value.byteLength;
        if (size > maxBytes) throw new Error("Native readiness exceeded its declared input bound");
        packet += decoder.decode(value, { stream: true });
      }
      return ApiReadySchema.parse(JSON.parse(packet.slice(0, packet.indexOf("\n"))));
    })(), startup.server.supervision.readiness_timeout_ms);
    expect(ready).toMatchObject({
      pid: child.pid, group: startup.group, modules: [startup.group], port: startup.server.port,
      nonce: startup.group === "planning" ? startup.planner.nonce
        : startup.group === "delivery" ? startup.delivery.nonce : startup.nonce,
    });
    return {
      child, ready, errors,
      async call(path: string, body?: unknown, headers: Record<string, string> = {}) {
        const request_id = randomUUID();
        const command = NativeRequestSchema.parse({
          request_id, path, method: body === undefined ? "GET" : "POST",
          headers: { "content-type": "application/json", ...headers },
          ...(body === undefined ? {} : { body }),
        });
        const response = new Promise<NativeReply>((resolve, reject) => { pending.set(request_id, { resolve, reject }); });
        try {
          child.send(command);
          const result = await beforeDeadline(response, startup.server.supervision.readiness_timeout_ms);
          if (result.kind === "failed") throw new Error(result.code);
          return result;
        } finally { pending.delete(request_id); }
      },
      async stop(signal?: "SIGTERM") {
        if (child.exitCode === null) {
          if (signal === undefined) child.stdin.end();
          else child.kill(signal);
        }
        try { expect(await beforeDeadline(exited, startup.server.supervision.shutdown_timeout_ms)).toBe(0); }
        catch (error) {
          if (child.exitCode === null) child.kill("SIGKILL");
          await beforeDeadline(exited, startup.server.supervision.forced_exit_timeout_ms);
          throw error;
        }
      },
    };
  } catch (error) {
    child.stdin.end();
    try { await beforeDeadline(exited, startup.server.supervision.shutdown_timeout_ms); }
    catch (cleanup) {
      child.kill("SIGKILL");
      await beforeDeadline(exited, startup.server.supervision.forced_exit_timeout_ms);
      throw new AggregateError([error, cleanup], "Native startup and cleanup failed");
    }
    throw error;
  } finally { reader.releaseLock(); }
}

test.skipIf(process.platform !== "linux")("owned IPC proves reciprocal native restart, target pins and retained results", async () => {
  const plannerFixture = await recordedPlannerProcess();
  const machineFixture = await recordedMachineTask();
  const probes = await loadConfig(join(machineFixture.root, "config", "host-probes.json"));
  const pin = (pid: number) => {
    const result = readProcessIdentity(pid, probes.max_proc_bytes, {});
    if (result.reason !== null) throw new Error("The actual owned native process has no verified start pin");
    return OwnedProcessSchema.parse({ pid: result.value.pid, start_ticks: result.value.start_ticks });
  };
  const plannerStartup = FeedApiStartupSchema.parse({
    group: "planning", planner: plannerFixture.startup,
    server: await loadHonoSettings(plannerFixture.directory, "planning"),
    directory: relative(plannerFixture.directory, plannerFixture.evidence).replaceAll("\\", "/"),
    run: { run_id: plannerFixture.startup.runtime.run_number, attempt: plannerFixture.startup.runtime.attempt,
      started_at: plannerFixture.startup.runtime.captured_at, context: operationMetadata(plannerFixture.startup.runtime) },
  });
  if (plannerStartup.group !== "planning") throw new Error("The native planner requires planning startup");
  let planning: Awaited<ReturnType<typeof startNative>> | undefined;
  let machine: Awaited<ReturnType<typeof startNative>> | undefined;
  let original: unknown;
  let failed = false;
  try {
    planning = await startNative(plannerFixture.directory, plannerStartup, plannerStartup.planner.settings.listener.max_body_bytes);
    machine = await startNative(machineFixture.root, machineFixture.startup, probes.max_request_body_bytes);
    const planningPin = pin(planning.child.pid);
    const machinePin = pin(machine.child.pid);
    expect(planningPin.pid).not.toBe(machinePin.pid);
    const parent = createRootContext();
    const profileInput = {
      identity: { pipeline_name: "owned-api-proof", task_name: "profile-planning", run_id: "700" },
      target: planningPin,
    };
    const started = StartTaskProfileResponseSchema.parse(JSON.parse(
      (await machine.call(START_TASK_PROFILE_PATH, profileInput, writeTraceContext(parent))).text,
    ));
    if (started.status !== "started") throw new Error("The real planner profile must start");
    expect(started.target).toEqual(planningPin);
    const completed = await machine.call(STOP_TASK_PROFILE_PATH, { handle: started.handle, outcome: "success" });
    const profile = StopTaskProfileResponseSchema.parse(JSON.parse(completed.text));
    if (profile.status !== "stopped") throw new Error("The real profile must close explicitly");
    expect(profile.profile.processes.worker.closing).toMatchObject(planningPin);
    const fingerprint = FingerprintResponseSchema.parse(JSON.parse((await machine.call(FINGERPRINT_PATH, {
      date: "2026-11-04", writer: {
        run_id: "2026-11-04-700", attempt: 3, git_sha: plannerFixture.startup.runtime.git_sha,
        job: null, shard: 0, pipeline_name: "owned-api-proof", task_name: "capture-host", producer: "telemetry.silicon",
      },
    })).text));
    if (fingerprint.status !== "written" || fingerprint.files[0] === undefined) throw new Error("The native host result must persist");
    const file = join(machineFixture.root, "state", fingerprint.files[0].path);
    const bytes = await readFile(file);
    await planning.stop("SIGTERM");
    expect(pin(machine.child.pid)).toEqual(machinePin);
    expect(JSON.parse((await machine.call(API_HEALTH_PATH)).text)).toEqual({ identity: machine.ready });
    expect((await machine.call(STOP_TASK_PROFILE_PATH, { handle: started.handle, outcome: "error" })).text).toBe(completed.text);
    planning = await startNative(plannerFixture.directory, {
      ...plannerStartup, planner: { ...plannerStartup.planner, nonce: randomUUID() },
    }, plannerStartup.planner.settings.listener.max_body_bytes);
    const replacementPlanningPin = pin(planning.child.pid);
    expect(planning.ready.nonce).not.toBe(plannerStartup.planner.nonce);
    const source = plannerFixture.inputs.harvest.sources[0]!;
    const fetched = FetchResponseSchema.parse(JSON.parse((await planning.call(
      `${PLANNER_API_PREFIX}${PLANNER_API_PATHS.fetch}`, { feed_id: source.id, fetch_item_type: "feed" },
    )).text));
    expect(fetched.failure).toBeNull();
    const interrupted = StartTaskProfileResponseSchema.parse(JSON.parse((await machine.call(START_TASK_PROFILE_PATH, {
      ...profileInput, target: replacementPlanningPin,
    })).text));
    if (interrupted.status !== "started") throw new Error("The replacement planner must be profiled by the same machine server");
    await machine.stop();
    const reported = (await machine.errors).trim().split("\n").map(line => JSON.parse(line))
      .filter(value => value.event === "task_profile").map(value => TaskProfileSchema.parse(value.profile));
    expect(reported.find(value => value.spanId === interrupted.spanId)).toMatchObject({
      outcome: "cancelled", end_reason: "service_stopped",
      processes: { worker: { closing: replacementPlanningPin } },
    });
    expect(pin(planning.child.pid)).toEqual(replacementPlanningPin);
    expect(JSON.parse((await planning.call(API_HEALTH_PATH)).text)).toEqual({ identity: planning.ready });
    machine = await startNative(machineFixture.root, { ...machineFixture.startup, nonce: randomUUID() }, probes.max_request_body_bytes);
    const parsed = ParseResponseSchema.parse(JSON.parse((await planning.call(
      `${PLANNER_API_PREFIX}${PLANNER_API_PATHS.parse}`, { links: [operationLink(fetched)] },
    )).text));
    expect(parsed.failure).toBeNull();
    expect(parsed.links).toEqual([operationLink(fetched)]);
    expect(await readFile(file)).toEqual(bytes);
    expect(profile.profile.processes.worker.closing).toMatchObject(planningPin);
  } catch (error) { failed = true; original = error; throw error; }
  finally {
    const stopped = await Promise.allSettled([planning?.stop(), machine?.stop()]);
    const cleaned = await Promise.allSettled([plannerFixture.close(), machineFixture.close()]);
    const errors = [...stopped, ...cleaned].flatMap(value => value.status === "rejected" ? [value.reason] : []);
    if (errors.length) throw new AggregateError(failed ? [original, ...errors] : errors, "Native ownership proof cleanup failed");
  }
}, 60000);
