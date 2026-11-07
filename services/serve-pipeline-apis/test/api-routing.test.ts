/** Do declared native paths dispatch their own payloads through shared hosting without aliases? */
import { expect, test } from "bun:test";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createApiApp } from "../src/create-api-app";
import { API_HEALTH_PATH, ApiReadySchema } from "../src/api-startup";
import { loadHonoSettings } from "../src/load-settings";
import { createMachineApp } from "../../host-probes/src/api/create-machine-app";
import { createFingerprintHandler, FINGERPRINT_PATH, HEALTH_PATH } from "../../host-fingerprints/src/api/server";
import { fixture } from "../../host-fingerprints/test/fixture";
import { loadConfig } from "../../host-probes/src/config";
import {
  CACHE_LATENCY_PATH, createSampleHandler, SAMPLE_PATH, START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH,
} from "../../host-probes/src/api/server";
import { HostSampleSchema } from "../../host-probes/src/probe/sample-host";
import { DELIVERY_API_PATHS, PLANNER_API_PATHS, PLANNER_API_PREFIX, createRootContext } from "@idhazh/common-contracts";
import { createFeedApiApp } from "../../feed-ingest-plan/scripts/create-feed-api-app";
import { recordedPlan } from "../../feed-ingest-plan/test/plan-recordings";
import { PlannerReadySchema } from "../../feed-ingest-plan/src/config/planner-startup";
import { SafePersistHttpReadySchema } from "../../feed-ingest-plan/scripts/feed-ingest-plan-delivery-result";

test("exported host and shared paths use the fixed HTTP protocol date", () => {
  expect({
    FINGERPRINT_PATH, HEALTH_PATH, SAMPLE_PATH, START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH,
    CACHE_LATENCY_PATH, API_HEALTH_PATH,
  }).toEqual({
    FINGERPRINT_PATH: "/api/2026-11-05/capture-host-fingerprint",
    HEALTH_PATH: "/api/2026-11-05/get-host-fingerprint-health",
    SAMPLE_PATH: "/api/2026-11-05/sample-host",
    START_TASK_PROFILE_PATH: "/api/2026-11-05/start-task-profile",
    STOP_TASK_PROFILE_PATH: "/api/2026-11-05/stop-task-profile",
    CACHE_LATENCY_PATH: "/api/2026-11-05/measure-cache-latency",
    API_HEALTH_PATH: "/api/2026-11-05/get-api-health",
  });
});

test("shared planning and delivery keep distinct native health and refuse every retired feed route", async () => {
  const recorded = await recordedPlan();
  const host = await fixture();
  const config = await loadConfig();
  host.settings.observability.host_fingerprint = false;
  const runtime = { ...createRootContext(), git_sha: recorded.runtime.git_sha, run_number: "700",
    attempt: 1, captured_at: "2026-10-21T23:59:59Z" };
  const identity = ApiReadySchema.parse({
    event: "typescript_api_ready", nonce: crypto.randomUUID(), pid: process.pid, port: recorded.inputs.settings.listener.port,
    group: "planning", modules: ["planning", "machine"], enabled: true,
  });
  const plannerIdentity = PlannerReadySchema.parse({
    event: "planner_ready", nonce: identity.nonce, pid: identity.pid, port: identity.port, runtime,
  });
  const deliveryIdentity = SafePersistHttpReadySchema.parse({
    event: "safe_persist_ready", nonce: identity.nonce, pid: identity.pid, port: identity.port,
  });
  const planning = createFeedApiApp({
    identity, planner: { inputs: recorded.inputs, runtime: recorded.runtime, identity: plannerIdentity },
    machine: {
      fingerprint: { config: host.config, settings: host.settings, options: { outputRoot: host.directory } },
      probes: { config, context: { platform: "unsupported" } },
    },
  });
  const delivery = createFeedApiApp({
    identity: ApiReadySchema.parse({ ...identity, group: "delivery", modules: ["delivery"] }),
    delivery: { root: recorded.directory, directory: recorded.directory, gitSha: recorded.runtime.git_sha,
      identity: deliveryIdentity, maxBodyBytes: recorded.inputs.settings.listener.max_body_bytes,
      signal: new AbortController().signal },
  });
  const request = (suffix: string, method: string) => new Request(`http://127.0.0.1${PLANNER_API_PREFIX}${suffix}`, {
    method, ...(method === "GET" ? {} : { body: "{}" }),
  });
  try {
    const plannerHealth = await planning.fetch(request(PLANNER_API_PATHS.health, "GET"));
    expect(plannerHealth.status).toBe(200);
    expect(await plannerHealth.json()).toEqual({ status: "available", planner_enabled: true, identity: plannerIdentity });
    const deliveryHealth = await delivery.fetch(request(DELIVERY_API_PATHS.health, "GET"));
    expect(deliveryHealth.status).toBe(200);
    expect(await deliveryHealth.json()).toEqual({ identity: deliveryIdentity });
    expect((await planning.fetch(request(DELIVERY_API_PATHS.health, "GET"))).status).toBe(404);
    expect((await delivery.fetch(request(PLANNER_API_PATHS.health, "GET"))).status).toBe(404);
    for (const suffix of [
      "/health", "/plan", "/fetch", "/parse", "/collections", "/collections/exists", "/collections/complete",
      "/collections/cancel", "/collections/finalize", "/collections/release", "/feed-health-state", "/safe-persist-data",
    ]) {
      for (const app of [planning, delivery]) for (const method of ["GET", "POST"]) {
        const response = await app.fetch(request(suffix, method));
        expect(response.status, `${method} ${suffix}`).toBe(404);
        expect(response.headers.get("Location")).toBeNull();
      }
    }
    expect(recorded.transport.requests).toEqual([]);
  } finally {
    await Promise.all([planning.close(), delivery.close()]);
    await recorded.close();
    await host.cleanup();
  }
});

test("shared dispatch preserves native disabled payloads, uncached identity and method refusals", async () => {
  const host = await fixture();
  const config = await loadConfig();
  const server = await loadHonoSettings(fileURLToPath(new URL("../../../", import.meta.url)));
  host.settings.observability.host_fingerprint = false;
  config.task_profile.enabled = false;
  config.cache_probe.counters.enabled = false;
  config.cache_probe.latency.enabled = false;
  const context = { platform: "unsupported" };
  const options = { outputRoot: join(host.directory, "never-written") };
  const identity = ApiReadySchema.parse({
    event: "typescript_api_ready", nonce: crypto.randomUUID(), pid: process.pid, port: server.port,
    group: "machine", modules: ["machine"], enabled: true,
  });
  const fingerprint = createFingerprintHandler(host.config, host.settings, options);
  const probe = createSampleHandler(config, context);
  const app = createApiApp({
    identity, create: () => createMachineApp({
      fingerprint: { config: host.config, settings: host.settings, options },
      probes: { config, context },
    }),
  });
  const request = (path: string, method: string, body?: unknown) => new Request(`http://127.0.0.1${path}`, {
    method, ...(body === undefined ? {} : {
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }),
  });
  try {
    const commands = [
      { path: FINGERPRINT_PATH, method: "POST", body: host.apiInput, native: fingerprint },
      { path: HEALTH_PATH, method: "GET", body: undefined, native: fingerprint },
      { path: START_TASK_PROFILE_PATH, method: "POST", body: {
        identity: { pipeline_name: "recorded-work", task_name: "route-contract", run_id: "recorded-run" },
        target: { pid: 4242, start_ticks: "12345" },
      }, native: probe },
      { path: STOP_TASK_PROFILE_PATH, method: "POST", body: {
        handle: "c80a7d40-7821-4454-b118-669eb8f5f290", outcome: "success",
      }, native: probe },
      { path: CACHE_LATENCY_PATH, method: "POST", body: {}, native: probe },
    ];
    for (const command of commands) {
      const native = await command.native(request(command.path, command.method, command.body));
      const shared = await app.fetch(request(command.path, command.method, command.body));
      expect(native.status).toBe(200);
      expect(shared.status).toBe(native.status);
      expect(shared.headers.get("Cache-Control")).toBe("no-store");
      expect(await shared.json()).toEqual(await native.json());
    }
    for (const [path, method] of [
      [FINGERPRINT_PATH, "POST"], [HEALTH_PATH, "GET"], [SAMPLE_PATH, "GET"],
      [START_TASK_PROFILE_PATH, "POST"], [STOP_TASK_PROFILE_PATH, "POST"], [CACHE_LATENCY_PATH, "POST"],
    ] as const) {
      const response = await app.fetch(request(path, method === "GET" ? "POST" : "GET"));
      expect(response.status).toBe(405);
      expect(response.headers.get("Allow")).toBe(method);
      expect(await response.json()).toEqual({ error: "Method not allowed" });
    }
    const native = HostSampleSchema.parse(await (await probe(request(SAMPLE_PATH, "GET"))).json());
    const shared = HostSampleSchema.parse(await (await app.fetch(request(SAMPLE_PATH, "GET"))).json());
    const { sampled_at: nativeAt, interval_ms: nativeInterval, ...nativeReadings } = native;
    const { sampled_at: sharedAt, interval_ms: sharedInterval, ...sharedReadings } = shared;
    expect(sharedReadings).toEqual(nativeReadings);
    expect(shared.unavailable.cpu).toBe("unsupported_platform");
    expect(nativeAt.endsWith("Z") && sharedAt.endsWith("Z")).toBe(true);
    expect(nativeInterval >= 0 && sharedInterval >= 0).toBe(true);
    const health = await app.fetch(request(API_HEALTH_PATH, "GET"));
    expect(health.status).toBe(200);
    expect(health.headers.get("Cache-Control")).toBe("no-store");
    expect(await health.json()).toEqual({ identity });
    const wrongHealth = await app.fetch(request(API_HEALTH_PATH, "POST"));
    expect(wrongHealth.status).toBe(404);
    expect(await wrongHealth.json()).toEqual({ code: "NOT_FOUND" });
    for (const path of [
      "/health", "/api/2026-10-20/fingerprint", "/api/2026-10-20/health", "/api/2026-10-20/sample",
      "/api/2026-10-24/start-task-profile", "/api/2026-10-24/stop-task-profile", "/api/2026-10-24/cache/latency",
      "/api/2026-11-04/get-api-health", "/api/2026-11-06/capture-host-fingerprint",
      ...[FINGERPRINT_PATH, HEALTH_PATH, SAMPLE_PATH, START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH,
        CACHE_LATENCY_PATH, API_HEALTH_PATH].map(path => `${path}/`),
    ]) {
      for (const method of ["GET", "POST"]) {
        const response = await app.fetch(request(path, method));
        expect(response.status, `${method} ${path}`).toBe(404);
        expect(response.headers.get("Location")).toBeNull();
      }
    }
    expect(await Bun.file(options.outputRoot).exists()).toBe(false);
  } finally {
    await app.close();
    await probe.close();
    await host.cleanup();
  }
});
