/** Which effective controls governed this invocation rather than its committed defaults? */
import { z } from "zod";
import { FeedIngestConfigSchema } from "../../../packages/common-contracts/src/index";
import { PlanRequestSchema, resolvePlanRequest } from "../src/api/plan-request";
import { resolvePolicy } from "../src/config/resolve-policy";
import { FeedHistoryPolicySchema } from "../src/read-ledger-history/read-feed-history";
import { escapeMarkdown } from "./feed-ingest-plan-report-format";
import { allocateTierBudgets, resolveTierWindows } from "../src/article-freshness-policy";

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
    notice: "Effective settings were not saved. Committed defaults do not prove which controls this run used.",
    rows: [["Effective settings", "Unavailable; committed defaults are not evidence of the controls used"]],
  };
  const { config, request: supplied, history, parser_concurrency } = WorkflowPolicySchema.parse(input);
  const request = resolvePlanRequest(supplied, config);
  const policy = resolvePolicy({ config });
  const percent = (value: number) => `${(value * 100).toFixed(2)} percent`;
  const source = (key: keyof typeof supplied) => supplied[key] === undefined ? "configuration" : "workflow override";
  const maximum = `${request.article_limit} articles`;
  const ages = config.curate_articles.feed_quality_tiers.map(rule =>
    `Tier ${rule.tier}: ${resolveTierWindows(rule, request.freshness_hours).steps.join(" / ")} hours`).join("; ");
  const workers = `${request.shards} workers; ${request.partition_strategy}`;
  const rows = [
    ["Application", selectionRan ? "Selection ran with these effective controls" : "Requested controls; selection did not run"],
    ["Article age windows", `${ages} (${source("freshness_hours")})`],
    ["Article limit", `${maximum} (${source("article_limit")})`],
    ["Worker assignment", `${workers} (count: ${source("shards")}; distribution: ${source("partition_strategy")})`],
    ["Extraction", `${config.harvest.concurrency} concurrent fetches; ${config.harvest.fetch_timeout_ms} milliseconds fetch timeout; ${parser_concurrency} parser workers`],
    ["Minimum text", `${policy.triage.min_words} words per parsed item`],
    ["Recency score", `${policy.triage.recency_half_life_hours} hours half-life; weight ${policy.triage.recency_weight}`],
    ["Feed authority score", `Weight ${policy.curate_articles.source_authority_weight}; technical article-pass adjustment ${config.curate_articles.source_reliability_penalty_enabled ? "enabled" : "disabled"}; RSS reliability controls access only`],
    ["Tier article budgets", allocateTierBudgets(config, request.article_limit).map(budget =>
      `Tier ${budget.rule.tier}: target ${budget.target} articles; fresh ceiling ${budget.ceiling} articles`).join("; ")],
    ["Portfolio limits", `${percent(config.curate_articles.soft_caps.max_source_share)} per feed; ${percent(config.curate_articles.soft_caps.max_website_group_share)} per known website group; target ${config.curate_articles.soft_caps.min_distinct_sources} distinct feeds`],
    ["Limit relaxation order", config.curate_articles.soft_caps.relaxation_order.map(limit =>
      ({ distinct_sources: "distinct-feed target", source_share: "per-feed share" })[limit]).join(", ") || "No relaxation"],
    ["Diversity score deductions", `Publisher exposure ${policy.curate_articles.mmr_weights.lambda_source}; known website group ${policy.curate_articles.mmr_weights.lambda_website_group}`],
    ["Exploration slots", `${percent(config.curate_articles.exploration_slot_share)} for feeds not yet chosen when available`],
    ["History", `${config.discovered_articles.lookback_days} UTC days for article discovery; ${history.published_window_days} UTC days for prior publication; ${history.max_future_hours} hours future-time tolerance`],
    ["Article exclusions", `Blocked HTTP statuses: ${config.triage.blocked_http_statuses.join(", ")}; blocked categories: ${config.harvest.blocked_categories.join(", ") || "none"}; ${config.harvest.url_exclusions.length} configured URL exclusions`],
  ];
  return {
    notice: `${selectionRan ? "Used" : "Requested; selection did not run"}: ${ages}; `
      + `${maximum}; ${workers}; technical article-pass adjustment ${config.curate_articles.source_reliability_penalty_enabled ? "enabled" : "disabled"}. `
      + "The job summary records the effective scoring, exclusions, tier budgets and portfolio limits.",
    rows,
  };
}

export function formatPolicyTable(input: unknown, selectionRan: boolean) {
  const policy = formatWorkflowPolicy(input, selectionRan);
  return {
    notice: policy.notice,
    summary: [
      "## Table F - Policy used", "",
      "| Id | Control | Effective value |", "| --- | --- | --- |",
      ...policy.rows.map(([control, value], index) => `| F${index + 1} | ${escapeMarkdown(control!)} | ${escapeMarkdown(value!)} |`),
      "",
    ].join("\n"),
  };
}
