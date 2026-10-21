/** Does a config-only vertical patch resolve without changing another vertical? */
import { expect, test } from "bun:test";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

const resolverUrl = new URL("../src/config/resolve-policy.ts", import.meta.url);

test("a new vertical inherits global fields and applies only its declared patch", async () => {
  expect(existsSync(fileURLToPath(resolverUrl)), "Missing vertical planning policy resolver").toBe(true);
  const { loadPlanningConfig, resolvePolicy } = await import("../src/config/resolve-policy");
  const config = await Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json();
  const taxonomy = await Bun.file(new URL("../../../config/taxonomy.json", import.meta.url)).json();
  const baseline = loadPlanningConfig(config, taxonomy);
  const extended = loadPlanningConfig({
    ...config,
    vertical_overrides: {
      ...config.vertical_overrides,
      oceans: { triage: { max_age_hours: 12 }, curate: { mmr_weights: { lambda_lens: 0 } } },
    },
  }, {
    ...taxonomy,
    verticals: [
      ...taxonomy.verticals,
      { ...taxonomy.verticals[0], id: "oceans" },
      { ...taxonomy.verticals[0], id: "forests" },
    ],
  });
  const inherited = resolvePolicy(baseline, "ai");
  expect(resolvePolicy(extended, "oceans")).toEqual({
    triage: { ...inherited.triage, max_age_hours: 12 },
    curate: { ...inherited.curate, mmr_weights: { ...inherited.curate.mmr_weights, lambda_lens: 0 } },
  });
  expect(resolvePolicy(extended, "ai")).toEqual(inherited);
  expect(resolvePolicy(extended, "forests")).toEqual(inherited);
  expect(resolvePolicy(extended, "oceans", { freshness_hours: 8 }).triage).toEqual({
    ...inherited.triage, max_age_hours: 8,
  });
  expect(resolvePolicy(extended, "oceans").triage.max_age_hours).toBe(12);
  expect(resolvePolicy(extended, "oceans", { freshness_hours: 0.5 }).triage.max_age_hours).toBe(0.5);
});

const readInputs = async () => ({
  config: await Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json(),
  taxonomy: await Bun.file(new URL("../../../config/taxonomy.json", import.meta.url)).json(),
});

test("global policy resolves the authored defaults exactly", async () => {
  const { loadPlanningConfig, resolvePolicy } = await import("../src/config/resolve-policy");
  const { config, taxonomy } = await readInputs();
  expect(resolvePolicy(loadPlanningConfig(config, taxonomy), "ai")).toEqual({
    triage: {
      min_words_article: 180, min_words_abstract: 60, max_age_hours: 24,
      recency_half_life_hours: 18, recency_weight: 0.6,
    },
    curate: {
      source_authority_weight: 1, base_source_allowance: 3,
      bonus_uncovered_event_cluster: 1, bonus_underrepresented_vertical: 1,
      bonus_unique_evidence: 1,
      mmr_weights: {
        lambda_source: 0.25, lambda_source_kind: 0.05, lambda_domain: 0.15,
        lambda_vertical: 0.1, lambda_desk: 0.1, lambda_lens: 0.1,
        lambda_event_type: 0, lambda_event_cluster: 0.3, lambda_entity: 0, lambda_coverage: 0.1,
      },
    },
  });
});

test("each candidate policy field is independently replaceable, including zero", async () => {
  const { loadPlanningConfig, resolvePolicy } = await import("../src/config/resolve-policy");
  const { config, taxonomy } = await readInputs();
  const baseline = resolvePolicy(loadPlanningConfig(config, taxonomy), "ai");
  const triageChanges = {
    min_words_article: 240, min_words_abstract: 80, max_age_hours: 12,
    recency_half_life_hours: 9, recency_weight: 0,
  };
  const curateChanges = {
    source_authority_weight: 0, base_source_allowance: 0,
    bonus_uncovered_event_cluster: 0, bonus_underrepresented_vertical: 0, bonus_unique_evidence: 0,
  };
  for (const [name, value] of Object.entries(triageChanges)) {
    const loaded = loadPlanningConfig({
      ...config, vertical_overrides: { ai: { triage: { [name]: value } } },
    }, taxonomy);
    expect(resolvePolicy(loaded, "ai")).toEqual({
      ...baseline, triage: { ...baseline.triage, [name]: value },
    });
    expect(resolvePolicy(loaded, "energy")).toEqual(baseline);
  }
  for (const [name, value] of Object.entries(curateChanges)) {
    const loaded = loadPlanningConfig({
      ...config, vertical_overrides: { ai: { curate: { [name]: value } } },
    }, taxonomy);
    expect(resolvePolicy(loaded, "ai")).toEqual({
      ...baseline, curate: { ...baseline.curate, [name]: value },
    });
    expect(resolvePolicy(loaded, "energy")).toEqual(baseline);
  }
  for (const name of Object.keys(baseline.curate.mmr_weights)) {
    const value = baseline.curate.mmr_weights[name as keyof typeof baseline.curate.mmr_weights] + 0.2;
    const loaded = loadPlanningConfig({
      ...config, vertical_overrides: { ai: { curate: { mmr_weights: { [name]: value } } } },
    }, taxonomy);
    expect(resolvePolicy(loaded, "ai")).toEqual({
      ...baseline, curate: { ...baseline.curate, mmr_weights: { ...baseline.curate.mmr_weights, [name]: value } },
    });
    expect(resolvePolicy(loaded, "energy")).toEqual(baseline);
  }
});

test("reporting and global controls cannot change candidate policies", async () => {
  const { loadPlanningConfig, resolvePolicy } = await import("../src/config/resolve-policy");
  const { config, taxonomy } = await readInputs();
  const baseline = resolvePolicy(loadPlanningConfig(config, taxonomy), "ai");
  const loaded = loadPlanningConfig({
    ...config,
    harvest: { ...config.harvest, concurrency: 1 },
    workflow_reporting: { ...config.workflow_reporting, enabled: true },
    curate: {
      ...config.curate, article_limit: 5,
      soft_caps: { ...config.curate.soft_caps, max_source_share: 0.2 },
    },
    partition: { ...config.partition, default_shards: 2 },
  }, taxonomy);
  expect(resolvePolicy(loaded, "ai")).toEqual(baseline);
  expect(loaded.config.curate.article_limit).toBe(5);
});

test("invalid references, run fields, and null inheritance fail before resolution", async () => {
  const { loadPlanningConfig, resolvePolicy } = await import("../src/config/resolve-policy");
  const { config, taxonomy } = await readInputs();
  const loaded = loadPlanningConfig(config, taxonomy);
  expect(() => resolvePolicy(loaded, "missing")).toThrow("vertical.missing");
  expect(() => loadPlanningConfig({ ...config, vertical_overrides: { missing: {} } }, taxonomy))
    .toThrow("vertical_overrides.missing");
  expect(() => loadPlanningConfig({
    ...config, vertical_overrides: { ai: { triage: { recency_weight: null } } },
  }, taxonomy)).toThrow("recency_weight");
  for (const freshness_hours of [0, -1, NaN, Infinity]) {
    expect(() => resolvePolicy(loaded, "ai", { freshness_hours })).toThrow("freshness_hours");
  }
  const invalidRun = { recency_half_life_hours: 3, freshness_hours: 8 };
  expect(() => resolvePolicy(loaded, "ai", invalidRun))
    .toThrow("recency_half_life_hours");
});

test("resolving one candidate does not mutate global, vertical, or returned sibling settings", async () => {
  const { loadPlanningConfig, resolvePolicy } = await import("../src/config/resolve-policy");
  const { config, taxonomy } = await readInputs();
  const loaded = loadPlanningConfig({
    ...config, vertical_overrides: { ai: { curate: { mmr_weights: { lambda_desk: 0 } } } },
  }, taxonomy);
  const input = JSON.stringify(loaded);
  const result = resolvePolicy(loaded, "ai", { freshness_hours: 4 });
  result.curate.mmr_weights.lambda_lens = 99;
  expect(JSON.stringify(loaded)).toBe(input);
  expect(resolvePolicy(loaded, "ai").triage.max_age_hours).toBe(24);
  expect(resolvePolicy(loaded, "energy").curate.mmr_weights.lambda_lens).toBe(0.1);
});
