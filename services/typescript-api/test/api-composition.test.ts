/** Do real machine and recorded-source operations share one port and close all owned resources? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRootContext, PLANNER_API_PREFIX, PlannerSavedResponseSchema, writeTraceContext } from "@idhazh/common-contracts";
import { FingerprintResponseSchema } from "@idhazh/host-fingerprints/response";
import { FINGERPRINT_PATH } from "@idhazh/host-fingerprints/api";
import { loadConfig as loadProbeConfig } from "@idhazh/host-probes/config";
import { SAMPLE_PATH, START_TASK_PROFILE_PATH } from "@idhazh/host-probes/api";
import { fixture as fingerprintFixture } from "../../host-fingerprints/test/fixture";
import { recordedPlan } from "../../feed-ingest-plan/test/plan-recordings";
import { FetchResponseSchema, ParseResponseSchema } from "../../feed-ingest-plan/src/api/document-response.schema";
import { operationLink } from "../../feed-ingest-plan/src/api/operation-context";
import { PlannerReadySchema } from "../../feed-ingest-plan/src/config/planner-startup";
import { HostSampleSchema } from "../../host-probes/src/probe/sample-host";
import { StartTaskProfileResponseSchema } from "../../host-probes/src/api/task-command-schema";
import { parseProcessStat } from "../../host-probes/src/task-profile/process-stat";
import type { TaskProfile } from "../../host-probes/src/task-profile/profile-schema";
import { ApiReadySchema } from "../src/api-startup";
import { createApiApp, serveApiApp } from "../src/create-api-app";
import { HonoServerSettingsSchema, loadHonoSettings } from "../src/load-settings";

const json = (body: unknown, carrier = {}) => ({
  method: "POST", headers: { "content-type": "application/json", ...carrier }, body: JSON.stringify(body),
});

async function listenerSettings() {
  const config = await loadHonoSettings(fileURLToPath(new URL("../../../", import.meta.url)));
  const reservation = Bun.serve({ hostname: config.hostname, port: 0, fetch: () => new Response() });
  const port = reservation.port!;
  await reservation.stop(true);
  return { ...config, port };
}

test("one actual Bun port returns native fingerprint, sample, fetch and parse results", async () => {
  const recorded = await recordedPlan();
  const host = await fingerprintFixture();
  const settings = await listenerSettings();
  const parent = createRootContext();
  const identity = ApiReadySchema.parse({
    event: "typescript_api_ready", nonce: randomUUID(), pid: process.pid, port: settings.port,
    group: "planning", modules: ["planning", "machine"], enabled: true,
  });
  const probe = await loadProbeConfig(new URL("../../../config/host-probes.json", import.meta.url));
  const server = await serveApiApp(settings, {
    identity,
    planner: { inputs: recorded.inputs, runtime: recorded.runtime, identity: PlannerReadySchema.parse({
      event: "planner_ready", nonce: identity.nonce, pid: process.pid, port: settings.port,
      runtime: { ...parent, git_sha: recorded.runtime.git_sha, run_number: "700",
        attempt: 1, captured_at: "2026-10-21T23:59:59Z" },
    }) },
    fingerprint: { config: host.config, settings: host.settings, options: {
      outputRoot: join(host.directory, "state"), inspection: host.inspection,
    } },
    probes: { config: probe, context: { platform: "win32" } },
  });
  const origin = `http://${settings.hostname}:${server.port}`;
  let unrelatedRequests = 0;
  const unrelated = Bun.serve({ hostname: settings.hostname, port: 0, fetch() {
    unrelatedRequests++;
    return Response.json({ code: "UNRELATED_LISTENER" }, { status: 400 });
  } });
  try {
    expect(await (await fetch(`${origin}/health`)).json()).toEqual({ identity });
    const fingerprint = await fetch(`${origin}${FINGERPRINT_PATH}`, json(host.apiInput));
    expect(fingerprint.status).toBe(200);
    const captured = FingerprintResponseSchema.parse(await fingerprint.json());
    expect(captured.status).toBe("written");
    if (captured.status !== "written") throw new Error("The recorded host observation must be persisted");
    expect(captured.row.machine_memory_total_mib).toBe(16383.75);
    expect(captured.files).toHaveLength(1);
    expect(await Bun.file(join(host.directory, "state", captured.files[0]!.path)).exists()).toBe(true);
    const sample = await fetch(`${origin}${SAMPLE_PATH}`);
    expect(sample.status).toBe(200);
    expect(HostSampleSchema.parse(await sample.json()).unavailable.cpu).toBe("unsupported_platform");
    const source = recorded.inputs.harvest.sources[0]!;
    const response = await fetch(`${origin}${PLANNER_API_PREFIX}/fetch`, json({
      feed_id: source.id, fetch_item_type: "feed",
    }, writeTraceContext(parent)));
    expect(response.status).toBe(200);
    const fetched = FetchResponseSchema.parse(await response.json());
    expect(fetched.failure).toBeNull();
    expect(fetched.traceId).toBe(parent.traceId);
    const parsedResponse = await fetch(`${origin}${PLANNER_API_PREFIX}/parse`, json({
      links: [operationLink(fetched)],
    }, writeTraceContext(parent)));
    expect(parsedResponse.status).toBe(200);
    const parsed = ParseResponseSchema.parse(await parsedResponse.json());
    expect(parsed.failure).toBeNull();
    expect(parsed.parsed_count).toBeGreaterThan(0);
    expect(parsed.traceId).toBe(parent.traceId);
    expect(parsed.links).toEqual([operationLink(fetched)]);
    expect(fetched).not.toHaveProperty("body");
    expect(parsed).not.toHaveProperty("body");
    expect(recorded.transport.requests.map(request => request.url.href)).toEqual([source.url]);
    const planning = await fetch(`${origin}${PLANNER_API_PREFIX}/plan`, json({}, {
      host: `${settings.hostname}:${unrelated.port}`,
    }));
    const planned = PlannerSavedResponseSchema.parse(await planning.json());
    expect(planned).toHaveProperty("planning_complete");
    expect(unrelatedRequests).toBe(0);
  } finally {
    await server.stop();
    await server.stop();
    await unrelated.stop(true);
    const replacement = Bun.serve({ hostname: settings.hostname, port: settings.port, fetch: () => new Response() });
    await replacement.stop(true);
    await Promise.all([recorded.close(), host.cleanup()]);
  }
});

test("machine-only shutdown waits for its real profile worker and asynchronous report", async () => {
  const host = await fingerprintFixture();
  const settings = await listenerSettings();
  const config = await loadProbeConfig(new URL("../../../config/host-probes.json", import.meta.url));
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
  const server = await serveApiApp(settings, {
    identity,
    fingerprint: { config: host.config, settings: host.settings, options: { outputRoot: join(host.directory, "state") } },
    probes: { config, context: { platform: "linux", procRoot }, report: async profile => {
      reports.push(profile); reporting(); await releaseReport;
    } },
  });
  const origin = `http://${settings.hostname}:${server.port}`;
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
    expect(started.status).toBe("started");
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
});

test("readiness cannot advertise missing native modules or non-loopback configuration", async () => {
  const settings = await listenerSettings();
  expect(() => createApiApp({ identity: {
    event: "typescript_api_ready", nonce: randomUUID(), pid: process.pid, port: settings.port,
    group: "machine", modules: ["machine"], enabled: true,
  } })).toThrow("actual enabled API modules");
  expect(HonoServerSettingsSchema.safeParse({ ...settings, hostname: "0.0.0.0" }).success).toBe(false);
  expect(HonoServerSettingsSchema.safeParse({ ...settings, port: 0 }).success).toBe(false);
});
