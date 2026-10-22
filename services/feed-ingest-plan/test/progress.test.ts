/** Are source and article progress visible before the harvest batch finishes? */
import { expect, test } from "bun:test";
import { runFeedPlan } from "../src/run-feed-plan";
import type { ProgressRecord } from "../src/logging/progress-logger";
import { recordedPlan } from "./plan-recordings";

test("live progress uses the documented UUID envelope before buffered audit and native completion", async () => {
  const recorded = await recordedPlan();
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
    expect(types.indexOf("FEED_FETCH_COMPLETED")).toBeLessThan(types.indexOf("ARTICLE_EXTRACTION_STARTED"));
    expect(types).toContain("ARTICLE_EXTRACTION_COMPLETED");
    expect(types.at(-1)).toBe("PLANNING_STAGES_COMPLETED");
    expect(new Set(progress.map(event => event.eventId)).size).toBe(progress.length);
    for (const event of progress) {
      expect(event.eventId).toMatch(/^evt_[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
      expect(event.correlationId).toBe(result.context.correlation_id);
      expect(event.correlationId).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
      expect(event.message).toBe(`Pipeline Event: ${event.eventType}`);
      expect(event.timestamp).toMatch(/Z$/);
      expect(event.durationMs).toBeGreaterThanOrEqual(0);
    }
    for (const event of result.events) {
      expect(event.event_id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
      expect(event.correlation_id).toBe(result.context.correlation_id);
    }
  } finally { await recorded.close(); }
});
