/** Are accepted diagnostics mirrored safely, append-only and optional? */
import { expect, test } from "bun:test";
import { mkdir, mkdtemp, readFile, rm } from "node:fs/promises";
import { join, relative } from "node:path";
import { randomUUID } from "node:crypto";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { createRootContext, readCloudEvent } from "@idhazh/common-contracts";
import { ServerEventDataSchema, ServerEvidenceSchema, serverLogFilename } from "../src/server-evidence";
import type { ServerRun } from "../src/server-evidence";
import { recordedPlannerProcess } from "../../feed-ingest-plan/test/planner-process-recordings";
import { hostWriter } from "../../feed-ingest-plan/scripts/feed-ingest-plan-metadata";
import { FingerprintResponseSchema } from "@idhazh/host-fingerprints/response";
import { FINGERPRINT_PATH } from "@idhazh/host-fingerprints/api";
import { loadHonoSettings } from "../src/load-settings";
import { readServerEvidence } from "../src/read-server-evidence";
import { superviseApiTask } from "../src/supervise-api-task";

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
      event: "planner_error", code: "RECORDED_FAILURE", article_text: "PRIVATE_BODY",
      headers: { authorization: "PRIVATE_HEADER" },
    }));
    const second = await writeEvents(directory, run);
    const text = await readFile(join(directory, serverLogFilename(run)), "utf8");
    expect(text).toBe(first.error + second.error);
    expect(first.result.available).toBe(true);
    expect(text).not.toContain("PRIVATE_BODY");
    expect(text).not.toContain("PRIVATE_HEADER");
    const events = text.trim().split("\n").map(line => readCloudEvent(JSON.parse(line), value => ServerEventDataSchema.parse(value)));
    expect(new Set(events.map(event => event.id)).size).toBe(events.length);
    expect(events.filter(event => event.data.phase === "starting")).toHaveLength(2);
    expect(events.every(event => event.source === "/fixtures/typescript-api")).toBe(true);
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test("an unavailable file is a safe stderr warning and does not change successful work", async () => {
  const directory = await mkdtemp(join(tmpdir(), "api-events-"));
  const run = { run_id: "700", attempt: 3, started_at: "2026-11-04T00:00:00Z", context: createRootContext() };
  try {
    await mkdir(join(directory, serverLogFilename(run)));
    const { result, error } = await writeEvents(directory, run);
    expect(result.available).toBe(false);
    const events = error.trim().split("\n").map(line => readCloudEvent(JSON.parse(line), value => ServerEventDataSchema.parse(value)));
    expect(events.filter(event => event.data.phase === "log_unavailable")).toHaveLength(1);
    expect(events.at(-1)?.data).toMatchObject({ phase: "stopped", exit_code: 0 });
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test("a failed file mirror does not stop a real machine-only child or its fingerprint write", async () => {
  const fixture = await recordedPlannerProcess();
  const run = { run_id: "700", attempt: 3, started_at: fixture.startup.runtime.captured_at, context: createRootContext() };
  try {
    const settingsPath = join(fixture.directory, "config", "idhazh.json");
    const selected = await Bun.file(settingsPath).json();
    selected.observability.host_fingerprint_placement_enabled = false;
    selected.observability.host_fingerprint_bandwidth_jobs = [];
    await Bun.write(settingsPath, JSON.stringify(selected));
    await mkdir(join(fixture.evidence, serverLogFilename(run)));
    const result = await superviseApiTask({
      root: fixture.directory, kind: "TYPESCRIPT_API",
      startup: {
        group: "machine", nonce: randomUUID(), server: await loadHonoSettings(fixture.directory),
        directory: relative(fixture.directory, fixture.evidence).replaceAll("\\", "/"),
        state_root: relative(fixture.directory, fixture.inputs.outputRoot).replaceAll("\\", "/"),
        supervision: fixture.inputs.settings.supervision, run,
      },
      request: async (origin, signal) => {
        const response = await fetch(new URL(FINGERPRINT_PATH, origin), {
          method: "POST", headers: { "content-type": "application/json" }, signal,
          body: JSON.stringify({ date: "2026-10-21", writer: hostWriter({
            run_id: "2026-10-21-700", attempt: 3, git_sha: fixture.startup.runtime.git_sha,
          }) }),
        });
        expect(response.status).toBe(200);
        return FingerprintResponseSchema.parse(await response.json());
      },
    });
    expect(result.status).toBe("written");
    const [evidence] = await readServerEvidence(fixture.evidence);
    expect(evidence).toMatchObject({ startup: "ready", shutdown: "stopped", log_available: false, error_code: null });
    if (evidence === undefined) throw new Error("The real child must retain its same-run server outcome");
    expect(ServerEvidenceSchema.safeParse({
      ...evidence, log_filename: serverLogFilename({ ...run, attempt: 4 }),
    }).success).toBe(false);
    await expect(readServerEvidence(fixture.evidence, { run_id: "700", attempt: 4 })).rejects.toThrow("invocation");
  } finally { await fixture.close(); }
});
