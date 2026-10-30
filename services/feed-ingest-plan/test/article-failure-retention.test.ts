/** Read actual terminal failures back from native ledgers without retry archives or duplicate health counts. */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { mkdir, readdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { z } from "zod";
import { FeedHealthStateRowContract, RejectedArticleRowContract, RejectedArticleRowSchema } from "@idhazh/common-contracts";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { runFeedPlan } from "../src/run-feed-plan";
import { recordedPlan } from "./plan-recordings";
import { createPlanApp } from "../src/api/server";
import { deriveArticleIdentity } from "../src/harvest-feeds/article-identity";

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

async function rejectedRows(recorded: Awaited<ReturnType<typeof recordedPlan>>, paths: readonly string[]) {
  return (await Promise.all(paths.map(path => readPlannerParquet(
    join(recorded.inputs.outputRoot, path), "rejected-articles", RejectedArticleRowContract,
  )))).flatMap(file => file.rows);
}

test("terminal HTTP, DNS, TLS, timeout, robots and extraction failures survive zero-selection finalization once", async () => {
  for (const entry of await failureCases()) {
    const recorded = await recordedPlan();
    try {
      recorded.inputs.harvest.config.harvest.article_robots_policy = "enforce";
      recorded.inputs.harvest.extraction.max_retries = 1;
      recorded.inputs.harvest.config.harvest.request_headers.secondary = null;
      recorded.transport.recordings.responses["https://news.example/feed.xml"] = [{
        status: 200, body: `<rss version="2.0"><channel><title>Recorded failures</title><item><title>Actual offer</title><link>${entry.url}</link></item></channel></rss>`,
      }];
      if (entry.responses !== undefined) recorded.transport.recordings.responses[entry.url] = entry.responses;
      const result = await runFeedPlan({}, recorded.inputs, recorded.runtime);
      expect(result.row.status, entry.name).toBe("completed");
      expect(result.selected, entry.name).toEqual([]);
      const rows = await rejectedRows(recorded, result.files.rejected_articles!.files.map(file => file.path));
      expect(rows, entry.name).toHaveLength(1);
      expect(rows[0], entry.name).toMatchObject({
        stage: "harvest-feeds", ...entry.expected,
        reason_code: entry.expected.fetch_failure === "http" ? "FETCH_FAILED_HTTP"
          : entry.expected.fetch_failure === "timeout" ? "FETCH_TIMEOUT"
          : entry.expected.fetch_failure === null ? "EXTRACT_EMPTY" : "FETCH_FAILED",
      });
      const health = (await Promise.all(result.files.feed_health_state!.files.map(file =>
        readPlannerParquet(join(recorded.inputs.outputRoot, file.path), "feed-health-state", FeedHealthStateRowContract))))
        .flatMap(file => file.rows);
      expect(health.flatMap(row => row.rejection_counts).filter(row => row.subject === "article")
        .reduce((sum, row) => sum + row.count, 0), entry.name).toBe(1);
      if (entry.name === "rate-limited") {
        expect(recorded.transport.requests.filter(request => request.url.href === entry.url)).toHaveLength(2);
      }
      if (entry.expected.robots === "denied" || entry.expected.robots === "unknown") {
        expect(recorded.transport.requests.some(request => request.url.href === entry.url)).toBe(false);
      }
    } finally { await recorded.close(); }
  }
});

test("harvest and screening refusals both survive the same zero-selection run", async () => {
  const recorded = await recordedPlan();
  try {
    recorded.inputs.harvest.config.harvest.request_headers.secondary = null;
    recorded.inputs.harvest.config.triage.min_words = 10_000;
    recorded.transport.recordings.responses["https://news.example/second"] = [{ status: 403, body: "" }];
    const result = await runFeedPlan({}, recorded.inputs, recorded.runtime);
    expect(result.row.status).toBe("completed");
    expect(result.selected).toEqual([]);
    const rows = await rejectedRows(recorded, result.files.rejected_articles!.files.map(file => file.path));
    expect(rows).toHaveLength(2);
    expect(new Set(rows.map(row => row.candidate_id)).size).toBe(2);
    expect(rows.map(row => row.stage).sort()).toEqual(["harvest-feeds", "screen-article-candidates"]);
  } finally { await recorded.close(); }
});

test("a successful retry leaves no stale rejection and keeps selected identity and content", async () => {
  const recorded = await recordedPlan();
  try {
    recorded.inputs.harvest.extraction.max_retries = 1;
    recorded.transport.recordings.responses["https://news.example/robots.txt"] = [{
      status: 200, body: "User-agent: *\nDisallow: /\nAllow: /feed.xml\n",
    }];
    recorded.transport.recordings.responses["https://news.example/second"]!.unshift({ status: 503, body: "" });
    const result = await runFeedPlan({}, recorded.inputs, recorded.runtime);
    expect(result.row.status).toBe("completed");
    expect(result.selected).toHaveLength(2);
    expect(result.selected.every(article => article.article_text.length > 0)).toBe(true);
    expect(result.files.rejected_articles).toEqual({ status: "empty", files: [] });
  } finally { await recorded.close(); }
});

test("observed denial retains actual terminal target failures in one all-failed batch", async () => {
  const recorded = await recordedPlan();
  try {
    recorded.inputs.harvest.extraction.max_retries = 1;
    recorded.inputs.harvest.config.harvest.request_headers.secondary = null;
    const cases = (await failureCases()).filter(entry => entry.expected.fetch_failure !== null
      && entry.expected.robots === "allowed");
    cases.push({
      name: "target-dns", url: "https://news.example/target-dns", responses: [{ error: "ENOTFOUND" }],
      expected: { http_status: null, fetch_failure: "dns", error_code: "ENOTFOUND",
        robots: "allowed", robots_http_status: 200, robots_failure: null },
    });
    recorded.transport.recordings.responses["https://news.example/robots.txt"] = [{
      status: 200, body: "User-agent: *\nDisallow: /\nAllow: /feed.xml\n",
    }];
    recorded.transport.recordings.responses["https://news.example/feed.xml"] = [{
      status: 200, body: `<rss version="2.0"><channel><title>Recorded failures</title>${cases.map(entry =>
        `<item><title>Actual offer</title><link>${entry.url}</link></item>`).join("")}</channel></rss>`,
    }];
    for (const entry of cases) recorded.transport.recordings.responses[entry.url] = entry.responses!;
    const result = await runFeedPlan({}, recorded.inputs, recorded.runtime);
    expect(result.row.status).toBe("completed");
    expect(result.selected).toEqual([]);
    expect(result.files.rejected_articles!.files).toHaveLength(1);
    const rows = await rejectedRows(recorded, result.files.rejected_articles!.files.map(file => file.path));
    expect(rows).toHaveLength(cases.length);
    for (const entry of cases) {
      expect(rows.find(row => row.url_key === deriveArticleIdentity(entry.url, recorded.inputs.harvest.config.harvest).url_key), entry.name).toMatchObject({
        ...entry.expected, robots: "denied",
      });
      expect(recorded.transport.requests.some(request => request.url.href === entry.url)).toBe(true);
    }
    expect(recorded.transport.requests.filter(request => request.url.pathname === "/robots.txt")).toHaveLength(1);
  } finally { await recorded.close(); }
});

test("completed failures survive a later selected-ledger write failure", async () => {
  const recorded = await recordedPlan();
  try {
    recorded.inputs.harvest.config.harvest.request_headers.secondary = null;
    recorded.transport.recordings.responses["https://news.example/second"] = [{ status: 403, body: "" }];
    const parent = join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan");
    await mkdir(parent, { recursive: true });
    await writeFile(join(parent, "selected-articles"), "not a directory");
    const result = await runFeedPlan({}, recorded.inputs, recorded.runtime);
    expect(result.row.status).toBe("partial");
    expect(result.files.selected_articles).toBeUndefined();
    const rows = await rejectedRows(recorded, result.files.rejected_articles!.files.map(file => file.path));
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ http_status: 403, reason_code: "FETCH_FAILED_HTTP" });
  } finally { await recorded.close(); }
});

test("standalone fetch retains a terminal row outside its private receipt and replay adds no duplicate", async () => {
  const recorded = await recordedPlan();
  recorded.inputs.harvest.config.harvest.request_headers.secondary = null;
  recorded.transport.recordings.responses["https://news.example/robots.txt"] = [{
    status: 200, body: "User-agent: *\nDisallow: /\n",
  }];
  const app = createPlanApp(recorded.inputs, recorded.runtime);
  try {
    const body = JSON.stringify({
      request_id: randomUUID(), correlation_id: randomUUID(), feed_id: "recorded-news",
      fetch_item_type: "article", url: "https://news.example/not-found",
    });
    const request = () => app.request("/api/2026-10-20/fetch", {
      method: "POST", headers: { "content-type": "application/json" }, body,
    });
    expect((await request()).status).toBe(200);
    const before = recorded.transport.requests.length;
    expect((await request()).status).toBe(200);
    expect(recorded.transport.requests).toHaveLength(before);
    const directory = join("raw", "feed-ingest-plan", "rejected-articles", "2026", "10", "21");
    const paths = (await readdir(join(recorded.inputs.outputRoot, directory)))
      .filter(name => name.endsWith(".parquet")).map(name => join(directory, name));
    const rows = await rejectedRows(recorded, paths);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ http_status: 404, fetch_failure: "http", robots: "denied",
      robots_http_status: 200, robots_failure: null });
  } finally { app.close(); await recorded.close(); }
});

test("standalone extraction retains its observed response and repeated parsing adds no extra row", async () => {
  const recorded = await recordedPlan();
  const app = createPlanApp(recorded.inputs, recorded.runtime);
  try {
    const fetchId = randomUUID();
    const correlation = randomUUID();
    const post = (operation: string, value: unknown) => app.request(`/api/2026-10-20/${operation}`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(value),
    });
    const response = await post("fetch", {
      request_id: fetchId, correlation_id: correlation, feed_id: "recorded-news",
      fetch_item_type: "article", url: "https://news.example/empty-body",
    });
    expect(response.status).toBe(200);
    const fetched = z.object({ article_id: z.string() }).parse(await response.json());
    for (let index = 0; index < 2; index++) {
      const parsed = await post("parse", {
        request_id: randomUUID(), fetch_request_id: fetchId, article_id: fetched.article_id, correlation_id: correlation,
      });
      expect(parsed.status).toBe(200);
    }
    const directory = join("raw", "feed-ingest-plan", "rejected-articles", "2026", "10", "21");
    const paths = (await readdir(join(recorded.inputs.outputRoot, directory)))
      .filter(name => name.endsWith(".parquet")).map(name => join(directory, name));
    const rows = await rejectedRows(recorded, paths);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      stage: "harvest-feeds", reason_code: "EXTRACT_EMPTY", http_status: 200,
      fetch_failure: null, robots: "allowed", robots_http_status: 200,
    });
  } finally { app.close(); await recorded.close(); }
});
