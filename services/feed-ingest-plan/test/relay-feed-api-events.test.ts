/** Do validated feed diagnostics retain native facts, occurrence and request context? */
import { expect, test } from "bun:test";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import type { z } from "zod";
import {
  createCandidateId, createChildContext, createCloudEvent, createRootContext, FEED_INGEST_EVENT_VERSION,
  ArticleFailureDiagnosticSchema, FeedIngestEventDataSchema, HarvestDiagnosticsSchema,
  PlannerRunResponseSchema, readCloudEvent, readFeedIngestEvent, writeTraceContext,
} from "@idhazh/common-contracts";
import { ServerEventDataSchema, serverLogFilename } from "@idhazh/serve-pipeline-apis/evidence";
import type { ApiGroup, ServerRun } from "@idhazh/serve-pipeline-apis/evidence";
import { MachineServerEvidenceSchema as ServerEvidenceSchema } from "@idhazh/host-probes/machine-evidence";
import { MetadataDeliveryResultSchema } from "../scripts/feed-ingest-plan-delivery-result";
import { createDeliveryCompletionEvent, DeliveryCompletionDiagnosticSchema } from "../scripts/safe-persist-http-diagnostic";
import { readReportFailureEvidence } from "../scripts/feed-ingest-plan-report-evidence";
import { renderWorkflowPlanMarkdown } from "../scripts/feed-ingest-plan-report";
import { prepareProgressEvent } from "../src/logging/structured-logger";

async function writeEvents(directory: string, run: ServerRun, moduleLine?: string, moduleLines?: string[], group?: ApiGroup) {
  const child = Bun.spawn([process.execPath, fileURLToPath(new URL("./write-feed-api-events.ts", import.meta.url))], {
    stdin: new Blob([JSON.stringify({ directory, run, source: "/fixtures/typescript-api",
      ...(moduleLine === undefined ? {} : { module_line: moduleLine }),
      ...(moduleLines === undefined ? {} : { module_lines: moduleLines }),
      group: group ?? "planning" })]),
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
    const input = {
      source: "/fixtures/typescript-api", runNumber: "701", attempt: 4,
      status: result.status, commit: result.commit, files: result.files, context: createRootContext(),
    };
    const event = createDeliveryCompletionEvent(input);
    expect(readCloudEvent(event, value => DeliveryCompletionDiagnosticSchema.parse(value))).toEqual(event);
    expect(event.data).toMatchObject({ status: result.status, commit: result.commit, files: result.files,
      context: input.context, severity: "info", duration_ms: null, exit_code: null, code: null });
    expect(ServerEventDataSchema.safeParse(event.data).success).toBe(false);
    for (const invalid of [
      { phase: "ready" }, { group: "planning" }, { run_id: "local-run" }, { context: undefined },
      { context: null }, { paths }, { pid: process.pid }, { status: "completed" }, { commit: "A".repeat(40) },
      { files: -1 }, { severity: "debug" }, { duration_ms: -1 }, { duration_ms: Infinity },
      { exit_code: 0.5 }, { code: "unsafe text" },
    ]) expect(DeliveryCompletionDiagnosticSchema.safeParse({ ...event.data, ...invalid }).success).toBe(false);
    const ancillary = createDeliveryCompletionEvent({
      ...input, severity: "warning", duration_ms: 0, exit_code: -1, code: "RECORDED_FAILURE",
    });
    expect(ancillary.data).toMatchObject({ severity: "warning", duration_ms: 0, exit_code: -1, code: "RECORDED_FAILURE" });
    const lifecycle = {
      server_name: "hono-server", group: "delivery", run_id: "local-run", attempt: 1,
      phase: "ready", severity: "info", duration_ms: null, exit_code: null, code: null,
    } satisfies z.infer<typeof ServerEventDataSchema>;
    expect(ServerEventDataSchema.parse(lifecycle)).toEqual(lifecycle);
    expect(ServerEventDataSchema.safeParse({ ...lifecycle, phase: "operation_completed" }).success).toBe(false);
    expect(ServerEventDataSchema.safeParse({ ...lifecycle, context: input.context }).success).toBe(false);
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
      "./write-article-failure-events.ts", import.meta.url,
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
