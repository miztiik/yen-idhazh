/** Do real machine operations and profile shutdown work without a feed application? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRootContext, PLANNER_API_PREFIX, writeTraceContext } from "@idhazh/common-contracts";
import { FINGERPRINT_PATH } from "@idhazh/host-fingerprints/api";
import { FingerprintResponseSchema } from "@idhazh/host-fingerprints/response";
import { createApiApp, serveApiApp } from "@idhazh/serve-pipeline-apis/app";
import { API_HEALTH_PATH, ApiReadySchema } from "@idhazh/serve-pipeline-apis/startup";
import { loadHonoSettings, apiOrigin } from "@idhazh/serve-pipeline-apis/settings";
import { fixture as fingerprintFixture } from "../../host-fingerprints/test/fixture";
import { createMachineApp } from "../src/api/create-machine-app";
import { superviseMachineApiTask } from "../src/api/supervise-machine-api-task";
import { MachineServerEvidenceSchema, readMachineServerEvidence } from "../src/api/create-machine-server-evidence";
import { START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH } from "../src/api/server";
import { StartTaskProfileResponseSchema, StopTaskProfileResponseSchema } from "../src/api/task-command-schema";
import { loadConfig } from "../src/config";
import { parseProcessStat, readProcessIdentity } from "../src/task-profile/process-stat";
import { TaskProfileSchema } from "../src/task-profile/profile-schema";
import type { TaskProfile } from "../src/task-profile/profile-schema";
import { recordedMachineTask } from "./machine-api-recordings";
import { MachineApiStartupSchema } from "../src/api/read-machine-api-startup";

const json = (body: unknown, carrier = {}) => ({
  method: "POST", headers: { "content-type": "application/json", ...carrier }, body: JSON.stringify(body),
});

test("machine startup requires shared supervision without a legacy feed or top-level fallback", async () => {
  const server = await loadHonoSettings(fileURLToPath(new URL("../../../", import.meta.url)));
  const startup = MachineApiStartupSchema.parse({
    group: "machine", nonce: randomUUID(), state_root: "state", directory: "logs", server,
    run: { run_id: "700", attempt: 3, started_at: "2026-11-04T00:00:00Z", context: createRootContext() },
  });
  const { supervision, ...listener } = server;
  const missing = MachineApiStartupSchema.safeParse({ ...startup, server: listener });
  expect(missing.success).toBe(false);
  if (missing.success) throw new Error("Missing shared supervision must fail before child startup");
  expect(missing.error.issues.map(issue => issue.path)).toContainEqual(["server", "supervision"]);
  expect(MachineApiStartupSchema.safeParse({ ...startup, supervision }).success).toBe(false);
});

test("machine-only shutdown waits for its real profile worker and asynchronous report", async () => {
  const host = await fingerprintFixture();
  const settings = await loadHonoSettings(fileURLToPath(new URL("../../../", import.meta.url)));
  const reservation = Bun.serve({ hostname: settings.hostname, port: 0, fetch: () => new Response() });
  settings.port = reservation.port!;
  await reservation.stop(true);
  const config = await loadConfig(new URL("../../../config/host-probes.json", import.meta.url));
  config.task_profile.enabled = true;
  const procRoot = join(host.directory, "proc");
  await mkdir(join(procRoot, String(process.pid)), { recursive: true });
  const processInput = await Bun.file(new URL("../../../tests/fixtures/host-probes/process-inputs.json", import.meta.url)).json();
  const stat = processInput.stat.replace("4242 ", `${process.pid} `);
  await writeFile(join(procRoot, String(process.pid), "stat"), stat);
  const pin = parseProcessStat(process.pid, stat);
  if (pin.reason !== null) throw new Error("The named process recording must contain its PID pin");
  let release!: () => void;
  let reporting!: () => void;
  const releaseReport = new Promise<void>(resolve => { release = resolve; });
  const reportStarted = new Promise<void>(resolve => { reporting = resolve; });
  const reports: TaskProfile[] = [];
  const identity = ApiReadySchema.parse({
    event: "typescript_api_ready", nonce: randomUUID(), pid: process.pid, port: settings.port,
    group: "machine", modules: ["machine"], enabled: true,
  });
  const server = await serveApiApp(settings, createApiApp({
    identity, create: () => createMachineApp({
      fingerprint: { config: host.config, settings: host.settings, options: { outputRoot: join(host.directory, "state") } },
      probes: { config, context: { platform: "linux", procRoot }, report: async profile => {
        reports.push(profile); reporting(); await releaseReport;
      } },
    }),
  }));
  const origin = apiOrigin(settings);
  let closing: Promise<void> | undefined;
  try {
    expect((await fetch(`${origin}${PLANNER_API_PREFIX}/plan`, json({}))).status).toBe(404);
    const parent = createRootContext();
    const response = await fetch(`${origin}${START_TASK_PROFILE_PATH}`, json({
      identity: { pipeline_name: "recorded-work", task_name: "composed-profile", run_id: "recorded-run" },
      target: { pid: process.pid, start_ticks: pin.value.start_ticks },
    }, writeTraceContext(parent)));
    expect(response.status).toBe(200);
    const started = StartTaskProfileResponseSchema.parse(await response.json());
    if (started.status !== "started") throw new Error("The configured profile must start its real collector");
    let stopped = false;
    closing = server.stop();
    void closing.then(() => { stopped = true; });
    await reportStarted;
    expect(stopped).toBe(false);
    expect(reports).toHaveLength(1);
    expect(reports[0]!.traceId).toBe(started.traceId);
    expect(reports[0]!.spanId).toBe(started.spanId);
    release();
    await closing;
    expect(stopped).toBe(true);
  } finally {
    release();
    await (closing ?? server.stop());
    await host.cleanup();
  }
}, 30000);

test.skipIf(process.platform !== "linux")("the real machine child writes fingerprints, stops profiles and retains shutdown-only reports", async () => {
  const fixture = await recordedMachineTask();
  try {
    const probes = await loadConfig(join(fixture.root, "config", "host-probes.json"));
    const pin = readProcessIdentity(process.pid, probes.max_proc_bytes, {});
    if (pin.reason !== null) throw new Error("The actual Linux caller must have a verified process pin");
    const result = await superviseMachineApiTask({
      root: fixture.root, startup: fixture.startup,
      request: async (origin, signal) => {
        const health = await fetch(new URL(API_HEALTH_PATH, origin), { signal });
        const ready = ApiReadySchema.parse((await health.json()).identity);
        expect(ready).toMatchObject({
          group: "machine", modules: ["machine"], nonce: fixture.startup.nonce, port: fixture.startup.server.port,
        });
        expect(ready.pid).not.toBe(process.pid);
        expect((await fetch(`${origin}${PLANNER_API_PREFIX}/plan`, { ...json({}), signal })).status).toBe(404);
        const fingerprint = await fetch(origin + FINGERPRINT_PATH, { ...json({
          date: "2026-11-04", writer: {
            run_id: "2026-11-04-700", attempt: 3, job: null, pipeline_name: "recorded-work",
            task_name: "independent-machine", shard: 0, producer: "telemetry.silicon", git_sha: "a".repeat(40),
          },
        }), signal });
        expect(fingerprint.status).toBe(200);
        const written = FingerprintResponseSchema.parse(await fingerprint.json());
        if (written.status !== "written") throw new Error("The real machine child must write its fingerprint");
        expect(written.files).toHaveLength(1);
        expect(await Bun.file(join(fixture.root, "state", written.files[0]!.path)).exists()).toBe(true);
        const start = async () => {
          const response = await fetch(origin + START_TASK_PROFILE_PATH, { ...json({
            identity: { pipeline_name: "recorded-work", task_name: "independent-machine", run_id: "recorded-run" },
            target: { pid: process.pid, start_ticks: pin.value.start_ticks },
          }, writeTraceContext(fixture.startup.run.context)), signal });
          expect(response.status).toBe(200);
          const started = StartTaskProfileResponseSchema.parse(await response.json());
          if (started.status !== "started") throw new Error("The real Linux collector must start");
          return started;
        };
        const first = await start();
        const response = await fetch(origin + STOP_TASK_PROFILE_PATH, { ...json({ handle: first.handle, outcome: "success" }), signal });
        expect(response.status).toBe(200);
        const stopped = StopTaskProfileResponseSchema.parse(await response.json());
        if (stopped.status !== "stopped") throw new Error("Explicit stop must return the actual profile");
        expect(stopped.profile).toMatchObject({ traceId: first.traceId, spanId: first.spanId, outcome: "success", end_reason: "explicit_stop" });
        const interrupted = await start();
        return { pid: ready.pid, stopped: stopped.profile, interrupted };
      },
    });
    expect(() => process.kill(result.pid, 0)).toThrow();
    const [evidence] = await readMachineServerEvidence(fixture.evidence, { run_id: "700", attempt: 3 });
    if (evidence === undefined) throw new Error("The machine child must retain current-task evidence");
    expect(evidence).toMatchObject({ startup: "ready", shutdown: "stopped", exit_code: 0, error_code: null, cleanup_error_code: null });
    expect(evidence.reported_profiles).toHaveLength(2);
    expect(evidence.reported_profiles).toContainEqual(result.stopped);
    const profile = TaskProfileSchema.parse(evidence.reported_profiles.find(value => value.spanId === result.interrupted.spanId));
    expect(profile).toMatchObject({
      traceId: result.interrupted.traceId, outcome: "cancelled", end_reason: "service_stopped",
      parentSpanId: fixture.startup.run.context.spanId,
    });
    expect(profile.sample_count).toBeGreaterThanOrEqual(2);
    expect(profile.samples.at(-1)?.phase).toBe("closing");
    expect(MachineServerEvidenceSchema.safeParse({
      ...evidence, reported_profiles: [{ ...profile, sample_count: profile.sample_count + 1 }],
    }).success).toBe(false);
    const replacement = Bun.serve({ hostname: fixture.startup.server.hostname, port: fixture.startup.server.port, fetch: () => new Response() });
    await replacement.stop(true);
    const logs = await Bun.file(join(fixture.evidence, evidence.log_filename)).text();
    expect(logs).not.toContain('"samples"');
    expect(logs).not.toContain("independent-machine");
  } finally { await fixture.close(); }
}, 30000);
