/** Do source observations account for real entries, inactive feeds and every first loss? */
import { expect, test } from "bun:test";
import { runFeedPlan } from "../src/run-feed-plan";
import { reconcileStageMembership } from "../src/metrics/stage-membership";
import { deriveSourceRunSummaries } from "../src/metrics/source-run-summary";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";
import { deriveCandidateId } from "@idhazh/common-contracts";

test("real stage membership includes inactive, empty, failed and carrier sources without double counting", async () => {
  const recorded = await recordedPlan([
    source(), source({ id: "other-carrier", kind: "research" }),
    source({ id: "inactive", status: "draft" }),
    source({ id: "empty", url: "https://news.example/empty.xml" }),
    source({ id: "failed", url: "https://news.example/malformed.xml" }),
  ]);
  try {
    const result = await runFeedPlan({ partition_strategy: "none" }, recorded.inputs, recorded.runtime);
    const membership = reconcileStageMembership(result);
    const summaries = deriveSourceRunSummaries(result, membership);
    expect(summaries).toHaveLength(5);
    const active = summaries.filter(row => ["recorded-news", "other-carrier"].includes(row.source_id));
    expect(active.reduce((sum, row) => sum + row.parsed_count!, 0)).toBe(6);
    expect(active.reduce((sum, row) => sum + row.harvested_count!, 0)).toBe(4);
    expect(active.reduce((sum, row) => sum + row.eligible_count!, 0)).toBe(4);
    expect(active.reduce((sum, row) => sum + row.duplicate_count!, 0)).toBe(2);
    expect(active.reduce((sum, row) => sum + row.selected_count!, 0)).toBe(2);
    expect(summaries.find(row => row.source_id === "inactive")).toMatchObject({
      fetch_status: "not_requested", parse_status: "not_attempted", parsed_count: null,
      harvested_count: null, fetch_duration_ms: null, parse_duration_ms: null,
      eligible_count: 0, selected_count: 0, last_failure_reason: null,
      drop_reasons: [{ subject: "feed", stage: "harvest-feeds", reason: "SOURCE_INACTIVE", count: 1 }],
    });
    expect(summaries.find(row => row.source_id === "empty")).toMatchObject({
      parse_status: "empty", parsed_count: 0, harvested_count: 0, last_failure_reason: null,
    });
    expect(summaries.find(row => row.source_id === "failed")).toMatchObject({
      fetch_status: "success", parse_status: "failure", parsed_count: null,
      last_failure_at: result.context.now, last_failure_reason: "FEED_PARSE_FAILED",
    });
    for (const summary of summaries) {
      expect(summary).not.toHaveProperty("observation_phase");
      expect(summary).not.toHaveProperty("completion_evidence");
      expect(summary.published_count).toBeNull();
      expect(summary.lead_count).toBeNull();
      expect(summary.history_success_fraction).toBeNull();
      expect(summary.history_success_attempts).toBeNull();
      expect(summary.history_window_days).toBeNull();
      expect(summary.source.kind).toBe(result.evidence.harvest.feed_outcomes.find(row =>
        row.source.source_id === summary.source_id)!.source.kind);
    }
    expect(membership.eligible.length).toBe(membership.selected.length
      + result.evidence.curation.rejections.length);
    expect(membership.trace).toEqual(result.evidence.curation.trace);
    expect(membership.carrier_groups).toEqual(result.evidence.curation.carriers.groups);
    const before = structuredClone(result);
    result.events[0]!.attempt++;
    expect(() => reconcileStageMembership(result)).toThrow("events.run");
    result.events = before.events;
    result.evidence.screening.rejections.push(result.evidence.harvest.rejections.find(row => row.subject === "article")!);
    expect(() => reconcileStageMembership(result)).toThrow("first terminal loss");
  } finally { await recorded.close(); }
}, 30000);

test("screening and normalization counts derive from actual memberships, not aggregate events", async () => {
  const recorded = await recordedPlan();
  try {
    const result = await runFeedPlan({ freshness_hours: 12, partition_strategy: "none" }, recorded.inputs, recorded.runtime);
    const membership = reconcileStageMembership(result);
    const [summary] = deriveSourceRunSummaries(result, membership);
    expect(summary).toMatchObject({
      harvested_count: 0, fresh_count: 0, eligible_count: 0, normalized_count: 0, selected_count: 0,
    });
    expect(summary!.drop_reasons).toContainEqual({
      subject: "article", stage: "harvest-feeds", reason: "STALE_MAX_AGE_EXCEEDED", count: 2,
    });
    const completion = result.events.find(event => event.payload.kind === "stage_completion"
      && event.stage === "screen-article-candidates")!;
    if (completion.payload.kind !== "stage_completion") throw new Error("Missing real completion");
    completion.payload.output_count++;
    expect(() => reconcileStageMembership(result)).toThrow("counts");
  } finally { await recorded.close(); }
}, 30000);

test("recorded operational evidence keeps its attempts and window separate from article quality", async () => {
  const recorded = await recordedPlan();
  recorded.runtime.evidence = new Map([0, 2].map(ordinal => [
    deriveCandidateId("2026-10-21-700", "recorded-news", ordinal), {
      publisher: { value: "Recorded publisher", origin: "recorded-publisher-attribute" },
      parent_domain: null, primary_evidence: null, estimated_work: 300,
      operational: { success_fraction: 0.5, attempted: 4, window_days: 7 },
    },
  ]));
  try {
    const result = await runFeedPlan({ partition_strategy: "none" }, recorded.inputs, recorded.runtime);
    const [summary] = deriveSourceRunSummaries(result, reconcileStageMembership(result));
    expect(summary).toMatchObject({
      history_success_fraction: 0.5, history_success_attempts: 4, history_window_days: 7,
    });
    for (const measurement of result.evidence.curation.quality) {
      expect(measurement.operational).toEqual({ success_fraction: 0.5, attempted: 4, window_days: 7 });
      expect(measurement.base_article_score).toBe(measurement.components.authority + measurement.components.recency);
      expect(measurement.article.informative_verdict).toBeNull();
    }
    const membership = reconcileStageMembership(result);
    const article = result.evidence.curation.input[1]!;
    result.evidence.curation.input[1] = {
      ...article, evidence: { ...article.evidence, operational: { success_fraction: 1, attempted: 4, window_days: 7 } },
    };
    expect(() => deriveSourceRunSummaries(result, membership)).toThrow("operational_history");
  } finally { await recorded.close(); }
}, 30000);
