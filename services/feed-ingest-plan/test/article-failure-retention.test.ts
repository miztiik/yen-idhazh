/** Read terminal fetch, extraction and persistence refusals from their real native boundaries. */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { z } from "zod";
import { ParsedFeedBatchSchema, RejectedArticleRowContract, RejectedArticleRowSchema, SelectedArticlesArtifactSchema } from "@idhazh/common-contracts";
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

async function failureCases() {
  const response = z.object({ status: z.int().optional(), body: z.string().optional(), error: z.string().optional() });
  return z.object({ cases: z.array(z.object({
    name: z.string(), url: z.string(), responses: z.array(response).optional(),
    expected: z.strictObject({
      http_status: RejectedArticleRowSchema.shape.http_status,
      fetch_failure: RejectedArticleRowSchema.shape.fetch_failure,
      error_code: RejectedArticleRowSchema.shape.error_code,
      robots: RejectedArticleRowSchema.shape.robots,
      robots_http_status: RejectedArticleRowSchema.shape.robots_http_status,
      robots_failure: RejectedArticleRowSchema.shape.robots_failure,
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
  const batches: string[] = [];
  try {
    for (const url of urls) {
      const request = { request_id: randomUUID(), correlation_id: randomUUID(), feed_id: "recorded-news",
        fetch_item_type: "article", url };
      const response = await app.request("/api/2026-10-31/fetch", {
        method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(request),
      });
      expect(response.status).toBe(200);
      const fetched = FetchResponseSchema.parse(await response.json());
      if (fetched.body_sha256 !== null) {
        const parsed = await app.request("/api/2026-10-31/parse", {
          method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({
            request_id: randomUUID(), fetch_request_id: fetched.fetch_request_id,
            article_id: fetched.article_id, correlation_id: fetched.correlation_id,
          }),
        });
        expect(parsed.status).toBe(200);
        batches.push(ParseResponseSchema.parse(await parsed.json()).batch_id);
      }
    }
    return batches;
  } finally { await app.close(); }
}

test("terminal HTTP, DNS, TLS, timeout, robots and extraction failures retain their native outcome fields once", async () => {
  const cases = await failureCases();
  const recorded = await recordedPlan();
  try {
    delete recorded.runtime.run_number;
    delete recorded.runtime.correlation_id;
    recorded.inputs.harvest.config.harvest.article_robots_policy = "enforce";
    recorded.inputs.harvest.extraction.max_retries = 0;
    recorded.inputs.harvest.config.harvest.request_headers.secondary = null;
    for (const entry of cases) if (entry.responses) recorded.transport.recordings.responses[entry.url] = entry.responses;
    await capture(recorded, cases.map(entry => entry.url));
    const rows = await rejectedRows(recorded);
    expect(rows).toHaveLength(cases.length);
    expect(new Set(rows.map(row => row.url_key)).size).toBe(cases.length);
    for (const entry of cases) {
      expect(rows.find(row => row.url_key === deriveArticleIdentity(entry.url, recorded.inputs.harvest.config.harvest).url_key),
        entry.name).toMatchObject({ stage: "harvest-feeds", ...entry.expected });
      if (["robots-denied", "robots-unknown"].includes(entry.expected.fetch_failure ?? "")) {
        expect(recorded.transport.requests.some(request => request.url.href === entry.url)).toBe(false);
      }
    }
  } finally { await recorded.close(); }
});

test("persistence retains both refusal stages with an actual empty selected artifact", async () => {
  const recorded = await recordedPlan();
  try {
    recorded.inputs.harvest.config.triage.min_words = 10_000;
    recorded.inputs.harvest.config.partition.enabled = false;
    const [parsedId] = await capture(recorded, ["https://news.example/not-found", "https://news.example/second"]);
    const { batch } = await executeSelection({ batch_id: parsedId }, recorded.inputs, recorded.runtime);
    const result = await executePersistence({ batch_id: batch.batch_id }, recorded.inputs, recorded.runtime);
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
    recorded.transport.recordings.responses["https://news.example/second"]!.unshift({ status: 503, body: "" });
    const [id] = await capture(recorded, ["https://news.example/second"]);
    const batch = stageStore(recorded.inputs).read("parsed", id!, ParsedFeedBatchSchema);
    expect(batch.candidates).toHaveLength(1);
    expect(batch.candidates[0]!.article_text.length).toBeGreaterThan(0);
    expect(batch.candidates[0]!.url_key).toBe(deriveArticleIdentity("https://news.example/second", recorded.inputs.harvest.config.harvest).url_key);
    expect(await rejectedRows(recorded)).toEqual([]);
    expect(recorded.transport.requests.filter(request => request.url.pathname === "/second")).toHaveLength(2);
  } finally { await recorded.close(); }
});

test("observed robots denial retains the actual dispatched target failures", async () => {
  const recorded = await recordedPlan();
  try {
    const cases = (await failureCases()).filter(entry => entry.expected.fetch_failure !== null && entry.expected.robots === "allowed");
    recorded.inputs.harvest.config.harvest.article_robots_policy = "observe";
    recorded.inputs.harvest.extraction.max_retries = 0;
    recorded.inputs.harvest.config.harvest.request_headers.secondary = null;
    recorded.transport.recordings.responses["https://news.example/robots.txt"] = [{ status: 200, body: "User-agent: *\nDisallow: /\n" }];
    for (const entry of cases) if (entry.responses) recorded.transport.recordings.responses[entry.url] = entry.responses;
    await capture(recorded, cases.map(entry => entry.url));
    const rows = await rejectedRows(recorded);
    expect(rows).toHaveLength(cases.length);
    for (const entry of cases) {
      expect(rows.find(row => row.url_key === deriveArticleIdentity(entry.url, recorded.inputs.harvest.config.harvest).url_key),
        entry.name).toMatchObject({ ...entry.expected, robots: "denied" });
      expect(recorded.transport.requests.some(request => request.url.href === entry.url)).toBe(true);
    }
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
    await expect(executePersistence({ batch_id: batch.batch_id }, recorded.inputs, recorded.runtime)).rejects.toThrow();
    expect(await readFile(path)).toEqual(before);
    expect(recorded.events.at(-1)).toMatchObject({ operation: "persist", phase: "failed" });
  } finally { await recorded.close(); }
});
