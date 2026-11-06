/** Do safe probe diagnostics retain real operation carriers without copying private measurements? */
import { expect, test } from "bun:test";
import { createChildContext, createRootContext, readTraceContext, writeTraceContext } from "@idhazh/common-contracts";
import {
  createProbeCompletionEvent, createProbeFailureEvent, HOST_PROBE_EVENT_VERSION, ProbeEventSchema, readProbeEvent,
} from "../src/api/create-probe-event";
import type { ProbeEvent } from "../src/api/create-probe-event";
import { loadConfig } from "../src/config";
import { CACHE_LATENCY_PATH, createSampleHandler, SAMPLE_PATH, START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH } from "../src/api/server";
import type { TaskProfile } from "../src/task-profile/profile-schema";

test.each(["sample", "start-task-profile", "stop-task-profile", "cache-latency"] as const)(
  "%s completion describes handling, not measurement availability", operation => {
    const context = createChildContext(createRootContext({ traceState: "probe=retained" }));
    const event = createProbeCompletionEvent({ context, operation, outcome: "handled" });
    expect(event.source).toBe("/services/host-probes");
    expect(event.data).toEqual({ operation, outcome: "handled" });
    expect(event).toMatchObject(writeTraceContext(context));
    expect(readProbeEvent(JSON.parse(JSON.stringify(event)))).toEqual(event);
    expect(createProbeCompletionEvent({ context, operation, outcome: "handled" }).id).not.toBe(event.id);
    for (const fields of [
      { outcome: "success" }, { operation: "unknown" }, { profile: {} }, { pid: 1 }, { cpu_percent: 0 },
    ]) expect(ProbeEventSchema.safeParse({ ...event, data: { ...event.data, ...fields } }).success).toBe(false);
  },
);

test("disabled probe commands retain an honest outcome without a handle or measurements", () => {
  const event = createProbeCompletionEvent({
    context: createRootContext(), operation: "start-task-profile", outcome: "disabled",
  });
  expect(event.data).toEqual({ operation: "start-task-profile", outcome: "disabled" });
  expect(ProbeEventSchema.meta()).toMatchObject({
    version: HOST_PROBE_EVENT_VERSION,
    readCompatibility: "current_only; diagnostic readers and writers change together",
    changelog: [{ version: HOST_PROBE_EVENT_VERSION }],
  });
});

test.each([
  ["host_probe_failed", "HOST_PROBE_FAILED"],
  ["host_probe_cleanup_failed", "HOST_PROBE_CLEANUP_FAILED"],
  ["host_probe_body_cleanup_failed", "HOST_PROBE_BODY_CLEANUP_FAILED"],
  ["task_profile_failed", "TASK_PROFILE_FAILED"],
] as const)("%s exposes only its exact native code", (type, code) => {
  const event = createProbeFailureEvent({ context: createRootContext(), type });
  expect(event.type).toBe(type);
  expect(event.data).toEqual({ code });
  expect(readProbeEvent(event)).toEqual(event);
  for (const fields of [
    { source: "has spaces" }, { source: "/another-producer" }, { traceparent: "invalid" },
    { tracestate: "invalid state" }, { type: "unknown" },
    { data: { code: "PRIVATE_EXCEPTION" } }, { data: { code, detail: "PRIVATE_DETAIL" } },
    { data: { code: type === "host_probe_failed" ? "TASK_PROFILE_FAILED" : "HOST_PROBE_FAILED" } },
  ]) expect(() => readProbeEvent({ ...event, ...fields })).toThrow();
});

test("real sample and disabled commands emit native outcomes without profiles or invented measurements", async () => {
  const config = await loadConfig();
  config.task_profile.enabled = false;
  config.cache_probe.latency.enabled = false;
  const events: ProbeEvent[] = [];
  const profiles: TaskProfile[] = [];
  const parent = createRootContext({ traceState: "probe=http" });
  const handler = createSampleHandler(config, { platform: "unsupported" },
    profile => { profiles.push(profile); }, { writeEvent: event => { events.push(event); } });
  const command = (path: string, body: unknown) => new Request(`http://localhost${path}`, {
    method: "POST", headers: { "content-type": "application/json", ...writeTraceContext(parent) },
    body: JSON.stringify(body),
  });
  try {
    const sample = await handler(new Request(`http://localhost${SAMPLE_PATH}`, { headers: writeTraceContext(parent) }));
    expect(sample.status).toBe(200);
    expect((await sample.json()).cpu).toBeNull();
    expect((await (await handler(command(CACHE_LATENCY_PATH, {}))).json()).status).toBe("disabled");
    const input = {
      identity: { pipeline_name: "native-tests", task_name: "profile", run_id: "native-run" },
      target: { pid: 1, start_ticks: "1" },
    };
    expect(await (await handler(command(START_TASK_PROFILE_PATH, input))).json())
      .toEqual({ status: "disabled", reason: "configured_off" });
    expect(await (await handler(command(STOP_TASK_PROFILE_PATH, { handle: crypto.randomUUID(), outcome: "success" }))).json())
      .toEqual({ status: "disabled", reason: "configured_off" });
    expect(events.map(event => event.data)).toEqual([
      { operation: "sample", outcome: "handled" }, { operation: "cache-latency", outcome: "disabled" },
      { operation: "start-task-profile", outcome: "disabled" }, { operation: "stop-task-profile", outcome: "disabled" },
    ]);
    expect(profiles).toEqual([]);
    for (const event of events) {
      expect(ProbeEventSchema.parse(event).source).toBe("/services/host-probes");
      const operation = readTraceContext({ traceparent: event.traceparent, tracestate: event.tracestate });
      expect(operation?.traceId).toBe(parent.traceId);
      expect(operation?.spanId).not.toBe(parent.spanId);
      expect(operation?.traceState).toBe(parent.traceState);
    }
    expect((await handler(command(START_TASK_PROFILE_PATH, {}))).status).toBe(400);
    expect(events.at(-1)).toMatchObject({ type: "host_probe_failed", data: { code: "HOST_PROBE_FAILED" } });
    expect(profiles).toEqual([]);
  } finally { await handler.close(); }
});

test("a real body-cancellation failure keeps its receiving operation and no private exception text", async () => {
  const config = await loadConfig();
  config.cache_probe.lifecycle_timeout_ms = 1;
  const events: ProbeEvent[] = [];
  const parent = createRootContext({ traceState: "body=receiving" });
  const handler = createSampleHandler(config, { platform: "unsupported" }, undefined,
    { writeEvent: event => { events.push(event); } });
  try {
    const response = await handler(new Request(`http://localhost${CACHE_LATENCY_PATH}`, {
      method: "POST", headers: { "content-type": "application/json", ...writeTraceContext(parent) },
      body: new ReadableStream<Uint8Array>({
        start(controller) { controller.enqueue(new TextEncoder().encode("{")); },
        cancel() { throw new Error("PRIVATE_CANCEL_ERROR"); },
      }),
    }));
    expect(response.status).toBe(400);
    await response.json();
    const cleanup = events.find(event => event.type === "host_probe_body_cleanup_failed");
    const failure = events.find(event => event.type === "host_probe_failed");
    expect(cleanup).toBeDefined();
    expect(failure).toBeDefined();
    expect(cleanup?.traceparent).toBe(failure?.traceparent);
    expect(readTraceContext({ traceparent: cleanup?.traceparent, tracestate: cleanup?.tracestate })?.traceId).toBe(parent.traceId);
    expect(JSON.stringify(events)).not.toContain("PRIVATE_CANCEL_ERROR");
  } finally { await handler.close(); }
});
