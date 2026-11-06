/** Do native profile diagnostics remain validated, body-free and independent of optional mirrors? */
import { expect, test } from "bun:test";
import { mkdir, mkdtemp, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { createRootContext, readCloudEvent } from "@idhazh/common-contracts";
import { ServerEventDataSchema, serverLogFilename } from "@idhazh/serve-pipeline-apis/evidence";
import type { ServerRun } from "@idhazh/serve-pipeline-apis/evidence";
import { FINGERPRINT_PATH } from "@idhazh/host-fingerprints/api";
import { FingerprintResponseSchema } from "@idhazh/host-fingerprints/response";
import { superviseMachineApiTask } from "../src/api/supervise-machine-api-task";
import { MachineServerEvidenceSchema, readMachineServerEvidence } from "../src/api/create-machine-server-evidence";
import { TaskProfileSchema } from "../src/task-profile/profile-schema";
import { recordedMachineTask } from "./machine-api-recordings";
import { createFingerprintCompletionEvent, createFingerprintFailureEvent } from "@idhazh/host-fingerprints/diagnostic";
import { createProbeCompletionEvent, createProbeFailureEvent } from "../src/api/create-probe-event";

async function writeEvents(directory: string, run: ServerRun, moduleLine?: string, moduleLines?: string[]) {
  const child = Bun.spawn([process.execPath, fileURLToPath(new URL("./write-machine-api-events.ts", import.meta.url))], {
    stdin: new Blob([JSON.stringify({
      directory, run, source: "/fixtures/typescript-api",
      ...(moduleLine === undefined ? {} : { module_line: moduleLine }),
      ...(moduleLines === undefined ? {} : { module_lines: moduleLines }),
    })]),
    stdout: "pipe", stderr: "pipe",
  });
  const [output, error, code] = await Promise.all([
    new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited,
  ]);
  expect(code, error).toBe(0);
  return { result: JSON.parse(output), error };
}

test("native machine events are mirrored unchanged while unknown and unsafe events are refused", async () => {
  const directory = await mkdtemp(join(tmpdir(), "machine-native-events-"));
  const run = { run_id: "700", attempt: 3, started_at: "2026-11-05T00:00:00Z", context: createRootContext() };
  const context = createRootContext({ traceState: "machine=retained" });
  const fingerprint = createFingerprintCompletionEvent({ context, status: "disabled" });
  const probe = createProbeCompletionEvent({ context, operation: "cache-latency", outcome: "disabled" });
  const events = [
    fingerprint, probe, createFingerprintFailureEvent({ context }),
    ...(["host_probe_failed", "host_probe_cleanup_failed", "host_probe_body_cleanup_failed", "task_profile_failed"] as const)
      .map(type => createProbeFailureEvent({ context, type })),
    fingerprint,
  ];
  const invalid = [
    { ...fingerprint, type: "unknown" }, { ...fingerprint, source: "has spaces" },
    { ...probe, traceparent: "invalid" }, { ...probe, data: { ...probe.data, profile: "PRIVATE_PROFILE" } },
    { event: "unknown", body: "PRIVATE_BODY" },
  ];
  try {
    const projected = await writeEvents(directory, run, undefined,
      [...events, ...invalid].map(event => JSON.stringify(event)));
    const readback = projected.error.trim().split("\n").map(line => JSON.parse(line));
    expect(readback.filter(event => event.type !== "hono.server")).toEqual(events);
    const warnings = readback.filter(event => event.type === "hono.server" && event.data.phase === "module_failed");
    expect(warnings).toHaveLength(invalid.length);
    expect(warnings.every(event => event.data.code === "CHILD_DIAGNOSTIC_INVALID")).toBe(true);
    expect(projected.result.profile_count).toBe(0);
    expect(projected.error).not.toContain("PRIVATE_");
    expect(await readFile(join(directory, serverLogFilename(run)), "utf8")).toBe(projected.error);
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test("a real successful default profile report is not a server error or a repeated measurement dump", async () => {
  const child = Bun.spawn([process.execPath, fileURLToPath(new URL("./report-recorded-task-profile.ts", import.meta.url))], {
    stdout: "pipe", stderr: "pipe",
  });
  const [output, error, code] = await Promise.all([
    new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited,
  ]);
  expect(code, error).toBe(0);
  expect(JSON.parse(output)).toEqual({ native_http_status: 200, result: "stopped", task_outcome: "success" });
  const records = error.trim().split("\n").map(line => ({ line, data: JSON.parse(line) }));
  const reported = records.filter(record => record.data.event === "task_profile");
  expect(reported).toHaveLength(1);
  expect(TaskProfileSchema.parse(reported[0]!.data.profile).outcome).toBe("success");
  const directory = await mkdtemp(join(tmpdir(), "api-profile-events-"));
  const run = { run_id: "700", attempt: 3, started_at: "2026-11-04T00:00:00Z", context: createRootContext() };
  try {
    const projected = await writeEvents(directory, run, reported[0]!.line);
    expect(projected.result.profile_count).toBe(1);
    const events = projected.error.trim().split("\n")
      .map(line => readCloudEvent(JSON.parse(line), value => ServerEventDataSchema.parse(value)));
    expect(events.map(event => event.data.phase)).toEqual(["starting", "stopped"]);
    expect(projected.error).not.toContain("profile-report-regression");
    expect(await readFile(join(directory, serverLogFilename(run)), "utf8")).toBe(projected.error);
    const invalid = await writeEvents(directory, run, JSON.stringify({
      event: "task_profile", profile: { body: "PRIVATE_BODY" },
    }));
    const warnings = invalid.error.trim().split("\n")
      .map(line => readCloudEvent(JSON.parse(line), value => ServerEventDataSchema.parse(value)));
    expect(warnings.find(event => event.data.phase === "module_failed")?.data)
      .toMatchObject({ severity: "warning", code: "CHILD_DIAGNOSTIC_INVALID" });
    expect(invalid.error).not.toContain("PRIVATE_BODY");
  } finally { await rm(directory, { recursive: true, force: true }); }
}, 30000);

test("a failed file mirror does not stop a real machine-only child or its fingerprint write", async () => {
  const fixture = await recordedMachineTask();
  const run = fixture.startup.run;
  try {
    await mkdir(join(fixture.evidence, serverLogFilename(run)));
    const result = await superviseMachineApiTask({
      root: fixture.root, startup: fixture.startup,
      request: async (origin, signal) => {
        const response = await fetch(new URL(FINGERPRINT_PATH, origin), {
          method: "POST", headers: { "content-type": "application/json" }, signal,
          body: JSON.stringify({ date: "2026-11-04", writer: {
            run_id: "2026-11-04-700", attempt: 3, git_sha: "a".repeat(40), job: null, shard: 0,
            pipeline_name: "recorded-work", task_name: "independent-machine", producer: "telemetry.silicon",
          } }),
        });
        expect(response.status).toBe(200);
        return FingerprintResponseSchema.parse(await response.json());
      },
    });
    expect(result.status).toBe("written");
    const [evidence] = await readMachineServerEvidence(fixture.evidence);
    expect(evidence).toMatchObject({ startup: "ready", shutdown: "stopped", log_available: false, error_code: null });
    if (evidence === undefined) throw new Error("The real child must retain its same-run server outcome");
    expect(evidence.pid).toBeGreaterThan(0);
    expect(MachineServerEvidenceSchema.safeParse({
      ...evidence, log_filename: serverLogFilename({ ...run, attempt: 4 }),
    }).success).toBe(false);
    await expect(readMachineServerEvidence(fixture.evidence, { run_id: "700", attempt: 4 })).rejects.toThrow("invocation");
  } finally { await fixture.close(); }
}, 30000);
