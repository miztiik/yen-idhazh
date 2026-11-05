/** Are accepted diagnostics mirrored safely, append-only and optional? */
import { expect, test } from "bun:test";
import { mkdir, mkdtemp, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { createRootContext, readCloudEvent } from "@idhazh/common-contracts";
import { ServerEventDataSchema, serverLogFilename } from "../src/server-evidence";
import type { ServerRun } from "../src/server-evidence";

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
    const text = await readFile(join(directory, serverLogFilename(run)), "utf8");
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
    await mkdir(join(directory, serverLogFilename(run)));
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
