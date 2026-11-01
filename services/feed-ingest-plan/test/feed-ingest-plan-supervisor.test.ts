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
    })).rejects.toThrow("could not bind");
    expect(requests).toBe(0);
    expect(await Bun.file(join(fixture.evidence, "response.json")).exists()).toBe(false);
    expect((await fetch(`http://127.0.0.1:${occupied.port}`)).status).toBe(200);
  } finally { await occupied.stop(true); await fixture.close(); }
});

test("a real child with missing authored inputs exits before readiness and is reaped", async () => {
  const fixture = await recordedPlannerProcess();
  try {
    fixture.startup.settings.inputs.taxonomy = "config/absent.json";
    await expect(invokePlannerHttp(fixture.inputs, fixture.startup, {}, fixture.evidence))
      .rejects.toThrow();
    await assertReleased(fixture.inputs.settings.listener.port);
  } finally { await fixture.close(); }
});

test("expired readiness cancels startup and leaves no listener", async () => {
  const fixture = await recordedPlannerProcess();
  try {
    fixture.inputs.settings.supervision.readiness_timeout_ms = 1;
    fixture.startup.settings.supervision.readiness_timeout_ms = 1;
    await expect(invokePlannerHttp(fixture.inputs, fixture.startup, {}, fixture.evidence, {
      serverEntry: fixture.serverEntry,
    })).rejects.toThrow("PLANNER_READY_TIMEOUT");
    await assertReleased(fixture.inputs.settings.listener.port);
  } finally { await fixture.close(); }
});

test("identity mismatch refuses HTTP work and closes the owned child", async () => {
  const fixture = await recordedPlannerProcess();
  try {
    // The parent expects a different port; the child must never receive a plan.
    fixture.inputs.settings = {
      ...fixture.inputs.settings,
      listener: { ...fixture.inputs.settings.listener, port: fixture.inputs.settings.listener.port + 1 },
    };
    await expect(invokePlannerHttp(fixture.inputs, fixture.startup, {}, fixture.evidence, {
      serverEntry: fixture.serverEntry,
    })).rejects.toThrow("Readiness does not match");
    expect(await Bun.file(join(fixture.evidence, "response.json")).exists()).toBe(false);
    await assertReleased(fixture.startup.settings.listener.port);
  } finally { await fixture.close(); }
});

test("cancellation during real recorded feed work reaps the child and releases its port", async () => {
  const fixture = await recordedPlannerProcess([source({ url: "https://news.example/timeout" })]);
  const cancellation = new AbortController();
  let pending: ReturnType<typeof invokePlannerHttp> | undefined;
  try {
    fixture.inputs.settings.supervision.shutdown_timeout_ms = 200;
    fixture.startup.settings.supervision.shutdown_timeout_ms = 200;
    pending = invokePlannerHttp(fixture.inputs, fixture.startup, {}, fixture.evidence, {
      serverEntry: fixture.serverEntry, signal: cancellation.signal,
    });
    void pending.catch(() => {});
    const health = `http://127.0.0.1:${fixture.inputs.settings.listener.port}/api/2026-10-31/health`;
    const deadline = AbortSignal.timeout(fixture.inputs.settings.supervision.readiness_timeout_ms);
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
    await expect(pending).rejects.toThrow("Recorded workflow cancellation");
    expect(() => process.kill(identity!.pid, 0)).toThrow();
    await assertReleased(fixture.inputs.settings.listener.port);
  } finally { cancellation.abort(); await pending?.catch(() => {}); await fixture.close(); }
}, 60000);

test("parent disappearance closes the child pipe and the child bounds its own drain", async () => {
  const fixture = await recordedPlannerProcess([source({ url: "https://news.example/timeout" })]);
  fixture.startup.settings.supervision.shutdown_timeout_ms = 200;
  const parent = Bun.spawn([process.execPath, fileURLToPath(new URL("./planner-supervisor-recording.ts", import.meta.url))], {
    cwd: fixture.directory, stdin: new Blob([JSON.stringify(fixture.startup)]), stdout: "ignore", stderr: "inherit",
  });
  let childPid: number | undefined;
  let childGone = false;
  try {
    await awaitRecordedRequest(fixture.directory, AbortSignal.timeout(fixture.startup.settings.supervision.readiness_timeout_ms));
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
    })).rejects.toThrow("HTTP readiness does not match the owned child");
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

test("startup rejects executable runtime members, unknown controls and non-loopback listeners", async () => {
  const fixture = await readPlannerStartupRecording();
    expect(PlannerStartupSchema.safeParse({
      ...fixture.startup, runtime: { ...fixture.startup.runtime, clock: () => new Date() },
    }).success).toBe(false);
    expect(PlannerStartupSchema.safeParse({
      ...fixture.startup, settings: { ...fixture.startup.settings,
        listener: { ...fixture.startup.settings.listener, hostname: "0.0.0.0" } },
    }).success).toBe(false);
    expect(PlannerStartupSchema.safeParse({ ...fixture.startup, output_root: "C:\\state" }).success).toBe(false);
});
