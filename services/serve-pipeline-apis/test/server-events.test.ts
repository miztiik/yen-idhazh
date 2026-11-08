/** Are accepted diagnostics mirrored safely, append-only and optional? */
import { expect, test } from "bun:test";
import { mkdir, mkdtemp, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { createRootContext, readCloudEvent } from "@idhazh/common-contracts";
import { ServerEventDataSchema, serverLogFilename } from "../src/server-evidence";
import type { ServerRun } from "../src/server-evidence";
import {
  createRequestFailureEvent, readRequestFailureEvent, REQUEST_FAILURE_EVENT_VERSION, RequestFailureEventSchema,
} from "../src/create-request-failure-event";

async function writeEvents(directory: string, run: ServerRun, moduleLine?: string) {
  const child = Bun.spawn([process.execPath, fileURLToPath(new URL("./write-server-events.ts", import.meta.url))], {
    stdin: new Blob([JSON.stringify({ directory, run, source: "/fixtures/typescript-api",
      ...(moduleLine === undefined ? {} : { module_line: moduleLine }) })]),
    stdout: "pipe", stderr: "pipe",
  });
  const [output, error, code] = await Promise.all([
    new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited,
  ]);
  expect(code, error).toBe(0);
  return { result: JSON.parse(output), error };
}

test("server restarts append identical live CloudEvents without private bodies or headers", async () => {
  const directory = await mkdtemp(join(tmpdir(), "api-events-"));
  const run = { run_id: "700", attempt: 3, started_at: "2026-11-04T23:59:59Z", context: createRootContext() };
  try {
    const first = await writeEvents(directory, run, JSON.stringify({
      phase: "module_failed", severity: "error", code: "RECORDED_FAILURE", article_text: "PRIVATE_BODY",
      headers: { authorization: "PRIVATE_HEADER" },
    }));
    const second = await writeEvents(directory, run);
    const text = await readFile(join(directory, serverLogFilename("machine", run)), "utf8");
    expect(text).toBe(first.error + second.error);
    expect(first.result.available).toBe(true);
    expect(text).not.toContain("PRIVATE_BODY");
    expect(text).not.toContain("PRIVATE_HEADER");
    const events = text.trim().split("\n").map(line => readCloudEvent(JSON.parse(line), value => ServerEventDataSchema.parse(value)));
    for (const event of events) expect(event.data).not.toHaveProperty("pid");
    expect(new Set(events.map(event => event.id)).size).toBe(events.length);
    expect(events.filter(event => event.data.phase === "starting")).toHaveLength(2);
    expect(events.every(event => event.source === "/fixtures/typescript-api")).toBe(true);
    expect(events.find(event => event.data.code === "RECORDED_FAILURE")?.data.severity).toBe("error");
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test("an unavailable file is a safe stderr warning and does not change successful work", async () => {
  const directory = await mkdtemp(join(tmpdir(), "api-events-"));
  const run = { run_id: "700", attempt: 3, started_at: "2026-11-04T00:00:00Z", context: createRootContext() };
  try {
    await mkdir(join(directory, serverLogFilename("machine", run)));
    const { result, error } = await writeEvents(directory, run);
    expect(result.available).toBe(false);
    const events = error.trim().split("\n").map(line => readCloudEvent(JSON.parse(line), value => ServerEventDataSchema.parse(value)));
    expect(events.filter(event => event.data.phase === "log_unavailable")).toHaveLength(1);
    expect(events.at(-1)?.data).toMatchObject({ phase: "stopped", exit_code: 0 });
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test("invalid diagnostic JSON remains a safe warning", async () => {
  const directory = await mkdtemp(join(tmpdir(), "api-events-"));
  const run = { run_id: "700", attempt: 3, started_at: "2026-11-04T00:00:00Z", context: createRootContext() };
  try {
    const { error } = await writeEvents(directory, run, "PRIVATE_INVALID_JSON");
    const events = error.trim().split("\n").map(line => readCloudEvent(JSON.parse(line), value => ServerEventDataSchema.parse(value)));
    expect(events.find(event => event.data.phase === "module_failed")?.data)
      .toMatchObject({ severity: "warning", code: "CHILD_DIAGNOSTIC_INVALID" });
    expect(error).not.toContain("PRIVATE_INVALID_JSON");
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test("native request failures retain their occurrence and carrier through the real relay", async () => {
  const directory = await mkdtemp(join(tmpdir(), "api-native-failure-"));
  const run = { run_id: "700", attempt: 3, started_at: "2026-11-05T00:00:00Z", context: createRootContext() };
  const context = createRootContext({ traceState: "request=retained" });
  const event = createRequestFailureEvent({ context });
  expect(createRequestFailureEvent({ context }).id).not.toBe(event.id);
  expect(event.data).toEqual({ code: "API_OPERATION_FAILED" });
  expect(event.source).toBe("/services/typescript-api");
  expect(readRequestFailureEvent(JSON.parse(JSON.stringify(event)))).toEqual(event);
  expect(RequestFailureEventSchema.meta()).toMatchObject({
    version: REQUEST_FAILURE_EVENT_VERSION,
    readCompatibility: "current_only; diagnostic readers and writers change together",
  });
  for (const fields of [
    { source: "has spaces" }, { source: "/another-producer" }, { traceparent: "invalid" },
    { type: "unknown" }, { data: { code: "PRIVATE_EXCEPTION" } },
  ]) expect(() => readRequestFailureEvent({ ...event, ...fields })).toThrow();
  try {
    const accepted = await writeEvents(directory, run, JSON.stringify(event));
    const lines = accepted.error.trim().split("\n").map(line => JSON.parse(line));
    expect(lines[1]).toEqual(event);
    expect(lines).toHaveLength(3);
    const rejected = await writeEvents(directory, run, JSON.stringify({
      ...event, data: { ...event.data, body: "PRIVATE_BODY" },
    }));
    expect(rejected.error).toContain("CHILD_DIAGNOSTIC_INVALID");
    expect(rejected.error).not.toContain("PRIVATE_BODY");
    expect(await readFile(join(directory, serverLogFilename("machine", run)), "utf8"))
      .toBe(accepted.error + rejected.error);
  } finally { await rm(directory, { recursive: true, force: true }); }
});
