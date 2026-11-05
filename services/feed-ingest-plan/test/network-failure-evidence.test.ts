/** Do diagnostic writes and logs preserve real responses without bodies or repeated run identity? */
import { expect, test } from "bun:test";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { ArticleFailureDiagnosticSchema, createRootContext, deriveUrlKey, RawDocumentFailureSchema, NetworkFailureDetailsSchema, PLANNER_API_PREFIX, writeTraceContext } from "@idhazh/common-contracts";
import { PLANNER_EVENT_SOURCE } from "../src/declare-event-source";
import type { FeedIngestEvent } from "@idhazh/common-contracts";
import { rawDocumentContentsFilename, rawDocumentContentsPath, ArtifactRootSchema } from "../src/selected-artifact-path";
import { createStageLogger, prepareProgressEvent } from "../src/logging/structured-logger";
import { finishRawDocumentFailures, failureMetadata } from "../src/dump-raw-document-failure";
import { prepareWorkflowArtifacts } from "../scripts/feed-ingest-plan-artifacts";
import { finishRunOutput } from "../scripts/finish-run-output";
import { createPlanTestServer } from "./plan-test-server";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";
import { stageStore } from "../src/api/stage-store";
import { FetchResponseSchema, ParseResponseSchema } from "../src/api/document-response.schema";
import { operationLink, operationMetadata } from "../src/api/operation-context";

function assertBodyFree(value: unknown) {
  if (value === null || typeof value !== "object") return;
  for (const [key, nested] of Object.entries(value)) {
    expect([
      "body", "article_text", "body_sample", "text_sample", "run_id", "transport",
      "robots", "robots_failure", "robots_http_status", "robots_response_evidence", "body_limit_source",
    ]).not.toContain(key);
    assertBodyFree(nested);
  }
}

test("article byte cutoffs retain the native lower bound, response bytes and profile without header values", async () => {
  const f = await recordedPlan();
  f.inputs.harvest.extraction.max_body_bytes = 1024;
  f.inputs.harvest.config.harvest.request_headers.secondary = null;
  f.transport.recordings.responses["https://news.example/second"]![0]!.headers = {
    "content-type": "text/html; private=PRIVATE_HEADER", server: "PRIVATE_HEADER",
  };
  const app = createPlanTestServer(f.inputs, f.runtime);
  try {
    const result = await app.request(`${PLANNER_API_PREFIX}/fetch`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ fetch_item_type: "article", feed_id: "recorded-news", url: "https://news.example/second" }),
    });
    expect(result.status).toBe(200);
    const response = FetchResponseSchema.parse(await result.json());
    expect(response.failure).toBe("body-too-large");
    expect(response).not.toHaveProperty("diagnostics");
    const [diagnostic] = f.events.flatMap(event => {
      const parsed = ArticleFailureDiagnosticSchema.safeParse(event);
      return parsed.success ? [parsed.data] : [];
    });
    expect(diagnostic?.data.details.diagnostics).toMatchObject({
      fetch_failure: "body-too-large", fetch_ms: null, quality: null,
      body_limit: { configured_limit_bytes: 1024,
        observed_at_least_bytes: Buffer.byteLength(f.transport.recordings.bodies.article) },
      response_evidence: { decoded_bytes: Buffer.byteLength(f.transport.recordings.bodies.article),
        request_profile: "firefox", content_type: "text/html", selected_headers: {}, headers_truncated: [] },
    });
    expect(JSON.stringify(diagnostic)).not.toMatch(/PRIVATE_|https?:\/\//);
  } finally { await app.close(); await f.close(); }
});

test("actual parse failures write and package metadata under one validated generated filename", async () => {
  const fixture = await recordedPlan([source({ url: "https://news.example/malformed.xml" })]);
  fixture.runtime.attempt = 3;
  fixture.inputs.settings.dump_raw_document_contents = true;
  const app = createPlanTestServer(fixture.inputs, fixture.runtime);
  const caller = createRootContext();
  async function post(operation: string, body: unknown) {
    const response = await app.request(`${PLANNER_API_PREFIX}/${operation}`, {
      method: "POST", headers: { "content-type": "application/json", ...writeTraceContext(caller) }, body: JSON.stringify(body),
    });
    expect(response.status).toBe(200);
    return response.json();
  }
  try {
    const fetched = FetchResponseSchema.parse(await post("fetch", {
      feed_id: "recorded-news", fetch_item_type: "feed",
    }));
    const captured = stageStore(fixture.inputs).fetchedDocument(fetched)!;
    const artifact = captured.document;
    const parsed = ParseResponseSchema.parse(await post("parse", { links: [operationLink(fetched)] }));
    expect(parsed.failure).toBe("malformed-feed");
    const canonicalUrl = `${artifact.canonical_url}?page=2`;
    const documentId = deriveUrlKey(canonicalUrl);
    const projection = failureMetadata({
      ...operationMetadata(parsed), document_kind: "feed", operation: "parse",
      failed_at: "2026-10-21T23:59:59Z", failure_reason: "malformed-feed",
      document: {
        ...artifact, canonical_url: canonicalUrl, document_id: documentId,
        observation: { ...artifact.observation, document_id: documentId },
        attempt_observations: artifact.attempt_observations.map(observation => ({ ...observation, document_id: documentId })),
        requested_url: "https://news.example/feed.xml?token=private",
        attempts: artifact.attempts.map(attempt => ({ ...attempt,
          request_url: "https://news.example/request?tracking=private#fragment" })),
        redirects: [{ request_url: "https://news.example/input?page=private",
          destination_url: "https://news.example/output?signature=private", http_status: 302 }],
      },
    });
    assertBodyFree(projection);
    expect(projection.document.canonical_url).toBe(artifact.canonical_url);
    expect(projection.document.document_id).toBe(documentId);
    expect(projection.document.requested_url).toBeNull();
    expect(projection.document.attempts.every(attempt => attempt.request_url === "https://news.example/request")).toBe(true);
    expect(projection.document.redirects[0]).toMatchObject({
      request_url: "https://news.example/input", destination_url: null,
    });
    expect(JSON.stringify(projection)).not.toContain("private");
    await finishRawDocumentFailures(fixture.inputs);
    const filename = rawDocumentContentsFilename(captured.context);
    expect(filename).toBe(`raw-document-contents-2026-10-21-${fetched.run_id.slice(11)}-3.jsonl`);
    const path = rawDocumentContentsPath(fixture.inputs.settings.inputs.artifact_root, captured.context);
    const text = await readFile(join(fixture.directory, path), "utf8");
    const record = RawDocumentFailureSchema.parse(JSON.parse(text.trim()));
    assertBodyFree(record);
    expect(record.document.body_sha256).toBe(artifact.body_sha256);
    expect(record.document.attempts).toEqual(artifact.attempts);
    expect(record.document.attempt_observations).toHaveLength(artifact.attempts.length);
    expect(text).not.toContain(artifact.body!);
    const event = fixture.events.find(event => event.data.operation === "parse" && event.data.phase === "failed")!;
    expect(event.data.details.network_failure).toMatchObject({
      http_status: 200, final_attempted_url: "https://news.example/malformed.xml", failed_url: null,
      response_evidence: { decoded_bytes: Buffer.byteLength(artifact.body!), request_profile: "firefox" },
    });
    await mkdir(join(fixture.directory, "config"));
    await writeFile(join(fixture.directory, "config", "feed-ingest-plan-service.json"), JSON.stringify(fixture.inputs.settings));
    const packaging = join(fixture.directory, "packaging");
    const outputs = await prepareWorkflowArtifacts({
      root: fixture.directory, directory: packaging, runNumber: fetched.run_id.slice(11),
      runId: fetched.run_id, attempt: 3, gitSha: fixture.runtime.git_sha, dumpRawDocumentContents: true,
    });
    expect(outputs.raw_document_contents).toBe(`raw-document-artifacts/${filename}`);
    if (outputs.raw_document_contents === undefined) throw new Error("Failed parse metadata was not packaged");
    expect(await readFile(join(packaging, outputs.raw_document_contents!), "utf8")).toBe(text);
    const finish = {
      root: fixture.directory, temporaryRoot: packaging, runNumber: fetched.run_id.slice(11),
      runId: fetched.run_id, attempt: 3, gitSha: fixture.runtime.git_sha,
      collectionOutcome: "failure", planningComplete: "false", finalizationOutcome: "failure",
      uploadOutcome: "success", artifactId: "123", dumpRawDocumentContents: true,
      rawDocumentContents: outputs.raw_document_contents, rawUploadOutcome: "failure",
    };
    try {
      await finishRunOutput(finish);
      throw new Error("An unconfirmed diagnostic upload must fail");
    } catch (error) {
      expect(error).toBeInstanceOf(AggregateError);
      if (!(error instanceof AggregateError)) throw error;
      expect(error.errors.some(error => error.message === "The raw document artifact upload was not confirmed")).toBe(true);
    }
    const { runId: _runId, ...withoutRunId } = finish;
    await expect(finishRunOutput(withoutRunId)).rejects.toThrow("Diagnostic artifact requires runId");
    await expect(finishRunOutput({ ...finish, rawDocumentContents: "raw-document-artifacts/raw-document-contents.jsonl" })).rejects.toThrow();
    expect(ArtifactRootSchema.safeParse("a".repeat(512)).success).toBe(false);
  } finally { await app.close(); await fixture.close(); }
});

test("required network evidence survives clean and rejected flexible details without admitting caller secrets", async () => {
  const evidence = NetworkFailureDetailsSchema.parse({
    requested_url: "https://news.example/input?page=2", final_attempted_url: null,
    failed_url: "https://news.example/article?token=private", http_status: 503, request_profile: "firefox",
    response_evidence: null, attempt: null,
  });
  const events: FeedIngestEvent[] = [];
  createStageLogger({ run_id: "2026-10-21-700", ...createRootContext() },
    PLANNER_EVENT_SOURCE, event => events.push(event))("request-attempt", "failed");
  const base = events[0]!;
  for (const details of [{}, { body: "private", token: "private" }]) {
    const event = prepareProgressEvent({ ...base, data: { ...base.data, details } }, [], undefined, undefined, evidence);
    expect(event.data.details.network_failure).toMatchObject({
      requested_url: "https://news.example/input", final_attempted_url: null, failed_url: null,
      http_status: 503, request_profile: "firefox",
    });
    expect(JSON.stringify(event)).not.toContain("private");
  }
  expect(() => prepareProgressEvent({ ...base, data: { ...base.data, phase: "completed", details: {} } }, [],
    undefined, undefined, evidence)).toThrow("Network failure evidence requires");
});
