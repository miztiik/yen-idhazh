/** Exercise HTTP refusals, live parser admission and discovery preservation without planning. */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { existsSync } from "node:fs";
import { SelectedFeedBatchSchema, SelectedArticleRowContract } from "@idhazh/common-contracts";
import { createPlanTestServer } from "./plan-test-server";
import { recordedPlan } from "./plan-recordings";
import { ArticleParserPool } from "../src/harvest-feeds/article-parser-pool";
import { FetchResponseSchema, ParseResponseSchema } from "../src/api/document-response.schema";
import { recordedPersistenceBatch } from "./persistence-recordings";
import { readPlannerOutputRecording } from "./planner-output-recordings";
import { stageStore } from "../src/api/stage-store";
import { collectRecordedFeeds } from "./collection-recordings";
import { CompletedCollectionSchema } from "../src/api/collection-contracts";
import { writeRows } from "./partition-fixtures";

const prefix = "/api/2026-10-31";
const json = (body: unknown) => ({ method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });

test("HTTP health and refusals cannot start source work", async () => {
  const recorded = await recordedPlan();
  const app = createPlanTestServer(recorded.inputs, recorded.runtime);
  try {
    recorded.inputs.settings.enabled = false;
    expect(await (await app.request(`${prefix}/health`)).json()).toEqual({ status: "available", planner_enabled: false });
    expect((await app.request(`${prefix}/plan`, json({}))).status).toBe(503);
    expect((await app.request(`${prefix}/plan`, { ...json({}), body: "{" })).status).toBe(400);
    expect((await app.request(`${prefix}/plan`, json({ extra: true }))).status).toBe(400);
    expect((await app.request(`${prefix}/plan`, json({ padding: "x".repeat(recorded.inputs.settings.listener.max_body_bytes) }))).status).toBe(413);
    expect((await app.request(`${prefix}/feeds`)).status).toBe(404);
    expect((await app.request("/api/2026-10-20/health")).status).toBe(404);
    expect((await app.request(`${prefix}/feed-health-state`, json({ batch_id: randomUUID(), action: "record" }))).status).toBe(503);
    expect(recorded.transport.requests).toHaveLength(0);
    expect(existsSync(join(recorded.inputs.outputRoot, "raw"))).toBe(false);
  } finally { await app.close(); await recorded.close(); }
});

test("a real source-health write refusal returns an API error and leaves native siblings intact", async () => {
  const recorded = await recordedPlan();
  const app = createPlanTestServer(recorded.inputs, recorded.runtime);
  try {
    const { health } = await readPlannerOutputRecording();
    const batch = await recordedPersistenceBatch(recorded.inputs, recorded.runtime);
    stageStore(recorded.inputs).replace("selected", SelectedFeedBatchSchema, { ...batch, health_rows: health.rows });
    const parent = join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan");
    await mkdir(parent, { recursive: true });
    const rows = SelectedArticleRowContract.schema.array().parse(await Bun.file(new URL(
      "../../../tests/fixtures/feed-ingest-plan/entry-points/selected-articles.rows.json", import.meta.url)).json());
    const written = await writeRows(recorded.inputs.outputRoot, "selected-articles", rows[0]!.date, SelectedArticleRowContract, rows);
    const sibling = join(recorded.inputs.outputRoot, written.files[0]!.path);
    const before = await readFile(sibling);
    await writeFile(join(parent, "feed-health-state"), "obstruction");
    const response = await app.request(`${prefix}/feed-health-state`, json({ batch_id: batch.batch_id, action: "record" }));
    expect(response.status).toBe(500);
    const error = await response.json();
    expect(error).toMatchObject({ code: "PLAN_FAILED" });
    expect(error).not.toHaveProperty("planning_complete");
    expect(await readFile(sibling)).toEqual(before);
    expect(recorded.transport.requests).toHaveLength(0);
  } finally { await app.close(); await recorded.close(); }
});

test("overlapping standalone documents keep independent identities and bounded live parser admission", async () => {
  const recorded = await recordedPlan();
  delete recorded.runtime.run_number;
  delete recorded.runtime.correlation_id;
  recorded.inputs.settings.listener.parser_concurrency = 2;
  let active = 0;
  let peak = 0;
  let notify!: () => void;
  const parsing = new Promise<void>(resolve => { notify = resolve; });
  const pool = new ArticleParserPool(2, phase => {
    if (phase === "started") { active++; peak = Math.max(peak, active); notify(); }
    else active--;
  });
  recorded.runtime.parser_pool = pool;
  const app = createPlanTestServer(recorded.inputs, recorded.runtime);
  try {
    const fetched = await Promise.all(["https://news.example/second", "https://news.example/story/"].map(async url => {
      const response = await app.request(`${prefix}/fetch`, json({
        request_id: randomUUID(), correlation_id: randomUUID(), feed_id: "recorded-news", fetch_item_type: "article", url,
      }));
      expect(response.status).toBe(200);
      return FetchResponseSchema.parse(await response.json());
    }));
    const pending = fetched.map(async document => {
      const response = await app.request(`${prefix}/parse`, json({
        request_id: randomUUID(), fetch_request_id: document.fetch_request_id,
        article_id: document.article_id, correlation_id: document.correlation_id,
      }));
      expect(response.status).toBe(200);
      return ParseResponseSchema.parse(await response.json());
    });
    await parsing;
    expect((await app.request(`${prefix}/health`)).status).toBe(200);
    const parsed = await Promise.all(pending);
    expect(peak).toBeGreaterThan(0);
    expect(peak).toBeLessThanOrEqual(recorded.inputs.settings.listener.parser_concurrency);
    expect(new Set(fetched.map(document => document.run_id)).size).toBe(2);
    expect(new Set(parsed.map(document => document.batch_id)).size).toBe(2);
    for (const result of parsed) {
      const health = await app.request(`${prefix}/feed-health-state`, json({ batch_id: result.batch_id, action: "summarize" }));
      expect(health.status).toBe(200);
      expect((await health.json()).rows.some((row: { article_requests: number }) => row.article_requests > 0)).toBe(true);
    }
    expect(recorded.events.some(event => event.operation === "plan")).toBe(false);
  } finally { await app.close(); pool.close(); await recorded.close(); }
});

test("collection discovery bytes survive a later persistence refusal without reopening work", async () => {
  const recorded = await recordedPlan();
  try {
    recorded.transport.recordings.bodies.rss = `<rss version="2.0"><channel><title>Recorded stale feed</title>
      <item><title>Stale offer</title><link>https://news.example/second</link><pubDate>Wed, 01 Jan 2020 00:00:00 GMT</pubDate></item>
      </channel></rss>`;
    const completed = await collectRecordedFeeds(recorded.inputs, recorded.runtime);
    const receipt = CompletedCollectionSchema.parse(completed.completion).discovered_articles;
    expect(receipt.files.length).toBeGreaterThan(0);
    const bytes = await Promise.all(receipt.files.map(file => readFile(join(recorded.inputs.outputRoot, file.path))));
    const batch = await recordedPersistenceBatch(recorded.inputs, recorded.runtime);
    const target = join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan");
    await mkdir(target, { recursive: true });
    await writeFile(join(target, "selected-articles"), "obstruction");
    const app = createPlanTestServer(recorded.inputs, recorded.runtime);
    try {
      expect((await app.request(`${prefix}/persist-selected-articles`, json({ batch_id: batch.batch_id }))).status).toBe(500);
      expect(recorded.events.at(-1)).toMatchObject({
        operation: "persist", phase: "failed", details: { failure_code: "PERSIST_FAILED" },
      });
    } finally { await app.close(); }
    for (const [index, file] of receipt.files.entries()) expect(await readFile(join(recorded.inputs.outputRoot, file.path))).toEqual(bytes[index]!);
  } finally { await recorded.close(); }
});
