/** Does one global planner policy substitute cleanly without vertical-specific controls? */
import { expect, test } from "bun:test";
import { loadPlanningConfig, resolvePolicy } from "../src/config/resolve-policy";
import { FeedHarvestConfigSchema } from "@idhazh/common-contracts";

const readInputs = () => Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json();

test("authored article word ceilings are required and independently configurable", async () => {
  const config = await readInputs();
  expect(loadPlanningConfig(config).config.harvest.max_input_words).toBe(20000);
  expect(FeedHarvestConfigSchema.shape.max_input_words.parse(undefined)).toBe(20000);
  expect(loadPlanningConfig({
    ...config, harvest: { ...config.harvest, max_input_words: 1000 },
  }).config.harvest.max_input_words).toBe(1000);
  const { max_input_words: _words, ...harvest } = config.harvest;
  expect(() => loadPlanningConfig({ ...config, harvest })).toThrow("max_input_words");
  for (const max_input_words of [0, -1, 1.5, null, "20000", Number.MAX_SAFE_INTEGER + 1]) {
    expect(() => loadPlanningConfig({ ...config, harvest: { ...config.harvest, max_input_words } }))
      .toThrow("max_input_words");
  }
  expect(() => loadPlanningConfig({ ...config, version: "2026-11-05" })).toThrow("version");
});

test("global policy needs no taxonomy and refuses removed vertical overrides", async () => {
  const config = await readInputs();
  const loaded = loadPlanningConfig(config);
  expect(loaded).not.toHaveProperty("taxonomy");
  expect(loaded.config).not.toHaveProperty("vertical_overrides");
  const baseline = resolvePolicy(loaded);
  for (const vertical_overrides of [{}, { ai: {} }, { oceans: { triage: { max_age_hours: 12 } } }]) {
    expect(() => loadPlanningConfig({ ...config, vertical_overrides })).toThrow("vertical_overrides");
  }
  expect(baseline.triage).not.toHaveProperty("max_age_hours");
  expect(resolvePolicy(loaded)).toEqual(baseline);
});

test("global policy resolves the current authored values without a second vocabulary", async () => {
  const config = await readInputs();
  const resolved = resolvePolicy(loadPlanningConfig(config));
  expect(resolved.triage).toEqual({
    min_words: config.triage.min_words,
    recency_half_life_hours: config.triage.recency_half_life_hours,
    recency_weight: config.triage.recency_weight,
  });
  expect(resolved.curate_articles).toEqual({
    source_authority_weight: config.curate_articles.source_authority_weight,
  });
});

test("each global candidate policy field is independently replaceable, including zero", async () => {
  const config = await readInputs();
  const loaded = loadPlanningConfig(config);
  const baseline = resolvePolicy(loaded);
  const triageChanges = {
    min_words: 240,
    recency_half_life_hours: 9, recency_weight: 0,
  };
  const curateChanges = { source_authority_weight: 0 };
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
      global_age_ceiling_hours: 12,
      diversity: { lambda_domain: 1, lambda_feed: 2, novelty_bonus: 0 },
      substance: {
        ...config.curate_articles.substance, word_count_ramp_end: 100,
        substantive_paragraph_min_words: 10, substantive_paragraph_min_sentences: 3,
      },
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
  expect(() => loadPlanningConfig({ ...config, triage: { ...config.triage, recency_weight: null } })).toThrow("recency_weight");
  for (const removed of ["source_based_quality_buckets", "soft_caps", "mmr_weights", "exploration_slot_share"]) {
    expect(() => loadPlanningConfig({
      ...config, curate_articles: {
        ...config.curate_articles, [removed]: {},
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
      ...config.curate_articles, source_authority_weight: 0,
    },
  });
  const before = JSON.stringify(loaded);
  const result = resolvePolicy(loaded);
  result.curate_articles.source_authority_weight = 99;
  expect(JSON.stringify(loaded)).toBe(before);
  expect(resolvePolicy(loaded).curate_articles.source_authority_weight).toBe(0);
  expect(resolvePolicy(loadPlanningConfig(config)).curate_articles.source_authority_weight)
    .toBe(config.curate_articles.source_authority_weight);
});
