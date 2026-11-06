/** Do real machine and recorded-source operations share one port and close all owned resources? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRootContext, PLANNER_API_PREFIX, PlannerSavedResponseSchema, readTraceContext, writeTraceContext } from "@idhazh/common-contracts";
import type { FingerprintEvent } from "@idhazh/host-fingerprints/diagnostic";
import type { ProbeEvent } from "@idhazh/host-probes/diagnostic";
import { FingerprintResponseSchema } from "@idhazh/host-fingerprints/response";
import { FINGERPRINT_PATH } from "@idhazh/host-fingerprints/api";
import { loadConfig as loadProbeConfig } from "@idhazh/host-probes/config";
import { SAMPLE_PATH } from "@idhazh/host-probes/api";
import { fixture as fingerprintFixture } from "../../host-fingerprints/test/fixture";
import { recordedPlan } from "./plan-recordings";
import { FetchResponseSchema, ParseResponseSchema } from "../src/api/document-response.schema";
import { operationLink } from "../src/api/operation-context";
import { PlannerReadySchema } from "../src/config/planner-startup";
import { HostSampleSchema } from "../../host-probes/src/probe/sample-host";
import { ApiReadySchema } from "@idhazh/serve-pipeline-apis/startup";
import { serveApiApp } from "@idhazh/serve-pipeline-apis/app";
import { createFeedApiApp } from "../scripts/create-feed-api-app";
import { loadHonoSettings } from "@idhazh/serve-pipeline-apis/settings";

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
  const nativeEvents: (FingerprintEvent | ProbeEvent)[] = [];
  const server = await serveApiApp(settings, createFeedApiApp({
    identity,
    planner: { inputs: recorded.inputs, runtime: recorded.runtime, identity: PlannerReadySchema.parse({
      event: "planner_ready", nonce: identity.nonce, pid: process.pid, port: settings.port,
      runtime: { ...parent, git_sha: recorded.runtime.git_sha, run_number: "700",
        attempt: 1, captured_at: "2026-10-21T23:59:59Z" },
    }) },
    machine: {
      fingerprint: { config: host.config, settings: host.settings, options: {
        outputRoot: join(host.directory, "state"), inspection: host.inspection,
      }, diagnostics: { writeEvent: event => { nativeEvents.push(event); } } },
      probes: { config: probe, context: { platform: "win32" },
        diagnostics: { writeEvent: event => { nativeEvents.push(event); } } },
    },
  }));
  const origin = `http://${settings.hostname}:${server.port}`;
  let unrelatedRequests = 0;
  const unrelated = Bun.serve({ hostname: settings.hostname, port: 0, fetch() {
    unrelatedRequests++;
    return Response.json({ code: "UNRELATED_LISTENER" }, { status: 400 });
  } });
  try {
    expect(await (await fetch(`${origin}/health`)).json()).toEqual({ identity });
    const fingerprint = await fetch(`${origin}${FINGERPRINT_PATH}`, json(host.apiInput, writeTraceContext(parent)));
    expect(fingerprint.status).toBe(200);
    const captured = FingerprintResponseSchema.parse(await fingerprint.json());
    expect(captured.status).toBe("written");
    if (captured.status !== "written") throw new Error("The recorded host observation must be persisted");
    expect(captured.row.machine_memory_total_mib).toBe(16383.75);
    expect(captured.files).toHaveLength(1);
    expect(await Bun.file(join(host.directory, "state", captured.files[0]!.path)).exists()).toBe(true);
    const sample = await fetch(`${origin}${SAMPLE_PATH}`, { headers: writeTraceContext(parent) });
    expect(sample.status).toBe(200);
    expect(HostSampleSchema.parse(await sample.json()).unavailable.cpu).toBe("unsupported_platform");
    expect(nativeEvents.map(event => [event.source, event.type, event.data])).toEqual([
      ["/services/host-fingerprints", "host_fingerprint_completed", { status: "written" }],
      ["/services/host-probes", "host_probe_completed", { operation: "sample", outcome: "handled" }],
    ]);
    for (const event of nativeEvents) {
      const operation = readTraceContext({ traceparent: event.traceparent, tracestate: event.tracestate });
      expect(operation?.traceId).toBe(parent.traceId);
      expect(operation?.spanId).not.toBe(parent.spanId);
    }
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

test("readiness cannot advertise missing native modules", async () => {
  const settings = await listenerSettings();
  expect(() => createFeedApiApp({ identity: {
    event: "typescript_api_ready", nonce: randomUUID(), pid: process.pid, port: settings.port,
    group: "machine", modules: ["machine"], enabled: true,
  } })).toThrow("actual enabled API modules");
});
