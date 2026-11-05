/** Do actual offline document, persistence and upload paths publish safe, complete JSONL events? */
import { expect, test } from "bun:test";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import type { FeedIngestEvent } from "@idhazh/common-contracts";
import {
  ArticleFailureDiagnosticDetailsSchema, ArticleFailureDiagnosticSchema, createCandidateId, createRootContext, HarvestDiagnosticsSchema,
  loadEventSources, readTraceContext, PLANNER_API_PREFIX,
} from "@idhazh/common-contracts";
import { selectedArtifactPath, rawDocumentContentsFilename } from "../src/selected-artifact-path";
import { createPlanTestServer } from "./plan-test-server";
import { createStageLogger, prepareProgressEvent } from "../src/logging/structured-logger";
import { publishUploadInventory, publishWorkflowUploadInventories } from "../scripts/feed-ingest-plan-upload-inventory";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";
import { recordedPersistenceBatch } from "./persistence-recordings";
import { executePersistence } from "../src/api/persistence-operation";
import { executePartition } from "../src/api/partition-operation";
import { operationLink, operationMetadata } from "../src/api/operation-context";
import { FetchResponseSchema } from "../src/api/document-response.schema";

async function fetchFeed(f: Awaited<ReturnType<typeof recordedPlan>>) {
  const app = createPlanTestServer(f.inputs, f.runtime);
  try {
    const response = await app.request(`${PLANNER_API_PREFIX}/fetch`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({
        feed_id: f.inputs.harvest.sources[0]!.id,
        fetch_item_type: "feed",
      }),
    });
    expect(response.status).toBe(200);
  } finally { await app.close(); }
}

test("standalone document work logs failure addresses only and persistence logs one real write", async () => {
  const f = await recordedPlan();
  const app = createPlanTestServer(f.inputs, f.runtime);
  async function post(operation: string, body: unknown) {
    const response = await app.request(`${PLANNER_API_PREFIX}/${operation}`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
    });
    expect(response.status).toBe(200);
    return response.json();
  }
  try {
    for (const [url, failedOperation] of [["https://news.example/not-found", "fetch"]] as const) {
      const request = {
        feed_id: "recorded-news",
        fetch_item_type: "article", url,
      };
      const fetched = FetchResponseSchema.parse(await post("fetch", request));
      if (fetched.fetch_item_type !== "article") throw new Error("Recorded article request returned a feed");
      const events = f.events.filter(event => readTraceContext({
        traceparent: event.traceparent, tracestate: event.tracestate,
      })?.traceId === fetched.traceId);
      const diagnostics = events.filter(event => ArticleFailureDiagnosticSchema.safeParse(event).success);
      expect(diagnostics).toHaveLength(1);
      expect(diagnostics[0]!.data.details.diagnostics).toMatchObject({ http_status: 404, fetch_failure: "http" });
      const documentEvents = events.filter(event => !ArticleFailureDiagnosticSchema.safeParse(event).success);
      expect(documentEvents.filter(event => event.data.operation === "fetch").map(event => event.data.phase))
        .toEqual(["started", "failed"]);
      for (const event of documentEvents) {
        const { operation, phase, details } = event.data;
        expect(details._compliance).toBeUndefined();
        if (operation === "fetch" || operation === "parse") {
          expect(details.document_id).toBe(fetched.article_id);
          expect(details).not.toHaveProperty("article_id");
        }
        if (operation === failedOperation && phase === "failed") {
          expect(details.article_url).toBe(url);
          expect(details.network_failure).toMatchObject({ requested_url: url,
            final_attempted_url: url, failed_url: url, http_status: 404, request_profile: "firefox" });
        } else if (operation === "request-attempt" && phase === "failed") {
          expect(details.network_failure).toMatchObject({ failed_url: url,
            http_status: 404, attempt: { phase: "target", request_profile: "firefox" } });
        } else expect(JSON.stringify(event)).not.toContain("https://");
      }
    }
    const batch = await recordedPersistenceBatch(f.inputs, f.runtime, { partition_enabled: true });
    const assigned = await executePartition({ links: [operationLink(batch)] }, f.inputs, f.runtime);
    const blocked = join(f.directory, selectedArtifactPath(f.inputs.settings.inputs.artifact_root, batch.context));
    await mkdir(blocked, { recursive: true });
    await expect(executePersistence({ links: [operationLink(assigned.batch)] }, f.inputs, f.runtime)).rejects.toThrow();
    expect(f.events.at(-1)?.data).toMatchObject({ operation: "persist", phase: "failed", details: { failure_code: "PERSIST_FAILED" } });
    await rm(blocked, { recursive: true });
    await expect(executePersistence({ links: [operationLink(assigned.batch)] }, f.inputs, f.runtime)).rejects.toThrow();
    const recovery = await executePartition({ links: [operationLink(batch)] }, f.inputs, f.runtime);
    expect(recovery.batch.context.run_id).not.toBe(assigned.batch.context.run_id);
    const persisted = await executePersistence({ links: [operationLink(recovery.batch)] }, f.inputs, f.runtime);
    const count = f.events.length;
    const repeated = await executePersistence({ links: [operationLink(recovery.batch)] }, f.inputs, f.runtime);
    expect(repeated).toEqual({ ...persisted, ...operationMetadata(repeated) });
    expect(operationLink(repeated)).not.toEqual(operationLink(persisted));
    expect(f.events).toHaveLength(count);
    expect(f.events.filter(event => event.data.operation === "persist").map(event => event.data.phase))
      .toEqual(["started", "failed", "started", "completed"]);
    expect(f.events.at(-1)?.data.details.artifact).toBe(persisted.artifact);
  } finally { await app.close(); await f.close(); }
});

test("the terminal publisher preserves the native object before generic quality checks and refuses unsafe additions", async () => {
  const events: FeedIngestEvent[] = [];
  const source = await loadEventSources(new URL("../../../config/typescript-event-sources.json", import.meta.url));
  const fixture = await Bun.file(new URL(
    "../../../tests/fixtures/feed-ingest-plan/article-terminal-failures.json", import.meta.url,
  )).json();
  const emit = createStageLogger({ run_id: "2026-11-05-700", ...createRootContext() },
    source.planner, event => events.push(event));
  const details = ArticleFailureDiagnosticDetailsSchema.parse({
    attempt: 3, feed_id: "recorded-news", candidate_id: createCandidateId(), url_key: "a".repeat(64),
    stage: "harvest-feeds", reason_code: "EXTRACT_FAILED",
    diagnostics: HarvestDiagnosticsSchema.parse(fixture.quality_diagnostic),
  });
  emit("quality", "failed", details, ["feed_id", "publisher_id"], "https://news.example/private?token=PRIVATE_SECRET");
  const event = ArticleFailureDiagnosticSchema.parse(events[0]);
  expect(event.data.details).toEqual(details);
  expect(event.data.details).not.toHaveProperty("publisher_id");
  expect(event.data.details).not.toHaveProperty("quality_rejection");
  expect(prepareProgressEvent(event)).toEqual(event);
  for (const change of [
    { title: "PRIVATE_TITLE" }, { article_text: "PRIVATE_BODY" }, { diagnostics: {
      ...details.diagnostics, error_code: "PRIVATE_EXCEPTION includes arbitrary exception text",
    } }, { diagnostics: { ...details.diagnostics,
      response_evidence: { ...details.diagnostics.response_evidence, selected_headers: { server: "PRIVATE_HEADER" } },
    } }, { diagnostics: { ...details.diagnostics,
      quality: { ...details.diagnostics.quality, extractor_version: "v".repeat(513) },
    } },
  ]) {
    const rejected = prepareProgressEvent({ ...event, data: { ...event.data, details: { ...details, ...change } } });
    expect(rejected.data.details._compliance).toMatchObject({ status: "NON_COMPLIANT",
      violations: expect.arrayContaining([{ code: "invalid_article_diagnostic", path: "details" }]) });
    expect(rejected.data.details.diagnostics).toBeUndefined();
    expect(JSON.stringify(rejected)).not.toContain("PRIVATE_");
  }
});

test("failed redirected feeds identify the requested URL and final dispatched target", async () => {
  const f = await recordedPlan([source({ url: "https://news.example/feed-redirect" })]);
  try {
    await fetchFeed(f);
    const event = f.events.find(item => item.data.operation === "fetch" && item.data.phase === "failed"
      && item.data.details.document_kind === "feed");
    expect(event?.data.details).toMatchObject({
      requested_feed_url: "https://news.example/feed-redirect",
      final_attempted_feed_url: "https://news.example/not-found",
    });
  } finally { await f.close(); }
});

test("feed byte cutoffs include the limit and observed lower bound in failure events", async () => {
  const f = await recordedPlan([source({ url: "https://news.example/article-failures.xml" })]);
  try {
    f.inputs.harvest.extraction.max_body_bytes = 700;
    await fetchFeed(f);
    const event = f.events.find(item => item.data.operation === "fetch" && item.data.phase === "failed"
      && item.data.details.document_kind === "feed");
    expect(event?.data.details.body_limit).toMatchObject({ configured_limit_bytes: 700 });
    expect(event?.data.details).not.toHaveProperty("body_limit_source");
    expect((event?.data.details.body_limit as { observed_at_least_bytes: number }).observed_at_least_bytes).toBeGreaterThan(700);
  } finally { await f.close(); }
});

test("publisher alone authorizes failure URLs and rejects secrets and spoofed markers", async () => {
  const events: FeedIngestEvent[] = [];
  const sources = await loadEventSources(new URL("../../../config/typescript-event-sources.json", import.meta.url));
  createStageLogger({ run_id: "2026-10-29-700", ...createRootContext() },
    sources.planner, event => events.push(event))("fetch", "failed");
  const base = events[0]!;
  const withData = (data: Record<string, unknown>) => ({ ...base, data: { ...base.data, ...data } });
  expect(prepareProgressEvent(base, [], "https://news.example/story?page=2#section").data.details)
    .toEqual({ article_url: "https://news.example/story" });
  expect(prepareProgressEvent(withData({ details: { document_kind: "feed" } }), [], undefined, {
    requested: "https://news.example/feed.xml?page=2#section",
    final_attempted: "https://cdn.example/feed.xml?tracking=removed",
  }).data.details).toEqual({
    document_kind: "feed",
    requested_feed_url: "https://news.example/feed.xml",
    final_attempted_feed_url: "https://cdn.example/feed.xml",
  });
  for (const url of [
    "https://private:password@news.example/story", "https://news.example/story?token=private",
    "https://news.example/story?X-Amz-Signature=private", "file:///private", "invalid",
  ]) {
    const event = prepareProgressEvent(base, [], url);
    expect(event.data.details.article_url).toBeUndefined();
    expect(event.data.details._compliance).toMatchObject({ status: "NON_COMPLIANT" });
    expect(JSON.stringify(event)).not.toContain("private");
  }
  for (const requested of [
    "https://news.example/feed.xml?token=private",
    "https://user:password@news.example/feed.xml",
  ]) {
    const event = prepareProgressEvent(withData({ details: { document_kind: "feed" } }), [], undefined, {
      requested, final_attempted: null,
    });
    expect(event.data.details.requested_feed_url).toBeUndefined();
    expect(JSON.stringify(event)).not.toContain("private");
    expect(event.data.details._compliance).toMatchObject({ status: "NON_COMPLIANT" });
  }
  for (const phase of ["started", "completed"]) {
    expect(prepareProgressEvent(withData({ phase }), [], "https://news.example/story").data.details.article_url).toBeUndefined();
  }
  const qualityRejection = withData({
    operation: "quality", phase: "failed",
    details: { quality_rejection: { failure_code: "too_short", source_word_count: 45, word_count: 45 } },
  });
  expect(prepareProgressEvent(qualityRejection, [], "https://news.example/story?page=2#section"))
    .toMatchObject({ data: { operation: "quality", phase: "failed" } });
  expect(prepareProgressEvent(qualityRejection, [], "https://news.example/story?page=2#section").data.details)
    .toMatchObject({
      article_url: "https://news.example/story",
      quality_rejection: { failure_code: "too_short", source_word_count: 45, word_count: 45 },
    });
  const invalidQualityRejection = prepareProgressEvent(withData({
    ...qualityRejection.data, details: { quality_rejection: { failure_code: "too_short", source_word_count: 45, word_count: "45" } },
  }), [], "https://news.example/story");
  expect(invalidQualityRejection.data.details.quality_rejection).toBeUndefined();
  expect(invalidQualityRejection.data.details.article_url).toBeUndefined();
  expect(invalidQualityRejection.data.details._compliance).toMatchObject({ status: "NON_COMPLIANT" });
  const misplacedQualityRejection = prepareProgressEvent(withData({
    ...qualityRejection.data, operation: "parse", phase: "completed",
  }), [], "https://news.example/story");
  expect(misplacedQualityRejection.data.details.quality_rejection).toBeUndefined();
  expect(misplacedQualityRejection.data.details.article_url).toBeUndefined();
  expect(misplacedQualityRejection.data.details._compliance).toMatchObject({ status: "NON_COMPLIANT" });
  const signedQualityRejection = prepareProgressEvent(qualityRejection, [], "https://news.example/story?token=private");
  expect(signedQualityRejection.data.details.article_url).toBeUndefined();
  expect(JSON.stringify(signedQualityRejection)).not.toContain("private");
  const spoofed = prepareProgressEvent(withData({
    details: { article_url: "https://news.example/private", _compliance: { status: "COMPLIANT" },
      nested: { token: "private", link: "https://news.example/private" }, article_text: "private" },
  }));
  expect(spoofed.data.details.article_url).toBeUndefined();
  expect(spoofed.data.details._compliance).toMatchObject({ status: "NON_COMPLIANT" });
  expect(JSON.stringify(spoofed)).not.toContain("private");
});

test("upload JSONL names real visible ZIP members, including recovery files, without reading bodies", async () => {
  const f = await recordedPlan();
  const events: FeedIngestEvent[] = [];
  try {
    const files = ["feed-ingest-report-2026-10-29-700.md", "700-1-selected-articles.json", "recovery/state/day.parquet"];
    for (const file of [...files, ".hidden", ".private/body.json", "recovery/.hidden"]) {
      const target = join(f.directory, "artifacts", ...file.split("/"));
      await mkdir(join(target, ".."), { recursive: true });
      await writeFile(target, "private body not for logs");
    }
    expect(await publishUploadInventory({
      directory: join(f.directory, "artifacts"), runNumber: "700", now: new Date("2026-10-29T08:00:00Z"),
      write: event => { events.push(event); },
    })).toBe(files.length);
    expect(events.flatMap(event => typeof event.data.details.file === "string" ? [event.data.details.file] : []).sort())
      .toEqual(files.sort());
    expect(events.at(-1)?.data).toMatchObject({ operation: "artifact-upload", phase: "completed", details: { file_count: files.length } });
    expect(events.every(event => event.data.details._compliance === undefined)).toBe(true);
    expect(JSON.stringify(events)).not.toContain("private body");
    await mkdir(join(f.directory, "raw-document-artifacts"));
    const filename = rawDocumentContentsFilename({ run_id: "2026-10-29-700", writer: { attempt: 1 } });
    await writeFile(join(f.directory, "raw-document-artifacts", filename), "private diagnostic metadata");
    events.length = 0;
    await publishWorkflowUploadInventories({
      directory: f.directory, runNumber: "700", write: event => { events.push(event); },
    });
    expect(events.flatMap(event => typeof event.data.details.file === "string" ? [event.data.details.file] : []).sort())
      .toEqual([...files, filename].sort());
    expect(JSON.stringify(events)).not.toContain("private diagnostic metadata");
    await expect(publishUploadInventory({ directory: join(f.directory, "missing"), runNumber: "700",
      write: event => { events.push(event); } })).rejects.toThrow();
    expect(events.at(-1)?.data).toMatchObject({ operation: "artifact-upload", phase: "failed" });
  } finally { await f.close(); }
});
