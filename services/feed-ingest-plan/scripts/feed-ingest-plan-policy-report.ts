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
    notice: "Effective settings were not recorded; committed defaults do not prove what this run used.",
    rows: [["Effective settings", "Not recorded", "Policy evidence unavailable"]],
  };
  const { config, request: supplied, history, parser_concurrency } = WorkflowPolicySchema.parse(input);
  const request = resolvePlanRequest(supplied, config);
  const policy = resolvePolicy({ config });
  const source = (key: keyof typeof supplied) => supplied[key] === undefined ? "configuration" : "workflow override";
  const configured = (label: string, value: string | number | boolean): [string, string, string] =>
    [label, String(value), "configuration"];
  const rows: [string, string, string][] = [
    configured("Policy config version", config.version),
    ["Article limit", String(request.article_limit), source("article_limit")],
    ["Article assignments", String(request.shards), source("shards")],
    ["Assignment strategy", request.partition_strategy, source("partition_strategy")],
    configured("Fetch concurrency", config.harvest.concurrency),
    configured("Fetch timeout (ms)", config.harvest.fetch_timeout_ms),
    configured("Parser workers", parser_concurrency),
    configured("Minimum article words", policy.triage.min_words),
    configured("Recency half-life (hours)", policy.triage.recency_half_life_hours),
    configured("Recency weight", policy.triage.recency_weight),
    configured("Authority coefficient", policy.curate_articles.source_authority_weight),
    ...allocateArticleQualityBucketBudgets(config, request.article_limit).flatMap(budget => [
      configured(`Tier ${budget.rule.tier} age steps (hours)`, resolveArticleQualityBucketWindows(budget.rule).steps.join(" / ")),
      [`Tier ${budget.rule.tier} article target / ceiling`, `${budget.target} / ${budget.ceiling}`, "effective article limit and configuration"] satisfies [string, string, string],
    ]),
    configured("Per-feed share limit (fraction)", config.curate_articles.soft_caps.max_source_share),
    configured("Website-group share limit (fraction)", config.curate_articles.soft_caps.max_website_group_share),
    configured("Distinct-feed target", config.curate_articles.soft_caps.min_distinct_sources),
    configured("Limit relaxation order", JSON.stringify(config.curate_articles.soft_caps.relaxation_order)),
    configured("Publisher exposure weight", policy.curate_articles.mmr_weights.lambda_source),
    configured("Website-group exposure weight", policy.curate_articles.mmr_weights.lambda_website_group),
    configured("Exploration share (fraction)", config.curate_articles.exploration_slot_share),
    configured("Feed-status history (represented UTC days)", config.feedback.lifecycle_window_days),
    configured("Failing checks before rest", history.availability_strikes_before_rest),
    configured("Rested runs before retry", history.availability_strikes_before_rest),
    configured("Reliability history (represented UTC days)", history.reliability_window_days),
    configured("Reliability floor (fraction)", history.reliability_floor),
    configured("Article-pass adjustment enabled", config.curate_articles.source_reliability_penalty_enabled),
    configured("Request history (closed UTC days)", config.feedback.request_report_closed_days),
    configured("Discovery history (UTC days)", config.discovered_articles.lookback_days),
    configured("Prior-publication history (UTC days)", history.published_window_days),
    configured("Future-date tolerance (hours)", history.max_future_hours),
    configured("Blocked HTTP statuses", JSON.stringify(config.triage.blocked_http_statuses)),
    configured("Blocked categories", JSON.stringify(config.harvest.blocked_categories)),
    configured("URL exclusion rules", config.harvest.url_exclusions.length),
  ];
  return {
    notice: `Policy config version: ${config.version}; selection started: ${selectionRan}; `
      + `article limit: ${request.article_limit} (${source("article_limit")}); article assignments: ${request.shards}; `
      + `strategy: ${request.partition_strategy}; article-pass adjustment enabled: `
      + `${config.curate_articles.source_reliability_penalty_enabled}. Full settings are in Effective policy.`,
    rows,
  };
}

export function formatPolicyTable(input: unknown, selectionRan: boolean) {
  const policy = formatWorkflowPolicy(input, selectionRan);
  const overrides = policy.rows.filter(([, , source]) => source === "workflow override").map(([setting]) => setting);
  return {
    notice: policy.notice,
    summary: [
      "## Table B - Effective policy", "",
      "| Id | Setting | Effective value |", "| --- | --- | --- |",
      ...policy.rows.map(([setting, value], index) =>
        `| B${index + 1} | ${escapeMarkdown(setting!)} | ${escapeMarkdown(value!)} |`),
      ...(input === undefined ? ["", "Policy evidence was not supplied; committed defaults are not evidence."] : [
        "", `Workflow overrides: ${overrides.length ? overrides.map(value => escapeMarkdown(value!)).join(", ") : "none"}. `
          + "Other controls use configuration; tier targets and ceilings use the effective article limit.",
      ]),
      "", "The article limit is a maximum. Selection started is a run fact, not an enabled setting.",
      "Shares and the reliability floor use the JSON fractions: 0 means none; 1 means the whole.",
      "Authority multiplies the coefficient by each feed's configured weight and source-tier weight; it is not the tier weight alone.",
      "A productive feed check returns at least one usable URL. Rest requires known failure history; retry follows the configured skipped-run count, not a UTC timer.",
      "bin-pack balances estimated article work; round-robin assigns in selected order; none uses one assignment.",
      "",
    ].join("\n"),
  };
}
