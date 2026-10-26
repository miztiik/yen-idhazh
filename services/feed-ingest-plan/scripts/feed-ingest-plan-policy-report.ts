/** Which effective controls governed this invocation rather than its committed defaults? */
import { z } from "zod";
import { FeedIngestConfigSchema } from "../../../packages/common-contracts/src/index";
import { PlanRequestSchema, resolvePlanRequest } from "../src/api/plan-request";
import { resolvePolicy } from "../src/config/resolve-policy";
import { FeedHistoryPolicySchema } from "../src/read-ledger-history/read-feed-history";
import { escapeMarkdown } from "./feed-ingest-plan-report-format";

export const WorkflowPolicySchema = z.strictObject({
  config: FeedIngestConfigSchema,
  request: PlanRequestSchema,
  history: FeedHistoryPolicySchema.extend({
    max_future_hours: z.number().finite().nonnegative(),
    seen_window_days: z.int().nonnegative(),
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
  const policy = resolvePolicy({ config }, supplied.freshness_hours === undefined ? {}
    : { freshness_hours: supplied.freshness_hours });
  const percent = (value: number) => `${(value * 100).toFixed(2)} percent`;
  const source = (key: keyof typeof supplied) => supplied[key] === undefined ? "configuration" : "workflow override";
  const maximum = request.article_limit === null ? "No article limit" : `${request.article_limit} articles`;
  const workers = `${request.shards} workers; ${request.partition_strategy}`;
  const rows = [
    ["Application", selectionRan ? "Selection ran with these effective controls" : "Requested controls; selection did not run"],
    ["Maximum article age", `${policy.triage.max_age_hours} hours (${source("freshness_hours")})`],
    ["Article limit", `${maximum} (${source("article_limit")})`],
    ["Worker assignment", `${workers} (count: ${source("shards")}; distribution: ${source("partition_strategy")})`],
    ["Extraction", `${config.harvest.concurrency} concurrent fetches; ${config.harvest.fetch_timeout_ms} milliseconds fetch timeout; ${parser_concurrency} parser workers`],
    ["Minimum text", `${policy.triage.min_words_article} words per article; ${policy.triage.min_words_abstract} words per abstract`],
    ["Recency score", `${policy.triage.recency_half_life_hours} hours half-life; weight ${policy.triage.recency_weight}`],
    ["Feed authority score", `Weight ${policy.curate.source_authority_weight}; measured reliability penalty ${config.curate.source_reliability_penalty_enabled ? "enabled" : "disabled"}`],
    ["Per-feed allowance", `${policy.curate.base_source_allowance} articles; ${policy.curate.bonus_unique_evidence} extra for unique evidence`],
    ["Portfolio limits", `${percent(config.curate.soft_caps.max_source_share)} per feed; ${percent(config.curate.soft_caps.max_parent_domain_share)} per known parent domain; target ${config.curate.soft_caps.min_distinct_sources} distinct feeds`],
    ["Limit relaxation order", config.curate.soft_caps.relaxation_order.map(limit =>
      ({ distinct_sources: "distinct-feed target", source_share: "per-feed share" })[limit]).join(", ") || "No relaxation"],
    ["Diversity score deductions", `Publisher exposure ${policy.curate.mmr_weights.lambda_source}; source kind ${policy.curate.mmr_weights.lambda_source_kind}; known parent domain ${policy.curate.mmr_weights.lambda_domain}`],
    ["Exploration slots", `${percent(config.curate.exploration_slot_share)} for feeds not yet chosen when available`],
    ["History", `${history.seen_window_days} UTC days for first sight; ${history.published_window_days} UTC days for prior publication; ${history.max_future_hours} hours future-time tolerance`],
    ["Article exclusions", `Blocked HTTP statuses: ${config.triage.blocked_http_statuses.join(", ")}; blocked categories: ${config.harvest.blocked_categories.join(", ") || "none"}; ${config.harvest.url_exclusions.length} configured URL exclusions`],
  ];
  return {
    notice: `${selectionRan ? "Used" : "Requested; selection did not run"}: maximum age ${policy.triage.max_age_hours} hours; `
      + `${maximum}; ${workers}; measured reliability penalty ${config.curate.source_reliability_penalty_enabled ? "enabled" : "disabled"}. `
      + "The job summary records the effective scoring, exclusions, allowances and portfolio limits.",
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
