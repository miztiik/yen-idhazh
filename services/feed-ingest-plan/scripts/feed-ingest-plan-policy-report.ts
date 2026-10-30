/** Which effective controls governed this invocation rather than its committed defaults? */
import { z } from "zod";
import { FeedIngestConfigSchema } from "../../../packages/common-contracts/src/index";
import { PlanRequestSchema, resolvePlanRequest } from "../src/api/plan-request";
import { resolvePolicy } from "../src/config/resolve-policy";
import { resolveRunPolicy, RunPolicyOverridesSchema } from "../src/config/resolve-run-policy";
import { FeedAvailabilityConfigSchema } from "../src/availability/availability-config";
import { FeedHistoryPolicySchema } from "../src/read-ledger-history/read-feed-history";
import { escapeMarkdown } from "../src/reporting/markdown-format";
import {
  allocateSourceBasedQualityBucketBudgets, resolveSourceBasedQualityBucketWindows,
} from "../src/article-freshness-policy";

export const WorkflowPolicySchema = z.strictObject({
  config: FeedIngestConfigSchema,
  request: PlanRequestSchema.extend(RunPolicyOverridesSchema.shape),
  history: FeedHistoryPolicySchema.extend({
    max_future_hours: z.number().finite().nonnegative(),
    published_window_days: z.int().nonnegative(),
    settled_failure_codes: z.array(z.string()),
  }),
  parser_concurrency: z.int().positive(),
  availability: FeedAvailabilityConfigSchema.optional(),
});

export function formatWorkflowPolicy(input: unknown, selectionRan: boolean) {
  if (input === undefined) return {
    notice: "Applied settings were not recorded; committed defaults do not prove what this run used.",
    rows: [["Effective settings", "Settings used by the run", "Not recorded; defaults are not evidence"]],
  };
  const { config: recordedConfig, request: supplied, history, parser_concurrency, availability } = WorkflowPolicySchema.parse(input);
  const config = resolveRunPolicy(recordedConfig, supplied);
  const { institutional_age_hours: _institutional, trade_press_age_hours: _trade,
    community_age_hours: _community, ...selectionRequest } = supplied;
  const request = resolvePlanRequest(selectionRequest, config);
  const policy = resolvePolicy({ config });
  const percent = (value: number) => `${(value * 100).toFixed(2)} percent`;
  const source = (key: keyof typeof supplied) => supplied[key] === undefined ? "configuration" : "workflow override";
  const maximum = `${request.article_limit} articles (${source("article_limit")})`;
  const ageSources: Record<string, keyof typeof supplied> = {
    institutional: "institutional_age_hours", "trade-press": "trade_press_age_hours", community: "community_age_hours",
  };
  const ages = config.curate_articles.source_based_quality_buckets.map(rule =>
    `${rule.id} (source tier ${rule.source_tier_id}): ${resolveSourceBasedQualityBucketWindows(rule).steps.join(" / ")} hours`
      + ` (${ageSources[rule.id] === undefined ? "configuration" : source(ageSources[rule.id]!)})`).join("; ");
  const rows = [
    ["Selection", "Whether these controls governed selection", selectionRan ? "Applied" : "Requested; selection did not run"],
    ["Age windows", "Source-based article age windows", ages],
    ["Article cap", "Maximum articles selected", maximum],
    ["Workers", "Count and assignment method", config.partition.enabled
      ? `${request.shards}; ${request.partition_strategy} (count: ${source("shards")}; method: ${source("partition_strategy")})`
      : "Worker assignment disabled (configuration)"],
    ["Fetch and parse", "Fetch concurrency / deadline per HTTP attempt / parse deadline including queue / parser workers",
      `${config.harvest.concurrency} / ${config.harvest.fetch_timeout_ms} ms / ${config.harvest.parse_timeout_ms} ms / ${parser_concurrency}`],
    ["Minimum text", "Parsed words required", `${policy.triage.min_words} words`],
    ["Recency", "Half-life / score weight", `${policy.triage.recency_half_life_hours} hours / ${policy.triage.recency_weight}`],
    ["Feed authority", "Estimated source authority weight; not an article-quality verdict", `${policy.curate_articles.source_authority_weight}`],
    ["Source-based budgets", "Article targets / fresh ceilings; not article quality verdicts", allocateSourceBasedQualityBucketBudgets(config, request.article_limit).map(budget =>
      `${budget.rule.id} (source tier ${budget.rule.source_tier_id}): ${budget.target} / ${budget.ceiling}`).join("; ")],
    ["Portfolio limits", "Per-feed share / website-group share / distinct feeds", `${percent(config.curate_articles.soft_caps.max_source_share)} / ${percent(config.curate_articles.soft_caps.max_website_group_share)} / ${config.curate_articles.soft_caps.min_distinct_sources}`],
    ["Limit relaxation", "Order when portfolio limits conflict", config.curate_articles.soft_caps.relaxation_order.map(limit =>
      ({ distinct_sources: "distinct-feed target", source_share: "per-feed share" })[limit]).join(", ") || "None"],
    ["Diversity", "Publisher / website-group deductions", `${policy.curate_articles.mmr_weights.lambda_source} / ${policy.curate_articles.mmr_weights.lambda_website_group}`],
    ["Exploration", "Share for feeds not yet chosen", percent(config.curate_articles.exploration_slot_share)],
    ["Feed-status lookback", "History used for reporting; not the timed-rest clock", `${config.feedback.lifecycle_window_days} UTC days`],
    ["Durable feed availability", "Consecutive failures / initial rest / recovery rest / failed recovery checks and minimum episode age",
      availability === undefined ? "Not recorded; effective availability controls are unavailable"
        : `${availability.consecutive_failed_checks_before_rest} / ${availability.rest_hours} hours / `
          + `${availability.recovery_rest_hours} hours / ${availability.failed_recovery_checks_before_retirement} / `
          + `${availability.retirement_minimum_age_hours} hours`],
    ["Reliability adjustment", "History days / minimum authority / article-pass adjustment", `${history.reliability_window_days} UTC days / ${percent(history.reliability_floor)} / ${config.curate_articles.source_reliability_penalty_enabled ? "on" : "off"}`],
    ["Request history", "Completed UTC days counted", `${config.feedback.request_report_closed_days} days`],
    ["Article history", "Discovery / prior-publication window / future tolerance", `${config.discovered_articles.lookback_days} / ${history.published_window_days} UTC days / ${history.max_future_hours} hours`],
    ["Article exclusions", "Blocked HTTP statuses / categories / URL rules", `${config.triage.blocked_http_statuses.join(", ")} / ${config.harvest.blocked_categories.join(", ") || "none"} / ${config.harvest.url_exclusions.length}`],
  ];
  return {
    notice: `${selectionRan ? "Applied" : "Requested only"}: max ${maximum}; `
      + `${config.partition.enabled ? `${request.shards} workers (${request.partition_strategy})` : "worker assignment disabled"}; `
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
