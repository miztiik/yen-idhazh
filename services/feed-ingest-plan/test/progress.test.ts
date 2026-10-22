/** Are source and article progress visible before the harvest batch finishes? */
import { expect, test } from "bun:test";
import { runFeedPlan } from "../src/run-feed-plan";
import type { ProgressRecord } from "../src/logging/progress-logger";
import { recordedPlan } from "./plan-recordings";
import { parseFeed } from "../src/harvest-feeds/feed-client";

test("live progress uses the documented UUID envelope before buffered audit and native completion", async () => {
  const recorded = await recordedPlan();
  const first = (await parseFeed(recorded.transport.recordings.bodies.rss))[0]!;
  if (first.link === null) throw new Error("Recorded entry must identify its target");
  recorded.transport.recordings.responses[first.link] = [{
    status: 200,
    body: recorded.transport.recordings.bodies.article.replace("</head>", '<script type="application/ld+json">{</script></head>'),
  }];
  const progress: ProgressRecord[] = [];
  let earlyFeed = false;
  recorded.runtime.progress = event => {
    progress.push(event);
    if (event.eventType === "FEED_FETCH_COMPLETED") earlyFeed = recorded.events.length === 0;
  };
  try {
    const result = await runFeedPlan({ article_limit: 1, partition_strategy: "none" }, recorded.inputs, recorded.runtime);
    expect(earlyFeed).toBe(true);
    expect(progress[0]!.eventType).toBe("PIPELINE_STARTED");
    const types = progress.map(event => event.eventType);
    expect(types).toContain("FEED_DISCOVERY_STARTED");
    expect(types.indexOf("FEED_FETCH_COMPLETED")).toBeLessThan(types.indexOf("ARTICLE_HARVEST_STARTED"));
    expect(types).toContain("ARTICLE_HARVEST_COMPLETED");
    const warning = progress.find(event => event.eventType === "ARTICLE_EXTRACTION_WARNING")!;
    if (!warning?.diagnostics) throw new Error("Extraction warning must retain diagnostic evidence");
    expect(warning.level).toBe("WARN");
    expect(warning.source_id).toBe("recorded-news");
    expect(warning.diagnostics?.warnings).toEqual(["malformed-json-ld"]);
    const article = result.evidence.harvest.articles.find(item => item.observation.candidate_id === warning.candidate_id)!;
    expect(article.candidate).not.toBeNull();
    expect(article.observation.diagnostics).toEqual(warning.diagnostics);
    expect(result.events.some(event => event.payload.kind === "candidate_decision"
      && event.payload.assessment.candidate_id === warning.candidate_id
      && event.payload.assessment.diagnostics?.warnings.includes("malformed-json-ld"))).toBe(true);
    expect(types.at(-1)).toBe("PLANNING_STAGES_COMPLETED");
    expect(new Set(progress.map(event => event.eventId)).size).toBe(progress.length);
    for (const event of progress) {
      expect(event.eventId).toMatch(/^evt_[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
      expect(event.correlationId).toBe(result.context.correlation_id);
      expect(event.correlationId).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
      expect(event.message).toBe(`Pipeline Event: ${event.eventType}`);
      expect(event.timestamp).toMatch(/Z$/);
      if (["FEED_FETCH_COMPLETED", "ARTICLE_HARVEST_COMPLETED"].includes(event.eventType)) {
        expect(event.durationMs).toBeGreaterThanOrEqual(0);
        expect(event).toHaveProperty("diagnostics");
        if (event.diagnostics !== null) expect(event.diagnostics?.fetch_ms).toBeGreaterThanOrEqual(0);
      } else expect(event.durationMs).toBeNull();
    }
    for (const event of result.events) {
      expect(event.event_id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
      expect(event.correlation_id).toBe(result.context.correlation_id);
    }
  } finally { await recorded.close(); }
});
