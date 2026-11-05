/** Are accepted diagnostics mirrored safely, append-only and optional? */
import { expect, test } from "bun:test";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { join, relative } from "node:path";
import { randomUUID } from "node:crypto";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import type { z } from "zod";
import {
  createCandidateId, createChildContext, createCloudEvent, createRootContext, FEED_INGEST_EVENT_VERSION,
  ArticleFailureDiagnosticSchema, FeedIngestEventDataSchema, HarvestDiagnosticsSchema,
  PlannerRunResponseSchema, readCloudEvent, readFeedIngestEvent, writeTraceContext,
} from "@idhazh/common-contracts";
import { ServerEventDataSchema, ServerEvidenceSchema, serverLogFilename } from "../src/server-evidence";
import type { ApiGroup, ServerRun } from "../src/server-evidence";
import { SafePersistHttpDiagnosticSchema } from "@idhazh/feed-ingest-plan/delivery-diagnostic";
import { MetadataDeliveryResultSchema } from "@idhazh/feed-ingest-plan/delivery-contracts";
import { createDeliveryCompletionEvent, DeliveryCompletionDiagnosticSchema } from "../src/delivery-completion-diagnostic";
import { recordedPlannerProcess } from "../../feed-ingest-plan/test/planner-process-recordings";
import { hostWriter } from "../../feed-ingest-plan/scripts/feed-ingest-plan-metadata";
import { FingerprintResponseSchema } from "@idhazh/host-fingerprints/response";
import { FINGERPRINT_PATH } from "@idhazh/host-fingerprints/api";
import { loadHonoSettings } from "../src/load-settings";
import { readServerEvidence } from "../src/read-server-evidence";
import { superviseApiTask } from "../src/supervise-api-task";
import { TaskProfileSchema } from "@idhazh/host-probes/profile";
import { readReportFailureEvidence } from "../../feed-ingest-plan/scripts/feed-ingest-plan-report-evidence";
import { renderWorkflowPlanMarkdown } from "../../feed-ingest-plan/scripts/feed-ingest-plan-report";
import { prepareProgressEvent } from "../../feed-ingest-plan/src/logging/structured-logger";

async function writeEvents(directory: string, run: ServerRun, moduleLine?: string, moduleLines?: string[], group?: ApiGroup) {
  const child = Bun.spawn([process.execPath, fileURLToPath(new URL("./write-server-events.ts", import.meta.url))], {
    stdin: new Blob([JSON.stringify({ directory, run, source: "/fixtures/typescript-api",
      ...(moduleLine === undefined ? {} : { module_line: moduleLine }),
      ...(moduleLines === undefined ? {} : { module_lines: moduleLines }),
      group: group ?? (moduleLines === undefined ? "machine" : "planning") })]),
    stdout: "pipe", stderr: "pipe",
  });
  const [output, error, code] = await Promise.all([
    new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited,
  ]);
  expect(code, error).toBe(0);
  return { result: JSON.parse(output), error, pid: child.pid };
}

test("delivery completions retain native facts and full request context instead of supervision", async () => {
  const directory = await mkdtemp(join(tmpdir(), "api-delivery-events-"));
  const run = { run_id: "700", attempt: 3, started_at: "2026-11-05T00:00:00Z", context: createRootContext() };
  const linked = createRootContext();
  const context = createChildContext(createRootContext({ traceState: "diagnostics=retained" }), {
    links: [{ traceId: linked.traceId, spanId: linked.spanId }],
  });
  const diagnostic = {
    event: "safe_persist_http_completed", run_number: "701", attempt: 4,
    status: "landed", commit: "a".repeat(40), files: 2, context,
  };
  try {
    const result = await writeEvents(directory, run, JSON.stringify(diagnostic), undefined, "delivery");
    const events = result.error.trim().split("\n").map(line => JSON.parse(line));
    const completion = events.find(event => event.type === diagnostic.event);
    expect(completion.data).toEqual({
      server_name: "hono-server", group: "delivery", run_id: diagnostic.run_number, attempt: diagnostic.attempt,
      phase: "operation_completed", status: diagnostic.status, commit: diagnostic.commit, files: diagnostic.files,
      context, severity: "info", duration_ms: null, exit_code: null, code: null,
    });
    expect(completion).toMatchObject(writeTraceContext(context));
    expect(completion.source).toBe("/fixtures/typescript-api");
    const lifecycle = events.filter(event => event.type === "hono.server")
      .map(event => readCloudEvent(event, value => ServerEventDataSchema.parse(value)));
    expect(lifecycle.map(event => event.data.phase)).toEqual(["starting", "ready", "stopped"]);
    expect(lifecycle.every(event => event.traceparent === lifecycle[0]!.traceparent)).toBe(true);
    expect(lifecycle[0]!.traceparent).not.toBe(completion.traceparent);
    expect(await readFile(join(directory, serverLogFilename(run)), "utf8")).toBe(result.error);
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test("completion and lifecycle shapes remain strict while native statuses and ancillary fields retain their meaning", () => {
  const paths = ["raw/generated.parquet"];
  const nativeResults = [
    { status: "landed", commit: "a".repeat(40), files: 1, paths },
    { status: "already-on-main", commit: "b".repeat(64), files: 1, paths },
    { status: "no-changes", commit: null, files: 0, paths: [] },
    { status: "failed", commit: null, files: 1, paths },
  ].map(result => MetadataDeliveryResultSchema.parse(result));
  for (const result of nativeResults) {
    const diagnostic = SafePersistHttpDiagnosticSchema.parse({
      event: "safe_persist_http_completed", run_number: "701", attempt: 4,
      status: result.status, commit: result.commit, files: result.files, context: createRootContext(),
    });
    const event = createDeliveryCompletionEvent({ source: "/fixtures/typescript-api", diagnostic });
    expect(readCloudEvent(event, value => DeliveryCompletionDiagnosticSchema.parse(value))).toEqual(event);
    expect(event.data).toMatchObject({ status: result.status, commit: result.commit, files: result.files,
      context: diagnostic.context, severity: "info", duration_ms: null, exit_code: null, code: null });
    expect(ServerEventDataSchema.safeParse(event.data).success).toBe(false);
    for (const invalid of [
      { phase: "ready" }, { group: "planning" }, { run_id: "local-run" }, { context: undefined },
      { context: null }, { paths }, { pid: process.pid }, { status: "completed" }, { commit: "A".repeat(40) },
      { files: -1 }, { severity: "debug" }, { duration_ms: -1 }, { duration_ms: Infinity },
      { exit_code: 0.5 }, { code: "unsafe text" },
    ]) expect(DeliveryCompletionDiagnosticSchema.safeParse({ ...event.data, ...invalid }).success).toBe(false);
    const ancillary = createDeliveryCompletionEvent({
      source: event.source, diagnostic, severity: "warning", duration_ms: 0, exit_code: -1, code: "RECORDED_FAILURE",
    });
    expect(ancillary.data).toMatchObject({ severity: "warning", duration_ms: 0, exit_code: -1, code: "RECORDED_FAILURE" });
    const lifecycle = {
      server_name: "hono-server", group: "delivery", run_id: "local-run", attempt: 1,
      phase: "ready", severity: "info", duration_ms: null, exit_code: null, code: null,
    } satisfies z.infer<typeof ServerEventDataSchema>;
    expect(ServerEventDataSchema.parse(lifecycle)).toEqual(lifecycle);
    expect(ServerEventDataSchema.safeParse({ ...lifecycle, phase: "operation_completed" }).success).toBe(false);
    expect(ServerEventDataSchema.safeParse({ ...lifecycle, context: diagnostic.context }).success).toBe(false);
    expect(ServerEventDataSchema.safeParse({ ...lifecycle, status: result.status }).success).toBe(false);
  }
});

test("invalid or missing completion context and unlisted fields produce safe typed warnings, not fallback completions", async () => {
  const directory = await mkdtemp(join(tmpdir(), "api-invalid-delivery-"));
  const run = { run_id: "700", attempt: 3, started_at: "2026-11-05T00:00:00Z", context: createRootContext() };
  const diagnostic = {
    event: "safe_persist_http_completed", run_number: "701", attempt: 4,
    status: "no-changes", commit: null, files: 0, context: createRootContext(),
  };
  const invalid = [
    { context: undefined }, { context: null }, { context: { ...diagnostic.context, spanId: "0".repeat(16) } },
    { context: { ...diagnostic.context, links: undefined } },
    { paths: ["PRIVATE_PATH"] }, { headers: { authorization: "PRIVATE_HEADER" } }, { pid: process.pid },
    { status: "PRIVATE_STATUS" }, { commit: "PRIVATE_COMMIT" }, { files: -1 }, { run_number: undefined },
    { attempt: 0 },
  ];
  try {
    const result = await writeEvents(directory, run, undefined,
      invalid.map(fields => JSON.stringify({ ...diagnostic, ...fields })), "delivery");
    const events = result.error.trim().split("\n")
      .map(line => readCloudEvent(JSON.parse(line), value => ServerEventDataSchema.parse(value)));
    expect(events.filter(event => event.data.phase === "module_failed")).toHaveLength(invalid.length);
    expect(events.filter(event => event.data.phase === "module_failed").every(event =>
      event.data.severity === "warning" && event.data.code === "CHILD_DIAGNOSTIC_INVALID")).toBe(true);
    expect(events.every(event => event.type === "hono.server")).toBe(true);
    expect(result.error).not.toContain("PRIVATE_");
    expect(result.error).not.toContain('"pid"');
    expect(await readFile(join(directory, serverLogFilename(run)), "utf8")).toBe(result.error);
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test("terminal article diagnostics retain their original occurrence and operation through real stderr and mirror", async () => {
  const directory = await mkdtemp(join(tmpdir(), "api-article-events-"));
  const run = { run_id: "700", attempt: 3, started_at: "2026-11-05T00:00:00Z", context: createRootContext() };
  const event = createCloudEvent({
    source: "/fixtures/planner", type: "planner.progress", context: createRootContext(),
    data: {
      version: FEED_INGEST_EVENT_VERSION, run_id: "2026-11-05-700", operation: "parse", phase: "failed",
      details: {
        attempt: 3, feed_id: "recorded-news", candidate_id: createCandidateId(), url_key: "a".repeat(64),
        stage: "harvest-feeds", reason_code: "EXTRACT_FAILED",
        diagnostics: HarvestDiagnosticsSchema.parse({
          http_status: 200, extraction_failure: "parser-failed", failure_code: "unknown",
          stopped_stage: "extract", detail: "parser-failed", extract_ms: 0,
        }),
      },
    },
    parseData: value => FeedIngestEventDataSchema.parse(value),
  });
  try {
    const result = await writeEvents(directory, run, JSON.stringify(event));
    const lines = result.error.trim().split("\n").map(line => JSON.parse(line));
    expect(lines[1]).toEqual(event);
    expect(lines).toHaveLength(3);
    expect(await readFile(join(directory, serverLogFilename(run)), "utf8")).toBe(result.error);
    expect(result.result.available).toBe(true);
    const invalid = await writeEvents(directory, run, JSON.stringify(prepareProgressEvent({
      ...event, data: { ...event.data, details: { ...event.data.details, title: "PRIVATE_TITLE" } },
    })));
    expect(invalid.error).not.toContain("PRIVATE_TITLE");
    expect(invalid.error).toContain("CHILD_DIAGNOSTIC_INVALID");
    const blocked = join(directory, "blocked");
    await mkdir(join(blocked, serverLogFilename(run)), { recursive: true });
    const unavailable = await writeEvents(blocked, run, JSON.stringify(event));
    expect(unavailable.result.available).toBe(false);
    expect(unavailable.error.trim().split("\n").map(line => JSON.parse(line))).toContainEqual(event);
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test("real parser, empty, quality, missing-title and fetch failures survive stderr, mirror readback and the native report", async () => {
  const directory = await mkdtemp(join(tmpdir(), "api-article-report-"));
  try {
    const child = Bun.spawn([process.execPath, fileURLToPath(new URL(
      "../../feed-ingest-plan/test/write-article-failure-events.ts", import.meta.url,
    ))], { stdin: new Blob([JSON.stringify({ directory })]), stdout: "pipe", stderr: "pipe" });
    const [output, stderr, code] = await Promise.all([
      new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited,
    ]);
    expect(code, stderr).toBe(0);
    const response = PlannerRunResponseSchema.parse(JSON.parse(output).response);
    const before = structuredClone(response);
    const nativeLines = stderr.trim().split("\n");
    const native = nativeLines.map(line => readFeedIngestEvent(JSON.parse(line))).flatMap(event => {
      const parsed = ArticleFailureDiagnosticSchema.safeParse(event);
      return parsed.success ? [parsed.data] : [];
    });
    expect(native).toHaveLength(9);
    expect(new Set(native.map(event => event.data.details.candidate_id)).size).toBe(9);
    const run = { run_id: response.run_id.slice(11), attempt: response.attempt,
      started_at: response.started_at, context: createRootContext() };
    const mirrored = await writeEvents(directory, run, undefined, nativeLines);
    const readback = mirrored.error.trim().split("\n").flatMap(line => {
      const parsed = ArticleFailureDiagnosticSchema.safeParse(JSON.parse(line));
      return parsed.success ? [parsed.data] : [];
    });
    expect(readback).toEqual(native);
    expect(await readFile(join(directory, serverLogFilename(run)), "utf8")).toBe(mirrored.error);
    await writeFile(join(directory, "hono-server-planning.json"), JSON.stringify(ServerEvidenceSchema.parse({
      version: "2026-11-04", server_name: "hono-server", group: "planning",
      run_id: run.run_id, attempt: run.attempt, started_at: run.started_at,
      pid: mirrored.pid, startup: "not_started", startup_ms: null,
      shutdown: "stopped", exit_code: 0, log_filename: mirrored.result.filename, log_available: mirrored.result.available,
      error_code: null, cleanup_error_code: null,
    })));
    const evidence = await readReportFailureEvidence({ directory, response });
    expect(evidence.article_diagnostics).toEqual(native);
    expect(evidence.articles).toHaveLength(8);
    const paths = response.files.rejected_articles?.files.map(file => join(directory, "state", file.path)) ?? [];
    const bytes = await Promise.all(paths.map(path => readFile(path)));
    const report = renderWorkflowPlanMarkdown({ response, failures: evidence });
    const folded = report.markdown.match(/```json\n([\s\S]*?)\n```/);
    expect(JSON.parse(folded![1]!)).toEqual(native);
    const attention = report.markdown.split("<details>")[0]!;
    for (const cause of ["missing document root", "empty content", "too short", "missing title"]) {
      expect(attention).toContain(cause);
    }
    expect(native.find(event => event.data.operation === "quality")?.data.details.diagnostics).toMatchObject({
      warnings: ["malformed-json-ld"], quality: { too_short: true, rejected: true, token_count: null },
    });
    expect(native.find(event => event.data.details.reason_code === "EXTRACT_EMPTY")?.data.details.diagnostics.quality).toBeNull();
    expect(JSON.stringify(native)).not.toMatch(/PRIVATE_|https?:\/\/|article_text|<html>/);
    expect(report.markdown).not.toContain("PRIVATE_");
    expect(response).toEqual(before);
    expect(await Promise.all(paths.map(path => readFile(path)))).toEqual(bytes);
  } finally { await rm(directory, { recursive: true, force: true }); }
});

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
    for (const event of events) expect(event.data).not.toHaveProperty("pid");
    expect(new Set(events.map(event => event.id)).size).toBe(events.length);
    expect(events.filter(event => event.data.phase === "starting")).toHaveLength(2);
    expect(events.every(event => event.source === "/fixtures/typescript-api")).toBe(true);
    expect(events.find(event => event.data.code === "RECORDED_FAILURE")?.data.severity).toBe("error");
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test("a real successful default profile report is not a server error or a repeated measurement dump", async () => {
  const child = Bun.spawn([process.execPath, fileURLToPath(new URL("./profile-report-recording.ts", import.meta.url))], {
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
    expect(evidence.pid).toBeGreaterThan(0);
    expect(ServerEvidenceSchema.safeParse({
      ...evidence, log_filename: serverLogFilename({ ...run, attempt: 4 }),
    }).success).toBe(false);
    await expect(readServerEvidence(fixture.evidence, { run_id: "700", attempt: 4 })).rejects.toThrow("invocation");
  } finally { await fixture.close(); }
});
