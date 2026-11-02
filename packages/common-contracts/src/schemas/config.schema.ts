/** Which authored planner settings are valid before a run? */
import { z } from "zod";
import {
  NonEmptySchema, PositiveCountSchema, PositiveSchema, reject,
} from "./primitives";
import {
  FeedCurationPolicySchema, FeedDiversityPolicySchema, FeedScreeningPolicySchema, FeedSubstancePolicySchema,
} from "./policy.schema";
import { FEED_INGEST_CONFIG_VERSION } from "../version";
import { RequestProfileSchema, ResponseDiagnosticsConfigSchema } from "./http-response-evidence.schema";

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
const BrowserProfileSchema = z.strictObject({
  browser: RequestProfileSchema,
  headers: z.partialRecord(z.enum(["accept", "accept-language"]), NonEmptySchema.regex(/^[\x20-\x7e]+$/)),
});
export const FeedRequestHeadersSchema = z.strictObject({
  primary: BrowserProfileSchema,
  secondary: BrowserProfileSchema.nullable(),
  recoverable_http_statuses: z.array(z.int().min(400).max(599)),
  recovery_min_body_bytes: z.int().nonnegative(),
}).superRefine((value, ctx) => {
  if (new Set(value.recoverable_http_statuses).size !== value.recoverable_http_statuses.length) {
    reject(ctx, "recoverable_http_statuses must not repeat a status", ["recoverable_http_statuses"]);
  }
});
export const RequestPacingSettingsSchema = z.strictObject({
  enabled: z.boolean().describe(
    "Apply shared process-local domain and publisher pacing. Remove this switch and its bypass path when source request pacing is no longer needed.",
  ),
  domain_delay_ms: z.int().nonnegative(),
  publisher_delay_ms: z.int().nonnegative(),
  jitter_ms: z.int().nonnegative(),
});
export type RequestPacingSettings = z.infer<typeof RequestPacingSettingsSchema>;
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
  parse_timeout_ms: PositiveCountSchema.default(10000).describe(
    "Parse-request deadline in milliseconds, including worker queue time. The default is unmeasured.",
  ),
  tidy_urls: z.boolean().describe(
    "Apply additional article cleanup before removing all queries and fragments. Remove this switch and the disabled path when additional cleanup becomes mandatory.",
  ),
  request_headers: FeedRequestHeadersSchema,
  response_diagnostics: ResponseDiagnosticsConfigSchema,
  request_pacing: RequestPacingSettingsSchema,
  semantic_fallback: FeedSemanticFallbackConfigSchema,
  blocked_categories: z.array(NonEmptySchema),
  url_exclusions: z.array(FeedUrlExclusionSchema),
});
export const FeedTriageConfigSchema = FeedScreeningPolicySchema.extend({
  blocked_http_statuses: z.array(z.int().min(100).max(599)),
});
export const FeedWebsiteGroupingConfigSchema = z.strictObject({
  include_private_suffixes: z.boolean().default(true),
});
export const FeedCurateArticlesConfigSchema = FeedCurationPolicySchema.extend({
  article_limit: PositiveCountSchema,
  global_age_ceiling_hours: PositiveSchema,
  diversity: FeedDiversityPolicySchema,
  substance: FeedSubstancePolicySchema,
  source_reliability_penalty_enabled: z.boolean().default(true).describe(
    "Apply measured source reliability separately from article quality. Remove this switch and its disabled path when isolated selection becomes the sole planner.",
  ),
  website_grouping: FeedWebsiteGroupingConfigSchema.default({ include_private_suffixes: true }),
});
export const FeedPartitionConfigSchema = z.strictObject({
  enabled: z.boolean().default(true).describe(
    "Assign selected articles to workers. Remove this switch and the bypass path when worker assignment becomes mandatory.",
  ),
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
  score_decimal_places: z.int().min(0).max(100).default(3)
    .describe("Displayed score precision within the ECMAScript Number.toFixed range; saved scores remain exact."),
  enabled: z.boolean().default(true).describe(
    "External reporting only. Remove this key, adapter, tests, and workflow invocation together when development reporting is no longer needed.",
  ),
  removal_condition: NonEmptySchema,
});
export const FeedFeedbackConfigSchema = z.strictObject({
  lifecycle_window_days: PositiveCountSchema.default(31),
  request_report_closed_days: PositiveCountSchema.default(7),
});
export const FeedLifecyclePolicySchema = z.strictObject({
  consecutive_failed_checks_before_rest: PositiveCountSchema,
  rest_hours: PositiveSchema,
  recovery_rest_hours: PositiveSchema,
  failed_recovery_checks_before_retirement: PositiveCountSchema,
  retirement_minimum_age_hours: PositiveSchema,
});
export type FeedLifecyclePolicy = z.infer<typeof FeedLifecyclePolicySchema>;
export const FeedIngestConfigSchema = z.strictObject({
  version: z.literal(FEED_INGEST_CONFIG_VERSION),
  availability: FeedLifecyclePolicySchema,
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
}).meta({
  version: FEED_INGEST_CONFIG_VERSION,
  changelog: [
    { version: FEED_INGEST_CONFIG_VERSION, change: "Remove article robots policy from target-only ingestion." },
    { version: FEED_INGEST_CONFIG_VERSION, change: "Use global age, substance and diversity scoring without tier allocation or selection caps." },
    { version: "2026-11-01", change: "Configure shared domain and publisher request pacing." },
    { version: "2026-11-01", change: "Use native browser profiles and configured safe response headers." },
  ],
});

export type FeedIngestConfig = z.infer<typeof FeedIngestConfigSchema>;
