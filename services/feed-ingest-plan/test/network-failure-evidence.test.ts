/** Do diagnostic writes and logs preserve real responses without bodies or repeated run identity? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { RawDocumentFailureSchema, NetworkFailureDetailsSchema } from "@idhazh/common-contracts";
import { rawDocumentContentsFilename, rawDocumentContentsPath, ArtifactRootSchema } from "../src/selected-artifact-path";
import { prepareProgressEvent } from "../src/logging/structured-logger";
import { finishRawDocumentFailures, failureMetadata } from "../src/dump-raw-document-failure";
import { prepareWorkflowArtifacts } from "../scripts/feed-ingest-plan-artifacts";
import { finishRunOutput } from "../scripts/finish-run-output";
import { createPlanTestServer } from "./plan-test-server";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";
import { stageStore } from "../src/api/stage-store";
import { FetchResponseSchema, ParseResponseSchema } from "../src/api/document-response.schema";

function assertBodyFree(value: unknown) {
  if (value === null || typeof value !== "object") return;
  for (const [key, nested] of Object.entries(value)) {
    expect(["body", "article_text", "body_sample", "text_sample", "run_id", "transport"]).not.toContain(key);
    assertBodyFree(nested);
  }
}

test("actual parse failures write and package metadata under one validated generated filename", async () => {
  const fixture = await recordedPlan([source({ url: "https://news.example/malformed.xml" })]);
  fixture.runtime.attempt = 3;
  fixture.inputs.settings.dump_raw_document_contents = true;
  const app = createPlanTestServer(fixture.inputs, fixture.runtime);
  const requestId = randomUUID();
  const correlationId = randomUUID();
  async function post(operation: string, body: unknown) {
    const response = await app.request(`/api/2026-10-31/${operation}`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
    });
    expect(response.status).toBe(200);
    return response.json();
  }
  try {
    const fetched = FetchResponseSchema.parse(await post("fetch", {
      request_id: requestId, correlation_id: correlationId, feed_id: "recorded-news", fetch_item_type: "feed",
    }));
    const captured = stageStore(fixture.inputs).fetchedDocument(requestId)!;
    const artifact = captured.document;
    const projection = failureMetadata({
      document_kind: "feed", request_id: requestId, operation: "parse",
      failed_at: "2026-10-21T23:59:59Z", failure_reason: "malformed-feed",
      document: {
        ...artifact, canonical_url: `${artifact.canonical_url}?page=2#section`,
        requested_url: "https://news.example/feed.xml?token=private",
        attempts: artifact.attempts.map(attempt => ({ ...attempt,
          request_url: "https://news.example/request?tracking=private#fragment" })),
        redirects: [{ request_url: "https://news.example/input?page=private",
          destination_url: "https://news.example/output?signature=private", http_status: 302 }],
      },
    });
    assertBodyFree(projection);
    expect(projection.document.canonical_url).toBe(artifact.canonical_url);
    expect(projection.document.requested_url).toBeNull();
    expect(projection.document.attempts.every(attempt => attempt.request_url === "https://news.example/request")).toBe(true);
    expect(projection.document.redirects[0]).toMatchObject({
      request_url: "https://news.example/input", destination_url: null,
    });
    expect(JSON.stringify(projection)).not.toContain("private");
    const parsed = ParseResponseSchema.parse(await post("parse", {
      request_id: randomUUID(), fetch_request_id: requestId,
      article_id: fetched.article_id, correlation_id: correlationId,
    }));
    expect(parsed.failure).toBe("malformed-feed");
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
    const event = fixture.events.find(event => event.operation === "parse" && event.phase === "failed")!;
    expect(event.details.network_failure).toMatchObject({
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

test("required network evidence survives clean and rejected flexible details without admitting caller secrets", () => {
  const evidence = NetworkFailureDetailsSchema.parse({
    requested_url: "https://news.example/input?page=2", final_attempted_url: null,
    failed_url: "https://news.example/robots.txt?token=private", http_status: 503, request_profile: "firefox",
    response_evidence: null, robots_response_evidence: null, robots_http_status: 503, robots_failure: "http", attempt: null,
  });
  const base = {
    run_id: "2026-10-21-700", correlation_id: randomUUID(), occurred_at: "2026-10-21T23:59:59Z",
    operation: "request-attempt", phase: "failed",
  };
  for (const details of [{}, { body: "private", token: "private" }]) {
    const event = prepareProgressEvent({ ...base, details }, [], undefined, undefined, evidence);
    expect(event.details.network_failure).toMatchObject({
      requested_url: "https://news.example/input", final_attempted_url: null, failed_url: null,
      http_status: 503, request_profile: "firefox",
    });
    expect(JSON.stringify(event)).not.toContain("private");
  }
  expect(() => prepareProgressEvent({ ...base, phase: "completed", details: {} }, [],
    undefined, undefined, evidence)).toThrow("Network failure evidence requires");
});
