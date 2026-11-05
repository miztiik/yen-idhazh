/** Do safe probe diagnostics retain real operation carriers without copying private measurements? */
import { expect, test } from "bun:test";
import { createChildContext, createRootContext, writeTraceContext } from "@idhazh/common-contracts";
import {
  createProbeCompletionEvent, createProbeFailureEvent, HOST_PROBE_EVENT_VERSION, ProbeEventSchema, readProbeEvent,
} from "../src/api/create-probe-event";

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
