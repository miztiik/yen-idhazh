/** Are real feed/article updates visible before completion without retaining audit payloads? */
import { expect, test } from "bun:test";
import { FeedIngestEventSchema, ParsedFeedBatchSchema } from "@idhazh/common-contracts";
import { runFeedPlan } from "../src/run-feed-plan";
import type { ProgressRecord } from "../src/logging/progress-logger";
import { stageStore } from "../src/api/stage-store";
import { recordedPlan } from "./plan-recordings";
import { parseFeed } from "../src/harvest-feeds/feed-client";
import { cleanRequestTarget } from "../src/harvest-feeds/request-url";

test("live progress precedes completion and the structured event stream stays sparse and body-free", async () => {
  const recorded = await recordedPlan();
  const first = (await parseFeed(recorded.transport.recordings.bodies.rss))[0]!;
  if (first.link === null) throw new Error("Recorded entry must identify its target");
  const target = recorded.inputs.harvest.config.harvest.tidy_urls ? cleanRequestTarget(first.link).href : first.link;
  recorded.transport.recordings.responses[target] = [{
    status: 200,
    body: recorded.transport.recordings.bodies.article.replace("</head>", '<script type="application/ld+json">{</script></head>'),
  }];
  const progress: ProgressRecord[] = [];
  let earlyFeed = false;
  recorded.runtime.progress = event => {
    progress.push(event);
    if (event.eventType === "FEED_FETCH_COMPLETED") {
      earlyFeed = !recorded.events.some(event => event.operation === "plan" && event.phase === "completed");
    }
  };
  try {
    const result = await runFeedPlan({ article_limit: 1, partition_strategy: "none" }, recorded.inputs, recorded.runtime);
    expect(result.row.status).toBe("completed");
    expect(earlyFeed).toBe(true);
    const types = progress.map(event => event.eventType);
    expect(types[0]).toBe("FEED_FETCH_STARTED");
    expect(types.indexOf("FEED_FETCH_COMPLETED")).toBeLessThan(types.indexOf("ARTICLE_HARVEST_STARTED"));
    expect(types).toContain("ARTICLE_HARVEST_COMPLETED");
    expect(types).toContain("ARTICLE_EXTRACTION_WARNING");
    const batch = stageStore(recorded.inputs).read("parsed", result.batches.parsed_batch_id!, ParsedFeedBatchSchema);
    expect(Object.values(batch.observations).some(observation =>
      observation.diagnostics?.warnings.includes("malformed-json-ld"))).toBe(true);
    for (const event of progress) {
      expect(Object.keys(event).sort()).toEqual(["eventType", "feed_id", "output_count"]);
      expect(event.feed_id).toBe("recorded-news");
      if (event.eventType === "FEED_FETCH_COMPLETED") expect(event.output_count).toBe(3);
    }
    expect(recorded.events.at(-1)).toMatchObject({ operation: "plan", phase: "completed", output_count: 1 });
    for (const event of recorded.events) {
      expect(FeedIngestEventSchema.parse(event)).toEqual(event);
      expect(event.run_id).toBe(result.context.run_id);
      expect(event.correlation_id).toBe(result.context.correlation_id);
      expect(event.occurred_at).toMatch(/Z$/);
      expect(event).not.toHaveProperty("payload");
      expect(event).not.toHaveProperty("article_text");
      expect(event).not.toHaveProperty("policy");
      expect(event).not.toHaveProperty("source_id");
      expect(FeedIngestEventSchema.safeParse({ ...event, source_id: event.feed_id }).success).toBe(false);
      if (event.duration_ms !== null) expect(event.duration_ms).toBeGreaterThanOrEqual(0);
    }
    const parserEvents = recorded.events.filter(event => event.operation === "parse");
    expect(parserEvents.length).toBeGreaterThan(0);
    for (const event of parserEvents) {
      expect(event.feed_id).toBe("recorded-news");
      if (event.phase === "started") expect(event.duration_ms).toBeNull();
      else expect(event.duration_ms).not.toBeNull();
      if (event.duration_ms !== null) expect(event.duration_ms).toBeGreaterThanOrEqual(0);
    }
    expect(result).not.toHaveProperty("events");
    expect(JSON.stringify(progress)).not.toContain(result.selected[0]!.article_text);
    expect(JSON.stringify(recorded.events)).not.toContain(result.selected[0]!.article_text);
  } finally { await recorded.close(); }
});
