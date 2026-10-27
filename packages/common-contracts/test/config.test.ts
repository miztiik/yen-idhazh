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
    for (const id of ["bbc", "the-conversation-africa", "the-hindu-businessline"]) {
      expect(PublisherIdSchema.parse(id)).toBe(id);
    }
    for (const id of ["BBC", "the_hindu", "mint 2"]) {
      expect(PublisherIdSchema.safeParse(id).success).toBe(false);
    }
  });

  test("authored defaults preserve word thresholds, age, and reporting isolation", async () => {
    const config = configs.FeedIngestConfigSchema.parse(await readConfig());
    expect(config.triage).toEqual({
      min_words_article: 180, min_words_abstract: 60, blocked_http_statuses: [401, 403, 429],
      max_age_hours: 24, recency_half_life_hours: 18, recency_weight: 0.6,
    });
    expect(config.curate.article_limit).toBe(100);
    expect(config.harvest.tidy_urls).toBe(true);
    expect(config.content_filters).toMatchObject({
      media: { enabled: true, enclosure_type_prefixes: ["audio/", "video/"] },
      press_release: { enabled: true, sample_chars: 600 },
      link_heavy: { enabled: true, max_link_density: 0.4, max_list_items: 10, list_word_limit: 150 },
    });
    expect(config.feedback.lifecycle_window_days).toBe(31);
    expect(config.feedback.request_report_closed_days).toBe(7);
    expect(Object.keys(config.feedback)).toEqual(["lifecycle_window_days", "request_report_closed_days"]);
    const { feedback: _feedback, ...legacyConfig } = config;
    expect(configs.FeedIngestConfigSchema.parse(legacyConfig).feedback.request_report_closed_days).toBe(7);
    expect(configs.FeedIngestConfigSchema.parse({
      ...config, feedback: { request_report_closed_days: 2 },
    }).feedback).toMatchObject({
      lifecycle_window_days: 31, request_report_closed_days: 2,
    });
    for (const retired of ["window_days", "minimum_measured_opportunities", "minimum_measured_coverage", "component_weights"]) {
      expect(configs.FeedIngestConfigSchema.safeParse({ ...config, feedback: { ...config.feedback, [retired]: 1 } }).success).toBe(false);
    }
    expect(config.curate.source_reliability_penalty_enabled).toBe(true);
    const { source_reliability_penalty_enabled: _enabled, ...previousCurate } = config.curate;
    expect(configs.FeedCurateConfigSchema.parse(previousCurate).source_reliability_penalty_enabled).toBe(true);
    expect(configs.FeedCurateConfigSchema.parse({
      ...config.curate, source_reliability_penalty_enabled: false,
    }).source_reliability_penalty_enabled).toBe(false);
    expect(config.curate.mmr_weights.lambda_source_kind).toBe(0.05);
    expect(config).not.toHaveProperty("vertical_overrides");
    expect(config.workflow_reporting.enabled).toBe(true);
    expect(configs.FeedWorkflowReportingConfigSchema.parse({
      removal_condition: config.workflow_reporting.removal_condition,
    }).enabled).toBe(true);
    expect(configs.FeedWorkflowReportingConfigSchema.parse({
      ...config.workflow_reporting, enabled: false,
    }).enabled).toBe(false);
  });

  test.each([
    [["triage", "min_words_article"], 0],
    [["triage", "min_words_abstract"], 1.5],
    [["triage", "max_age_hours"], null],
    [["triage", "recency_weight"], -1],
    [["triage", "kind"], "research"],
    [["curate", "source_authority_weight"], Infinity],
    [["curate", "source_reliability_penalty_enabled"], null],
    [["curate", "base_source_allowance"], -1],
    [["curate", "mmr_weights", "lambda_domain"], NaN],
    [["curate", "mmr_weights", "lambda_lens"], 0],
    [["curate", "soft_caps", "max_source_share"], 0],
    [["harvest", "concurrency"], "2"],
    [["content_filters", "media", "enabled"], "true"],
    [["content_filters", "media", "enclosure_type_prefixes"], ["audio"]],
    [["content_filters", "press_release", "sample_chars"], 0],
    [["content_filters", "press_release", "markers"], []],
    [["content_filters", "link_heavy", "max_link_density"], 1.1],
    [["content_filters", "link_heavy", "max_list_items"], -1],
    [["content_filters", "link_heavy", "list_word_limit"], 0],
    [["partition", "default_shards"], 9],
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

  test("each independent penalty accepts zero without dropping other dimensions", () => {
    const weights = { lambda_source: 0.1, lambda_source_kind: 0.05, lambda_domain: 0.1 };
    for (const name of Object.keys(policies.FeedPenaltyWeightsSchema.shape)) {
      expect(policies.FeedPenaltyWeightsSchema.parse({ ...weights, [name]: 0 })[name as keyof typeof weights]).toBe(0);
    }
  });

  test.each([0, -1, "12", NaN, Infinity, null, false])("rejects invalid freshness %j", value => {
    expect(policies.PlanningRunOverridesSchema.safeParse({ freshness_hours: value }).success).toBe(false);
  });

  test("global config rejects bad bounds, unknown keys, and invalid references", async () => {
    const config = await readConfig();
    const profiles = config.harvest.request_headers;
    expect(configs.FeedRequestHeadersSchema.parse({ ...profiles, secondary: null }).secondary).toBeNull();
    for (const headers of [
      {}, { host: "internal.example" },
      { authorization: "credentials" }, { accept: "text/html\r\nhost: internal.example" },
      { accept: "" }, { Accept: "text/html" },
    ]) {
      for (const name of ["primary", "secondary"]) {
        expect(configs.FeedRequestHeadersSchema.safeParse({ ...profiles, [name]: headers }).success).toBe(false);
      }
    }
    expect(configs.FeedRequestHeadersSchema.safeParse({
      ...profiles, recoverable_http_statuses: [403, 403],
    }).success).toBe(false);
    expect(configs.FeedRequestHeadersSchema.safeParse({
      ...profiles, recovery_min_body_bytes: -1,
    }).success).toBe(false);
    for (const patch of [
      { partition: { ...config.partition, min_shards: 9 } },
      { partition: { ...config.partition, default_shards: 9 } },
      { harvest: { ...config.harvest, concurrency: "24" } },
      { harvest: { ...config.harvest, tidy_urls: "true" } },
      { harvest: { ...config.harvest, semantic_fallback: {
        ...config.harvest.semantic_fallback, content_roots: [],
      } } },
      { harvest: { ...config.harvest, semantic_fallback: {
        ...config.harvest.semantic_fallback, min_root_chars: -1,
      } } },
      { curate: { ...config.curate, article_limit: 0 } },
      { curate: { ...config.curate, article_limit: 1.5 } },
      { curate: { ...config.curate, source_reliability_penalty_enabled: "true" } },
      { curate: { ...config.curate, source_reliability_penalty_enabled: null } },
      { feedback: {
        ...config.feedback, component_weights: { cpu: 0.2, private_memory: 0.2, requests: 0.2 },
      } },
      { triage: { ...config.triage, min_words_article: true } },
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
