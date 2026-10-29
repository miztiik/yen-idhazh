/** Do actual offline document, persistence and upload paths publish safe, complete JSONL events? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { PartitionedFeedBatchSchema } from "@idhazh/common-contracts";
import type { FeedIngestEvent } from "@idhazh/common-contracts";
import { stageStore } from "../src/api/stage-store";
import { selectedArtifactPath } from "../src/selected-artifact-path";
import { createPlanApp } from "../src/api/server";
import { prepareProgressEvent } from "../src/logging/structured-logger";
import { publishUploadInventory } from "../scripts/feed-ingest-plan-upload-inventory";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";
import { runFeedPlan } from "../src/run-feed-plan";

test("standalone document work logs failure addresses only and persistence logs one real write", async () => {
  const f = await recordedPlan();
  const app = createPlanApp(f.inputs, f.runtime);
  async function post(operation: string, body: unknown) {
    const response = await app.request(`/api/2026-10-20/${operation}`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
    });
    expect(response.status).toBe(200);
    return response.json();
  }
  try {
    for (const [url, failedOperation] of [
      ["https://news.example/not-found", "fetch"],
      ["https://news.example/rootless", "parse"],
      ["https://news.example/second", null],
    ] as const) {
      const request = {
        request_id: randomUUID(), correlation_id: randomUUID(), feed_id: "recorded-news",
        fetch_item_type: "article", url,
      };
      const fetched = await post("fetch", request);
      const afterFetch = f.events.length;
      expect(await post("fetch", request)).toEqual(fetched);
      expect(f.events).toHaveLength(afterFetch);
      let parsed;
      if (failedOperation !== "fetch") parsed = await post("parse", {
        request_id: randomUUID(), fetch_request_id: request.request_id,
        article_id: fetched.article_id, correlation_id: request.correlation_id,
      });
      const events = f.events.filter(event => event.correlation_id === request.correlation_id);
      expect(events.filter(event => event.operation === "fetch").map(event => event.phase))
        .toEqual(["started", failedOperation === "fetch" ? "failed" : "completed"]);
      if (failedOperation !== "fetch") {
        expect(events.filter(event => event.operation === "parse").map(event => event.phase))
          .toEqual(["started", failedOperation === "parse" ? "failed" : "completed"]);
      }
      for (const event of events) {
        expect(event.details._compliance).toBeUndefined();
        expect(event.details.article_id).toBe(fetched.article_id);
        if (event.operation === failedOperation && event.phase === "failed") {
          expect(event.details.article_url).toBe(url);
        } else expect(JSON.stringify(event)).not.toContain("https://");
      }
      if (parsed !== undefined && failedOperation === null) {
        const selected = await post("select-articles", { batch_id: parsed.batch_id });
        const partition = await post("partition-articles", { batch_id: selected.batch_id, strategy: "none" });
        const batch = stageStore(f.inputs).read("partitioned", partition.batch_id, PartitionedFeedBatchSchema);
        const blocked = join(f.directory, selectedArtifactPath(f.inputs.settings.inputs.artifact_root, batch.context));
        await mkdir(blocked, { recursive: true });
        const failure = await app.request("/api/2026-10-20/persist-selected-articles", {
          method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ batch_id: partition.batch_id }),
        });
        expect(failure.status).toBe(500);
        expect(f.events.at(-1)).toMatchObject({ operation: "persist", phase: "failed", details: { failure_code: "PERSIST_FAILED" } });
        await rm(blocked, { recursive: true });
        const persisted = await post("persist-selected-articles", { batch_id: partition.batch_id });
        const count = f.events.length;
        expect(await post("persist-selected-articles", { batch_id: partition.batch_id })).toEqual(persisted);
        expect(f.events).toHaveLength(count);
        expect(f.events.filter(event => event.operation === "persist").map(event => event.phase))
          .toEqual(["started", "failed", "started", "completed"]);
        expect(f.events.at(-1)?.details.artifact).toBe(persisted.artifact);
      }
    }
    const excludedUrl = `https://${f.inputs.harvest.config.content_filters.media.url_rules[0]!.host}/watch`;
    const excludedRequest = {
      request_id: randomUUID(), correlation_id: randomUUID(), feed_id: "recorded-news",
      fetch_item_type: "article", url: excludedUrl,
    };
    const excluded = await app.request("/api/2026-10-20/fetch", {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(excludedRequest),
    });
    expect(excluded.status).toBe(409);
    const excludedEvents = f.events.filter(event => event.correlation_id === excludedRequest.correlation_id);
    expect(excludedEvents.map(event => event.phase)).toEqual(["started", "failed"]);
    expect(excludedEvents.at(-1)?.details.article_url).toBe(excludedUrl);
  } finally { app.close(); await f.close(); }
});

test("composed document failures include addresses without success leaks or duplicate persistence", async () => {
  const f = await recordedPlan([source({ url: "https://news.example/article-failures.xml" })]);
  try {
    await runFeedPlan({ partition_strategy: "none" }, f.inputs, f.runtime);
    expect(f.events.some(event => event.operation === "fetch" && event.phase === "failed"
      && event.details.article_url === "https://news.example/not-found")).toBe(true);
    expect(f.events.some(event => event.operation === "parse" && event.phase === "failed"
      && event.details.article_url === "https://news.example/rootless")).toBe(true);
    for (const event of f.events.filter(event => event.phase !== "failed")) {
      expect(JSON.stringify(event)).not.toContain("https://");
    }
    expect(f.events.filter(event => event.operation === "persist").map(event => event.phase)).toEqual(["started", "completed"]);
  } finally { await f.close(); }
});

test("publisher alone authorizes failure URLs and rejects secrets and spoofed markers", () => {
  const base = {
    run_id: "2026-10-29-700", correlation_id: randomUUID(), occurred_at: "2026-10-29T08:00:00Z",
    operation: "fetch", phase: "failed", details: {},
  };
  expect(prepareProgressEvent(base, [], "https://news.example/story?page=2#section").details)
    .toEqual({ article_url: "https://news.example/story" });
  for (const url of [
    "https://private:password@news.example/story", "https://news.example/story?token=private",
    "https://news.example/story?X-Amz-Signature=private", "file:///private", "invalid",
  ]) {
    const event = prepareProgressEvent(base, [], url);
    expect(event.details.article_url).toBeUndefined();
    expect(event.details._compliance).toMatchObject({ status: "NON_COMPLIANT" });
    expect(JSON.stringify(event)).not.toContain("private");
  }
  for (const phase of ["started", "completed"]) {
    expect(prepareProgressEvent({ ...base, phase }, [], "https://news.example/story").details.article_url).toBeUndefined();
  }
  const spoofed = prepareProgressEvent({
    ...base, details: { article_url: "https://news.example/private", _compliance: { status: "COMPLIANT" },
      nested: { token: "private", link: "https://news.example/private" }, article_text: "private" },
  });
  expect(spoofed.details.article_url).toBeUndefined();
  expect(spoofed.details._compliance).toMatchObject({ status: "NON_COMPLIANT" });
  expect(JSON.stringify(spoofed)).not.toContain("private");
});

test("upload JSONL names real visible ZIP members, including recovery files, without reading bodies", async () => {
  const f = await recordedPlan();
  const events: FeedIngestEvent[] = [];
  try {
    const files = ["700-1-report.md", "700-1-selected-articles.json", "recovery/state/day.parquet"];
    for (const file of [...files, ".hidden", ".private/body.json", "recovery/.hidden"]) {
      const target = join(f.directory, "artifacts", ...file.split("/"));
      await mkdir(join(target, ".."), { recursive: true });
      await writeFile(target, "private body not for logs");
    }
    expect(await publishUploadInventory({
      directory: join(f.directory, "artifacts"), runNumber: "700", now: new Date("2026-10-29T08:00:00Z"),
      write: event => { events.push(event); },
    })).toBe(files.length);
    expect(events.flatMap(event => typeof event.details.file === "string" ? [event.details.file] : []).sort())
      .toEqual(files.sort());
    expect(events.at(-1)).toMatchObject({ operation: "artifact-upload", phase: "completed", details: { file_count: files.length } });
    expect(events.every(event => event.details._compliance === undefined)).toBe(true);
    expect(JSON.stringify(events)).not.toContain("private body");
    await expect(publishUploadInventory({ directory: join(f.directory, "missing"), runNumber: "700",
      write: event => { events.push(event); } })).rejects.toThrow();
    expect(events.at(-1)).toMatchObject({ operation: "artifact-upload", phase: "failed" });
  } finally { await f.close(); }
});
