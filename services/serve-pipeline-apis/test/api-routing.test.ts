/** Do the declared host paths dispatch native payloads through shared hosting without aliases? */
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
