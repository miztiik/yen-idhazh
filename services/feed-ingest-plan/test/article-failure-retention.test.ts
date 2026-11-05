/** Read terminal fetch, extraction and persistence refusals from their real native boundaries. */
import { expect, test } from "bun:test";
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { z } from "zod";
import { ArticleFailureDiagnosticSchema, CandidateIdSchema, ParsedFeedBatchSchema, PLANNER_API_PREFIX, RawDocumentFailureSchema, RejectedArticleRowContract, RejectedArticleRowSchema, SelectedArticlesArtifactSchema } from "@idhazh/common-contracts";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { recordedPlan } from "./plan-recordings";
import { createPlanTestServer } from "./plan-test-server";
import { FetchResponseSchema, ParseResponseSchema } from "../src/api/document-response.schema";
import { stageStore } from "../src/api/stage-store";
import { deriveArticleIdentity } from "../src/harvest-feeds/article-identity";
import { recordedPersistenceBatch } from "./persistence-recordings";
import { executePersistence } from "../src/api/persistence-operation";
import { writeRows } from "./partition-fixtures";
import { executeSelection } from "../src/api/selection-operation";
import { operationLink } from "../src/api/operation-context";
import { rawDocumentContentsPath } from "../src/selected-artifact-path";
import type { OperationLink } from "@idhazh/common-contracts";

async function failureCases() {
  const response = z.object({ status: z.int().optional(), body: z.string().optional(), error: z.string().optional() });
  return z.object({ cases: z.array(z.object({
    name: z.string(), url: z.string(), responses: z.array(response).optional(),
    expected: z.strictObject({
      http_status: RejectedArticleRowSchema.shape.http_status,
      fetch_failure: RejectedArticleRowSchema.shape.fetch_failure,
      error_code: RejectedArticleRowSchema.shape.error_code,
    }),
  })) }).parse(await Bun.file(new URL(
    "../../../tests/fixtures/feed-ingest-plan/article-terminal-failures.json", import.meta.url,
  )).json()).cases;
}
async function rejectedRows(recorded: Awaited<ReturnType<typeof recordedPlan>>) {
  const directory = join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan", "rejected-articles", "2026", "10", "21");
  let paths: string[];
  try { paths = (await readdir(directory)).filter(name => name.endsWith(".parquet")); }
  catch (error) {
    if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error;
    return [];
  }
  return (await Promise.all(paths.map(path => readPlannerParquet(join(directory, path), "rejected-articles", RejectedArticleRowContract))))
    .flatMap(file => file.rows);
}
async function capture(recorded: Awaited<ReturnType<typeof recordedPlan>>, urls: string[]) {
  const app = createPlanTestServer(recorded.inputs, recorded.runtime);
  const references: OperationLink[] = [];
  try {
    for (const url of urls) {
      const request = { feed_id: "recorded-news",
        fetch_item_type: "article", url };
      const response = await app.request(`${PLANNER_API_PREFIX}/fetch`, {
        method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(request),
      });
      expect(response.status).toBe(200);
      const fetched = FetchResponseSchema.parse(await response.json());
      if (fetched.fetch_item_type !== "article") throw new Error("Expected an article fetch");
      expect(CandidateIdSchema.parse(fetched.candidate_id)).toBe(fetched.candidate_id);
      expect(fetched.article_id).toBe(deriveArticleIdentity(url).url_key);
      expect(fetched).not.toHaveProperty("document_id");
      if (fetched.body_sha256 !== null) {
        const held = stageStore(recorded.inputs).fetchedDocument(fetched);
        expect(held?.candidate_id).toBe(fetched.candidate_id);
        expect(held?.document.candidate_id).toBe(fetched.candidate_id);
        expect(held?.document.attempt_observations.every(value => value.candidate_id === fetched.candidate_id)).toBe(true);
        const parsed = await app.request(`${PLANNER_API_PREFIX}/parse`, {
          method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({
            links: [operationLink(fetched)],
          }),
        });
        expect(parsed.status).toBe(200);
        const result = ParseResponseSchema.parse(await parsed.json());
        if (result.fetch_item_type !== "article") throw new Error("Expected an article parse");
        expect(result.candidate_id).toBe(fetched.candidate_id);
        expect(result.article_id).toBe(fetched.article_id);
        expect(result).not.toHaveProperty("document_id");
        references.push(operationLink(result));
      }
    }
    return references;
  } finally { await app.close(); }
}

test("terminal HTTP, DNS, TLS, timeout and extraction failures retain their native outcome fields once", async () => {
  const cases = await failureCases();
  const recorded = await recordedPlan();
  try {
    delete recorded.runtime.run_number;
    recorded.inputs.harvest.extraction.max_retries = 0;
    recorded.inputs.settings.dump_raw_document_contents = true;
    recorded.inputs.harvest.config.harvest.request_headers.secondary = null;
    for (const entry of cases) if (entry.responses) recorded.transport.recordings.responses[entry.url] = entry.responses;
    await capture(recorded, cases.map(entry => entry.url));
    const rows = await rejectedRows(recorded);
    expect(rows).toHaveLength(cases.length);
    expect(new Set(rows.map(row => row.url_key)).size).toBe(cases.length);
    for (const entry of cases) {
      const row = rows.find(row =>
        row.url_key === deriveArticleIdentity(entry.url).url_key);
      expect(row, entry.name).toMatchObject({
        stage: "harvest-feeds", ...entry.expected,
        pacing_settings: recorded.inputs.harvest.config.harvest.request_pacing,
      });
      expect(row?.pacing_time_ms).not.toBeNull();
      expect(Object.keys(row!).sort()).toEqual(Object.keys(RejectedArticleRowSchema.shape).sort());
      const failures = (await readFile(join(recorded.directory, rawDocumentContentsPath(
        recorded.inputs.settings.inputs.artifact_root, { run_id: row!.run_id, writer: { attempt: row!.attempt } },
      )), "utf8")).trim().split("\n").map(line => RawDocumentFailureSchema.parse(JSON.parse(line)));
      expect(failures).toHaveLength(1);
      expect(failures[0]!.document.candidate_id).toBe(row!.candidate_id);
      expect(failures[0]!.document.observation.candidate_id).toBe(row!.candidate_id);
      expect(recorded.events.some(event => event.data.phase === "started"
        && event.data.details.candidate_id === row!.candidate_id)).toBe(true);
    }
    expect(recorded.transport.requests.map(request => request.url.href)).toEqual(cases.map(entry => entry.url));
  } finally { await recorded.close(); }
});

test("persistence retains both refusal stages with an actual empty selected artifact", async () => {
  const recorded = await recordedPlan();
  try {
    recorded.inputs.harvest.config.triage.min_words = 10_000;
    recorded.inputs.harvest.config.partition.enabled = false;
    const [parsed] = await capture(recorded, ["https://news.example/not-found", "https://news.example/second"]);
    const { batch } = await executeSelection({ links: [parsed] }, recorded.inputs, recorded.runtime);
    const result = await executePersistence({ links: [operationLink(batch)] }, recorded.inputs, recorded.runtime);
    const actual = await rejectedRows(recorded);
    expect(actual).toHaveLength(2);
    expect(new Set(actual.map(row => row.candidate_id)).size).toBe(2);
    expect(actual.map(row => row.stage).sort()).toEqual(["harvest-feeds", "screen-article-candidates"]);
    expect(SelectedArticlesArtifactSchema.parse(await Bun.file(join(recorded.directory, result.artifact)).json()).articles).toEqual([]);
  } finally { await recorded.close(); }
});

test("a successful retry retains captured identity and text without a stale native rejection", async () => {
  const recorded = await recordedPlan();
  try {
    recorded.inputs.harvest.extraction.max_retries = 1;
    const beforeDispatch: string[] = [];
    recorded.transport.on_request = () => {
      const started = recorded.events.findLast(event => event.data.operation === "fetch"
        && event.data.phase === "started" && event.data.details.document_kind === "article");
      beforeDispatch.push(CandidateIdSchema.parse(started?.data.details.candidate_id));
    };
    recorded.transport.recordings.responses["https://news.example/second"]!.unshift({ status: 503, body: "" });
    const [id] = await capture(recorded, ["https://news.example/second"]);
    const batch = stageStore(recorded.inputs).read("parsed", id!, ParsedFeedBatchSchema);
    expect(batch.candidates).toHaveLength(1);
    expect(batch.candidates[0]!.article_text.length).toBeGreaterThan(0);
    expect(batch.candidates[0]!.url_key).toBe(deriveArticleIdentity("https://news.example/second").url_key);
    const candidateId = batch.candidates[0]!.candidate_id;
    expect(beforeDispatch).toEqual([candidateId, candidateId]);
    expect(batch.observations[candidateId]!.candidate_id).toBe(candidateId);
    expect(recorded.events.filter(event => event.data.details.document_kind === "article")
      .every(event => event.data.details.candidate_id === candidateId)).toBe(true);
    expect(await rejectedRows(recorded)).toEqual([]);
    expect(recorded.events.some(event => ArticleFailureDiagnosticSchema.safeParse(event).success)).toBe(false);
    expect(recorded.transport.requests.filter(request => request.url.pathname === "/second")).toHaveLength(2);
  } finally { await recorded.close(); }
});

test("native parser, quality and missing-title refusals keep complete safe diagnostics without changing saved row membership", async () => {
  const fixture = await Bun.file(new URL(
    "../../../tests/fixtures/feed-ingest-plan/article-terminal-failures.json", import.meta.url,
  )).json();
  const recorded = await recordedPlan();
  try {
    recorded.inputs.harvest.config.harvest.request_headers.secondary = null;
    for (const entry of fixture.article_inputs) recorded.transport.recordings.responses[entry.url] = entry.responses;
    await capture(recorded, fixture.article_inputs.map((entry: { url: string }) => entry.url));
    const diagnostics = recorded.events.flatMap(event => {
      const parsed = ArticleFailureDiagnosticSchema.safeParse(event);
      return parsed.success ? [parsed.data] : [];
    });
    expect(diagnostics).toHaveLength(fixture.article_inputs.length);
    const rows = await rejectedRows(recorded);
    expect(rows).toHaveLength(2);
    for (const entry of fixture.article_inputs) {
      const event = diagnostics.find(event => event.data.details.url_key === deriveArticleIdentity(entry.url).url_key)!;
      expect(event.data).toMatchObject({
        operation: entry.operation, phase: "failed", details: {
          reason_code: entry.reason_code, diagnostics: { extraction_failure: entry.extraction_failure, fetch_ms: null,
            response_evidence: { content_type: "text/html", selected_headers: {}, headers_truncated: [] } },
        },
      });
      expect(event.data.details.diagnostics.extract_ms).toBeGreaterThanOrEqual(0);
      expect(event.data.details).not.toHaveProperty("publisher_id");
      expect(event.data.details).not.toHaveProperty("quality_rejection");
      expect(event.data.details).not.toHaveProperty("_compliance");
      const parse = recorded.events.find(value => value.data.operation === "parse" && value.data.phase === "started"
        && value.data.details.candidate_id === event.data.details.candidate_id)!;
      expect(event.traceparent).toBe(parse.traceparent);
      const row = rows.find(row => row.candidate_id === event.data.details.candidate_id);
      if (entry.name === "missing-title") expect(row).toBeUndefined();
      else expect(row).toMatchObject({
        reason_code: entry.reason_code, http_status: event.data.details.diagnostics.http_status,
        candidate_id: event.data.details.candidate_id, url_key: event.data.details.url_key,
      });
    }
    const quality = diagnostics.find(event => event.data.operation === "quality")!.data.details.diagnostics;
    expect(quality.quality).toMatchObject({ too_short: true, not_prose: false, rejected: true, token_count: null });
    expect(quality.warnings).toContain("malformed-json-ld");
    expect(JSON.stringify(diagnostics)).not.toMatch(/PRIVATE_|https?:\/\/|article_text|<html>/);
  } finally { await recorded.close(); }
});

test("completed rejection bytes survive a real selected-ledger write failure", async () => {
  const recorded = await recordedPlan();
  try {
    const rejected = RejectedArticleRowContract.schema.array().parse(await Bun.file(new URL(
      "../../../tests/fixtures/feed-ingest-plan/entry-points/rejected-articles.rows.json", import.meta.url)).json());
    const written = await writeRows(recorded.inputs.outputRoot, "rejected-articles", rejected[0]!.date, RejectedArticleRowContract, rejected);
    const path = join(recorded.inputs.outputRoot, written.files[0]!.path);
    const before = await readFile(path);
    const parent = join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan");
    await mkdir(parent, { recursive: true });
    await writeFile(join(parent, "selected-articles"), "not a directory");
    const batch = await recordedPersistenceBatch(recorded.inputs, recorded.runtime);
    await expect(executePersistence({ links: [operationLink(batch)] }, recorded.inputs, recorded.runtime)).rejects.toThrow();
    expect(await readFile(path)).toEqual(before);
    expect(recorded.events.at(-1)?.data).toMatchObject({ operation: "persist", phase: "failed" });
  } finally { await recorded.close(); }
});
