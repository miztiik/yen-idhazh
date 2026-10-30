/** Prove real loopback stage orchestration and the partition bypass with offline source recordings. */
import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { SelectedArticlesArtifactSchema } from "@idhazh/common-contracts";
import { createPlanApp } from "../src/api/server";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";
import { randomUUID } from "node:crypto";
import { getCollection } from "../src/api/collection-operation";

for (const enabled of [true, false]) test(`HTTP collection completes all feeds before global selection; partition enabled=${enabled}`, async () => {
  const fixture = await recordedPlan([source(), source({ id: "second-feed", url: "https://news.example/second.xml" })]);
  fixture.inputs.harvest.config.partition.enabled = enabled;
  fixture.transport.recordings.responses["https://news.example/second.xml"] =
    fixture.transport.recordings.responses["https://news.example/feed.xml"]!;
  const calls: string[] = [];
  const failures: unknown[] = [];
  const app = createPlanApp(fixture.inputs, { ...fixture.runtime, stage_fetch: async request => {
    calls.push(new URL(request.url).pathname.split("/").at(-1)!);
    const response = await fetch(request);
    if (!response.ok) failures.push(await response.clone().json());
    return response;
  } });
  let server: ReturnType<typeof Bun.serve>;
  server = Bun.serve({ hostname: "127.0.0.1", port: 0, idleTimeout: 0, fetch: request =>
    app.fetch(request, { stage_origin: `http://127.0.0.1:${server.port}` }) });
  try {
    const response = await fetch(`http://127.0.0.1:${server.port}/api/2026-10-20/plan`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ article_limit: 2 }),
    });
    const summary = await response.json();
    expect(response.status, JSON.stringify({ summary, failures })).toBe(200);
    expect(summary.planning_complete).toBe(true);
    expect(calls[0]).toBe("collections");
    expect(calls.filter(call => call === "fetch").length).toBeGreaterThanOrEqual(2);
    expect(calls.filter(call => call === "parse").length).toBeGreaterThanOrEqual(2);
    expect(calls.indexOf("complete")).toBeGreaterThan(calls.lastIndexOf("parse"));
    expect(calls.indexOf("select-articles")).toBeGreaterThan(calls.indexOf("complete"));
    expect(calls.includes("partition-articles")).toBe(enabled);
    expect(summary.assignments.every((assignment: { worker_assignment: number | null }) =>
      enabled ? assignment.worker_assignment !== null : assignment.worker_assignment === null)).toBe(true);
    expect(summary.dispatch_count).toBe(enabled ? fixture.inputs.harvest.config.partition.default_shards : 0);
    const artifact = SelectedArticlesArtifactSchema.parse(JSON.parse(
      await readFile(join(fixture.directory, summary.selected_articles_artifact), "utf8"),
    ));
    expect(artifact.articles.length).toBeGreaterThan(0);
    expect(summary.files.selected_articles.status).toBe("written");
    expect(JSON.stringify(summary)).not.toContain(artifact.articles[0]!.article_text);
  } finally { await server.stop(true); app.close(); await fixture.close(); }
}, 30000);

test("unfinished or cancelled collection cannot be selected and a feed cannot be claimed twice", async () => {
  const fixture = await recordedPlan();
  const app = createPlanApp(fixture.inputs, fixture.runtime);
  const post = (body: unknown) => ({ method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  const prefix = "/api/2026-10-20";
  const id = randomUUID();
  try {
    const begun = await app.request(`${prefix}/collections`, post({ collection_id: id, request: {} }));
    expect(begun.status).toBe(200);
    const collection = getCollection(fixture.inputs, id);
    expect((await app.request(`${prefix}/collections/complete`, post({ collection_id: id }))).status).toBe(409);
    expect((await app.request(`${prefix}/select-articles`, post({ batch_id: collection.parsed_batch_id }))).status).toBe(409);
    const body = { request_id: randomUUID(), collection_id: id, feed_id: "recorded-news",
      correlation_id: collection.context.correlation_id, fetch_item_type: "feed" };
    const fetched = await app.request(`${prefix}/fetch`, post(body));
    expect(fetched.status, await fetched.clone().text()).toBe(200);
    expect((await app.request(`${prefix}/fetch`, post({ ...body, request_id: randomUUID() }))).status).toBe(409);
    expect((await app.request(`${prefix}/collections/cancel`, post({ collection_id: id }))).status).toBe(200);
    expect(collection.signal.signal.aborted).toBe(true);
    expect((await app.request(`${prefix}/collections/complete`, post({ collection_id: id }))).status).toBe(409);
  } finally { app.close(); await fixture.close(); }
}, 30000);

test("valid empty feed completes a truthful empty output without partition requests", async () => {
  const fixture = await recordedPlan();
  fixture.inputs.harvest.config.partition.enabled = false;
  fixture.transport.recordings.responses["https://news.example/feed.xml"] = [{
    status: 200, body: '<rss version="2.0"><channel><title>Empty feed</title></channel></rss>',
  }];
  const { runFeedPlan } = await import("../src/run-feed-plan");
  try {
    const result = await runFeedPlan({}, fixture.inputs, fixture.runtime);
    expect(result.row.status).toBe("completed");
    expect(result.row.selected_count).toBe(0);
    expect(result.row.dispatch_count).toBe(0);
    expect(result.batches.partition_batch_id).toBeUndefined();
    expect(result.files.selected_articles).toEqual({ status: "empty", files: [] });
    const artifact = SelectedArticlesArtifactSchema.parse(JSON.parse(
      await readFile(join(fixture.directory, result.row.selected_articles_artifact!), "utf8"),
    ));
    expect(artifact.articles).toEqual([]);
  } finally { await fixture.close(); }
}, 30000);
