/** Do shared-only HTTP children retain their lifetime, diagnostics and failure evidence? */
import { expect, test } from "bun:test";
import { mkdir, mkdtemp, readFile, rm } from "node:fs/promises";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createRootContext, readCloudEvent } from "@idhazh/common-contracts";
import { z } from "zod";
import { ApiHostStartupSchema, enabledModules } from "../src/api-startup";
import { apiOrigin, loadHonoSettings, SupervisionSettingsSchema } from "../src/load-settings";
import { readApiReadiness } from "../src/read-api-readiness";
import { readServerEvidence } from "../src/read-server-evidence";
import { createServerEvidenceSchema, ServerEventDataSchema, serverEvidenceFilename } from "../src/server-evidence";
import { superviseApiTask } from "../src/supervise-api-task";
import { superviseHttpChild } from "../src/supervise-http-child";
import type { HttpChildObservation } from "../src/supervise-http-child";
import { HOST_CLOSED_FILENAME, HostClosedSchema, HostFailure, HostStartupSchema, hostFailure } from "./run-host-lifetime";
import type { HostStartup } from "./run-host-lifetime";

const serverEntry = fileURLToPath(new URL("./run-host-lifetime.ts", import.meta.url));
const sharedSettings = await loadHonoSettings(fileURLToPath(new URL("../../../", import.meta.url)));
const supervision = SupervisionSettingsSchema.parse({
  ...sharedSettings.supervision,
  readiness_timeout_ms: 10_000, shutdown_timeout_ms: 5_000, forced_exit_timeout_ms: 3_000,
});
const evidenceSchema = createServerEvidenceSchema(z.never());
const diagnosticSchema = ServerEventDataSchema.pick({ phase: true, code: true, severity: true }).strip();
type HostFixture = { root: string; startup: HostStartup };

async function withHost(
  overrides: Partial<Pick<HostStartup, "startup_delay_ms" | "close_delay_ms">>,
  exercise: (fixture: HostFixture) => Promise<void>,
) {
  const root = resolve(await mkdtemp(".host-lifetime-"));
  try {
    const reservation = Bun.serve({ hostname: sharedSettings.hostname, port: 0, fetch: () => new Response() });
    const port = reservation.port!;
    await reservation.stop(true);
    const startup = HostStartupSchema.parse({
      server: { ...sharedSettings, port, idle_timeout_seconds: 5, supervision },
      run: { run_id: "shared-host", attempt: 1, started_at: "2026-11-05T00:00:00Z", context: createRootContext() },
      directory: "evidence", group: "machine", nonce: crypto.randomUUID(),
      startup_delay_ms: 0, close_delay_ms: 0, max_request_body_bytes: 1024,
      ...overrides,
    });
    await mkdir(join(root, "config"));
    await mkdir(join(root, startup.directory));
    await Bun.write(join(root, "config", "typescript-event-sources.json"), JSON.stringify({
      typescript_api: "/fixtures/shared-host", planner: "/fixtures/planner",
      summarizer: "/fixtures/summarizer", workflow: "/fixtures/workflow",
    }));
    await exercise({ root, startup });
  } finally { await rm(root, { recursive: true, force: true }); }
}

function childInput({ root, startup }: HostFixture) {
  return {
    root, startup, serverEntry, kind: "TYPESCRIPT_API" as const,
    supervision: startup.server.supervision, maxControlBytes: 4096, failure: hostFailure,
    ready: (message: unknown, pid: number, signal: AbortSignal) => readApiReadiness({
      message, expected: {
        event: "typescript_api_ready", nonce: startup.nonce, pid, port: startup.server.port,
        group: startup.group, modules: enabledModules(startup.group), enabled: true,
      },
      server: startup.server, context: startup.run.context, kind: "TYPESCRIPT_API", failure: hostFailure, signal,
    }),
  };
}

function taskInput(fixture: HostFixture) {
  return {
    ...childInput(fixture), evidenceSchema,
    decodeDiagnostic(raw: unknown) {
      const diagnostic = diagnosticSchema.safeParse(raw);
      return diagnostic.success ? { kind: "event" as const, data: diagnostic.data } : { kind: "invalid" as const };
    },
  };
}

async function retained({ root, startup }: HostFixture) {
  const directory = join(root, startup.directory);
  const evidence = evidenceSchema.parse(await Bun.file(join(directory, serverEvidenceFilename("machine"))).json());
  expect(await readServerEvidence(directory, evidenceSchema, startup.run)).toEqual([evidence]);
  const log = await readFile(join(directory, evidence.log_filename), "utf8");
  const events = log.trim().split("\n").map(line => readCloudEvent(JSON.parse(line), value => ServerEventDataSchema.parse(value)));
  return { evidence, log, events };
}

async function assertReleased(fixture: HostFixture, pid: number | null) {
  if (pid === null) throw new Error("No owned child was observed");
  try { process.kill(pid, 0); throw new Error("Owned child still exists"); }
  catch (error) { expect(error).toMatchObject({ code: "ESRCH" }); }
  const replacement = Bun.serve({
    hostname: fixture.startup.server.hostname, port: fixture.startup.server.port,
    fetch: () => new Response("replacement"),
  });
  try {
    expect(await (await fetch(apiOrigin(fixture.startup.server), { signal: AbortSignal.timeout(5_000) })).text())
      .toBe("replacement");
  } finally { await replacement.stop(true); }
}

test("private startup rejects missing or invalid server.supervision by field name", () => {
  const { supervision: controls, ...server } = sharedSettings;
  const startup = {
    server: sharedSettings, directory: "evidence",
    run: { run_id: "shared-startup", attempt: 1, started_at: "2026-11-05T00:00:00Z", context: createRootContext() },
  };
  expect(ApiHostStartupSchema.parse(startup).server.supervision).toEqual(controls);
  const invalid = [
    { server, path: "server.supervision" },
    { server: { ...server, supervision: null }, path: "server.supervision" },
    { server: { ...server, supervision: { ...controls, readiness_timeout_ms: 0 } }, path: "server.supervision.readiness_timeout_ms" },
    { server: { ...server, supervision: { ...controls, shutdown_timeout_ms: -1 } }, path: "server.supervision.shutdown_timeout_ms" },
    { server: { ...server, supervision: { ...controls, forced_exit_timeout_ms: 1.5 } }, path: "server.supervision.forced_exit_timeout_ms" },
  ];
  for (const input of invalid) {
    const result = ApiHostStartupSchema.safeParse({ ...startup, server: input.server });
    expect(result.success, input.path).toBe(false);
    if (result.success) throw new Error(`Startup accepted invalid ${input.path}`);
    expect(result.error.issues.map(issue => issue.path.join("."))).toContain(input.path);
  }
});

test("shared hosting awaits cancelled work, application close and the final diagnostic", async () => {
  await withHost({}, async fixture => {
    let pending: Promise<Response> | undefined;
    const result = await superviseApiTask({
      ...taskInput(fixture),
      async request(origin, signal) {
        const deadline = AbortSignal.any([signal, AbortSignal.timeout(5_000)]);
        const response = await fetch(origin, {
          method: "POST", body: "PRIVATE_REQUEST_BODY", headers: { authorization: "PRIVATE_HEADER" }, signal: deadline,
        });
        expect(response.status).toBe(200);
        const value: unknown = await response.json();
        const failed = await fetch(new URL("/fail", origin), { signal: deadline });
        expect(failed.status).toBe(500);
        expect(await failed.json()).toEqual({ code: "API_OPERATION_FAILED" });
        pending = fetch(new URL("/wait", origin), { signal: deadline });
        void pending.catch(() => {});
        expect((await fetch(new URL("/entered", origin), { signal: deadline })).status).toBe(204);
        return value;
      },
    });
    await pending?.catch(() => {});
    expect(result).toEqual({ body: "PRIVATE_REQUEST_BODY", origin: apiOrigin(fixture.startup.server) });
    const { evidence, log, events } = await retained(fixture);
    expect(evidence).toMatchObject({
      startup: "ready", shutdown: "stopped", exit_code: 0, error_code: null,
      cleanup_error_code: null, log_available: true, reported_profiles: [],
    });
    const closed = HostClosedSchema.parse(await Bun.file(join(fixture.root, "evidence", HOST_CLOSED_FILENAME)).json());
    expect(evidence.pid).toBe(closed.pid);
    expect(closed).toMatchObject({
      parent_cancelled: true, application_cancelled: true, request_cancelled: true, close_calls: 1,
    });
    expect(events.some(event => event.data.code === "HOST_CLOSED")).toBe(true);
    expect(events.some(event => event.data.phase === "ready")).toBe(true);
    expect(events.every(event => event.source === "/fixtures/shared-host")).toBe(true);
    for (const secret of ["PRIVATE_REQUEST_BODY", "PRIVATE_HEADER", "PRIVATE_OPERATION_FAILURE"]) {
      expect(log).not.toContain(secret);
    }
    await assertReleased(fixture, evidence.pid);
  });
}, 25_000);

test("a readiness deadline retains failed-startup evidence and reaps the child", async () => {
  await withHost({ startup_delay_ms: 1000 }, async fixture => {
    await expect(superviseApiTask({
      ...taskInput(fixture), supervision: { ...fixture.startup.server.supervision, readiness_timeout_ms: 50 },
      async request() { throw new Error("A request must not run before readiness"); },
    })).rejects.toMatchObject({ code: "TYPESCRIPT_API_READY_TIMEOUT" });
    const { evidence } = await retained(fixture);
    expect(evidence).toMatchObject({
      startup: "failed", shutdown: "stopped", error_code: "TYPESCRIPT_API_READY_TIMEOUT", cleanup_error_code: null,
    });
    expect(await Bun.file(join(fixture.root, "evidence", HOST_CLOSED_FILENAME)).exists()).toBe(false);
    await assertReleased(fixture, evidence.pid);
  });
}, 25_000);

test("a failed request retains both causes when its exact child needs forced cleanup", async () => {
  await withHost({ close_delay_ms: 10_000 }, async fixture => {
    const unrelated = Bun.serve({ hostname: "127.0.0.1", port: 0, fetch: () => new Response("unrelated") });
    try {
      const original = new HostFailure("HOST_TASK_FAILED", "Task request failed");
      const error: unknown = await superviseApiTask({
        ...taskInput(fixture), supervision: { ...fixture.startup.server.supervision, shutdown_timeout_ms: 300 },
        async request() { throw original; },
      }).catch((failure: unknown) => failure);
      expect(error).toBeInstanceOf(HostFailure);
      if (!(error instanceof HostFailure)) throw new Error("The failure policy did not retain the task failure");
      expect(error.code).toBe(original.code);
      expect(error.cause).toBeInstanceOf(AggregateError);
      if (!(error.cause instanceof AggregateError)) throw new Error("Cleanup lost one of the failure causes");
      expect(error.cause.errors).toEqual([original, expect.objectContaining({ code: "TYPESCRIPT_API_SHUTDOWN_TIMEOUT" })]);
      const { evidence, events } = await retained(fixture);
      expect(evidence).toMatchObject({
        startup: "ready", shutdown: "forced", error_code: original.code, cleanup_error_code: "TYPESCRIPT_API_CLEANUP_FAILED",
      });
      expect(evidence.exit_code).not.toBeNull();
      expect(evidence.exit_code).not.toBe(0);
      expect(events.some(event => event.data.phase === "forced")).toBe(true);
      expect(events.some(event => event.data.code === "HOST_CLOSE_STARTED")).toBe(true);
      expect(await Bun.file(join(fixture.root, "evidence", HOST_CLOSED_FILENAME)).exists()).toBe(false);
      expect(await (await fetch(`http://127.0.0.1:${unrelated.port}`, { signal: AbortSignal.timeout(5_000) })).text())
        .toBe("unrelated");
      await assertReleased(fixture, evidence.pid);
    } finally { await unrelated.stop(true); }
  });
}, 25_000);

test("caller cancellation aborts the real request and drains diagnostics before returning", async () => {
  await withHost({}, async fixture => {
    const cancellation = new AbortController();
    const observations: HttpChildObservation[] = [];
    const diagnostics: string[] = [];
    let pending: Promise<Response> | undefined;
    await expect(superviseHttpChild({
      ...childInput(fixture), signal: cancellation.signal,
      observe: event => observations.push(event), diagnostics: line => diagnostics.push(line),
      async request(origin, signal) {
        const deadline = AbortSignal.any([signal, AbortSignal.timeout(5_000)]);
        pending = fetch(new URL("/wait", origin), { signal: deadline });
        void pending.catch(() => {});
        await fetch(new URL("/entered", origin), { signal: deadline });
        cancellation.abort(new Error("PRIVATE_CANCEL_REASON"));
        return await pending;
      },
    })).rejects.toMatchObject({ code: "HOST_CANCELLED" });
    await pending?.catch(() => {});
    expect(observations.map(event => event.phase)).toEqual(["started", "ready", "stopping", "stopped"]);
    const closed = HostClosedSchema.parse(await Bun.file(join(fixture.root, "evidence", HOST_CLOSED_FILENAME)).json());
    expect(closed).toMatchObject({ parent_cancelled: true, application_cancelled: true, request_cancelled: true, close_calls: 1 });
    expect(observations.every(event => event.pid === closed.pid)).toBe(true);
    expect(JSON.parse(diagnostics.at(-1)!)).toEqual({ phase: "stopping", severity: "info", code: "HOST_CLOSED" });
    expect(diagnostics.join("\n")).not.toContain("PRIVATE_CANCEL_REASON");
    await assertReleased(fixture, closed.pid);
  });
}, 25_000);
