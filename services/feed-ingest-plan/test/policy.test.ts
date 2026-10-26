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

test("global policy resolves the authored defaults exactly", async () => {
  const config = await readInputs();
  expect(resolvePolicy(loadPlanningConfig(config))).toEqual({
    triage: {
      min_words_article: 180, min_words_abstract: 60, max_age_hours: 24,
      recency_half_life_hours: 18, recency_weight: 0.6,
    },
    curate: {
      source_authority_weight: 1, base_source_allowance: 3, bonus_unique_evidence: 1,
      mmr_weights: { lambda_source: 0.25, lambda_source_kind: 0.05, lambda_domain: 0.15 },
    },
  });
});

test("each global candidate policy field is independently replaceable, including zero", async () => {
  const config = await readInputs();
  const loaded = loadPlanningConfig(config);
  const baseline = resolvePolicy(loaded);
  const triageChanges = {
    min_words_article: 240, min_words_abstract: 80, max_age_hours: 12,
    recency_half_life_hours: 9, recency_weight: 0,
  };
  const curateChanges = { source_authority_weight: 0, base_source_allowance: 0, bonus_unique_evidence: 0 };
  for (const [name, value] of Object.entries(triageChanges)) {
    const changed = loadPlanningConfig({ ...config, triage: { ...config.triage, [name]: value } });
    expect(resolvePolicy(changed)).toEqual({ ...baseline, triage: { ...baseline.triage, [name]: value } });
    expect(resolvePolicy(loaded)).toEqual(baseline);
  }
  for (const [name, value] of Object.entries(curateChanges)) {
    const changed = loadPlanningConfig({ ...config, curate: { ...config.curate, [name]: value } });
    expect(resolvePolicy(changed)).toEqual({ ...baseline, curate: { ...baseline.curate, [name]: value } });
    expect(resolvePolicy(loaded)).toEqual(baseline);
  }
  for (const name of Object.keys(baseline.curate.mmr_weights)) {
    for (const value of [0, baseline.curate.mmr_weights[name as keyof typeof baseline.curate.mmr_weights] + 0.2]) {
      const changed = loadPlanningConfig({
        ...config, curate: { ...config.curate, mmr_weights: { ...config.curate.mmr_weights, [name]: value } },
      });
      expect(resolvePolicy(changed)).toEqual({
        ...baseline, curate: { ...baseline.curate, mmr_weights: { ...baseline.curate.mmr_weights, [name]: value } },
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
    curate: {
      ...config.curate, article_limit: 5,
      soft_caps: { ...config.curate.soft_caps, max_source_share: 0.2 },
    },
    feedback: { lifecycle_window_days: 5, request_report_closed_days: 2 },
    partition: { ...config.partition, default_shards: 2 },
  });
  expect(resolvePolicy(loaded)).toEqual(baseline);
  expect(loaded.config.curate.article_limit).toBe(5);
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
      ...config, curate: { ...config.curate, mmr_weights: { ...config.curate.mmr_weights, [removed]: 1 } },
    })).toThrow(removed);
  }
  for (const removed of ["metrics", "qualification", "component_weights"]) {
    expect(() => loadPlanningConfig({ ...config, feedback: { ...config.feedback, [removed]: {} } })).toThrow(removed);
  }
});

test("resolving one candidate mutates neither global policy nor returned sibling settings", async () => {
  const config = await readInputs();
  const loaded = loadPlanningConfig({
    ...config, curate: { ...config.curate, mmr_weights: { ...config.curate.mmr_weights, lambda_domain: 0 } },
  });
  const before = JSON.stringify(loaded);
  const result = resolvePolicy(loaded, { freshness_hours: 4 });
  result.curate.mmr_weights.lambda_domain = 99;
  expect(JSON.stringify(loaded)).toBe(before);
  expect(resolvePolicy(loaded).triage.max_age_hours).toBe(24);
  expect(resolvePolicy(loaded).curate.mmr_weights.lambda_domain).toBe(0);
  expect(resolvePolicy(loadPlanningConfig(config)).curate.mmr_weights.lambda_domain).toBe(0.15);
});
