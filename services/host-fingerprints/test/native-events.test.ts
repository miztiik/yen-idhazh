/** Do fingerprint diagnostics retain native occurrences while refusing private or malformed data? */
import { expect, test } from "bun:test";
import { createRootContext, writeTraceContext } from "@idhazh/common-contracts";
import {
  createFingerprintCompletionEvent, createFingerprintFailureEvent, FingerprintEventSchema,
  HOST_FINGERPRINT_EVENT_VERSION, readFingerprintEvent,
} from "../src/api/create-fingerprint-event";

test.each(["written", "disabled"] as const)("fingerprint %s outcomes retain their operation and saved occurrence", status => {
  const context = createRootContext({ traceState: "fingerprint=retained" });
  const event = createFingerprintCompletionEvent({ context, status });
  const next = createFingerprintCompletionEvent({ context, status });
  expect(event.source).toBe("/services/host-fingerprints");
  expect(event.type).toBe("host_fingerprint_completed");
  expect(event.data).toEqual({ status });
  expect(event).toMatchObject(writeTraceContext(context));
  expect(next.id).not.toBe(event.id);
  expect(next.traceparent).toBe(event.traceparent);
  expect(readFingerprintEvent(JSON.parse(JSON.stringify(event)))).toEqual(event);
});

test("fingerprint failures expose only their fixed code and retain the current schema contract", () => {
  const event = createFingerprintFailureEvent({ context: createRootContext() });
  expect(event.type).toBe("host_fingerprint_failed");
  expect(event.data).toEqual({ code: "HOST_FINGERPRINT_FAILED" });
  expect(readFingerprintEvent(event)).toEqual(event);
  expect(FingerprintEventSchema.meta()).toMatchObject({
    version: HOST_FINGERPRINT_EVENT_VERSION,
    readCompatibility: "current_only; diagnostic readers and writers change together",
    changelog: [{ version: HOST_FINGERPRINT_EVENT_VERSION }],
  });
  for (const fields of [
    { source: "has spaces" }, { source: "/another-producer" }, { traceparent: "invalid" },
    { tracestate: "invalid state" }, { type: "host_fingerprint_unknown" },
    { data: { code: "PRIVATE_EXCEPTION" } }, { data: { code: "HOST_FINGERPRINT_FAILED", pid: 1 } },
    { data: { status: "written" } },
  ]) expect(() => readFingerprintEvent({ ...event, ...fields })).toThrow();
  const completed = createFingerprintCompletionEvent({ context: createRootContext(), status: "written" });
  expect(FingerprintEventSchema.safeParse({
    ...completed, data: { ...completed.data, paths: ["PRIVATE_PATH"] },
  }).success).toBe(false);
  expect(FingerprintEventSchema.safeParse({ ...completed, data: { status: "success" } }).success).toBe(false);
});
