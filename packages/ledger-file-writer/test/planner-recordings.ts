/** Bounded current planner inputs for real native-file writer checks. */
import {
  DiscoveredArticleRowContract, DiscoveredArticleRowSchema, FeedHealthStateRowContract,
  FeedHealthStateRowSchema, PlanRunRowContract, PlanRunRowSchema,
  SelectedArticleRowContract, SelectedArticleRowSchema, SelectedArtifactArticleSchema,
  deriveUrlKey, selectedArticleMetadata,
} from "@idhazh/common-contracts";
import type { LedgerRowContract } from "../src/ledger-types";

export function selectedArticle(day = "2026-10-20") {
  return SelectedArtifactArticleSchema.parse({
    url_key: deriveUrlKey("https://example.org/article/1"), feed_id: "fixture-feed",
    publisher_id: null, canonical_url: "https://example.org/article/1", title: "Caf\u00e9 \u6771\u4eac",
    categories: ["world", "science"], article_text: "Sanitized artifact-only body.",
    author: null, published_at: `${day}T10:00:00.123Z`, published_at_source: "selection",
    tier: 1, weight: 1, applied_tier_weight: 0.5,
    editorial_rank: 1, estimated_work: 180, worker_assignment: 0,
    ratings: {
      base_article_score: 1.5, marginal_score: 1.25, adjustments: [
        { term: "feed-reliability", value: null }, { term: "publisher-exposure", value: 0 },
        { term: "domain", value: -0.25 },
      ], recency_score: 1, feed_authority_score: 0.5,
    },
    feed_allowance: 3, exploration_slot: false, cap_relaxations: [],
    timing_at: `${day}T10:00:00.123Z`, timing_basis: "first_seen", age_hours: 0,
    allowance_reasons: [],
  });
}

export type PlannerRecording = {
  name: "discovered-articles" | "selected-articles" | "feed-health-state" | "plan-runs";
  row: Record<string, unknown>;
  contract: LedgerRowContract<Record<string, unknown>>;
};

export function plannerRecordings(day = "2026-10-20", attempt = 1, execution = 1): PlannerRecording[] {
  const run_id = `${day}-${execution}`;
  const at = `${day}T10:00:00.123Z`;
  return [
    {
      name: "discovered-articles", contract: DiscoveredArticleRowContract,
      row: DiscoveredArticleRowSchema.parse({ url_key: selectedArticle(day).url_key, first_seen_at: at, date: day }),
    },
    {
      name: "selected-articles", contract: SelectedArticleRowContract,
      row: SelectedArticleRowSchema.parse({
        ...selectedArticleMetadata(selectedArticle(day)), run_id, attempt, date: day,
      }),
    },
    {
      name: "feed-health-state", contract: FeedHealthStateRowContract,
      row: FeedHealthStateRowSchema.parse({
        feed_id: "fixture-feed", endpoint_key: deriveUrlKey("https://example.org/feed"),
        checked_at: at, permission: "allowed", availability: "eligible", strikes: 0,
        rested_runs: 0, last_failure_code: null, status: 200,
        reliability: {
          productive: 0, attempted: 0, success_fraction: null, from_day: null,
          through_day: null, production_factor: null, complete: false,
        },
        date: day, feed_reads: 1, productive_reads: 1, failed_reads: 0,
        article_candidates: 1, articles_selected: 1, feed_requests: 2,
        article_requests: 1, robots_requests: 0, counts_complete: true,
        rejection_counts: [], run_id, attempt, items: 1, outcome: "ok",
      }),
    },
    {
      name: "plan-runs", contract: PlanRunRowContract,
      row: PlanRunRowSchema.parse({
        run_id, started_at: at, duration_ms: 25, status: "completed", failure_code: null,
        selected_count: 0, strategy: "none", dispatch_count: 0, selected_articles_artifact: null,
        api_timings: [{ operation: "feed-health-before-fetch", duration_ms: 0, status: "completed" }],
        date: day, attempt, lifecycle_window_days: 31, reliability_floor: 0.5,
        reliability_penalty_enabled: true, evaluated_at: at, request_report_closed_days: 7,
        reliability_window_days: 30, selection_started_at_utc: null,
      }),
    },
  ];
}
