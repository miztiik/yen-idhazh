/** Which authored planner settings and vertical references are valid before a run? */
import { z } from "zod";
import {
  NonEmptySchema, PositiveCountSchema, PositiveSchema, SlugSchema, reject,
} from "./primitives";
import {
  FeedCurationPolicySchema, FeedScreeningPolicySchema, VerticalPolicyOverrideSchema,
} from "./policy.schema";

export const FeedUrlExclusionSchema = z.strictObject({
  host: z.hostname(),
  path_prefix: z.string().startsWith("/").refine(value =>
    value.startsWith("/") && !/[?#\\]/.test(value) && !value.startsWith("//")
    && (value === "/" || !value.endsWith("/"))
    && new URL(value, "https://example.invalid").pathname === value,
  "path_prefix must be an absolute path without query, fragment, dot segments or trailing slash"),
  include_subdomains: z.boolean(),
});
export const FeedHarvestConfigSchema = z.strictObject({
  concurrency: PositiveCountSchema,
  fetch_timeout_ms: PositiveCountSchema,
  user_agent: NonEmptySchema,
  blocked_categories: z.array(NonEmptySchema),
  url_exclusions: z.array(FeedUrlExclusionSchema),
});
export const FeedTriageConfigSchema = FeedScreeningPolicySchema.extend({
  blocked_http_statuses: z.array(z.int().min(100).max(599)),
});
export const FeedSoftCapsSchema = z.strictObject({
  max_source_share: PositiveSchema.max(1),
  max_parent_domain_share: PositiveSchema.max(1),
  max_event_cluster_items: PositiveCountSchema,
  min_distinct_sources: PositiveCountSchema,
  relaxation_order: z.array(z.enum(["distinct_sources", "source_share"])),
}).superRefine((value, ctx) => {
  if (new Set(value.relaxation_order).size !== value.relaxation_order.length) {
    reject(ctx, "relaxation_order must not repeat a limit", ["relaxation_order"]);
  }
});
export const FeedCurateConfigSchema = FeedCurationPolicySchema.extend({
  article_limit: PositiveCountSchema.nullable(),
  source_reliability_penalty_enabled: z.boolean().default(true).describe(
    "Apply measured source reliability separately from article quality. Remove this switch and its disabled path when isolated selection becomes the sole planner.",
  ),
  soft_caps: FeedSoftCapsSchema,
  exploration_slot_share: z.number().finite().min(0).max(1),
});
export const FeedPartitionConfigSchema = z.strictObject({
  default_strategy: z.enum(["bin-pack", "round-robin", "none"]),
  default_shards: PositiveCountSchema,
  min_shards: PositiveCountSchema,
  max_shards: PositiveCountSchema,
}).superRefine((value, ctx) => {
  if (value.min_shards > value.max_shards) reject(ctx, "min_shards exceeds max_shards", ["min_shards"]);
  if (value.default_shards < value.min_shards || value.default_shards > value.max_shards) {
    reject(ctx, "default_shards must be within min_shards and max_shards", ["default_shards"]);
  }
});
export const FeedSealConfigSchema = z.strictObject({
  dispatches_prefix: z.array(SlugSchema).min(1),
  rejections_prefix: z.array(SlugSchema).min(1),
  compression: z.enum(["snappy", "zstd", "none"]),
});
export const FeedWorkflowReportingConfigSchema = z.strictObject({
  enabled: z.boolean().default(true).describe(
    "External reporting only. Remove this key, adapter, tests, and workflow invocation together when development reporting is no longer needed.",
  ),
  removal_condition: NonEmptySchema,
});
export const FeedMetricsConfigSchema = z.strictObject({
  rolling_window_days: PositiveCountSchema,
  overlap_windows_days: z.array(PositiveCountSchema).min(1),
  top_source_counts: z.array(PositiveCountSchema).min(1),
});
export const FeedOperationalComponentWeightsSchema = z.strictObject({
  cpu: z.number().finite().min(0).default(1 / 3),
  private_memory: z.number().finite().min(0).default(1 / 3),
  requests: z.number().finite().min(0).default(1 / 3),
}).superRefine((value, ctx) => {
  if (Math.abs(value.cpu + value.private_memory + value.requests - 1) > 1e-9) {
    reject(ctx, "operational component weights must sum to one");
  }
});
export const FeedFeedbackConfigSchema = z.strictObject({
  window_days: PositiveCountSchema.default(7),
  minimum_measured_opportunities: PositiveCountSchema.default(20),
  minimum_measured_coverage: z.number().finite().min(0).max(1).default(0.8),
  component_weights: FeedOperationalComponentWeightsSchema.prefault({}),
});
export const FeedIngestConfigSchema = z.strictObject({
  version: z.literal("2026-10-20"),
  harvest: FeedHarvestConfigSchema,
  triage: FeedTriageConfigSchema,
  curate: FeedCurateConfigSchema,
  vertical_overrides: z.record(SlugSchema, VerticalPolicyOverrideSchema),
  partition: FeedPartitionConfigSchema,
  seal: FeedSealConfigSchema,
  workflow_reporting: FeedWorkflowReportingConfigSchema,
  metrics: FeedMetricsConfigSchema,
  feedback: FeedFeedbackConfigSchema.prefault({}),
});

// Only the taxonomy fields this reader computes on are declared here.
export const PlanningTaxonomySchema = z.object({
  verticals: z.array(z.object({ id: SlugSchema })).min(1),
}).superRefine((value, ctx) => {
  const ids = value.verticals.map(vertical => vertical.id);
  if (new Set(ids).size !== ids.length) reject(ctx, "verticals contains duplicate ids", ["verticals"]);
});
export type FeedIngestConfig = z.infer<typeof FeedIngestConfigSchema>;
export type PlanningTaxonomy = z.infer<typeof PlanningTaxonomySchema>;

export function validatePlanningReferences(config: FeedIngestConfig, taxonomy: PlanningTaxonomy): void {
  const ids = new Set(taxonomy.verticals.map(vertical => vertical.id));
  for (const id of Object.keys(config.vertical_overrides)) {
    if (!ids.has(id)) throw new Error(`vertical_overrides.${id}: unknown taxonomy vertical`);
  }
}
