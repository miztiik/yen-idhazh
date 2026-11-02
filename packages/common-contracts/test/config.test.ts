/** Do global planner settings reject invalid values and retired per-vertical controls? */
import { expect, test } from "bun:test";
import { z } from "zod";
import { PublisherIdSchema } from "../src/schemas/source.schema";
import * as policies from "../src/schemas/policy.schema";
import * as configs from "../src/schemas/config.schema";

export const configSchemas = { ...policies, ...configs };

if (Bun.argv.includes("--emit-schemas")) {
  process.stdout.write(JSON.stringify(Object.fromEntries(
    Object.entries(configSchemas)
      .flatMap(([name, schema]) => schema instanceof z.ZodType
        ? [[name.replace(/Schema$/, ""), z.toJSONSchema(schema, { io: "input" })]]
        : []),
  )));
} else {
  const readConfig = () => Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json();

  test("publisher IDs use the shared lowercase slug rule", () => {
    for (const id of ["publisher-alpha", "publisher-group-2", "publisher-x"]) {
      expect(PublisherIdSchema.parse(id)).toBe(id);
    }
    for (const id of ["BBC", "the_hindu", "mint 2"]) {
      expect(PublisherIdSchema.safeParse(id).success).toBe(false);
    }
  });

  test("authored planner config conforms to its declared schema", async () => {
    const config = configs.FeedIngestConfigSchema.parse(await readConfig());
    expect(config).toHaveProperty("curate_articles");
    expect(config).not.toHaveProperty("curate");
  });

  test("current harvesting refuses the removed article robots setting without a replacement mode", async () => {
    const config = await readConfig();
    expect(configs.FeedIngestConfigSchema.parse(config).harvest).not.toHaveProperty("article_robots_policy");
    for (const article_robots_policy of ["enforce", "observe", false, null]) {
      expect(() => configs.FeedIngestConfigSchema.parse({
        ...config, harvest: { ...config.harvest, article_robots_policy },
      })).toThrow("article_robots_policy");
    }
  });

  test("schema-valid planner settings can change without a live-value assertion", async () => {
    const config = configs.FeedIngestConfigSchema.parse(await readConfig());
    const changed = {
      ...config,
      triage: { ...config.triage, min_words: config.triage.min_words + 1 },
      harvest: { ...config.harvest, concurrency: config.harvest.concurrency + 1 },
    };
    expect(configs.FeedIngestConfigSchema.parse(changed)).toEqual(changed);
  });

  test("private suffix parsing is enabled by the schema default", () => {
    expect(configs.FeedWebsiteGroupingConfigSchema.parse({}).include_private_suffixes).toBe(true);
  });

  test("request pacing accepts zero delays and rejects invalid settings", async () => {
    const config = await readConfig();
    const settings = { enabled: true, domain_delay_ms: 0, publisher_delay_ms: 0, jitter_ms: 0 };
    expect(configs.RequestPacingSettingsSchema.parse(settings)).toEqual(settings);
    expect(configs.RequestPacingSettingsSchema.parse({ ...settings, enabled: false }).enabled).toBe(false);
    for (const patch of [
      { enabled: "true" }, { domain_delay_ms: -1 }, { domain_delay_ms: 1.5 },
      { publisher_delay_ms: -1 }, { jitter_ms: -1 }, { extra: true },
    ]) {
      expect(configs.RequestPacingSettingsSchema.safeParse({ ...settings, ...patch }).success).toBe(false);
    }
    expect(configs.FeedIngestConfigSchema.parse(config).harvest.request_pacing)
      .toEqual(config.harvest.request_pacing);
  });

  test("prepared scoring policy validates numeric bounds, curve order and trusted headline patterns", async () => {
    const config = await readConfig();
    const curate = configs.FeedCurateArticlesConfigSchema.parse(config.curate_articles);
    const substance = curate.substance;
    for (const patch of [
      { word_count_ramp_end: 0 }, { word_count_ramp_end: 1.5 },
      { word_count_sweet_spot_max: substance.word_count_ramp_end - 1 },
      { word_count_plateau_start: substance.word_count_sweet_spot_max },
      { length_scores: { full: -1 } }, { length_scores: { full: Infinity } },
      { long_form_floor_score: substance.length_scores.full + 1 },
      { long_form_floor_score: -1 }, { entity_density_weight: -1 },
      { entity_density_full_credit: 0 }, { entity_density_full_credit: Infinity },
      { headline_hype_penalty: -1 }, { headline_hype_penalty: NaN },
      { substantive_paragraph_min_words: 0 }, { substantive_paragraph_min_words: 1.5 },
      { substantive_paragraph_min_sentences: 0 }, { substantive_paragraph_min_sentences: 1.5 },
      { min_words: 100 }, { word_count_decline_end: 9000 }, { offset: 1 },
    ]) expect(policies.FeedSubstancePolicySchema.safeParse({ ...substance, ...patch }).success).toBe(false);
    for (const name of ["lambda_domain", "lambda_feed", "novelty_bonus"] as const) {
      expect(policies.FeedDiversityPolicySchema.parse({ ...curate.diversity, [name]: 0 })[name]).toBe(0);
      for (const value of [-1, Infinity, NaN, null]) {
        expect(policies.FeedDiversityPolicySchema.safeParse({ ...curate.diversity, [name]: value }).success).toBe(false);
      }
    }
    for (const name of [
      "shouting_weight", "punctuation_weight", "opening_mismatch_weight",
      "opening_text_max_characters", "keyword_min_letters", "shouting_min_letters", "shouting_min_words",
      "shouting_min_uppercase_fraction",
    ] as const) {
      for (const value of [-1, Infinity, NaN, null]) {
        expect(policies.FeedHeadlinePolicySchema.safeParse({ ...substance.headline, [name]: value }).success).toBe(false);
      }
    }
    for (const patch of [
      { shouting_min_uppercase_fraction: 1.01 }, { opening_text_max_characters: 0 },
      { keyword_min_letters: 1.5 }, { shouting_min_letters: 0 }, { shouting_min_words: 0 },
      { stop_words: ["the", "the"] }, { stop_words: ["The"] }, { stop_words: [""] },
      { punctuation_patterns: [] }, { punctuation_patterns: [""] }, { punctuation_patterns: ["["] },
      { punctuation_patterns: ["\\u{invalid}"] },
    ]) expect(policies.FeedHeadlinePolicySchema.safeParse({ ...substance.headline, ...patch }).success).toBe(false);
    expect(() => policies.FeedHeadlinePolicySchema.parse({
      ...substance.headline, punctuation_patterns: ["["],
    })).toThrow("punctuation_patterns");
    for (const value of [0, -1, Infinity, NaN, null]) {
      expect(configs.FeedCurateArticlesConfigSchema.safeParse({ ...curate, global_age_ceiling_hours: value }).success).toBe(false);
    }
    expect(policies.FeedSubstancePolicySchema.parse({
      ...substance, word_count_sweet_spot_max: substance.word_count_ramp_end,
      long_form_floor_score: substance.length_scores.full,
    }).long_form_floor_score).toBe(substance.length_scores.full);
    expect(policies.FeedHeadlinePolicySchema.parse({
      ...substance.headline, shouting_min_uppercase_fraction: 0,
    }).shouting_min_uppercase_fraction).toBe(0);
    expect(policies.FeedHeadlinePolicySchema.parse({
      ...substance.headline, shouting_min_uppercase_fraction: 1,
    }).shouting_min_uppercase_fraction).toBe(1);
    expect(configs.FeedIngestConfigSchema.safeParse({ ...config, version: "2026-11-01" }).success).toBe(false);
  });

  test("current policy refuses retired allocation and penalty controls by field name", async () => {
    const config = await readConfig();
    for (const name of ["source_based_quality_buckets", "soft_caps", "mmr_weights", "exploration_slot_share"]) {
      expect(() => configs.FeedCurateArticlesConfigSchema.parse({
        ...config.curate_articles, [name]: {},
      })).toThrow(name);
    }
    expect(() => policies.FeedCurationPolicySchema.parse({
      source_authority_weight: 1, mmr_weights: {},
    })).toThrow("mmr_weights");
  });

  test("partition enablement defaults on and its configured bounds stay enforced", () => {
    const bounds = { default_strategy: "bin-pack", default_shards: 4, min_shards: 1, max_shards: 20 };
    expect(configs.FeedPartitionConfigSchema.parse(bounds).enabled).toBe(true);
    expect(configs.FeedPartitionConfigSchema.parse({ ...bounds, enabled: false }).enabled).toBe(false);
    expect(configs.FeedPartitionConfigSchema.parse({ ...bounds, default_shards: 20 }).default_shards).toBe(20);
    expect(configs.FeedPartitionConfigSchema.safeParse({ ...bounds, default_shards: 21 }).success).toBe(false);
  });

  test.each([
    [["triage", "min_words"], 0],
    [["triage", "max_age_hours"], null],
    [["triage", "recency_weight"], -1],
    [["triage", "kind"], "research"],
    [["curate_articles", "source_authority_weight"], Infinity],
    [["curate_articles", "source_reliability_penalty_enabled"], null],
    [["curate_articles", "article_limit"], -1],
    [["curate_articles", "mmr_weights"], {}],
    [["curate_articles", "soft_caps"], {}],
    [["curate_articles", "source_based_quality_buckets"], []],
    [["curate_articles", "exploration_slot_share"], 0],
    [["discovered_articles", "lookback_days"], -1],
    [["harvest", "concurrency"], "2"],
    [["content_filters", "media", "enabled"], "true"],
    [["content_filters", "media", "enclosure_type_prefixes"], ["audio"]],
    [["content_filters", "press_release", "sample_chars"], 0],
    [["content_filters", "press_release", "markers"], []],
    [["content_filters", "link_heavy", "max_link_density"], 1.1],
    [["content_filters", "link_heavy", "max_list_items"], -1],
    [["content_filters", "link_heavy", "list_word_limit"], 0],
    [["partition", "enabled"], "true"],
    [["workflow_reporting", "enabled"], "true"],
    [["metrics"], {}],
    [["seal", "compression"], "gzip"],
    [["vertical_overrides"], {}],
    [["feedback", "lifecycle_window_days"], 0],
    [["feedback", "lifecycle_window_days"], 1.5],
    [["feedback", "request_report_closed_days"], 0],
    [["feedback", "request_report_closed_days"], 1.5],
    [["feedback", "request_report_closed_days"], null],
    [["feedback", "minimum_measured_opportunities"], 0],
    [["feedback", "minimum_measured_coverage"], 1.1],
    [["feedback", "component_weights"], { requests: -0.1 }],
    [["feedback", "component_weights"], { requests: 0.2 }],
  ] as const)("global config rejects invalid or retired settings: %j=%j", async (path, value) => {
    const config = await readConfig();
    let leaf = config;
    for (const segment of path.slice(0, -1)) leaf = leaf[segment];
    leaf[path.at(-1)!] = value;
    expect(configs.FeedIngestConfigSchema.safeParse(config).success).toBe(false);
  });

  test("global config rejects bad bounds, unknown keys, and invalid references", async () => {
    const config = await readConfig();
    const profiles = config.harvest.request_headers;
    expect(configs.FeedRequestHeadersSchema.parse({ ...profiles, secondary: null }).secondary).toBeNull();
    for (const browser of ["firefox", "chrome"]) {
      for (const headers of [{}, { accept: "application/xml" }, { "accept-language": "en" }]) {
        expect(configs.FeedRequestHeadersSchema.safeParse({ ...profiles, primary: { browser, headers } }).success).toBe(true);
      }
    }
    for (const headers of [
      { host: "internal.example" }, { "user-agent": "retired crawler" },
      { authorization: "credentials" }, { accept: "text/html\r\nhost: internal.example" },
      { accept: "" }, { Accept: "text/html" },
    ]) {
      for (const name of ["primary", "secondary"]) {
        expect(configs.FeedRequestHeadersSchema.safeParse({
          ...profiles, [name]: { browser: "firefox", headers },
        }).success).toBe(false);
      }
    }
    for (const primary of [{ accept: "text/html" }, { browser: "unsupported", headers: {} }]) {
      expect(configs.FeedRequestHeadersSchema.safeParse({ ...profiles, primary }).success).toBe(false);
    }
    expect(configs.FeedIngestConfigSchema.safeParse({
      ...config, harvest: { ...config.harvest, user_agent: "retired crawler" },
    }).success).toBe(false);
    expect(configs.FeedRequestHeadersSchema.safeParse({
      ...profiles, recoverable_http_statuses: [403, 403],
    }).success).toBe(false);
    expect(configs.FeedRequestHeadersSchema.safeParse({
      ...profiles, recovery_min_body_bytes: -1,
    }).success).toBe(false);
    for (const patch of [
      { partition: { ...config.partition, min_shards: config.partition.max_shards + 1 } },
      { partition: { ...config.partition, default_shards: config.partition.max_shards + 1 } },
      { harvest: { ...config.harvest, concurrency: "24" } },
      { harvest: { ...config.harvest, tidy_urls: "true" } },
      { harvest: { ...config.harvest, semantic_fallback: {
        ...config.harvest.semantic_fallback, content_roots: [],
      } } },
      { harvest: { ...config.harvest, semantic_fallback: {
        ...config.harvest.semantic_fallback, min_root_chars: -1,
      } } },
      { curate_articles: { ...config.curate_articles, article_limit: 0 } },
      { curate_articles: { ...config.curate_articles, article_limit: 1.5 } },
      { curate_articles: { ...config.curate_articles, source_reliability_penalty_enabled: "true" } },
      { curate_articles: { ...config.curate_articles, source_reliability_penalty_enabled: null } },
      { feedback: {
        ...config.feedback, component_weights: { cpu: 0.2, private_memory: 0.2, requests: 0.2 },
      } },
      { triage: { ...config.triage, min_words: true } },
      { triage: { ...config.triage, max_age_hours: Infinity } },
      { seal: { ...config.seal, dispatches_prefix: ["feed-ingest-plan", "dispatches"] } },
      { metrics: {} },
      { desk_overrides: {} },
      { vertical_overrides: { ai: { triage: { blocked_http_statuses: [] } } } },
    ]) {
      expect(configs.FeedIngestConfigSchema.safeParse({ ...config, ...patch }).success).toBe(false);
    }
    expect(configs.FeedIngestConfigSchema.safeParse({ ...config, vertical_overrides: {} }).success).toBe(false);
  });
}
