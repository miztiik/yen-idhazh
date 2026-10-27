/** Which authored planner settings are valid before a run? */
import { z } from "zod";
import {
  NonEmptySchema, PositiveCountSchema, PositiveSchema, reject,
} from "./primitives";
import {
  FeedCurationPolicySchema, FeedScreeningPolicySchema,
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
export const FeedMediaFilterSchema = z.strictObject({
  enabled: z.boolean().describe(
    "Exclude media offers. Remove this switch and the disabled path when this filter becomes mandatory.",
  ),
  enclosure_type_prefixes: z.array(NonEmptySchema.regex(/^[a-z][a-z0-9.+-]*\/$/)).min(1),
  url_rules: z.array(FeedUrlExclusionSchema),
});
export const FeedPressReleaseFilterSchema = z.strictObject({
  enabled: z.boolean().describe(
    "Exclude opening press-release markers. Remove this switch and the disabled path when this filter becomes mandatory.",
  ),
  sample_chars: PositiveCountSchema,
  markers: z.array(NonEmptySchema).min(1),
});
export const FeedLinkHeavyFilterSchema = z.strictObject({
  enabled: z.boolean().describe(
    "Exclude link-heavy articles. Remove this switch and the disabled path when this filter becomes mandatory.",
  ),
  max_link_density: z.number().finite().min(0).max(1),
  max_list_items: z.int().nonnegative(),
  list_word_limit: PositiveCountSchema,
});
export const FeedContentFiltersConfigSchema = z.strictObject({
  media: FeedMediaFilterSchema,
  press_release: FeedPressReleaseFilterSchema,
  link_heavy: FeedLinkHeavyFilterSchema,
});
// Navigation metadata cannot replace request authority, credentials or crawler identity.
const browserHeaderNames = new Set([
  "user-agent", "accept", "accept-language", "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform",
  "sec-fetch-dest", "sec-fetch-mode", "sec-fetch-site", "sec-fetch-user", "upgrade-insecure-requests",
]);
const BrowserHeadersSchema = z.record(z.string(), NonEmptySchema.regex(/^[\x20-\x7e]+$/)).superRefine((headers, ctx) => {
  if (!Object.keys(headers).length) reject(ctx, "a browser header profile must not be empty");
  for (const name of Object.keys(headers)) {
    if (!browserHeaderNames.has(name)) reject(ctx, "unsupported browser header", [name]);
  }
});
export const FeedRequestHeadersSchema = z.strictObject({
  primary: BrowserHeadersSchema,
  secondary: BrowserHeadersSchema.nullable(),
  recoverable_http_statuses: z.array(z.int().min(400).max(599)),
  recovery_min_body_bytes: z.int().nonnegative(),
}).superRefine((value, ctx) => {
  if (new Set(value.recoverable_http_statuses).size !== value.recoverable_http_statuses.length) {
    reject(ctx, "recoverable_http_statuses must not repeat a status", ["recoverable_http_statuses"]);
  }
});
export const FeedMetadataSelectorSchema = z.strictObject({
  selector: NonEmptySchema, attribute: NonEmptySchema.nullable(),
});
export const FeedSemanticFallbackConfigSchema = z.strictObject({
  content_roots: z.array(NonEmptySchema).min(1),
  remove_elements: z.array(NonEmptySchema).min(1),
  paragraph_elements: z.array(NonEmptySchema).min(1),
  min_root_chars: z.int().nonnegative(),
  min_paragraph_chars: z.int().nonnegative(),
  title_sources: z.array(FeedMetadataSelectorSchema).min(1),
  author_sources: z.array(FeedMetadataSelectorSchema).min(1),
});
export const FeedHarvestConfigSchema = z.strictObject({
  concurrency: PositiveCountSchema,
  fetch_timeout_ms: PositiveCountSchema,
  tidy_urls: z.boolean().describe(
    "Clean request targets only. Remove this switch and the disabled path when request cleanup becomes mandatory.",
  ),
  user_agent: NonEmptySchema,
  request_headers: FeedRequestHeadersSchema,
  semantic_fallback: FeedSemanticFallbackConfigSchema,
  blocked_categories: z.array(NonEmptySchema),
  url_exclusions: z.array(FeedUrlExclusionSchema),
});
export const FeedTriageConfigSchema = FeedScreeningPolicySchema.extend({
  blocked_http_statuses: z.array(z.int().min(100).max(599)),
});
export const FeedSoftCapsSchema = z.strictObject({
  max_source_share: PositiveSchema.max(1),
  max_website_group_share: PositiveSchema.max(1),
  min_distinct_sources: PositiveCountSchema,
  relaxation_order: z.array(z.enum(["distinct_sources", "source_share"])),
}).superRefine((value, ctx) => {
  if (new Set(value.relaxation_order).size !== value.relaxation_order.length) {
    reject(ctx, "relaxation_order must not repeat a limit", ["relaxation_order"]);
  }
});
export const FeedWebsiteGroupingConfigSchema = z.strictObject({
  include_private_suffixes: z.boolean().default(true),
});
export const FeedCurateArticlesConfigSchema = FeedCurationPolicySchema.extend({
  article_limit: PositiveCountSchema.nullable(),
  source_reliability_penalty_enabled: z.boolean().default(true).describe(
    "Apply measured source reliability separately from article quality. Remove this switch and its disabled path when isolated selection becomes the sole planner.",
  ),
  soft_caps: FeedSoftCapsSchema,
  exploration_slot_share: z.number().finite().min(0).max(1),
  website_grouping: FeedWebsiteGroupingConfigSchema.default({ include_private_suffixes: true }),
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
  compression: z.enum(["snappy", "zstd", "none"]),
});
export const FeedWorkflowReportingConfigSchema = z.strictObject({
  enabled: z.boolean().default(true).describe(
    "External reporting only. Remove this key, adapter, tests, and workflow invocation together when development reporting is no longer needed.",
  ),
  removal_condition: NonEmptySchema,
});
export const FeedFeedbackConfigSchema = z.strictObject({
  lifecycle_window_days: PositiveCountSchema.default(31),
  request_report_closed_days: PositiveCountSchema.default(7),
});
export const FeedIngestConfigSchema = z.strictObject({
  version: z.literal("2026-10-27"),
  harvest: FeedHarvestConfigSchema,
  content_filters: FeedContentFiltersConfigSchema,
  triage: FeedTriageConfigSchema,
  curate_articles: FeedCurateArticlesConfigSchema,
  discovered_articles: z.strictObject({ lookback_days: z.int().nonnegative().default(90) }).default({ lookback_days: 90 }),
  partition: FeedPartitionConfigSchema,
  seal: FeedSealConfigSchema,
  workflow_reporting: FeedWorkflowReportingConfigSchema,
  feedback: FeedFeedbackConfigSchema.default(
    FeedFeedbackConfigSchema.parse({}),
  ).meta({
    default: {}, type: "object", additionalProperties: false,
  }),
});

export type FeedIngestConfig = z.infer<typeof FeedIngestConfigSchema>;
