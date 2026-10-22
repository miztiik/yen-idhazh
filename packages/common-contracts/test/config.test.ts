/** Do the authored planner config and its typed patches reject invalid settings? */
import { expect, test } from "bun:test";
import { z } from "zod";
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

  test("authored defaults preserve word thresholds, age, and reporting isolation", async () => {
    const config = configs.FeedIngestConfigSchema.parse(await readConfig());
    expect(config.triage).toEqual({
      min_words_article: 180, min_words_abstract: 60, blocked_http_statuses: [401, 403, 429],
      max_age_hours: 24, recency_half_life_hours: 18, recency_weight: 0.6,
    });
    expect(config.curate.article_limit).toBe(100);
    expect(config.curate.mmr_weights.lambda_source_kind).toBe(0.05);
    expect(config.vertical_overrides).toEqual({});
    expect(config.workflow_reporting.enabled).toBe(true);
    expect(configs.FeedWorkflowReportingConfigSchema.parse({
      removal_condition: config.workflow_reporting.removal_condition,
    }).enabled).toBe(true);
    expect(configs.FeedWorkflowReportingConfigSchema.parse({
      ...config.workflow_reporting, enabled: false,
    }).enabled).toBe(false);
  });

  test.each([
    { triage: { min_words_article: 0 } },
    { triage: { min_words_abstract: 1.5 } },
    { triage: { max_age_hours: null } },
    { triage: { recency_weight: -1 } },
    { triage: { kind: "research" } },
    { curate: { source_authority_weight: Infinity } },
    { curate: { base_source_allowance: -1 } },
    { curate: { mmr_weights: { lambda_lens: NaN } } },
    { curate: { soft_caps: { max_source_share: 0.2 } } },
    { harvest: { concurrency: 2 } },
    { partition: { default_shards: 2 } },
    { workflow_reporting: { enabled: true } },
    { metrics: { rolling_window_days: 3 } },
    { seal: { compression: "zstd" } },
    { desk_overrides: {} },
  ])("vertical patch rejects invalid or global-only settings: %j", patch => {
    expect(policies.VerticalPolicyOverrideSchema.safeParse(patch).success).toBe(false);
  });

  test("each independent penalty accepts zero without dropping other dimensions", () => {
    for (const name of Object.keys(policies.FeedPenaltyWeightsSchema.shape)) {
      expect(policies.FeedPenaltyWeightsPatchSchema.parse({ [name]: 0 })).toEqual({ [name]: 0 });
    }
  });

  test.each([0, -1, "12", NaN, Infinity, null, false])("rejects invalid freshness %j", value => {
    expect(policies.PlanningRunOverridesSchema.safeParse({ freshness_hours: value }).success).toBe(false);
  });

  test("global config rejects bad bounds, unknown keys, and invalid references", async () => {
    const config = await readConfig();
    for (const patch of [
      { partition: { ...config.partition, min_shards: 9 } },
      { partition: { ...config.partition, default_shards: 9 } },
      { harvest: { ...config.harvest, concurrency: "24" } },
      { curate: { ...config.curate, article_limit: 0 } },
      { curate: { ...config.curate, article_limit: 1.5 } },
      { triage: { ...config.triage, min_words_article: true } },
      { triage: { ...config.triage, max_age_hours: Infinity } },
      { desk_overrides: {} },
      { vertical_overrides: { ai: { triage: { blocked_http_statuses: [] } } } },
    ]) {
      expect(configs.FeedIngestConfigSchema.safeParse({ ...config, ...patch }).success).toBe(false);
    }
    const parsed = configs.FeedIngestConfigSchema.parse({ ...config, vertical_overrides: { missing: {} } });
    expect(() => configs.validatePlanningReferences(parsed, { verticals: [{ id: "ai" }] }))
      .toThrow("vertical_overrides.missing");
    expect(() => configs.PlanningTaxonomySchema.parse({ verticals: [{ id: "ai" }, { id: "ai" }] }))
      .toThrow("duplicate ids");
  });
}
