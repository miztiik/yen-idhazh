/** Does one global planner policy substitute cleanly without vertical-specific controls? */
import { expect, test } from "bun:test";
import { loadPlanningConfig, resolvePolicy } from "../src/config/resolve-policy";

const readInputs = () => Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json();

test("global policy needs no taxonomy and refuses removed vertical overrides", async () => {
  const config = await readInputs();
  const loaded = loadPlanningConfig(config);
  expect(loaded).not.toHaveProperty("taxonomy");
  expect(loaded.config).not.toHaveProperty("vertical_overrides");
  const baseline = resolvePolicy(loaded);
  for (const vertical_overrides of [{}, { ai: {} }, { oceans: { triage: { max_age_hours: 12 } } }]) {
    expect(() => loadPlanningConfig({ ...config, vertical_overrides })).toThrow("vertical_overrides");
  }
  expect(resolvePolicy(loaded, { freshness_hours: 8 }).triage).toEqual({
    ...baseline.triage, max_age_hours: 8,
  });
  expect(resolvePolicy(loaded, { freshness_hours: 0.5 }).triage.max_age_hours).toBe(0.5);
  expect(resolvePolicy(loaded)).toEqual(baseline);
});

test("global policy resolves the current authored values without a second vocabulary", async () => {
  const config = await readInputs();
  const resolved = resolvePolicy(loadPlanningConfig(config));
  expect(resolved.triage).toEqual({
    min_words: config.triage.min_words, max_age_hours: config.triage.max_age_hours,
    recency_half_life_hours: config.triage.recency_half_life_hours,
    recency_weight: config.triage.recency_weight,
  });
  expect(resolved.curate_articles).toEqual({
    source_authority_weight: config.curate_articles.source_authority_weight,
    base_source_allowance: config.curate_articles.base_source_allowance,
    mmr_weights: config.curate_articles.mmr_weights,
  });
});

test("each global candidate policy field is independently replaceable, including zero", async () => {
  const config = await readInputs();
  const loaded = loadPlanningConfig(config);
  const baseline = resolvePolicy(loaded);
  const triageChanges = {
    min_words: 240, max_age_hours: 12,
    recency_half_life_hours: 9, recency_weight: 0,
  };
  const curateChanges = { source_authority_weight: 0, base_source_allowance: 0 };
  for (const [name, value] of Object.entries(triageChanges)) {
    const changed = loadPlanningConfig({ ...config, triage: { ...config.triage, [name]: value } });
    expect(resolvePolicy(changed)).toEqual({ ...baseline, triage: { ...baseline.triage, [name]: value } });
    expect(resolvePolicy(loaded)).toEqual(baseline);
  }
  for (const [name, value] of Object.entries(curateChanges)) {
    const changed = loadPlanningConfig({ ...config, curate_articles: { ...config.curate_articles, [name]: value } });
    expect(resolvePolicy(changed)).toEqual({ ...baseline, curate_articles: { ...baseline.curate_articles, [name]: value } });
    expect(resolvePolicy(loaded)).toEqual(baseline);
  }
  for (const name of Object.keys(baseline.curate_articles.mmr_weights)) {
    for (const value of [0, baseline.curate_articles.mmr_weights[name as keyof typeof baseline.curate_articles.mmr_weights] + 0.2]) {
      const changed = loadPlanningConfig({
        ...config, curate_articles: {
          ...config.curate_articles, mmr_weights: { ...config.curate_articles.mmr_weights, [name]: value },
        },
      });
      expect(resolvePolicy(changed)).toEqual({
        ...baseline, curate_articles: {
          ...baseline.curate_articles, mmr_weights: { ...baseline.curate_articles.mmr_weights, [name]: value },
        },
      });
      expect(resolvePolicy(loaded)).toEqual(baseline);
    }
  }
});

test("reporting and global portfolio controls cannot change candidate policies", async () => {
  const config = await readInputs();
  const baseline = resolvePolicy(loadPlanningConfig(config));
  const loaded = loadPlanningConfig({
    ...config,
    harvest: { ...config.harvest, concurrency: 1 },
    workflow_reporting: { ...config.workflow_reporting, enabled: true },
    curate_articles: {
      ...config.curate_articles, article_limit: 5,
      soft_caps: { ...config.curate_articles.soft_caps, max_source_share: 0.2 },
    },
    feedback: { lifecycle_window_days: 5, request_report_closed_days: 2 },
    partition: { ...config.partition, default_shards: 2 },
  });
  expect(resolvePolicy(loaded)).toEqual(baseline);
  expect(loaded.config.curate_articles.article_limit).toBe(5);
  expect(loaded.config.feedback).toEqual({ lifecycle_window_days: 5, request_report_closed_days: 2 });
});

test("removed controls, invalid run fields and null global policy fail before resolution", async () => {
  const config = await readInputs();
  const loaded = loadPlanningConfig(config);
  expect(() => loadPlanningConfig({ ...config, triage: { ...config.triage, recency_weight: null } })).toThrow("recency_weight");
  for (const freshness_hours of [0, -1, NaN, Infinity]) {
    expect(() => resolvePolicy(loaded, { freshness_hours })).toThrow("freshness_hours");
  }
  expect(() => resolvePolicy(loaded, { recency_half_life_hours: 3, freshness_hours: 8 } as never))
    .toThrow("recency_half_life_hours");
  expect(() => resolvePolicy(loaded, { vertical: "world" } as never)).toThrow("vertical");
  for (const removed of ["lambda_vertical", "lambda_desk", "lambda_lens", "lambda_event_type", "lambda_event_cluster", "lambda_entity", "lambda_coverage"]) {
    expect(() => loadPlanningConfig({
      ...config, curate_articles: {
        ...config.curate_articles, mmr_weights: { ...config.curate_articles.mmr_weights, [removed]: 1 },
      },
    })).toThrow(removed);
  }
  for (const removed of ["metrics", "qualification", "component_weights"]) {
    expect(() => loadPlanningConfig({ ...config, feedback: { ...config.feedback, [removed]: {} } })).toThrow(removed);
  }
});

test("resolving one candidate mutates neither global policy nor returned sibling settings", async () => {
  const config = await readInputs();
  const loaded = loadPlanningConfig({
    ...config, curate_articles: {
      ...config.curate_articles, mmr_weights: { ...config.curate_articles.mmr_weights, lambda_website_group: 0 },
    },
  });
  const before = JSON.stringify(loaded);
  const result = resolvePolicy(loaded, { freshness_hours: 4 });
  result.curate_articles.mmr_weights.lambda_website_group = 99;
  expect(JSON.stringify(loaded)).toBe(before);
  expect(resolvePolicy(loaded).triage.max_age_hours).toBe(config.triage.max_age_hours);
  expect(resolvePolicy(loaded).curate_articles.mmr_weights.lambda_website_group).toBe(0);
  expect(resolvePolicy(loadPlanningConfig(config)).curate_articles.mmr_weights.lambda_website_group)
    .toBe(config.curate_articles.mmr_weights.lambda_website_group);
});
