/** Does the real child boundary preserve output and identity, and release its exact listener after failure? */
import { expect, test } from "bun:test";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { writeFile } from "node:fs/promises";
import { PlannerReadySchema, PlannerStartupSchema } from "../src/config/planner-startup";
import { invokePlannerHttp } from "../scripts/feed-ingest-plan-supervisor";
import { recordedPlannerProcess, readPlannerStartupRecording } from "./planner-process-recordings";
import { collectWorkflowFiles } from "../scripts/feed-ingest-plan-current-files";
import { metadataRegistrations } from "./host-recordings";
import { source } from "./harvest-recordings";
import { writePlannerOutputRecording } from "./planner-output-recordings";
import { PLANNER_API_PATHS, PLANNER_API_PREFIX, PlannerFailureSchema } from "@idhazh/common-contracts";
import { readMachineServerEvidence } from "@idhazh/host-probes/machine-evidence";
import { writeWorkflowReport } from "../scripts/feed-ingest-plan-report";
import { prepareWorkflowArtifacts } from "../scripts/feed-ingest-plan-artifacts";
import { HonoServerSettingsSchema, loadHonoSettings } from "../../serve-pipeline-apis/src/load-settings";

function assertReleased(port: number) {
  const probe = Bun.serve({ hostname: "127.0.0.1", port, fetch: () => new Response() });
  return probe.stop(true);
}
async function awaitRecordedRequest(directory: string, signal: AbortSignal) {
  while (!await Bun.file(join(directory, "recorded-request.json")).exists()) {
    signal.throwIfAborted();
    await Bun.sleep(10);
  }
}

test("an occupied port fails without stopping or planning against the unrelated listener", async () => {
  const fixture = await recordedPlannerProcess();
  let requests = 0;
  const occupied = Bun.serve({
    hostname: "127.0.0.1", port: fixture.inputs.settings.listener.port,
    fetch() { requests++; return Response.json({ planner_enabled: true }); },
  });
  try {
    await expect(invokePlannerHttp(fixture.inputs, fixture.startup, {}, fixture.evidence, {
      serverEntry: fixture.serverEntry,
    })).rejects.toMatchObject({ code: "PLANNER_BIND_FAILED" });
    expect(requests).toBe(0);
    expect(await Bun.file(join(fixture.evidence, "response.json")).exists()).toBe(false);
    const [server] = await readMachineServerEvidence(fixture.evidence, { run_id: "700", attempt: 3 });
    expect(server).toMatchObject({
      group: "planning", startup: "failed", error_code: "PLANNER_BIND_FAILED", shutdown: "stopped",
    });
    expect(server?.startup_ms).toBeGreaterThanOrEqual(0);
    if (server === undefined) throw new Error("Failed startup must retain its observed server outcome");
    expect(await Bun.file(join(fixture.evidence, server.log_filename)).exists()).toBe(true);
    const report = await writeWorkflowReport({
      root: fixture.directory, directory: fixture.evidence, runNumber: "700", runId: "2026-10-21-700",
      summaryPath: join(fixture.evidence, "summary.md"),
    });
    expect(report.status).toBe("written");
    if (report.status !== "written") throw new Error("Configured reporting must retain failed startup");
    expect(report.markdown).toContain("PLANNER_BIND_FAILED");
    const artifacts = await prepareWorkflowArtifacts({
      root: fixture.directory, directory: fixture.evidence, runNumber: "700", attempt: 3,
      gitSha: fixture.startup.runtime.git_sha, runId: "2026-10-21-700", reportFilename: report.filename,
    });
    expect(artifacts.server_logs).toBe("server-logs");
    expect(await Bun.file(join(fixture.evidence, "server-logs", server.log_filename)).text())
      .toBe(await Bun.file(join(fixture.evidence, server.log_filename)).text());
    expect((await fetch(`http://127.0.0.1:${occupied.port}`)).status).toBe(200);
  } finally { await occupied.stop(true); await fixture.close(); }
});

test("a real child with missing authored inputs exits before readiness and is reaped", async () => {
  const fixture = await recordedPlannerProcess();
  try {
    fixture.startup.settings.inputs.planning = "config/absent.json";
    await expect(invokePlannerHttp(fixture.inputs, fixture.startup, {}, fixture.evidence))
      .rejects.toThrow();
    await assertReleased(fixture.inputs.settings.listener.port);
  } finally { await fixture.close(); }
});

test("expired readiness cancels startup and leaves no listener", async () => {
  const fixture = await recordedPlannerProcess();
  try {
    const server = await loadHonoSettings(fixture.directory);
    server.supervision.readiness_timeout_ms = 1;
    await writeFile(join(fixture.directory, "config", "hono-server.json"), JSON.stringify(server));
    await expect(invokePlannerHttp(fixture.inputs, fixture.startup, {}, fixture.evidence, {
      serverEntry: fixture.serverEntry,
    })).rejects.toThrow("PLANNER_READY_TIMEOUT");
    await assertReleased(fixture.inputs.settings.listener.port);
  } finally { await fixture.close(); }
});

test("identity mismatch refuses HTTP work and closes the owned child", async () => {
  for (const marker of ["recorded-readiness-mismatch", "recorded-runtime-mismatch"]) {
    const fixture = await recordedPlannerProcess();
    try {
      await writeFile(join(fixture.directory, marker), "Return different captured child controls");
      await expect(invokePlannerHttp(fixture.inputs, fixture.startup, {}, fixture.evidence, {
        serverEntry: fixture.serverEntry,
      })).rejects.toMatchObject({ code: "PLANNER_READY_IDENTITY" });
      expect(await Bun.file(join(fixture.evidence, "response.json")).exists()).toBe(false);
      await assertReleased(fixture.startup.settings.listener.port);
    } finally { await fixture.close(); }
  }
});

test("cancellation during real recorded feed work reaps the child and releases its port", async () => {
  const fixture = await recordedPlannerProcess([source({ url: "https://news.example/timeout" })]);
  const cancellation = new AbortController();
  let pending: ReturnType<typeof invokePlannerHttp> | undefined;
  try {
    const server = await loadHonoSettings(fixture.directory);
    server.supervision.shutdown_timeout_ms = 200;
    await writeFile(join(fixture.directory, "config", "hono-server.json"), JSON.stringify(server));
    pending = invokePlannerHttp(fixture.inputs, fixture.startup, {}, fixture.evidence, {
      serverEntry: fixture.serverEntry, signal: cancellation.signal,
    });
    void pending.catch(() => {});
    const health = `http://127.0.0.1:${fixture.inputs.settings.listener.port}${PLANNER_API_PREFIX}${PLANNER_API_PATHS.health}`;
    const deadline = AbortSignal.timeout(server.supervision.readiness_timeout_ms);
    let identity: ReturnType<typeof PlannerReadySchema.parse> | undefined;
    while (!identity) {
      deadline.throwIfAborted();
      try { identity = PlannerReadySchema.parse((await (await fetch(health, { signal: deadline })).json()).identity); }
      catch (error) {
        if (!(error instanceof Error) || !("code" in error) || !["ECONNREFUSED", "ConnectionRefused"].includes(String(error.code))) throw error;
        await Bun.sleep(10);
      }
    }
    expect(identity.pid).not.toBe(process.pid);
    expect(identity.nonce).toBe(fixture.startup.nonce);
    await awaitRecordedRequest(fixture.directory, deadline);
    cancellation.abort(new Error("Recorded workflow cancellation"));
    await expect(pending).rejects.toMatchObject({ failure: { safe_cause: "cancelled" } });
    expect(() => process.kill(identity!.pid, 0)).toThrow();
    await assertReleased(fixture.inputs.settings.listener.port);
  } finally { cancellation.abort(); await pending?.catch(() => {}); await fixture.close(); }
}, 60000);

test("parent disappearance closes the child pipe and the child bounds its own drain", async () => {
  const fixture = await recordedPlannerProcess([source({ url: "https://news.example/timeout" })]);
  const server = await loadHonoSettings(fixture.directory);
  server.supervision.shutdown_timeout_ms = 200;
  await writeFile(join(fixture.directory, "config", "hono-server.json"), JSON.stringify(server));
  const parent = Bun.spawn([process.execPath, fileURLToPath(new URL("./planner-supervisor-recording.ts", import.meta.url))], {
    cwd: fixture.directory, stdin: new Blob([JSON.stringify(fixture.startup)]), stdout: "ignore", stderr: "inherit",
  });
  let childPid: number | undefined;
  let childGone = false;
  try {
    await awaitRecordedRequest(fixture.directory, AbortSignal.timeout(server.supervision.readiness_timeout_ms));
    childPid = (await Bun.file(join(fixture.directory, "recorded-startup.json")).json()).pid;
    expect(childPid).not.toBe(parent.pid);
    parent.kill("SIGKILL");
    await parent.exited;
    const deadline = AbortSignal.timeout(5000);
    while (true) {
      try { process.kill(childPid!, 0); }
      catch (error) {
        if (!(error instanceof Error) || !("code" in error) || error.code !== "ESRCH") throw error;
        childGone = true;
        break;
      }
      deadline.throwIfAborted();
      await Bun.sleep(10);
    }
    await assertReleased(fixture.inputs.settings.listener.port);
  } finally {
    if (parent.exitCode === null) { parent.kill("SIGKILL"); await parent.exited; }
    if (childPid !== undefined && !childGone) {
      try { process.kill(childPid, "SIGKILL"); }
      catch (error) { if (!(error instanceof Error) || !("code" in error) || error.code !== "ESRCH") throw error; }
    }
    await fixture.close();
  }
}, 60000);

test("a short real child failure preserves existing native diagnostics and its original cause", async () => {
  const fixture = await recordedPlannerProcess();
  try {
    const recorded = await writePlannerOutputRecording(fixture.inputs);
    await writeFile(join(fixture.evidence, "response.json"), JSON.stringify(recorded.response));
    fixture.startup.settings.enabled = false;
    await expect(invokePlannerHttp(fixture.inputs, fixture.startup, {}, fixture.evidence, {
      serverEntry: fixture.serverEntry,
    })).rejects.toMatchObject({ code: "PLANNER_READY_IDENTITY" });
    const collected = await collectWorkflowFiles({
      root: fixture.directory, directory: fixture.evidence,
      identity: { run_id: "2026-10-21-700", attempt: 3, git_sha: fixture.startup.runtime.git_sha },
      registrations: await metadataRegistrations(),
    });
    expect(collected.failures).toEqual([]);
    expect(collected.paths.length).toBeGreaterThan(0);
    expect(await Bun.file(join(fixture.directory, "recorded-request.json")).exists()).toBe(false);
    await assertReleased(fixture.inputs.settings.listener.port);
  } finally { await fixture.close(); }
});

test("a real caller failure retains a separate nonzero child cleanup failure", async () => {
  const fixture = await recordedPlannerProcess();
  try {
    await writeFile(join(fixture.directory, "recorded-cleanup-failure"), "Fail a real post-stop input read");
    let failure: unknown;
    try {
      await invokePlannerHttp(fixture.inputs, fixture.startup, {}, fixture.evidence, {
        serverEntry: fixture.serverEntry,
        beforePlan: async () => {
          await Bun.file(join(fixture.evidence, "missing-caller-input.json")).json();
        },
      });
    } catch (error) { failure = error; }
    if (!(failure instanceof Error) || !("failure" in failure)) throw new Error("The real caller failure must be retained");
    const captured = PlannerFailureSchema.parse(failure.failure);
    expect(captured).toMatchObject({ operation: "workflow", system_code: "ENOENT" });
    expect(captured.causes).toContainEqual(expect.objectContaining({ operation: "listener-close" }));
    const [server] = await readMachineServerEvidence(fixture.evidence);
    expect(server).toMatchObject({ startup: "ready", shutdown: "failed", exit_code: 1,
      cleanup_error_code: "PLANNER_CLEANUP_FAILED" });
    await assertReleased(fixture.startup.settings.listener.port);
  } finally { await fixture.close(); }
});

test("startup rejects executable runtime members, unknown controls and non-loopback listeners", async () => {
  const fixture = await readPlannerStartupRecording();
    expect(PlannerStartupSchema.safeParse({
      ...fixture.startup, runtime: { ...fixture.startup.runtime, clock: () => new Date() },
    }).success).toBe(false);
    expect(HonoServerSettingsSchema.safeParse({
      ...await loadHonoSettings(fixture.inputs.root), hostname: "0.0.0.0",
    }).success).toBe(false);
    expect(PlannerStartupSchema.safeParse({ ...fixture.startup, output_root: "C:\\state" }).success).toBe(false);
});
