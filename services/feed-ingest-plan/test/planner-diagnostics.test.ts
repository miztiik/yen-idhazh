/** Exercise real entity recognition and original error preservation against bounded offline inputs. */
import { expect, test } from "bun:test";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { createCloudEvent, createRootContext, deriveCandidateId, deriveUrlKey, FEED_INGEST_EVENT_VERSION, FeedIngestEventDataSchema, FetchRequestSchema, loadEventSources, PlannerSavedResponseSchema } from "@idhazh/common-contracts";
import { recognizeArticleEntities } from "../src/recognize-article-entities";
import { capturePlannerFailure, combinePlannerFailures, describePlanError, readPlannerResponseError } from "../src/api/plan-failure";
import { retainFailureThroughCleanup } from "../src/api/retain-failure-through-cleanup";
import { prepareProgressEvent } from "../src/logging/structured-logger";
import { retainWorkflowFailure } from "../scripts/retain-workflow-failure";
import { renderExecutionFailure } from "../src/reporting/execution-failure-markdown";
import { createPrivateJsonlWriter } from "../src/write-private-jsonl";

function captureOptions() {
  const context = createRootContext();
  return {
    operation: "recognize-entities" as const,
    execution: { run_id: "2026-11-02-700", attempt: 3, git_sha: "a".repeat(40), traceId: context.traceId, spanId: context.spanId },
    limits: { max_stack_chars: 16384, max_causes: 3 },
  };
}
async function entityRecording() {
  return z.strictObject({
    title: z.string(), article_text: z.string(), article_tail: z.string(),
    excluded_script: z.string(), empty_title: z.string(), empty_body: z.string(),
  }).parse(await Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/article-entities.json", import.meta.url)).json());
}
function identity(execution: ReturnType<typeof captureOptions>["execution"]) {
  return { run_id: execution.run_id, attempt: execution.attempt, traceId: execution.traceId, git_sha: execution.git_sha,
    article_id: deriveUrlKey("https://news.example/second"),
    candidate_id: deriveCandidateId(execution.run_id, "recorded-news", 0),
    feed_id: "recorded-news", observed_at: "2026-11-02T23:00:00Z" };
}

test("real public people, places and organizations APIs retain original names and full body scope", async () => {
  const capture = captureOptions();
  const recorded = await entityRecording();
  const record = recognizeArticleEntities({
    ...identity(capture.execution), title: recorded.title, article_text: recorded.article_text,
    limits: { max_entities: 256, max_entity_chars: 160 },
  }, capture);
  expect(record.status).toBe("complete");
  for (const entity of [
    { kind: "person", scope: "title", text: "Ada Lovelace" },
    { kind: "place", scope: "title", text: "London" },
    { kind: "person", scope: "body", text: "Grace Hopper" },
    { kind: "place", scope: "body", text: "Paris" },
    { kind: "person", scope: "body", text: "Marie Curie" },
    { kind: "place", scope: "body", text: "Tokyo" },
    { kind: "organization", scope: "body", text: "United Nations" },
  ] as const) expect(record.entities).toContainEqual(entity);
  expect(record).not.toHaveProperty("article_text");
  expect(record).not.toHaveProperty("title");
  expect(recorded.title).toBe("Ada Lovelace visits London");
});

test("empty, unavailable and truncated entity evidence have distinct truthful records", async () => {
  const capture = captureOptions();
  const recorded = await entityRecording();
  const empty = recognizeArticleEntities({
    ...identity(capture.execution), title: recorded.empty_title, article_text: recorded.empty_body,
    limits: { max_entities: 256, max_entity_chars: 160 },
  }, capture);
  expect(empty).toMatchObject({ status: "complete", entities: [], failure: null });
  const unavailable = recognizeArticleEntities({
    ...identity(capture.execution), title: recorded.title, article_text: null,
    limits: { max_entities: 256, max_entity_chars: 160 },
  }, capture);
  expect(unavailable).toMatchObject({ status: "incomplete", title_status: "complete", body_status: "unavailable" });
  expect(unavailable.entities.every(entity => entity.scope === "title")).toBe(true);
  const bounded = recognizeArticleEntities({
    ...identity(capture.execution), title: recorded.title, article_text: recorded.article_text,
    limits: { max_entities: 1, max_entity_chars: 5 },
  }, capture);
  expect(bounded.status).toBe("truncated");
  expect(bounded.entities.length).toBeLessThanOrEqual(1);
  expect(bounded.entities.every(entity => entity.text.length <= 5)).toBe(true);
  expect(bounded.omitted_entities).toBeGreaterThan(0);
  expect(bounded.oversized_entities).toBeGreaterThan(0);
});

test("native error frames survive real cleanup refusal without body text or guessed consumer frames", async () => {
  const capture = captureOptions();
  const { execution } = capture;
  const directory = await mkdtemp(join(tmpdir(), "planner-safe-failure-"));
  try {
    const obstruction = join(directory, "obstruction");
    await writeFile(obstruction, "Private input");
    const root = fileURLToPath(new URL("../../../", import.meta.url));
    const error = new TypeError(`Cannot read properties of undefined (reading 'terms')\nPrivate article text, token=private\n    at injected (${join(root, "services", "feed-ingest-plan", "src", "run-feed-plan.ts")}:99999:1)`);
    const original = capturePlannerFailure(error, { ...capture, operation: "select" });
    expect(original.source?.file).toBe("services/feed-ingest-plan/test/planner-diagnostics.test.ts");
    expect(original.source?.line).not.toBe(99999);
    const retained = await retainFailureThroughCleanup(error, { ...capture, operation: "select" }, [
      { operation: "record-run", execute: () => mkdir(join(obstruction, "child")) },
    ]);
    const failure = retained.failure;
    expect(failure).not.toBeNull();
    if (failure === null) throw new Error("Expected retained execution failure");
    expect(failure.source).toEqual(original.source);
    expect(failure).toMatchObject({ error_type: "TypeError", safe_cause: "undefined-value", execution });
    expect(failure.causes).toContainEqual(expect.objectContaining({ operation: "record-run" }));
    const systemCode = failure.causes[0]?.system_code;
    if (systemCode == null) throw new Error("Expected the native filesystem refusal code");
    expect(["ENOENT", "ENOTDIR"]).toContain(systemCode);
    const serialized = JSON.stringify(describePlanError(retained, root));
    expect(serialized).not.toMatch(/[A-Za-z]:[\\/]/);
    expect(serialized).not.toContain("Private article text");
    expect(serialized).not.toContain("token=private");
    expect(serialized).not.toContain("injected");
    const sources = await loadEventSources(new URL("../../../config/typescript-event-sources.json", import.meta.url));
    const event = prepareProgressEvent(createCloudEvent({
      source: sources.planner, type: "planner.progress",
      context: { traceId: execution.traceId, spanId: execution.spanId, links: [] },
      data: { version: FEED_INGEST_EVENT_VERSION, run_id: execution.run_id, operation: "plan", phase: "failed", details: { failure } },
      parseData: value => FeedIngestEventDataSchema.parse(value),
    }));
    expect(event.data.details).not.toHaveProperty("_compliance");
    expect(event.data.details.failure).toEqual(failure);
    const report = renderExecutionFailure(failure);
    expect(report).toContain("Code accessed a missing value");
    expect(report).toContain(systemCode);
    expect(report).not.toContain("Private article text");
    const secondary = capturePlannerFailure(new Error("Secret cleanup message"), { ...capture, operation: "listener-close" });
    const bounded = combinePlannerFailures(failure, secondary, { max_stack_chars: 16384, max_causes: 0 });
    expect(bounded.causes).toEqual([]);
    expect(bounded.omitted_causes).toBeGreaterThan(0);
    await retainWorkflowFailure({ directory, error: retained, capture });
    const saved = PlannerSavedResponseSchema.parse(await Bun.file(join(directory, "response.json")).json());
    expect(saved.failure?.source).toEqual(original.source);
    await retainWorkflowFailure({ directory, error: new Error("Private shutdown message"),
      capture: { ...capture, operation: "listener-close" } });
    const later = PlannerSavedResponseSchema.parse(await Bun.file(join(directory, "response.json")).json());
    expect(later.failure?.source).toEqual(original.source);
    expect(later.failure?.causes.some(cause => cause.operation === "listener-close")).toBe(true);
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test("private JSONL drains a valid prefix and never publishes an invalid or unfinished record", async () => {
  const directory = await mkdtemp(join(tmpdir(), "planner-jsonl-"));
  try {
    const writer = createPrivateJsonlWriter(directory, "run/records.jsonl", z.strictObject({ value: z.int() }));
    await writer.append({ value: 1 });
    await writer.append({ value: 2 });
    await expect(writer.append({ value: "invalid" })).rejects.toThrow();
    expect(await Bun.file(join(directory, "run", "records.jsonl")).exists()).toBe(false);
    await expect(writer.finish()).rejects.toThrow("Private JSONL output did not complete");
    expect(await Bun.file(join(directory, "run", "records.jsonl")).text()).toBe('{"value":1}\n{"value":2}\n');
    expect(await Bun.file(join(directory, "run", "records.jsonl.part")).exists()).toBe(false);
    await expect(writer.append({ value: 3 })).rejects.toThrow("has finished");
    const empty = createPrivateJsonlWriter(directory, "run/empty.jsonl", z.strictObject({ value: z.int() }));
    await empty.finish();
    expect(await Bun.file(join(directory, "run", "empty.jsonl")).exists()).toBe(false);
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test("unknown receiver operations stay unknown through HTTP decoding and workflow retention", async () => {
  const capture = captureOptions();
  const invalid = FetchRequestSchema.safeParse({ fetch_item_type: "feed", feed_id: null });
  if (invalid.success) throw new Error("Expected the real fetch boundary to reject invalid controls");
  const directory = await mkdtemp(join(tmpdir(), "planner-unknown-receiver-"));
  try {
    for (const [index, execution] of [
      { ...capture.execution, spanId: null },
      { ...capture.execution, traceId: null, spanId: null },
    ].entries()) {
      const response = describePlanError(invalid.error, undefined, { ...capture, operation: "fetch", execution });
      const received = readPlannerResponseError(JSON.parse(JSON.stringify(response)), { ...capture, operation: "plan" });
      expect(received.failure?.execution).toEqual(execution);
      const output = join(directory, String(index));
      await retainWorkflowFailure({
        directory: output, error: received,
        capture: { ...capture, operation: "commit-ledgers" },
      });
      const saved = PlannerSavedResponseSchema.parse(await Bun.file(join(output, "response.json")).json());
      expect(saved.failure?.execution).toEqual(execution);
      expect(saved.failure?.operation).toBe("fetch");
      expect(saved.failure?.source).toEqual(response.failure?.source);
    }
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test("native cancellation remains cancellation rather than an unknown planner exception", () => {
  expect(capturePlannerFailure(new DOMException("Private cancellation reason", "AbortError"), captureOptions()))
    .toMatchObject({ error_type: "AbortError", safe_cause: "cancelled" });
});
