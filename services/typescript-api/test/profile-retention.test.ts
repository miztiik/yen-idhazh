/** Do interrupted native measurements survive graceful manager shutdown and process exit? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { createRootContext, writeTraceContext } from "@idhazh/common-contracts";
import { START_TASK_PROFILE_PATH } from "@idhazh/host-probes/api";
import { TaskProfileSchema } from "@idhazh/host-probes/profile";
import { StartTaskProfileResponseSchema } from "../../host-probes/src/api/task-command-schema";
import { parseProcessStat } from "../../host-probes/src/task-profile/process-stat";
import { recordedPlannerProcess } from "../../feed-ingest-plan/test/planner-process-recordings";
import { renderServerEvidence } from "../../feed-ingest-plan/scripts/feed-ingest-plan-server-report";
import { prepareServerArtifacts } from "../../feed-ingest-plan/scripts/feed-ingest-plan-server-artifacts";
import { ApiReadySchema } from "../src/api-startup";
import { loadHonoSettings } from "../src/load-settings";
import { readServerEvidence } from "../src/read-server-evidence";
import { superviseApiTask } from "../src/supervise-api-task";
import { ServerEvidenceSchema } from "../src/server-evidence";

test("shutdown-only native profile data survives manager cleanup and the owned process exit", async () => {
  const fixture = await recordedPlannerProcess();
  const run = { run_id: "700", attempt: 3, started_at: fixture.startup.runtime.captured_at, context: createRootContext() };
  try {
    const result = await superviseApiTask({
      root: fixture.directory, kind: "TYPESCRIPT_API",
      serverEntry: fileURLToPath(new URL("./profile-api-server-recording.ts", import.meta.url)),
      startup: {
        group: "machine", nonce: randomUUID(), server: await loadHonoSettings(fixture.directory),
        directory: relative(fixture.directory, fixture.evidence).replaceAll("\\", "/"),
        state_root: relative(fixture.directory, fixture.inputs.outputRoot).replaceAll("\\", "/"),
        supervision: fixture.inputs.settings.supervision, run,
      },
      request: async (origin, signal) => {
        const health = await fetch(new URL("/health", origin), { signal });
        const ready = ApiReadySchema.parse((await health.json()).identity);
        const input = await Bun.file(new URL("../../../tests/fixtures/host-probes/process-inputs.json", import.meta.url)).json();
        const pin = parseProcessStat(ready.pid, input.stat.replace("4242 ", `${ready.pid} `));
        if (pin.reason !== null) throw new Error("The named process recording must contain its PID pin");
        const response = await fetch(new URL(START_TASK_PROFILE_PATH, origin), {
          method: "POST", signal,
          headers: { "content-type": "application/json", ...writeTraceContext(run.context) },
          body: JSON.stringify({
            identity: { pipeline_name: "recorded-work", task_name: "shutdown-profile-retention", run_id: "recorded-run" },
            target: { pid: ready.pid, start_ticks: pin.value.start_ticks },
          }),
        });
        expect(response.status).toBe(200);
        const started = StartTaskProfileResponseSchema.parse(await response.json());
        if (started.status !== "started") throw new Error("The real collector must be active before server shutdown");
        return { started, pid: ready.pid };
      },
    });
    expect(() => process.kill(result.pid, 0)).toThrow();
    const [evidence] = await readServerEvidence(fixture.evidence, { run_id: "700", attempt: 3 });
    expect(evidence).toMatchObject({ startup: "ready", shutdown: "stopped", exit_code: 0 });
    if (evidence === undefined) throw new Error("Graceful server exit must retain its evidence");
    expect(evidence.reported_profiles).toHaveLength(1);
    const profile = TaskProfileSchema.parse(evidence.reported_profiles[0]);
    expect(profile).toMatchObject({
      outcome: "cancelled", end_reason: "service_stopped",
      traceId: result.started.traceId, spanId: result.started.spanId, parentSpanId: run.context.spanId,
      identity: { pipeline_name: "recorded-work", task_name: "shutdown-profile-retention", run_id: "recorded-run" },
    });
    expect(profile.sample_count).toBeGreaterThanOrEqual(2);
    expect(profile.samples.at(-1)?.phase).toBe("closing");
    const { reported_profiles: capturedProfiles, ...earlierEvidence } = evidence;
    expect(capturedProfiles).toHaveLength(1);
    expect(ServerEvidenceSchema.parse(earlierEvidence).reported_profiles).toEqual([]);
    await prepareServerArtifacts({ directory: fixture.evidence, runNumber: "700", attempt: 3 });
    const retained = ServerEvidenceSchema.parse(await Bun.file(
      join(fixture.evidence, "artifacts", "hono-server-machine.json"),
    ).json());
    expect(retained.reported_profiles).toEqual([profile]);
    const report = renderServerEvidence([evidence]);
    expect(report).toContain("Interrupted");
    expect(report).toContain(profile.traceId);
    expect(report).toContain(profile.spanId);
    const logs = await Bun.file(join(fixture.evidence, evidence.log_filename)).text();
    expect(logs).not.toContain("shutdown-profile-retention");
    expect(logs).not.toContain('"samples"');
  } finally { await fixture.close(); }
});
