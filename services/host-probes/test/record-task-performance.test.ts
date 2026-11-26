/** Does recording preserve one verified file per completed task and attempt? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { lstat, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { FINGERPRINT_PATH } from "@idhazh/host-fingerprints/api";
import { FingerprintResponseSchema } from "@idhazh/host-fingerprints/response";
import { createApiApp, serveApiApp } from "@idhazh/serve-pipeline-apis/app";
import { apiOrigin, loadHonoSettings } from "@idhazh/serve-pipeline-apis/settings";
import { fixture as fingerprintFixture } from "../../host-fingerprints/test/fixture";
import { createMachineApp } from "../src/api/create-machine-app";
import type { ProbeEvent } from "../src/api/create-probe-event";
import {
  createSampleHandler, RecordTaskPerformanceResponseSchema, serveSamples,
  SAMPLE_PATH, START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH,
} from "../src/api/server";
import { StartTaskProfileResponseSchema, StopTaskProfileResponseSchema } from "../src/api/task-command-schema";
import { loadConfig } from "../src/config";
import { parseProcessStat, readProcessIdentity } from "../src/task-profile/process-stat";
import { summarizeClosedTaskProfile } from "../src/task-profile/summarize-closed-profile";

const DAY = "2026-12-31";
const PATH = "/api/2026-11-26/record-task-performance";
const root = fileURLToPath(new URL("../../../", import.meta.url));
const execution = {
  run_id: `${DAY}-8`, attempt: 2, pipeline_name: "digest", shard: 1, git_sha: "a".repeat(40),
};
const work = {
  date: DAY,
  writer: { ...execution, task_name: "work" },
  measurement: { task_kind: "workflow-task", outcome: "success", elapsed_ms: 10.5, model_calls: 0 },
};
const settings = {
  observability: { host_telemetry_enabled: true, memory_profiling_enabled: true },
  ledger: { format: "parquet", compression_raw: "snappy", compression_compact: "zstd" },
} as const;

const options = (outputRoot: string) => ({
  outputRoot, execution: { ...execution, accounting_days: [DAY] }, settings,
});
const json = (body: unknown, headers: HeadersInit = {}): RequestInit => ({
  method: "POST", headers: { "Content-Type": "application/json", ...headers }, body: JSON.stringify(body),
});
const command = (body: unknown, headers?: HeadersInit) => new Request(`http://localhost${PATH}`, json(body, headers));

async function freePort(hostname: string) {
  const reservation = Bun.serve({ hostname, port: 0, fetch: () => new Response() });
  const port = reservation.port!;
  await reservation.stop(true);
  return port;
}

async function written(response: Response) {
  expect(response.status).toBe(200);
  const result = RecordTaskPerformanceResponseSchema.parse(await response.json());
  if (result.status !== "written") throw new Error("Expected one completed Parquet receipt");
  return result;
}

test("the native probe refuses foreign commands and fails closed on damaged evidence", async () => {
  const outputRoot = await mkdtemp(join(tmpdir(), "idhazh-task-recording-"));
  const config = await loadConfig();
  const events: ProbeEvent[] = [];
  const diagnostics = { writeEvent: (event: ProbeEvent) => { events.push(event); } };
  const unconfigured = createSampleHandler(config, { platform: "unsupported" }, undefined, diagnostics);
  const handler = createSampleHandler(config, { platform: "unsupported" }, undefined, diagnostics, options(outputRoot));
  try {
    expect((await unconfigured(command(work))).status).toBe(403);
    const refused = [
      command({ ...work, writer: { ...work.writer, producer: "other", job: null } }),
      command({ ...work, outputRoot: "PRIVATE_DESTINATION" }),
      command({ ...work, measurement: { ...work.measurement, run_id: execution.run_id, samples: [] } }),
      command({ ...work, measurement: { ...work.measurement, server_prompt_seconds: 4 } }),
      command({ ...work, measurement: { ...work.measurement, elapsed_ms: "10.5" } }),
      new Request(`http://localhost${PATH}`, {
        ...json(work), body: JSON.stringify(work).replace('"elapsed_ms":10.5', '"elapsed_ms":1e309'),
      }),
      command(work, { Origin: "http://localhost" }),
    ];
    for (const request of refused) expect((await handler(request)).status).toBe(400);
    for (const change of [
      { run_id: `${DAY}-9` }, { attempt: 1 }, { pipeline_name: "another-pipeline" },
      { shard: 0 }, { git_sha: "b".repeat(40) },
    ]) expect((await handler(command({ ...work, writer: { ...work.writer, ...change } }))).status).toBe(403);
    expect((await handler(command({ ...work, date: "2027-01-01" }))).status).toBe(403);
    expect((await handler(command({ ...work, extra: "x".repeat(config.max_request_body_bytes) }))).status).toBe(413);
    await expect(lstat(join(outputRoot, "raw"))).rejects.toMatchObject({ code: "ENOENT" });
    const recorded = await written(await handler(command(work)));
    expect(recorded.row).toMatchObject(work.measurement);
    expect(events.at(-1)?.data).toEqual({ operation: "record-task-performance", outcome: "written" });
    const path = join(outputRoot, recorded.files[0].path);
    await writeFile(path, "PRIVATE_INVALID_PARQUET");
    const failed = await handler(command(work));
    expect(failed.status).toBe(500);
    expect(await failed.json()).toEqual({ error: "Task performance persistence failed" });
    expect(await readFile(path, "utf8")).toBe("PRIVATE_INVALID_PARQUET");
    expect(events.at(-1)).toMatchObject({ type: "host_probe_failed", data: { code: "HOST_PROBE_FAILED" } });
    expect(JSON.stringify(events)).not.toMatch(/PRIVATE_|host_unit_id|elapsed_ms|\.parquet/);
  } finally {
    await Promise.all([unconfigured.close(), handler.close()]);
    await rm(outputRoot, { recursive: true, force: true });
  }
});

test("recording reports master off and paused families; memory off does not disable measured tasks", async () => {
  const outputRoot = await mkdtemp(join(tmpdir(), "idhazh-task-recording-controls-"));
  const config = await loadConfig();
  const events: ProbeEvent[] = [];
  const diagnostics = { writeEvent: (event: ProbeEvent) => { events.push(event); } };
  const launch = options(outputRoot);
  const registryPath = join(outputRoot, "paused-registry.json");
  await Bun.write(registryPath, JSON.stringify({ families: [{
    name: "task-performance", lifecycle_status: "paused",
    ledgers: [{ name: "task-performance", grain: "raw-and-compact", prefix: ["task-performance"] }],
  }] }));
  const disabled = createSampleHandler(config, {}, undefined, diagnostics, {
    ...launch, settings: { ...settings, observability: { ...settings.observability, host_telemetry_enabled: false } },
  });
  const paused = createSampleHandler(config, {}, undefined, diagnostics, { ...launch, registryPath });
  const memoryOff = createSampleHandler(config, {}, undefined, diagnostics, {
    ...launch, settings: { ...settings, observability: { ...settings.observability, memory_profiling_enabled: false } },
  });
  try {
    expect(await (await disabled(command(work))).json()).toEqual({
      status: "disabled", reason: "configured_off", row: null, files: [],
    });
    expect(await (await paused(command(work))).json()).toEqual({
      status: "skipped", reason: "ledger_not_active", row: null, files: [],
    });
    expect(events.map(event => event.data)).toEqual([
      { operation: "record-task-performance", outcome: "disabled" },
      { operation: "record-task-performance", outcome: "skipped" },
    ]);
    await expect(lstat(join(outputRoot, "raw"))).rejects.toMatchObject({ code: "ENOENT" });
    expect((await memoryOff(command({ ...work, measurement: { ...work.measurement, worker_rss_peak_kib: 1 } }))).status)
      .toBe(400);
    expect((await written(await memoryOff(command(work)))).row.worker_rss_peak_kib).toBeNull();
  } finally {
    await Promise.all([disabled.close(), paused.close(), memoryOff.close()]);
    await rm(outputRoot, { recursive: true, force: true });
  }
});

test("a listener restart returns the original receipt, refuses unequal evidence and preserves both tasks", async () => {
  const host = await fingerprintFixture();
  const outputRoot = join(host.directory, "state");
  const config = await loadConfig();
  const launch = options(outputRoot);
  const standalone = serveSamples({ ...config, listen_port: await freePort(config.listen_host) }, { writeEvent() {} }, launch);
  const post = (body: unknown) => fetch(new URL(PATH, standalone.url), json(body));
  const serving = {
    ...work, writer: { ...work.writer, task_name: "serve-summarizer" },
    measurement: { task_kind: "model-serving", outcome: "success", subject_id: "summary", model_load_ms: 125.5 },
  };
  try {
    const sample = await fetch(new URL(SAMPLE_PATH, standalone.url));
    expect(sample.status).toBe(200);
    await sample.json();
    const start = (pin: { pid: number; start_ticks: string }) => fetch(new URL(START_TASK_PROFILE_PATH, standalone.url), json({
      identity: { pipeline_name: execution.pipeline_name, task_name: "test-profile", run_id: execution.run_id },
      target: pin,
    }));
    const pin = readProcessIdentity(process.pid, config.max_proc_bytes, {});
    if (pin.reason === null) {
      const startReply = StartTaskProfileResponseSchema.parse(await (await start({
        pid: pin.value.pid, start_ticks: pin.value.start_ticks,
      })).json());
      if (startReply.status !== "started") throw new Error("The instrumented standalone listener did not start a profile");
      const stopReply = StopTaskProfileResponseSchema.parse(await (await fetch(new URL(STOP_TASK_PROFILE_PATH, standalone.url),
        json({ handle: startReply.handle, outcome: "success" }))).json());
      expect(stopReply.status).toBe("stopped");
    } else {
      if (process.platform === "linux") throw new Error("The live Linux worker must have a verified process pin");
      expect((await start({ pid: process.pid, start_ticks: "1" })).status).toBe(409);
      expect((await fetch(new URL(STOP_TASK_PROFILE_PATH, standalone.url),
        json({ handle: randomUUID(), outcome: "success" }))).status).toBe(404);
    }

    const [first, concurrent, sibling] = await Promise.all([post(work).then(written), post(work).then(written), post(serving).then(written)]);
    expect(concurrent).toEqual(first);
    expect(sibling.files[0].unit_id).not.toBe(first.files[0].unit_id);
    const firstPath = join(outputRoot, first.files[0].path);
    const originalBytes = await readFile(firstPath);
    const discarded = await post(work);
    expect(discarded.status).toBe(200);
    await discarded.body?.cancel();
    await standalone.stop();

    const procRoot = join(host.directory, "proc");
    const fixture = await Bun.file(new URL("../../../tests/fixtures/host-probes/process-inputs.json", import.meta.url)).json();
    const stat = fixture.stat.replace("4242 ", `${process.pid} `);
    const processDir = join(procRoot, String(process.pid));
    await mkdir(processDir, { recursive: true });
    await Promise.all([
      Bun.write(join(processDir, "stat"), stat),
      Bun.write(join(processDir, "status"), fixture.status),
      Bun.write(join(procRoot, "meminfo"), Bun.file(new URL("../../../tests/fixtures/host-probes/meminfo.txt", import.meta.url))),
    ]);
    const recordedPin = parseProcessStat(process.pid, stat);
    if (recordedPin.reason !== null) throw new Error("Invalid recorded process pin");
    const listener = await loadHonoSettings(root, "machine");
    listener.port = await freePort(listener.hostname);
    const composed = await serveApiApp(listener, createApiApp({
      identity: { event: "typescript_api_ready", nonce: randomUUID(), pid: process.pid,
        port: listener.port, group: "machine", modules: ["machine"], enabled: true },
      create: () => createMachineApp({
        fingerprint: { config: host.config, settings: host.settings, options: {
          outputRoot, registryPath: join(root, "config", "ledgers.json"), inspection: host.inspection,
        } },
        probes: { config, recording: launch, context: { platform: "linux", procRoot }, report() {},
          diagnostics: { writeEvent() {} } },
      }),
    }));
    const origin = apiOrigin(listener);
    const record = (body: unknown) => fetch(`${origin}${PATH}`, json(body));
    try {
      expect((await fetch(`${origin}${SAMPLE_PATH}`)).status).toBe(200);
      const started = StartTaskProfileResponseSchema.parse(await (await fetch(`${origin}${START_TASK_PROFILE_PATH}`, json({
        identity: { pipeline_name: execution.pipeline_name, task_name: "profiled-stage", run_id: execution.run_id },
        target: { pid: recordedPin.value.pid, start_ticks: recordedPin.value.start_ticks },
      }))).json());
      if (started.status !== "started") throw new Error("The instrumented composed listener did not start a profile");
      const stopped = StopTaskProfileResponseSchema.parse(await (await fetch(`${origin}${STOP_TASK_PROFILE_PATH}`,
        json({ handle: started.handle, outcome: "cancelled" }))).json());
      if (stopped.status !== "stopped") throw new Error("The composed listener did not return a closed profile");
      expect(stopped.profile.config).toMatchObject({ enabled: true, memory_enabled: true, machine_memory_enabled: true });
      const replay = await written(await record({ ...work, measurement: { ...work.measurement, subject_id: null } }));
      expect(replay).toEqual(first);
      expect((await record({ ...work, measurement: { ...work.measurement, elapsed_ms: 10.75 } })).status).toBe(409);
      expect(await readFile(firstPath)).toEqual(originalBytes);
      expect(await written(await record(serving))).toEqual(sibling);

      const fingerprint = FingerprintResponseSchema.parse(await (await fetch(`${origin}${FINGERPRINT_PATH}`, json({
        date: DAY, writer: { ...execution, job: null, task_name: "capture-runner", producer: "telemetry.silicon" },
      }))).json());
      if (fingerprint.status !== "written" || !fingerprint.files[0]?.unit_id) throw new Error("Expected a verified host capture");
      const profile = summarizeClosedTaskProfile(stopped.profile);
      const profiled = { ...work, writer: { ...work.writer, task_name: stopped.profile.identity.task_name },
        measurement: { task_kind: "workflow-task", ...profile, host_unit_id: fingerprint.files[0].unit_id } };
      expect((await record({ ...profiled, measurement: { ...profiled.measurement, host_unit_id: first.files[0].unit_id } })).status)
        .toBe(400);
      const closed = await written(await record(profiled));
      expect(closed.row).toMatchObject(profiled.measurement);
      expect(closed.row).not.toHaveProperty("samples");
      expect(closed.row.machine_memory_available_min_kib).toBe(8192000);

      await composed.stop(true);
      const laterExecution = { ...launch.execution, attempt: execution.attempt + 1 };
      const later = createSampleHandler(config, {}, undefined, { writeEvent() {} }, { ...launch, execution: laterExecution });
      let higherAttempt;
      try {
        const writer = { ...work.writer, attempt: laterExecution.attempt };
        expect((await later(command({ ...work, writer, measurement: {
          ...work.measurement, host_unit_id: fingerprint.files[0].unit_id,
        } }))).status).toBe(400);
        higherAttempt = await written(await later(command({ ...work, writer, measurement: {
          ...work.measurement, elapsed_ms: 20.25,
        } })));
        expect(higherAttempt.files[0].unit_id).toBe(first.files[0].unit_id);
        expect(higherAttempt.files[0].file_id).not.toBe(first.files[0].file_id);
      } finally { await later.close(); }
      const python = Bun.spawnSync([process.env.IDHAZH_PYTHON ?? "python",
        fileURLToPath(new URL("./read-task-performance.py", import.meta.url)), outputRoot], {
        cwd: root, env: { ...process.env, PYTHONPATH: join(root, "backend") }, timeout: 15000,
        stdin: new TextEncoder().encode(JSON.stringify([first, sibling, closed, higherAttempt])),
      });
      expect(python.exitCode, python.stderr.toString()).toBe(0);
    } finally { await composed.stop(true); }
  } finally {
    await standalone.stop(true);
    await host.cleanup();
  }
}, 30000);
