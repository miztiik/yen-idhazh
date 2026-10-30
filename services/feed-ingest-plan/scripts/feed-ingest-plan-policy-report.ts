/** Which effective controls governed this invocation rather than its committed defaults? */
import { z } from "zod";
import { FeedIngestConfigSchema } from "../../../packages/common-contracts/src/index";
import { PlanRequestSchema, resolvePlanRequest } from "../src/api/plan-request";
import { resolvePolicy } from "../src/config/resolve-policy";
import { FeedHistoryPolicySchema } from "../src/read-ledger-history/read-feed-history";
import { escapeMarkdown } from "../src/reporting/markdown-format";
import {
  allocateArticleQualityBucketBudgets, resolveArticleQualityBucketWindows,
} from "../src/article-freshness-policy";

export const WorkflowPolicySchema = z.strictObject({
  config: FeedIngestConfigSchema,
  request: PlanRequestSchema,
  history: FeedHistoryPolicySchema.extend({
    max_future_hours: z.number().finite().nonnegative(),
    published_window_days: z.int().nonnegative(),
    settled_failure_codes: z.array(z.string()),
  }),
  parser_concurrency: z.int().positive(),
});

export function formatWorkflowPolicy(input: unknown, selectionRan: boolean) {
  if (input === undefined) return {
    notice: "Applied settings were not recorded; committed defaults do not prove what this run used.",
    rows: [["Effective settings", "Settings used by the run", "Not recorded; defaults are not evidence"]],
  };
  const { config, request: supplied, history, parser_concurrency } = WorkflowPolicySchema.parse(input);
  const request = resolvePlanRequest(supplied, config);
  const policy = resolvePolicy({ config });
  const percent = (value: number) => `${(value * 100).toFixed(2)} percent`;
  const source = (key: keyof typeof supplied) => supplied[key] === undefined ? "configuration" : "workflow override";
  const maximum = `${request.article_limit} articles (${source("article_limit")})`;
  const ages = config.curate_articles.article_quality_buckets.map(rule =>
    `Tier ${rule.tier}: ${resolveArticleQualityBucketWindows(rule).steps.join(" / ")} hours`).join("; ");
  const rows = [
    ["Selection", "Whether these controls governed selection", selectionRan ? "Applied" : "Requested; selection did not run"],
    ["Age windows", "Article freshness tiers", `${ages} (configuration)`],
    ["Article cap", "Maximum articles selected", maximum],
    ["Workers", "Count and assignment method", `${request.shards}; ${request.partition_strategy} (count: ${source("shards")}; method: ${source("partition_strategy")})`],
    ["Fetch and parse", "Fetch concurrency / timeout / parser workers", `${config.harvest.concurrency} / ${config.harvest.fetch_timeout_ms} ms / ${parser_concurrency}`],
    ["Minimum text", "Parsed words required", `${policy.triage.min_words} words`],
    ["Recency", "Half-life / score weight", `${policy.triage.recency_half_life_hours} hours / ${policy.triage.recency_weight}`],
    ["Feed authority", "Base authority weight", `${policy.curate_articles.source_authority_weight}`],
    ["Quality budgets", "Article targets / freshness ceilings by tier", allocateArticleQualityBucketBudgets(config, request.article_limit).map(budget =>
      `Tier ${budget.rule.tier}: ${budget.target} / ${budget.ceiling}`).join("; ")],
    ["Portfolio limits", "Per-feed share / website-group share / distinct feeds", `${percent(config.curate_articles.soft_caps.max_source_share)} / ${percent(config.curate_articles.soft_caps.max_website_group_share)} / ${config.curate_articles.soft_caps.min_distinct_sources}`],
    ["Limit relaxation", "Order when portfolio limits conflict", config.curate_articles.soft_caps.relaxation_order.map(limit =>
      ({ distinct_sources: "distinct-feed target", source_share: "per-feed share" })[limit]).join(", ") || "None"],
    ["Diversity", "Publisher / website-group deductions", `${policy.curate_articles.mmr_weights.lambda_source} / ${policy.curate_articles.mmr_weights.lambda_website_group}`],
    ["Exploration", "Share for feeds not yet chosen", percent(config.curate_articles.exploration_slot_share)],
    ["Feed-status lookback", "Days / failed checks before a feed rests", `${config.feedback.lifecycle_window_days} UTC days / ${history.availability_strikes_before_rest}`],
    ["Reliability adjustment", "History days / minimum authority / article-pass adjustment", `${history.reliability_window_days} UTC days / ${percent(history.reliability_floor)} / ${config.curate_articles.source_reliability_penalty_enabled ? "on" : "off"}`],
    ["Request history", "Completed UTC days counted", `${config.feedback.request_report_closed_days} days`],
    ["Article history", "Discovery / prior-publication window / future tolerance", `${config.discovered_articles.lookback_days} / ${history.published_window_days} UTC days / ${history.max_future_hours} hours`],
    ["Article exclusions", "Blocked HTTP statuses / categories / URL rules", `${config.triage.blocked_http_statuses.join(", ")} / ${config.harvest.blocked_categories.join(", ") || "none"} / ${config.harvest.url_exclusions.length}`],
  ];
  return {
    notice: `${selectionRan ? "Applied" : "Requested only"}: max ${maximum}; ${request.shards} workers (${request.partition_strategy}); `
      + `authority floor ${percent(history.reliability_floor)}; article-pass adjustment `
      + `${config.curate_articles.source_reliability_penalty_enabled ? "on" : "off"}. Full settings are in Applied policy.`,
    rows,
  };
}

export function formatPolicyTable(input: unknown, selectionRan: boolean) {
  const policy = formatWorkflowPolicy(input, selectionRan);
  return {
    notice: policy.notice,
    summary: [
      "## Table B - Applied policy", "",
      "| Id | Setting | What it controls | Effective value |", "| --- | --- | --- | --- |",
      ...policy.rows.map(([setting, meaning, value], index) =>
        `| B${index + 1} | ${escapeMarkdown(setting!)} | ${escapeMarkdown(meaning!)} | ${escapeMarkdown(value!)} |`),
      "",
    ].join("\n"),
  };
}
