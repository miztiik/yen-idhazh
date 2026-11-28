/** Do validated feed diagnostics retain native facts, occurrence and request context? */
import { expect, test } from "bun:test";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { Hono } from "hono";
import type { z } from "zod";
import {
  createCandidateId, createChildContext, createCloudEvent, createRootContext, deriveUrlKey, FEED_INGEST_EVENT_VERSION,
  ArticleFailureDiagnosticSchema, FeedIngestEventDataSchema, HarvestDiagnosticsSchema,
  PLANNER_API_PATHS, PLANNER_API_PREFIX, PLANNER_WORKFLOW_FAILURE_TYPE, PlannerWorkflowFailureSchema,
  PlannerRunResponseSchema, readCloudEvent, readFeedIngestEvent, writeTraceContext,
} from "@idhazh/common-contracts";
import type { FeedIngestEvent } from "@idhazh/common-contracts";
import { createApiApp } from "@idhazh/serve-pipeline-apis/app";
import { ServerEventDataSchema, serverLogFilename } from "@idhazh/serve-pipeline-apis/evidence";
import { HonoServerConfigSchema } from "@idhazh/serve-pipeline-apis/settings";
import type { ApiGroup, ServerRun } from "@idhazh/serve-pipeline-apis/evidence";
import { MachineServerEvidenceSchema as ServerEvidenceSchema } from "@idhazh/host-probes/machine-evidence";
import { MetadataDeliveryResultSchema } from "../scripts/feed-ingest-plan-delivery-result";
import {
  createDeliveryCompletionEvent, createDeliveryFailureEvent, DeliveryCompletionDiagnosticSchema, readDeliveryEvent,
} from "../scripts/safe-persist-http-diagnostic";
import { createFingerprintCompletionEvent, createFingerprintFailureEvent } from "@idhazh/host-fingerprints/diagnostic";
import { createProbeCompletionEvent, createProbeFailureEvent } from "@idhazh/host-probes/diagnostic";
import { DELIVERY_EVENT_SOURCE, PLANNER_EVENT_SOURCE } from "../src/declare-event-source";
import { readReportFailureEvidence } from "../scripts/feed-ingest-plan-report-evidence";
import { renderWorkflowPlanMarkdown } from "../scripts/feed-ingest-plan-report";
import { createStageLogger, prepareProgressEvent } from "../src/logging/structured-logger";
import { readArticleFailureDiagnostics } from "../scripts/read-article-failure-diagnostics";
import { createPlanTestServer } from "./plan-test-server";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";
import { recordedPersistenceBatch } from "./persistence-recordings";
import { executePersistence } from "../src/api/persistence-operation";
import { operationLink, operationMetadata } from "../src/api/operation-context";
import { selectedArtifactPath } from "../src/selected-artifact-path";
import { readDiscoveredEvidence } from "../src/read-ledger-history/read-discovered-evidence";

const listeners = HonoServerConfigSchema.parse(await Bun.file(
  new URL("../../../config/hono-server.json", import.meta.url),
).json()).listeners;

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

function workflowOccurrence(event: FeedIngestEvent) {
  const { data, ...envelope } = event;
  return PlannerWorkflowFailureSchema.parse({ ...envelope, type: PLANNER_WORKFLOW_FAILURE_TYPE, data: data.details.workflow_failure });
}

test("the workflow retains failed dispatches even after recovery and distinguishes terminal fetch and policy refusal", async () => {
  const recovered = source({ url: "https://news.example/recovered.xml", publisher_id: "recorded-publisher" });
  const terminal = source({ id: "recorded-unavailable", url: "https://unavailable.example/feed.xml" });
  const edge = "https://edge.example./PRIVATE_PATH?token=PRIVATE_QUERY";
  const f = await recordedPlan([recovered, terminal], [{ id: "recorded-publisher", display_name: "Recorded Publisher" }]);
  const run = { run_id: f.runtime.run_number!, attempt: 3, started_at: f.runtime.clock!().toISOString(),
    context: createRootContext({ traceState: "relay=retained" }) };
  f.runtime.attempt = run.attempt;
  f.inputs.harvest.config.harvest.concurrency = 1;
  f.inputs.harvest.extraction.max_retries = 1;
  f.inputs.harvest.extraction.backoff_initial_seconds = 0.01;
  f.inputs.harvest.config.harvest.request_headers.secondary = null;
  f.inputs.harvest.config.harvest.url_exclusions = [{
    host: "news.example", path_prefix: "/PRIVATE_BLOCKED", include_subdomains: false,
  }];
  f.transport.recordings.responses[recovered.url] = [{ status: 302, body: "", location: edge }];
  f.transport.recordings.responses[edge] = [
    { status: 429, body: "PRIVATE_BODY", headers: { "retry-after": "PRIVATE_HEADER" } },
    { status: 200, body: `<rss version="2.0"><channel><title>Recorded feed</title>
      <item><title>Blocked story</title><link>https://news.example/PRIVATE_BLOCKED/story</link></item>
      </channel></rss>` },
  ];
  f.transport.recordings.responses[terminal.url] = [
    { error: "ECONNRESET" }, { status: 404, body: "PRIVATE_BODY" },
  ];
  const app = createPlanTestServer(f.inputs, f.runtime);
  try {
    const response = await app.request(`${PLANNER_API_PREFIX}${PLANNER_API_PATHS.plan}`, {
      method: "POST", headers: { "content-type": "application/json", ...writeTraceContext(run.context) }, body: "{}",
    });
    expect(response.status).toBe(200);
    expect(PlannerRunResponseSchema.parse(await response.json()).planning_complete).toBe(true);
    expect(f.transport.requests.map(request => request.url.href)).toEqual([recovered.url, edge, edge, terminal.url, terminal.url]);
    const failed = f.events.filter(event => event.data.phase === "failed");
    const result = await writeEvents(f.directory, run, undefined, f.events.map(event => JSON.stringify(event)));
    const mirrored = result.error.trim().split("\n").map(line => JSON.parse(line));
    const native = mirrored.filter(event => event.type === PLANNER_WORKFLOW_FAILURE_TYPE).map(event => PlannerWorkflowFailureSchema.parse(event));
    expect(native).toEqual(failed.map(workflowOccurrence));
    expect(native.map(event => event.data)).toMatchObject([
      { kind: "failed-dispatch", operation: "request-attempt", document_kind: "feed",
        feed_id: recovered.id, publisher_id: recovered.publisher_id, document_id: deriveUrlKey(recovered.url),
        destination_domain: "edge.example", http_status: 429, cause: "http", error_code: null, retry: 0, sequence: 3 },
      { kind: "failed-dispatch", feed_id: terminal.id, publisher_id: null, destination_domain: "unavailable.example",
        http_status: null, cause: "network", error_code: "ECONNRESET", retry: 0, sequence: 1 },
      { kind: "failed-dispatch", feed_id: terminal.id, http_status: 404, cause: "http", retry: 1, sequence: 2 },
      { kind: "document-failure", operation: "fetch", document_kind: "feed", feed_id: terminal.id,
        document_id: deriveUrlKey(terminal.url), destination_domain: "unavailable.example", http_status: 404, cause: "http" },
    ]);
    expect(mirrored.filter(event => event.type !== PLANNER_WORKFLOW_FAILURE_TYPE).map(event => event.data.phase))
      .toEqual(["starting", "stopped"]);
    expect(result.error).not.toContain("PRIVATE_");
    expect(await readFile(join(f.directory, serverLogFilename("planning", run)), "utf8")).toBe(result.error);

    // Independent document requests use their own run identity, even with the same trace.
    const beforeRefusal = f.events.length;
    const refused = await app.request(`${PLANNER_API_PREFIX}${PLANNER_API_PATHS.fetch}`, {
      method: "POST", headers: { "content-type": "application/json", ...writeTraceContext(run.context) },
      body: JSON.stringify({ fetch_item_type: "article", feed_id: recovered.id, url: "https://news.example/PRIVATE_BLOCKED/story" }),
    });
    expect(refused.status).toBe(409);
    expect(await refused.json()).toMatchObject({ code: "ARTICLE_EXCLUDED" });
    const policyEvents = f.events.slice(beforeRefusal);
    const documentRun = { ...run, run_id: BigInt(`0x${run.context.traceId}`).toString() };
    const policyRelay = await writeEvents(f.directory, documentRun, undefined, policyEvents.map(event => JSON.stringify(event)));
    const policyReadback = policyRelay.error.trim().split("\n").map(line => JSON.parse(line))
      .filter(event => event.type === PLANNER_WORKFLOW_FAILURE_TYPE).map(event => PlannerWorkflowFailureSchema.parse(event));
    expect(policyReadback).toEqual(policyEvents.filter(event => event.data.phase === "failed").map(workflowOccurrence));
    expect(policyReadback).toHaveLength(1);
    expect(policyReadback[0]?.data).toMatchObject({
      kind: "policy-refusal", operation: "fetch", document_kind: "article", feed_id: recovered.id, cause: "BLOCKED_URL_MARKER",
    });
    expect(policyRelay.error).not.toContain("PRIVATE_");
    expect(await readFile(join(f.directory, serverLogFilename("planning", documentRun)), "utf8")).toBe(policyRelay.error);
  } finally { await app.close(); await f.close(); }
});

test("native history and planner stage causes stay separate from an actual Hono request exception", async () => {
  const f = await recordedPlan();
  try {
    const batch = await recordedPersistenceBatch(f.inputs, f.runtime);
    const context = batch.context;
    const run = { run_id: context.run_id.slice(11), attempt: context.writer.attempt, started_at: batch.evaluated_at,
      context: createRootContext() };
    const emit = createStageLogger({ ...context, ...operationMetadata(batch) }, f.inputs.event_source, f.runtime.log);
    await readDiscoveredEvidence({
      root: f.directory, now: batch.evaluated_at, registration: f.inputs.registrations.discovered_articles,
      discovered_files: ["raw/discovered-articles/PRIVATE_MISSING.parquet"], discovered_days: [], lookback_days: 1,
      concurrency: 1, log: emit,
    });
    await mkdir(join(f.directory, selectedArtifactPath(f.inputs.settings.inputs.artifact_root, context)), { recursive: true });
    await expect(executePersistence({ links: [operationLink(batch)] }, f.inputs, f.runtime)).rejects.toThrow();
    const requestFailures: unknown[] = [];
    const routes = new Hono();
    routes.post("/PRIVATE_ROUTE", () => { throw new Error("PRIVATE_EXCEPTION"); });
    routes.onError(error => { throw error; });
    const app = createApiApp({
      identity: { event: "typescript_api_ready", nonce: crypto.randomUUID(), pid: process.pid, port: listeners.planning.port,
        group: "planning", modules: ["planning"], enabled: true },
      create: () => ({ fetch: request => routes.fetch(request), maxRequestBodyBytes: 1024, async close() {} }),
      writeEvent: event => { requestFailures.push(event); },
    });
    try {
      const response = await app.fetch(new Request("http://127.0.0.1/PRIVATE_ROUTE?token=PRIVATE_QUERY", {
        method: "POST", headers: { authorization: "PRIVATE_HEADER", ...writeTraceContext(run.context) }, body: "PRIVATE_BODY",
      }));
      expect(response.status).toBe(500);
      expect(await response.json()).toEqual({ code: "API_OPERATION_FAILED" });
    } finally { await app.close(); }
    expect(requestFailures).toHaveLength(1);
    const failed = f.events.filter(event => event.data.phase === "failed");
    const result = await writeEvents(f.directory, run, undefined, [...f.events, ...requestFailures].map(event => JSON.stringify(event)));
    const mirrored = result.error.trim().split("\n").map(line => JSON.parse(line));
    const native = mirrored.filter(event => event.type === PLANNER_WORKFLOW_FAILURE_TYPE).map(event => PlannerWorkflowFailureSchema.parse(event));
    expect(native).toEqual(failed.map(workflowOccurrence));
    expect(native.map(event => event.data)).toContainEqual(expect.objectContaining({
      kind: "history-gap", operation: "history", scope: "planner-ledger", check: "named-file-read",
      cause: "missing", ledger: "discovered-articles", day: null, feed_id: null,
    }));
    expect(native.map(event => event.data)).toContainEqual(expect.objectContaining({
      kind: "stage-failure", operation: "persist", code: "PERSIST_FAILED", cause: "system-error", cause_operation: "persist",
    }));
    expect(mirrored.filter(event => event.type === "typescript_api_request_failed")).toEqual(requestFailures);
    expect(mirrored.filter(event => event.type === "hono.server").map(event => event.data.phase)).toEqual(["starting", "stopped"]);
    expect(result.error).not.toContain("PRIVATE_");
    expect(await readFile(join(f.directory, serverLogFilename("planning", run)), "utf8")).toBe(result.error);
  } finally { await f.close(); }
});

test("failed progress with an invalid cause, a forged carrier or an unowned run or attempt is refused visibly", async () => {
  const directory = await mkdtemp(join(tmpdir(), "feed-invalid-workflow-failures-"));
  const run = { run_id: "700", attempt: 3, started_at: "2026-11-05T00:00:00Z", context: createRootContext() };
  const events: FeedIngestEvent[] = [];
  const emit = createStageLogger({ run_id: "2026-11-05-700", writer: { attempt: run.attempt }, ...run.context },
    PLANNER_EVENT_SOURCE, event => { events.push(event); });
  emit("plan", "failed", { failure_code: "PLAN_FAILED" });
  const event = events[0]!;
  const native = workflowOccurrence(event).data;
  const replace = (failure: unknown) => ({ ...event, data: { ...event.data, details: { workflow_failure: failure } } });
  emit("plan", "failed", { workflow_failure: native });
  const invalid = [
    events[1], replace({ ...native, attempt: 4 }), replace({ ...native, run_id: "2026-11-05-701" }),
    replace({ ...native, run_id: "2026-11-04-700" }), replace({ ...native, version: "2026-11-05" }),
    replace({ ...native, operation: "persist" }),
    replace({ ...native, cause: "PRIVATE_EXCEPTION includes untrusted text" }),
    replace({ ...native, headers: { authorization: "PRIVATE_HEADER" } }),
    { ...event, source: "https://example.com/PRIVATE_PATH?token=PRIVATE_QUERY" },
    { ...event, data: { ...event.data, phase: "completed" } },
  ];
  try {
    const result = await writeEvents(directory, run, undefined, invalid.map(value => JSON.stringify(value)));
    const mirrored = result.error.trim().split("\n")
      .map(line => readCloudEvent(JSON.parse(line), value => ServerEventDataSchema.parse(value)));
    expect(mirrored.filter(event => event.data.phase === "module_failed").map(event => event.data.code))
      .toEqual(invalid.map(() => "CHILD_DIAGNOSTIC_INVALID"));
    expect(result.error).not.toContain("PRIVATE_");
    expect(await readFile(join(directory, serverLogFilename("planning", run)), "utf8")).toBe(result.error);
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

test("native delivery and machine events retain their exact producer envelopes through feed relay", async () => {
  const directory = await mkdtemp(join(tmpdir(), "feed-native-events-"));
  const run = { run_id: "700", attempt: 3, started_at: "2026-11-05T00:00:00Z", context: createRootContext() };
  const parent = createRootContext({ traceState: "delivery=retained" });
  const linked = createRootContext();
  const context = createChildContext(parent, { links: [{ traceId: linked.traceId, spanId: linked.spanId }] });
  const completion = createDeliveryCompletionEvent({
    source: DELIVERY_EVENT_SOURCE, runNumber: "701", attempt: 4, status: "no-changes", commit: null, files: 0, context,
  });
  const events = [
    completion, createDeliveryFailureEvent({ context, code: "INVALID_REQUEST" }),
    createDeliveryFailureEvent({ context, code: "CHILD_DIAGNOSTIC_INVALID" }),
    createFingerprintCompletionEvent({ context, status: "written" }), createFingerprintFailureEvent({ context }),
    createProbeCompletionEvent({ context, operation: "sample", outcome: "handled" }),
    ...(["host_probe_failed", "host_probe_cleanup_failed", "host_probe_body_cleanup_failed", "task_profile_failed"] as const)
      .map(type => createProbeFailureEvent({ context, type })),
  ];
  expect(readDeliveryEvent(JSON.parse(JSON.stringify(completion)))).toEqual(completion);
  try {
    const projected = await writeEvents(directory, run, undefined, events.map(event => JSON.stringify(event)), "delivery");
    const readback = projected.error.trim().split("\n").map(line => JSON.parse(line));
    expect(readback.filter(event => event.type !== "hono.server")).toEqual(events);
    expect(readback.filter(event => event.type === "hono.server" && event.data.code === "CHILD_DIAGNOSTIC_INVALID"))
      .toHaveLength(0);
    expect(await readFile(join(directory, serverLogFilename("delivery", run)), "utf8")).toBe(projected.error);
    const server = ServerEvidenceSchema.parse({
      version: "2026-11-07", server_name: "hono-server", group: "delivery",
      listener: listeners.delivery, identity: null, reported_profiles: [],
      run_id: run.run_id, attempt: run.attempt, started_at: run.started_at,
      pid: projected.pid, startup: "not_started", startup_ms: null, shutdown: "stopped", exit_code: 0,
      log_filename: projected.result.filename, log_available: projected.result.available,
      error_code: null, cleanup_error_code: null,
    });
    const evidence = await readArticleFailureDiagnostics({
      directory, servers: [server],
      expected: { run_id: "2026-11-05-700", attempt: run.attempt, traceId: run.context.traceId },
    });
    expect(evidence).toEqual({ article_diagnostics: [], gaps: [] });
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test("native delivery carrier conflicts and unsafe extra fields yield warnings without replacement events", async () => {
  const directory = await mkdtemp(join(tmpdir(), "feed-invalid-native-events-"));
  const run = { run_id: "700", attempt: 3, started_at: "2026-11-05T00:00:00Z", context: createRootContext() };
  const context = createRootContext({ traceState: "delivery=retained" });
  const completion = createDeliveryCompletionEvent({
    source: DELIVERY_EVENT_SOURCE, runNumber: "701", attempt: 4, status: "no-changes", commit: null, files: 0, context,
  });
  const invalid = [
    { ...completion, traceparent: writeTraceContext(createRootContext()).traceparent },
    { ...completion, tracestate: "different=state" }, { ...completion, source: "has spaces" },
    { ...completion, data: { ...completion.data, context: undefined } },
    { ...completion, data: { ...completion.data, context: { ...context, spanId: "0".repeat(16) } } },
    { ...completion, data: { ...completion.data, context: { ...context, links: undefined } } },
    { ...completion, data: { ...completion.data, headers: { authorization: "PRIVATE_HEADER" } } },
    { ...createDeliveryFailureEvent({ context, code: "INVALID_REQUEST" }), data: { code: "PRIVATE_EXCEPTION text" } },
    { ...completion, type: "unknown" },
  ];
  try {
    for (const event of invalid) expect(() => readDeliveryEvent(event)).toThrow();
    const projected = await writeEvents(directory, run, undefined, invalid.map(event => JSON.stringify(event)), "delivery");
    const readback = projected.error.trim().split("\n")
      .map(line => readCloudEvent(JSON.parse(line), value => ServerEventDataSchema.parse(value)));
    expect(readback.filter(event => event.data.phase === "module_failed")).toHaveLength(invalid.length);
    expect(readback.filter(event => event.data.phase === "module_failed")
      .every(event => event.data.code === "CHILD_DIAGNOSTIC_INVALID")).toBe(true);
    expect(projected.error).not.toContain("PRIVATE_");
    expect(await readFile(join(directory, serverLogFilename("delivery", run)), "utf8")).toBe(projected.error);
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
    expect(await readFile(join(directory, serverLogFilename("planning", run)), "utf8")).toBe(result.error);
    expect(result.result.available).toBe(true);
    const invalid = await writeEvents(directory, run, JSON.stringify(prepareProgressEvent({
      ...event, data: { ...event.data, details: { ...event.data.details, title: "PRIVATE_TITLE" } },
    })));
    expect(invalid.error).not.toContain("PRIVATE_TITLE");
    expect(invalid.error).toContain("CHILD_DIAGNOSTIC_INVALID");
    const blocked = join(directory, "blocked");
    await mkdir(join(blocked, serverLogFilename("planning", run)), { recursive: true });
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
    expect(await readFile(join(directory, serverLogFilename("planning", run)), "utf8")).toBe(mirrored.error);
    await writeFile(join(directory, "hono-server-planning.json"), JSON.stringify(ServerEvidenceSchema.parse({
      version: "2026-11-07", server_name: "hono-server", group: "planning",
      listener: listeners.planning, identity: null, reported_profiles: [],
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
