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
    notice: "Effective settings were not recorded; committed defaults do not prove what this run used.",
    rows: [["Effective settings", "Not recorded", "Policy evidence unavailable"]],
  };
  const { config: recordedConfig, request: supplied, history, parser_concurrency, availability } = WorkflowPolicySchema.parse(input);
  const config = resolveRunPolicy(recordedConfig, supplied);
  const { institutional_age_hours: _institutional, trade_press_age_hours: _trade,
    community_age_hours: _community, ...selectionRequest } = supplied;
  const request = resolvePlanRequest(selectionRequest, config);
  const policy = resolvePolicy({ config });
  const source = (key: keyof typeof supplied) => supplied[key] === undefined ? "configuration" : "workflow override";
  const assignmentSource = (key: "shards" | "partition_strategy") => config.partition.enabled
    ? source(key) : supplied[key] === undefined ? "partition disabled" : "ignored workflow override";
  const configured = (label: string, value: string | number | boolean): [string, string, string] =>
    [label, String(value), "configuration"];
  const ageSources: Record<string, keyof typeof supplied> = {
    institutional: "institutional_age_hours", "trade-press": "trade_press_age_hours", community: "community_age_hours",
  };
  const rows: [string, string, string][] = [
    configured("Policy config version", config.version),
    ["Article limit", String(request.article_limit), source("article_limit")],
    configured("Worker assignment enabled", config.partition.enabled),
    ["Article assignments", String(config.partition.enabled ? request.shards : 0), assignmentSource("shards")],
    ["Assignment strategy", config.partition.enabled ? request.partition_strategy : "bypassed", assignmentSource("partition_strategy")],
    configured("Fetch concurrency", config.harvest.concurrency),
    configured("Fetch timeout per HTTP attempt (ms)", config.harvest.fetch_timeout_ms),
    configured("Parse deadline including queue (ms)", config.harvest.parse_timeout_ms),
    configured("Parser workers", parser_concurrency),
    configured("Minimum article words", policy.triage.min_words),
    configured("Recency half-life (hours)", policy.triage.recency_half_life_hours),
    configured("Recency weight", policy.triage.recency_weight),
    configured("Estimated source authority coefficient", policy.curate_articles.source_authority_weight),
    ...allocateSourceBasedQualityBucketBudgets(config, request.article_limit).flatMap(budget => [
      [`${budget.rule.id} age steps (hours)`, resolveSourceBasedQualityBucketWindows(budget.rule).steps.join(" / "),
        source(ageSources[budget.rule.id]!)] satisfies [string, string, string],
      configured(`${budget.rule.id} source tier`, budget.rule.source_tier_id),
      [`${budget.rule.id} article target / ceiling`, `${budget.target} / ${budget.ceiling}`, "effective article limit and configuration"] satisfies [string, string, string],
    ]),
    configured("Per-feed share limit (fraction)", config.curate_articles.soft_caps.max_source_share),
    configured("Website-group share limit (fraction)", config.curate_articles.soft_caps.max_website_group_share),
    configured("Distinct-feed target", config.curate_articles.soft_caps.min_distinct_sources),
    configured("Limit relaxation order", JSON.stringify(config.curate_articles.soft_caps.relaxation_order)),
    configured("Publisher exposure weight", policy.curate_articles.mmr_weights.lambda_source),
    configured("Website-group exposure weight", policy.curate_articles.mmr_weights.lambda_website_group),
    configured("Exploration share (fraction)", config.curate_articles.exploration_slot_share),
    configured("Feed-status history (represented UTC days)", config.feedback.lifecycle_window_days),
    ["Availability controls", availability === undefined ? "Not recorded" : "Recorded", "configuration"],
    ...(availability === undefined ? [] : [
      configured("Consecutive failed logical checks before rest", availability.consecutive_failed_checks_before_rest),
      configured("Initial rest (hours)", availability.rest_hours),
      configured("Recovery rest after completion (hours)", availability.recovery_rest_hours),
      configured("Qualifying failed recovery checks before retirement", availability.failed_recovery_checks_before_retirement),
      configured("Minimum age since first confirmed source failure (hours)", availability.retirement_minimum_age_hours),
    ]),
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
      + `article limit: ${request.article_limit} (${source("article_limit")}); article assignments: ${config.partition.enabled ? request.shards : 0}; `
      + `strategy: ${config.partition.enabled ? request.partition_strategy : "bypassed"}; article-pass adjustment enabled: `
      + `${config.curate_articles.source_reliability_penalty_enabled}. Full settings are in Effective policy.`,
    rows,
  };
}

export function formatPolicyTable(input: unknown, selectionRan: boolean) {
  const policy = formatWorkflowPolicy(input, selectionRan);
  const overrides = policy.rows.filter(([, , source]) => source === "workflow override").map(([setting]) => setting);
  const ignored = policy.rows.filter(([, , source]) => source === "ignored workflow override").map(([setting]) => setting);
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
      ...(ignored.length ? ["", `Ignored workflow inputs because worker assignment is disabled: ${ignored.map(value => escapeMarkdown(value!)).join(", ")}.`] : []),
      "", "The article limit is a maximum. Selection started is a run fact, not an enabled setting.",
      "Shares and the reliability floor use the JSON fractions: 0 means none; 1 means the whole.",
      "Authority multiplies the coefficient by each feed's configured weight and source-tier weight; it is not the tier weight alone.",
      "A valid parsed feed, even empty, clears its availability episode. A recovery check is eligible at its UTC deadline.",
      "Retirement needs both configured gates and a new confirmed failing recovery; elapsed time starts at the first confirmed source failure.",
      "Source authority estimates expected quality; it is not an article-quality verdict.",
      "bin-pack balances estimated article work; round-robin assigns in selected order; none assigns worker 0. Disabling partition bypasses assignment.",
      "",
    ].join("\n"),
  };
}
