/** Does real portfolio curation retain independent evidence and exact decisions? */
import { expect, test } from "bun:test";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import {
  FeedIngestCandidateSchema, FeedIngestDispatchSchema, deriveCandidateId, deriveUrlKey,
  WriterIdentitySchema, HarvestDiagnosticsSchema,
} from "@idhazh/common-contracts";
import type { FeedIngestConfig } from "@idhazh/common-contracts";
import { tableFromIPC } from "apache-arrow";
import initializeParquet, { readParquet, readMetadata } from "parquet-wasm/esm";
import { loadPlanningConfig, resolvePolicy } from "../src/config/resolve-policy";
import type { PlanningConfig } from "../src/config/resolve-policy";
import { curateArticles, persistPortfolio } from "../src/curate-article-portfolio/editorial-selection";
import type { CurationPersistence } from "../src/curate-article-portfolio/editorial-selection";
import type { ArticleEvidence, OperationalEvidence, OpportunityEvidence, PortfolioArticle } from "../src/curate-article-portfolio/portfolio-input";
import { compareStory } from "../src/curate-article-portfolio/story-evidence";
import type { StoryComparison } from "../src/curate-article-portfolio/story-evidence";
import { groupCarriers } from "../src/curate-article-portfolio/carrier-cluster";
import { HarvestObservationSchema } from "../src/harvest-feeds/harvest-types";
import { recordedPlan } from "./plan-recordings";
import { inputs as harvestInputs, source } from "./harvest-recordings";
import { runFeedPlan, summarizePlan } from "../src/run-feed-plan";

type CandidateCase = {
  name: string; source: string; ordinal: number; vertical: string; kind: string;
  domain: string; publisher: string; publisher_id: string | null; title: string; published_at: string;
  desk: string | null; lenses: string[] | null; event_types: string[] | null;
  cluster: string | null; entities: string[] | null;
};
type Fixture = {
  observed_at: string; run_id: string; correlation_id: string; policy_version: string; config_sha256: string;
  reliability_floor: number;
  publisher_exposure_cases: {
    name: string; availability: "available" | "unavailable"; published: number;
    coefficient: number; first_penalty: number;
  }[];
  reliability_cases: {
    name: string; enabled: boolean; floor: number; alpha: OperationalEvidence | null; gamma: OperationalEvidence | null;
    winner: string; alpha_penalty: number | null; gamma_penalty: number | null;
  }[];
  candidates: CandidateCase[];
  expected: { baseline: string[]; each_saturation_coefficient_one: string[]; base_scores: Record<string, number>; selected_ranks: number[] };
  story_pairs: { left: string; right: string; expected: StoryComparison["method"] }[];
  recorded_format: {
    row_schema_version: string; candidate_first: string; selection_columns: string[];
    rejection_reason: string; selection_count: number; rejection_count: number;
    selection_unit_id: string; rejection_unit_id: string; selection_scalar_types: Record<string, string>;
  };
};
type Knobs = FeedIngestConfig["curate"];
const noOpportunity: OpportunityEvidence = {
  covered_event_clusters: null, underrepresented_verticals: null, origin: null,
};

async function inputs(patch: Partial<Knobs> = {}) {
  const [fixture, authored, taxonomy] = await Promise.all([
    Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/portfolio-cases.json", import.meta.url)).json() as Promise<Fixture>,
    Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json(),
    Bun.file(new URL("../../../config/taxonomy.json", import.meta.url)).json(),
  ]);
  const planning = loadPlanningConfig({
    ...authored,
    triage: { ...authored.triage, max_age_hours: 72, recency_half_life_hours: 18, recency_weight: 1 },
    curate: {
      ...authored.curate, article_limit: 2, base_source_allowance: 3,
      bonus_uncovered_event_cluster: 0, bonus_underrepresented_vertical: 0, bonus_unique_evidence: 0,
      source_authority_weight: 0, exploration_slot_share: 0,
      soft_caps: { ...authored.curate.soft_caps, max_source_share: 1, max_parent_domain_share: 1, min_distinct_sources: 1, max_event_cluster_items: 3 },
      mmr_weights: Object.fromEntries(Object.keys(authored.curate.mmr_weights).map(key => [key, 0])),
      ...patch,
    },
  }, taxonomy);
  return { fixture, planning };
}

function article(spec: CandidateCase, fixture: Fixture, planning: PlanningConfig): PortfolioArticle {
  const policy = resolvePolicy(planning, spec.vertical);
  const { mmr_weights, ...curate } = policy.curate;
  const url = `https://${spec.domain}/${spec.name}`;
  const candidate = FeedIngestCandidateSchema.parse({
    date: fixture.observed_at.slice(0, 10), correlation_id: fixture.correlation_id,
    run_id: fixture.run_id, candidate_id: deriveCandidateId(fixture.run_id, spec.source, spec.ordinal),
    entry_ordinal: spec.ordinal, source_id: spec.source, vertical: spec.vertical,
    source: {
      source_id: spec.source, publisher_id: spec.publisher_id,
      feed_url: `https://${spec.domain}/feed`, title: `${spec.source} feed title, not a masthead`,
      vertical: spec.vertical, kind: spec.kind, tier: 1, form: "article", status: "active",
      weight: 1, applied_tier_weight: 1,
    },
    canonical_url: url, url_key: deriveUrlKey(url), title: spec.title, categories: ["feed-category"],
    article_text: "Recorded factual report. ".repeat(100), word_count: 300, author: null,
    published_at: spec.published_at, fetched_at: fixture.observed_at,
    labels: {
      assigned_desk: spec.desk, lenses: spec.lenses, event_types: spec.event_types,
      event_cluster_id: spec.cluster, entities: spec.entities,
      origin: "recorded-fixture-labels", matcher_version: "fixture-1",
    },
    policy: { policy_version: fixture.policy_version, config_sha256: fixture.config_sha256, ...policy.triage, ...curate, ...mmr_weights },
  });
  const age = (Date.parse(fixture.observed_at) - Date.parse(spec.published_at)) / 3_600_000;
  const evidence: ArticleEvidence = {
    publisher: { value: spec.publisher, origin: "recorded-publisher-attribute" },
    parent_domain: { value: spec.domain, origin: "configured-parent-domain" },
    operational: { success_fraction: 0.5, attempted: 4, window_days: 7 },
    primary_evidence: null, estimated_work: candidate.word_count,
  };
  return {
    candidate, policy, observation: null, seen_availability: "unavailable",
    freshness: {
      timing_at: spec.published_at, timing_source: "published_at", age_hours: age,
      recency_bonus: policy.triage.recency_weight * 0.5 ** (Math.max(0, age) / policy.triage.recency_half_life_hours),
    }, evidence,
  };
}

function run(planning: PlanningConfig, fixture: Fixture, specs = fixture.candidates, opportunity = noOpportunity) {
  return curateArticles({
    articles: specs.map(spec => article(spec, fixture, planning)),
    planning, opportunity, observed_at: fixture.observed_at, reliability_floor: fixture.reliability_floor,
  });
}

function names(result: ReturnType<typeof run>) {
  return result.selected.map(a => new URL(a.candidate.canonical_url).pathname.slice(1));
}

test("fixed real stage selects exact identities, ranks, components and preserves content", async () => {
  const { fixture, planning } = await inputs();
  const diagnostics = HarvestDiagnosticsSchema.parse({ http_status: 200, fetch_ms: 17, extract_ms: 3 });
  const articles = fixture.candidates.map(spec => {
    const offered = article(spec, fixture, planning);
    return {
      ...offered,
      observation: HarvestObservationSchema.parse({
        candidate_id: offered.candidate.candidate_id, http_status: 200, paywall: false,
        robots: "allowed", fetch_failure: null, extraction: "success",
        observed_at: fixture.observed_at, paywall_evidence: "none", diagnostics,
      }),
    };
  });
  const result = curateArticles({ articles, planning, opportunity: noOpportunity, observed_at: fixture.observed_at, reliability_floor: fixture.reliability_floor });
  expect(names(result)).toEqual(fixture.expected.baseline);
  expect(result.rows.map(row => row.editorial_rank)).toEqual(fixture.expected.selected_ranks);
  expect(result.trace.map(step => step.selected_before.length)).toEqual([0, 1]);
  for (const step of result.trace) for (const entry of step.evaluated) {
    const original = result.input.find(a => a.candidate.candidate_id === entry.candidate_id)!;
    const name = new URL(original.candidate.canonical_url).pathname.slice(1);
    expect(entry.scores.base_article_score).toBe(fixture.expected.base_scores[name]!);
    expect(entry.scores.marginal_score).toBe(entry.scores.base_article_score);
  }
  expect(result.selected[0]!.candidate.article_text).toBe(article(fixture.candidates[0]!, fixture, planning).candidate.article_text);
  expect(result.rows[0]!.vertical).toBe("ai");
  expect(result.rows[0]!.candidate_id).toBe(fixture.recorded_format.candidate_first);
  expect(result.quality[0]!.operational).toEqual({ success_fraction: 0.5, attempted: 4, window_days: 7 });
  expect(result.quality[0]!.article.informative_verdict).toBeNull();
  expect(result.assessments.every(row => row.informative_verdict_status === "not_assessed"
    && row.suitability_verdict_status === "not_assessed")).toBe(true);
  expect(result.rejections).toHaveLength(1);
  expect(result.rejections[0]?.details.diagnostics).toEqual(diagnostics);
  expect(result.input.length).toBe(result.rows.length + result.rejections.length);
});

test("every saturation coefficient substitutes independently at each actual choice", async () => {
  const original = await inputs();
  const dimensions = ["source_kind", "domain", "vertical", "desk", "lens", "event_type", "event_cluster", "entity"] as const;
  for (const dimension of dimensions) {
    const key = `lambda_${dimension}` as keyof Knobs["mmr_weights"];
    const planning = loadPlanningConfig({
      ...original.planning.config,
      vertical_overrides: { ai: { curate: { mmr_weights: { [key]: 1 } } } },
    }, original.planning.taxonomy);
    const result = run(planning, original.fixture);
    expect(names(result)).toEqual(original.fixture.expected.each_saturation_coefficient_one);
    const second = result.trace.find(step => step.selected_before.length === 1)!;
    const middle = second.evaluated.find(value => value.candidate_id === deriveCandidateId(original.fixture.run_id, "alpha", 1))!;
    expect(middle.scores[dimension]).toEqual({ available: true, value: 1 });
    expect(middle.scores.marginal_score).toBe(-0.5);
    for (const other of dimensions.filter(value => value !== dimension)) expect(middle.scores[other].value).toBe(0);
    expect(result.rows[1]!.ratings[dimension].value).toBe(0);
    expect(result.rows[0]!.ratings[dimension].value).toBe(0);
  }
  const { fixture, planning } = await inputs();
  const specs = structuredClone(fixture.candidates);
  specs[1]!.source = "beta";
  for (const recorded of fixture.publisher_exposure_cases) {
    planning.config.curate.mmr_weights.lambda_source = recorded.coefficient;
    const articles = specs.map(spec => article(spec, fixture, planning));
    const before = structuredClone(articles);
    const result = curateArticles({
      articles, planning, observed_at: fixture.observed_at,
      opportunity: noOpportunity, reliability_floor: fixture.reliability_floor,
      publication_history: {
        day: fixture.observed_at.slice(0, 10), availability: recorded.availability,
        counts: new Map([["one-news", recorded.published]]),
      },
    });
    expect(result.rows).toHaveLength(2);
    expect(articles).toEqual(before);
    const first = result.trace[0]!.evaluated.find(entry => entry.candidate_id === articles[0]!.candidate.candidate_id)!;
    expect(first.scores.publisher_exposure).toMatchObject({
      publisher_id: "one-news", history_status: recorded.availability,
      published_today: recorded.availability === "available" ? recorded.published : null,
      selected_so_far: 0, planned_slots: 2, coefficient: recorded.coefficient, value: recorded.first_penalty,
    });
    expect(first.scores.source).toEqual({ available: false, value: null });
    expect(first.scores.base_article_score).toBe(1);
    expect(first.scores.marginal_score).toBe(1 - recorded.first_penalty);
    if (recorded.name === "unequal known publication") expect(names(result)[0]).toBe("alternative");
    if (recorded.name === "known empty day" || recorded.availability === "unavailable") {
      const sibling = result.trace[1]!.evaluated.find(entry => entry.candidate_id === articles[1]!.candidate.candidate_id)!;
      expect(sibling.scores.publisher_exposure).toMatchObject({
        publisher_id: "one-news", selected_so_far: 1, planned_slots: 2, value: recorded.coefficient / 2,
      });
    }
    expect(result.rows[0]!.ratings).toEqual(result.choices[0]!.scores);
    expect(result.assessments.find(row => row.candidate_id === result.rows[0]!.candidate_id)!.score_evidence)
      .toEqual(result.rows[0]!.ratings);
  }
  const unknown = curateArticles({
    articles: specs.map(spec => article({ ...spec, publisher_id: null }, fixture, planning)),
    planning, observed_at: fixture.observed_at, opportunity: noOpportunity, reliability_floor: fixture.reliability_floor,
  });
  expect(unknown.trace.flatMap(step => step.evaluated).every(entry =>
    entry.scores.publisher_exposure?.publisher_id === null
    && entry.scores.publisher_exposure.selected_so_far === 0
    && entry.scores.publisher_exposure.value === null)).toBe(true);
});

test("coverage uses recorded occurrence coverage, not entity or event-type overlap", async () => {
  const { fixture, planning } = await inputs();
  planning.config.curate.mmr_weights.lambda_coverage = 1;
  const specs = structuredClone(fixture.candidates);
  specs[0]!.cluster = "uncovered-occurrence";
  const result = run(planning, fixture, specs, {
    covered_event_clusters: ["shared-occurrence"], underrepresented_verticals: [], origin: "bounded-prior-coverage",
  });
  expect(names(result)).toEqual(["first", "alternative"]);
  for (const step of result.trace) {
    const middle = step.evaluated.find(value => value.candidate_id === deriveCandidateId(fixture.run_id, "alpha", 1))!;
    expect(middle.scores.coverage).toEqual({ available: true, value: 1 });
    expect(middle.scores.marginal_score).toBe(-0.5);
    expect(middle.scores.entity.value).toBe(0);
    expect(middle.scores.event_cluster.value).toBe(0);
  }
});

test("known-empty labels differ from unavailable labels and overlap is counted once", async () => {
  const { fixture, planning } = await inputs();
  planning.config.curate.article_limit = 3;
  planning.config.curate.mmr_weights.lambda_lens = 1;
  const result = run(planning, fixture);
  const final = result.rows.find(row => row.candidate_id === deriveCandidateId(fixture.run_id, "alpha", 1))!;
  expect(final.ratings.lens.value).toBe(0.5);
  for (const value of [null, []]) {
    const specs = structuredClone(fixture.candidates);
    specs[1]!.lenses = value;
    const changed = run(planning, fixture, specs);
    const second = changed.trace[1]!.evaluated.find(row => row.candidate_id === final.candidate_id)!;
    expect(second.scores.lens).toEqual(value === null
      ? { available: false, value: null } : { available: true, value: 0 });
  }
  const unknown = structuredClone(fixture.candidates);
  unknown[0]!.desk = null;
  const changed = run(planning, fixture, unknown);
  expect(changed.trace[1]!.evaluated.find(row => row.candidate_id === final.candidate_id)!.scores.desk.available).toBe(false);
  const sources = [source(), source({ id: "recorded-atom", url: "https://atom.example/feed.xml" })];
  const recorded = await recordedPlan(sources);
  try {
    recorded.inputs.harvest = await harvestInputs(sources, {
      lenses: [{ id: "headline-theme", keywords: ["entry"], weight: 0.9, status: "active", retired_on: null }],
      entities: [{ id: "watched-subject", aliases: ["entry"], status: "active", retired_on: null }],
      salience: [{ id: "unavailable-vote", title: "Failed optional feed", url: "https://news.example/malformed.xml", status: "active", retired_on: null }],
    });
    const config = recorded.inputs.harvest.config;
    config.triage.min_words_article = 100;
    config.curate.base_source_allowance = 10;
    config.curate.exploration_slot_share = 0;
    config.curate.soft_caps.max_source_share = 1;
    config.curate.soft_caps.min_distinct_sources = 1;
    for (const key of Object.keys(config.curate.mmr_weights) as (keyof typeof config.curate.mmr_weights)[]) {
      config.curate.mmr_weights[key] = key === "lambda_lens" || key === "lambda_entity" ? 1 : 0;
    }
    const wired = await runFeedPlan({ article_limit: 2 }, recorded.inputs, recorded.runtime);
    const curation = wired.evidence.curation;
    const unavailable = curateArticles({
      articles: curation.input.map(article => ({
        ...article, candidate: { ...article.candidate, labels: {
          ...article.candidate.labels, lenses: null, entities: null, origin: null, matcher_version: null,
        } },
      })),
      planning: wired.evidence.harvest.inputs, observed_at: wired.context.now,
      reliability_floor: recorded.inputs.clock_config.collect.reliability_floor,
      opportunity: curation.opportunity,
    });
    expect(curation.rows[0]!.candidate_id).toBe(unavailable.rows[0]!.candidate_id);
    expect(curation.rows[1]!.candidate_id).not.toBe(unavailable.rows[1]!.candidate_id);
    expect(curation.selected[1]!.candidate.title).toBe("Measured progress & public evidence");
    expect(curation.quality.map(row => row.components)).toEqual(unavailable.quality.map(row => row.components));
    const displaced = curation.trace[1]!.evaluated.find(row => row.candidate_id === unavailable.rows[1]!.candidate_id)!;
    expect(displaced.scores.lens).toEqual({ available: true, value: 1 });
    expect(displaced.scores.entity).toEqual({ available: true, value: 1 });
    for (const candidate of wired.evidence.harvest.candidates) {
      expect(candidate.planning_observations).toMatchObject({
        salience_available: false, on_front_page: null, salience_unavailable_reason: "salience-feed-unavailable",
        salience: [{ feed_id: "unavailable-vote", available: false, voted: null, unavailable_reason: "feed-parse-failed" }],
      });
    }
    expect(summarizePlan(wired).editorial_inputs).toMatchObject({
      headline_consumer: "existing_mmr_lens_entity_penalties", bonus_consumer: null,
      unavailable_consumers: ["salience_vote", "watchlist_bonus", "lens_weight_bonus"],
    });
    expect(wired.evidence.partition.dispatches[0]!.content.planning_observations)
      .toEqual(curation.selected[0]!.candidate.planning_observations);
  } finally { await recorded.close(); }
});

test("kind relabel changes no allowance, viability, or authority; zero disables its influence", async () => {
  const { fixture, planning } = await inputs();
  const baseline = run(planning, fixture);
  const specs = fixture.candidates.map(spec => ({ ...spec, kind: "new-configured-kind" }));
  const relabelled = run(planning, fixture, specs);
  expect(names(relabelled)).toEqual(names(baseline));
  expect([...relabelled.normalization.allowances.values()]).toEqual([...baseline.normalization.allowances.values()]);
  expect(relabelled.quality.map(q => q.components)).toEqual(baseline.quality.map(q => q.components));
  expect(relabelled.rejections.map(r => r.drop_reason)).toEqual(["MMR_PORTFOLIO_CUTOFF"]);
});

test("flooding duplicates cannot buy allowance or displace another qualifying source", async () => {
  const { fixture, planning } = await inputs({ article_limit: null, base_source_allowance: 1 });
  const articles = fixture.candidates.map(spec => article(spec, fixture, planning));
  const baseline = curateArticles({ articles, planning, observed_at: fixture.observed_at, opportunity: noOpportunity, reliability_floor: fixture.reliability_floor });
  const original = articles[0]!;
  const copies = Array.from({ length: 20 }, (_, index) => ({
    ...structuredClone(original),
    candidate: {
      ...original.candidate, candidate_id: deriveCandidateId(fixture.run_id, "alpha", index + 10),
      entry_ordinal: index + 10,
    },
  }));
  const flood = curateArticles({
    articles: [...articles, ...copies], planning, observed_at: fixture.observed_at, opportunity: noOpportunity,
    reliability_floor: fixture.reliability_floor,
  });
  expect(names(flood)).toEqual(names(baseline));
  expect(flood.rows.map(row => row.source_id).sort()).toEqual(["alpha", "gamma"]);
  expect(flood.normalization.allowances.get("alpha")!.allowance).toBe(1);
  expect(flood.rejections.filter(r => r.drop_reason === "DUPLICATE_CANONICAL_URL")).toHaveLength(20);
  const quota = flood.rejections.find(r => r.drop_reason === "SOURCE_QUOTA_EXCEEDED")!;
  expect(quota.details.limit).toBe(1);
  expect(quota.details.observed_value).toBe(2);
  const configured = loadPlanningConfig({
    ...planning.config, curate: { ...planning.config.curate, source_authority_weight: 1 },
  }, planning.taxonomy);
  const carriers = fixture.candidates.map(spec => {
    const offered = article({
      ...spec, published_at: fixture.observed_at,
      cluster: spec.name === "middle" ? "separate-occurrence" : "shared-occurrence",
    }, fixture, configured);
    return { ...offered, evidence: { ...offered.evidence, operational: {
      success_fraction: spec.source === "alpha" ? 0 : 0.75, attempted: 4, window_days: 7,
    } } };
  });
  const enabled = curateArticles({
    articles: carriers, planning: configured, observed_at: fixture.observed_at,
    opportunity: noOpportunity, reliability_floor: fixture.reliability_floor,
  });
  const disabled = curateArticles({
    articles: carriers, planning: loadPlanningConfig({
      ...configured.config, curate: { ...configured.config.curate, source_reliability_penalty_enabled: false },
    }, configured.taxonomy), observed_at: fixture.observed_at,
    opportunity: noOpportunity, reliability_floor: fixture.reliability_floor,
  });
  expect(names(disabled)).toEqual(["first"]);
  expect(names(enabled)).toEqual(names(disabled));
  expect(disabled.normalization.rejected.map(row => row.article.candidate.candidate_id))
    .toEqual([carriers[1]!.candidate.candidate_id]);
  expect(enabled.normalization.rejected.map(row => row.article.candidate.candidate_id))
    .toEqual(disabled.normalization.rejected.map(row => row.article.candidate.candidate_id));
  expect(enabled.carriers.suppressed).toEqual(disabled.carriers.suppressed);
  expect(enabled.rows.map(row => row.ratings.source_reliability)).toEqual([null]);
});

test("each bonus needs a distinct witness and is granted at most once", async () => {
  const { fixture, planning } = await inputs({
    article_limit: null, base_source_allowance: 1,
    bonus_uncovered_event_cluster: 1, bonus_underrepresented_vertical: 1, bonus_unique_evidence: 1,
  });
  const specs = Array.from({ length: 5 }, (_, i) => ({
    ...fixture.candidates[0]!, name: `alpha-${i}`, ordinal: i, cluster: `cluster-${i}`,
  }));
  const articles = specs.map(spec => {
    const a = article(spec, fixture, planning);
    return { ...a, evidence: { ...a.evidence, primary_evidence: { ids: [`record-${spec.ordinal}`], origin: "recorded-primary-document" } } };
  });
  const result = curateArticles({
    articles, planning, observed_at: fixture.observed_at, reliability_floor: fixture.reliability_floor,
    opportunity: { covered_event_clusters: [], underrepresented_verticals: ["ai"], origin: "bounded-history" },
  });
  const allowance = result.normalization.allowances.get("alpha")!;
  expect(allowance.allowance).toBe(4);
  expect(allowance.witnesses.map(w => w.kind)).toEqual(["uncovered_event_cluster", "underrepresented_vertical", "unique_evidence"]);
  expect(new Set(allowance.witnesses.map(w => w.url_key)).size).toBe(3);
  expect(result.rows).toHaveLength(4);
  const missing = curateArticles({ articles, planning, observed_at: fixture.observed_at, opportunity: noOpportunity, reliability_floor: fixture.reliability_floor });
  expect(missing.normalization.allowances.get("alpha")!.allowance).toBe(2);
  const alone = curateArticles({
    articles: articles.slice(0, 1), planning, observed_at: fixture.observed_at, reliability_floor: fixture.reliability_floor,
    opportunity: { covered_event_clusters: [], underrepresented_verticals: ["ai"], origin: "bounded-history" },
  });
  expect(alone.normalization.allowances.get("alpha")!.witnesses).toHaveLength(1);
});

test("soft caps relax only in configured order and parent-domain/cluster limits remain effective", async () => {
  const { fixture, planning } = await inputs({ article_limit: null });
  planning.config.curate.soft_caps = {
    max_source_share: 0.2, max_parent_domain_share: 1,
    max_event_cluster_items: 3, min_distinct_sources: 3,
    relaxation_order: ["distinct_sources", "source_share"],
  };
  const result = run(planning, fixture);
  expect(names(result)).toEqual(["first", "alternative", "middle"]);
  expect(result.rows[2]!.ratings.cap_relaxations).toEqual(["distinct_sources", "source_share"]);
  expect(result.trace.filter(step => step.choice === null).map(step => step.relaxations))
    .toEqual([[], ["distinct_sources"]]);
  planning.config.curate.soft_caps.max_parent_domain_share = 0.2;
  const domainCapped = run(planning, fixture);
  expect(domainCapped.rows).toHaveLength(2);
  expect(domainCapped.cutoffs[0]!.controls).toContainEqual({
    control: "parent_domain_share", observed_value: 2, limit: 1,
  });
  expect(domainCapped.rejections[0]!.details.observed_value).toBe(2);
  expect(domainCapped.rejections[0]!.details.limit).toBe(1);
  planning.config.curate.soft_caps.max_parent_domain_share = 1;
  planning.config.curate.soft_caps.max_event_cluster_items = 1;
  expect(run(planning, fixture).rows).toHaveLength(2);
});

test("exploration reserves configured slots only for viable unseen sources", async () => {
  const { fixture, planning } = await inputs({ exploration_slot_share: 0.5 });
  const result = run(planning, fixture);
  expect(names(result)).toEqual(["first", "alternative"]);
  expect(result.rows.map(row => row.ratings.exploration_slot)).toEqual([false, true]);
  // Two reserved slots require the second choice to bring another source.
  planning.config.curate.exploration_slot_share = 1;
  expect(names(run(planning, fixture))).toEqual(["first", "alternative"]);
  const invalid = article(fixture.candidates[2]!, fixture, planning);
  invalid.candidate.word_count = 0;
  expect(() => curateArticles({
    articles: [invalid], planning, observed_at: fixture.observed_at, opportunity: noOpportunity, reliability_floor: fixture.reliability_floor,
  })).toThrow("viability");
});

test("carrier evidence never invents vectors, mastheads, occurrence labels, or verification", async () => {
  const { fixture, planning } = await inputs();
  for (const pair of fixture.story_pairs) {
    const first = article({ ...fixture.candidates[0]!, title: pair.left }, fixture, planning);
    const second = article({
      ...fixture.candidates[2]!, title: pair.right,
      cluster: pair.expected === "unavailable" ? null : "shared-occurrence",
    }, fixture, planning);
    const compared = compareStory(first, second);
    expect(compared.method).toBe(pair.expected);
    expect(compared.semantic_similarity).toBeNull();
  }
  const a = article(fixture.candidates[0]!, fixture, planning);
  const controls = { enabled: planning.config.curate.source_reliability_penalty_enabled, reliability_floor: fixture.reliability_floor };
  let b = article({ ...fixture.candidates[2]!, cluster: "shared-occurrence" }, fixture, planning);
  b = { ...b, evidence: { ...b.evidence, publisher: null } };
  expect(compareStory(a, b).matches).toBeNull();
  expect(groupCarriers([a, b], controls).representatives).toHaveLength(2);
  b = { ...b, evidence: { ...b.evidence, publisher: { value: "One News", origin: "recorded" } } };
  expect(groupCarriers([a, b], controls).representatives).toHaveLength(2);
  b = { ...b, evidence: { ...b.evidence, publisher: { value: "Two News", origin: "recorded" } } };
  const grouped = groupCarriers([a, b], controls);
  expect(grouped.groups[0]!.outlets).toEqual(["One News", "Two News"]);
  expect(grouped.suppressed[0]!.representative.candidate.candidate_id).toBe(a.candidate.candidate_id);
  expect(grouped.suppressed[0]!.reason).toBe("REPLACED_BY_CARRIER");
});

test("all-pairs figure veto prevents A-B-C chaining despite a shared recorded cluster", async () => {
  const { fixture, planning } = await inputs();
  const specs = [12.9, 13, 13.1].map((number, i) => ({
    ...fixture.candidates[0]!, source: `outlet-${i}`, ordinal: 0, name: `carrier-${i}`,
    title: `Purchase ${number} billion`, publisher: `News ${i}`,
  }));
  const [a, b, c] = specs.map(spec => article(spec, fixture, planning));
  expect(compareStory(a!, b!).matches).toBe(true);
  expect(compareStory(b!, c!).matches).toBe(true);
  expect(compareStory(a!, c!).matches).toBe(false);
  const result = groupCarriers([a!, b!, c!], {
    enabled: planning.config.curate.source_reliability_penalty_enabled, reliability_floor: fixture.reliability_floor,
  });
  expect(result.groups.map(group => group.members.length).sort()).toEqual([1, 2]);
  for (const group of result.groups) {
    for (const left of group.members) for (const right of group.members) {
      if (left !== right) expect(compareStory(left, right).matches).toBe(true);
    }
  }
});

test("unknown timing stays unknown; first-seen keeps its own basis and timestamp", async () => {
  const { fixture, planning } = await inputs();
  const original = article(fixture.candidates[0]!, fixture, planning);
  const firstSeenAt = "2026-10-20T11:00:00Z";
  const ageHours = (Date.parse(fixture.observed_at) - Date.parse(firstSeenAt)) / 3_600_000;
  const policy = resolvePolicy(planning, original.candidate.vertical);
  for (const timing of ["first_seen", "unknown"] as const) {
    const changed: PortfolioArticle = {
      ...original,
      freshness: timing === "first_seen" ? {
        ...original.freshness, timing_source: timing, timing_at: firstSeenAt, age_hours: ageHours,
        recency_bonus: policy.triage.recency_weight * 0.5 ** (Math.max(0, ageHours) / policy.triage.recency_half_life_hours),
      } : { timing_at: null, timing_source: timing, age_hours: null, recency_bonus: 0 },
    };
    const result = curateArticles({ articles: [changed], planning, observed_at: fixture.observed_at, opportunity: noOpportunity, reliability_floor: fixture.reliability_floor });
    expect(result.assessments[0]!.timing_basis).toBe(timing === "first_seen" ? "first_seen" : "unavailable");
    expect(result.assessments[0]!.timing_at).toBe(timing === "first_seen" ? firstSeenAt : null);
    expect(result.quality[0]!.article.timing.timing_source).toBe(timing);
  }
});

test("admitted future timing preserves its signed observation and floors only the recency age", async () => {
  const { fixture, planning } = await inputs();
  const future = article({ ...fixture.candidates[0]!, published_at: "2026-10-21T13:00:00Z" }, fixture, planning);
  const result = curateArticles({ articles: [future], planning, observed_at: fixture.observed_at, opportunity: noOpportunity, reliability_floor: fixture.reliability_floor });
  expect(result.quality[0]!.article.timing.age_hours).toBe(-1);
  expect(result.quality[0]!.components.recency).toBe(1);
  expect(result.assessments[0]!.age_hours).toBe(-1);
  expect(result.assessments[0]!.timing_at).toBe("2026-10-21T13:00:00Z");
});

test("operational history, length, byline and kind never become model verdicts or a quality product", async () => {
  const { fixture, planning } = await inputs();
  planning.config.curate.source_authority_weight = 2;
  const original = article(fixture.candidates[0]!, fixture, planning);
  const changed: PortfolioArticle = {
    ...structuredClone(original),
    evidence: { ...original.evidence, operational: { success_fraction: 1, attempted: 100, window_days: 30 } },
    candidate: { ...original.candidate, word_count: 600, author: "Recorded Writer" },
  };
  const a = curateArticles({ articles: [original], planning, observed_at: fixture.observed_at, opportunity: noOpportunity, reliability_floor: fixture.reliability_floor });
  const b = curateArticles({ articles: [changed], planning, observed_at: fixture.observed_at, opportunity: noOpportunity, reliability_floor: fixture.reliability_floor });
  expect(a.rows[0]!.ratings.base_article_score).toBe(3);
  expect(b.rows[0]!.ratings.base_article_score).toBe(3);
  expect(a.rows[0]!.ratings.source_reliability).toBeNull();
  expect(b.rows[0]!.ratings.source_reliability).toBeNull();
  expect(a.rows[0]!.ratings.marginal_score).toBe(3);
  expect(b.rows[0]!.ratings.marginal_score).toBe(3);
  expect(b.quality[0]!.components).toEqual({ recency: 1, authority: 2 });
  expect(b.assessments[0]!.informative_verdict).toBeNull();
  expect(b.assessments[0]!.suitability_verdict).toBeNull();
  const operationalEvidence = {
    status: "qualified" as const, state_status: "current" as const, state_revision: 1,
    window_days: 7, window_start: "2026-10-14", window_end: "2026-10-20",
    total_requests: 20, wasted_requests: 10, observed_attempted_opportunities: 25,
    observed_measured_opportunities: 20, coverage: 0.8, operational_penalty: 1 / 6,
  };
  const qualified = curateArticles({
    articles: [{ ...original, evidence: { ...original.evidence, source_operational: operationalEvidence } }],
    planning, observed_at: fixture.observed_at, opportunity: noOpportunity,
    reliability_floor: fixture.reliability_floor,
  });
  expect(qualified.rows[0]!.ratings).toMatchObject({
    base_article_score: 3, marginal_score: 3 - (2 / 6),
    source_reliability: null, source_operational: operationalEvidence,
  });
  const unqualified = curateArticles({
    articles: [{
      ...original, evidence: { ...original.evidence, source_operational: {
        ...operationalEvidence, status: "insufficient_support", operational_penalty: null,
      } },
    }],
    planning, observed_at: fixture.observed_at, opportunity: noOpportunity,
    reliability_floor: fixture.reliability_floor,
  });
  expect(unqualified.rows[0]!.ratings).toMatchObject({
    marginal_score: 3, source_reliability: null,
    source_operational: { status: "insufficient_support", operational_penalty: null },
  });
  for (const recorded of fixture.reliability_cases) {
    const configured = loadPlanningConfig({
      ...planning.config, curate: {
        ...planning.config.curate, article_limit: 1, source_authority_weight: 1,
        source_reliability_penalty_enabled: recorded.enabled,
      },
    }, planning.taxonomy);
    const articles = [fixture.candidates[0]!, fixture.candidates[2]!].map(spec => {
      const offered = article({ ...spec, published_at: fixture.observed_at }, fixture, configured);
      return { ...offered, evidence: { ...offered.evidence,
        operational: spec.source === "alpha" ? recorded.alpha : recorded.gamma,
      } };
    });
    const before = structuredClone(articles);
    const withoutRssEvidence = articles.map(offered => ({
      ...offered, evidence: { ...offered.evidence, operational: null },
    }));
    const baseline = curateArticles({
      articles: withoutRssEvidence, planning: configured, observed_at: fixture.observed_at,
      opportunity: noOpportunity, reliability_floor: recorded.floor,
    });
    const result = curateArticles({
      articles, planning: configured, observed_at: fixture.observed_at,
      opportunity: noOpportunity, reliability_floor: recorded.floor,
    });
    expect(result.rows[0]!.source_id, recorded.name).toBe(baseline.rows[0]!.source_id);
    expect(articles, recorded.name).toEqual(before);
    for (const entry of result.trace[0]!.evaluated) {
      expect(entry.scores.base_article_score, recorded.name).toBe(2);
      expect(entry.scores.marginal_score, recorded.name).toBe(2);
      expect(entry.scores.source_reliability, recorded.name).toBeNull();
      expect(entry.scores.source_operational, recorded.name).toBeNull();
    }
    expect(result.assessments.every(row => row.score_evidence !== null
      && row.score_evidence.source_reliability === null
      && row.score_evidence.source_operational === null), recorded.name).toBe(true);
    expect(result.rows[0]!.ratings).toEqual(result.choices[0]!.scores);
    expect(result.quality.map(row => row.components), recorded.name).toEqual([
      { recency: 1, authority: 1 }, { recency: 1, authority: 1 },
    ]);
  }
  const sibling = article(fixture.candidates[1]!, fixture, planning);
  expect(() => curateArticles({
    articles: [original, { ...sibling, evidence: { ...sibling.evidence, operational: null } }],
    planning, observed_at: fixture.observed_at, opportunity: noOpportunity, reliability_floor: fixture.reliability_floor,
  })).toThrow("inconsistent per-source evidence");
});

test("stable ties, null article limit and source authority patches use the actual stage", async () => {
  const { fixture, planning } = await inputs({ article_limit: null, base_source_allowance: 40 });
  planning.config.curate.soft_caps.max_event_cluster_items = 40;
  const specs = Array.from({ length: 40 }, (_, index) => ({
    ...fixture.candidates[0]!, name: `tie-${index}`, ordinal: index,
  }));
  const forward = run(planning, fixture, specs);
  const reverse = run(planning, fixture, [...specs].reverse());
  expect(forward.rows).toHaveLength(40);
  expect(reverse.rows).toEqual(forward.rows);
  expect(forward.rows.map(row => row.candidate_id)).toEqual(forward.rows.map(row => row.candidate_id).sort());
  planning.config.vertical_overrides.ai = { curate: { source_authority_weight: 2 } };
  const authority = run(planning, fixture);
  expect(authority.rows.map(row => row.ratings.base_article_score)).toEqual([3, 2.5, 0.25]);
  expect(authority.rows[0]!.policy.source_authority_weight).toBe(2);
  expect(authority.rows[2]!.policy.source_authority_weight).toBe(0);
});

test("run freshness overrides remain separate from the unchanged harvested policy", async () => {
  const { fixture, planning } = await inputs();
  const original = article(fixture.candidates[0]!, fixture, planning);
  const changed = {
    ...original,
    policy: resolvePolicy(planning, original.candidate.vertical, { freshness_hours: 6 }),
  };
  const result = curateArticles({ articles: [changed], planning, observed_at: fixture.observed_at, opportunity: noOpportunity, reliability_floor: fixture.reliability_floor });
  expect(result.selected[0]!.candidate.policy.max_age_hours).toBe(72);
  expect(result.rows[0]!.policy.max_age_hours).toBe(6);
});

test("real screening results compose into exact curation without losing harvested content", async () => {
  const { screenArticleCandidates } = await import("../src/screen-article-candidates/triage-gates");
  const { fixture, planning } = await inputs();
  const root = await mkdtemp(join(tmpdir(), "screened-portfolio-"));
  try {
    const originals = fixture.candidates.map(spec => article(spec, fixture, planning));
    const short = article({ ...fixture.candidates[0]!, name: "short", ordinal: 99 }, fixture, planning).candidate;
    short.word_count = 3;
    short.article_text = "Too little substance";
    const context = await persistenceContext(root, fixture);
    const screened = await screenArticleCandidates({
      candidates: [...originals.map(original => original.candidate), short], observations: {},
      seen: { availability: "unavailable" }, planning,
      clock_config: { collect: { max_future_hours: 0 } },
      run: { now: fixture.observed_at, run_id: fixture.run_id, correlation_id: fixture.correlation_id, overrides: {} },
    }, {
      outputRoot: context.outputRoot,
      writerContext: { ...context.writerContext, task_name: "screen-article-candidates" },
      registryEntry: context.registrations.rejections, ledgerSettings: context.ledgerSettings,
    });
    expect(screened.sealing.status).toBe("written");
    expect(screened.rejections.map(row => row.drop_reason)).toEqual(["STUB_CONTENT"]);
    const result = curateArticles({
      articles: screened.admitted.map(admitted => ({
        ...admitted,
        evidence: originals.find(original => original.candidate.candidate_id === admitted.candidate.candidate_id)!.evidence,
      })),
      planning, opportunity: noOpportunity, observed_at: fixture.observed_at, reliability_floor: fixture.reliability_floor,
    });
    expect(names(result)).toEqual(fixture.expected.baseline);
    expect(result.rows.map(row => row.editorial_rank)).toEqual([1, 2]);
    expect(result.selected.map(value => value.candidate)).toEqual(originals.slice(0, 2).map(value => value.candidate));
    expect(result.rows.length + result.rejections.length + screened.rejections.length).toBe(4);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}, 30_000);

test("real screening and curation retain independent stage dates and policies in dispatch", async () => {
  const { screenArticleCandidates } = await import("../src/screen-article-candidates/triage-gates");
  const { fixture, planning } = await inputs();
  const root = await mkdtemp(join(tmpdir(), "portfolio-dispatch-contract-"));
  try {
    const original = article(fixture.candidates[0]!, fixture, planning);
    const context = await persistenceContext(root, fixture);
    for (const scenario of [
      { name: "baseline", observedAt: fixture.observed_at, overrides: {} },
      { name: "run override", observedAt: fixture.observed_at, overrides: { freshness_hours: 6 } },
      { name: "UTC midnight crossing", observedAt: "2026-10-22T00:00:00Z", overrides: {} },
    ] as const) {
      const screened = await screenArticleCandidates({
        candidates: [original.candidate], observations: {},
        seen: { availability: "unavailable" }, planning,
        clock_config: { collect: { max_future_hours: 0 } },
        run: {
          now: scenario.observedAt, run_id: fixture.run_id,
          correlation_id: fixture.correlation_id, overrides: scenario.overrides,
        },
      }, {
        outputRoot: context.outputRoot,
        writerContext: { ...context.writerContext, task_name: "screen-article-candidates" },
        registryEntry: context.registrations.rejections, ledgerSettings: context.ledgerSettings,
      });
      expect(screened.admitted, scenario.name).toHaveLength(1);
      const result = curateArticles({
        articles: screened.admitted.map(admitted => ({ ...admitted, evidence: original.evidence })),
        planning, opportunity: noOpportunity, observed_at: scenario.observedAt, reliability_floor: fixture.reliability_floor,
      });
      const content = result.selected[0]!.candidate;
      const selection = result.rows[0]!;
      expect(content, scenario.name).toEqual(original.candidate);
      expect(content.date).toBe(content.fetched_at.slice(0, 10));
      expect(selection.date).toBe(scenario.observedAt.slice(0, 10));
      expect(selection.policy.max_age_hours).toBe(scenario.overrides.freshness_hours ?? planning.config.triage.max_age_hours);
      const dispatch = FeedIngestDispatchSchema.safeParse({
        content, selection,
        partition: { strategy: "none", worker_assignment: 0, dispatch_count: 1 },
      });
      expect(dispatch.success, scenario.name).toBe(true);
      if (!dispatch.success) throw new Error("Expected independent stage context to form a valid dispatch");
      expect(dispatch.data.content.date).toBe(original.candidate.date);
      expect(dispatch.data.content.policy.max_age_hours).toBe(original.candidate.policy.max_age_hours);
      expect(dispatch.data.selection.date).toBe(scenario.observedAt.slice(0, 10));
      expect(dispatch.data.selection.policy.max_age_hours)
        .toBe(scenario.overrides.freshness_hours ?? planning.config.triage.max_age_hours);
    }
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}, 30_000);

function normalize(value: unknown): unknown {
  if (typeof value === "bigint") return Number(value);
  if (Array.isArray(value)) return value.map(normalize);
  if (value !== null && typeof value === "object") {
    if ("toJSON" in value && typeof value.toJSON === "function") return normalize(value.toJSON());
    return Object.fromEntries(Object.entries(value).map(([key, entry]) => [key, normalize(entry)]));
  }
  return value;
}

async function persistenceContext(root: string, fixture: Fixture): Promise<CurationPersistence> {
  const registered = await Bun.file(new URL("../../../config/ledgers.json", import.meta.url)).json();
  const family = registered.families.find((entry: { name: string }) => entry.name === "feed-ingest-plan");
  const registration = (name: string) => ({
    ...family.ledgers.find((entry: { name: string }) => entry.name === name),
    family: family.name, lifecycle_status: family.lifecycle_status,
  });
  return {
    outputRoot: join(root, "state"),
    writerContext: WriterIdentitySchema.parse({
      run_id: fixture.run_id, attempt: 1, job: null, pipeline_name: "feed-ingest-plan",
      task_name: "curate-article-portfolio", shard: 0, producer: "portfolio-fixture", git_sha: "a".repeat(40),
    }),
    ledgerSettings: { format: "parquet", compression_raw: "snappy", compression_compact: "zstd" },
    registrations: { selections: registration("editorial-selections"), rejections: registration("rejections") },
    date: fixture.observed_at.slice(0, 10),
  };
}

test("actual unsharded selection and rejection Parquet read back exact rows and writer identities", async () => {
  const { fixture, planning } = await inputs();
  const result = run(planning, fixture);
  const root = await mkdtemp(join(tmpdir(), "portfolio-parquet-"));
  try {
    const persisted = await persistPortfolio(result, await persistenceContext(root, fixture));
    await initializeParquet();
    for (const [ledger, stored, expectedRows] of [
      ["editorial-selections", persisted.selections, result.rows],
      ["rejections", persisted.rejections, result.rejections],
    ] as const) {
      expect(stored.status).toBe("written");
      expect(stored.files).toHaveLength(1);
      const file = stored.files[0]!;
      expect(file.path).toContain(`raw/feed-ingest-plan/${ledger}/2026/10/21/`);
      const bytes = new Uint8Array(await readFile(resolve(root, "state", file.path)));
      const wasm = readParquet(bytes);
      const table = tableFromIPC(wasm.intoIPCStream());
      const actual = table.toArray().map(row => normalize(row) as Record<string, unknown>);
      expect(actual).toHaveLength(expectedRows.length);
      for (let i = 0; i < expectedRows.length; i++) {
        expect(actual[i]).toMatchObject(expectedRows[i]!);
        expect(actual[i]).toMatchObject({
          run_id: fixture.run_id, attempt: 1, shard: 0, ledger,
          pipeline_name: "feed-ingest-plan", task_name: "curate-article-portfolio",
        });
        expect(actual[i]!.unit_id).toBe(file.unit_id);
      }
      const metadata = readMetadata(bytes);
      const fileMetadata = metadata.fileMetadata();
      const footer = new Map([...fileMetadata.keyValueMetadata()].map(([key, value]) => [String(key), String(value)]));
      expect(footer.get("schema_version")).toBe(expectedRows[0]!.version);
      expect(footer.get("file_id")).toBe(file.file_id);
      expect(footer.get("content_sha256")).toBe(file.content_sha256);
      fileMetadata.free();
      metadata.free();
      if (ledger === "editorial-selections") {
        expect(file.unit_id).toBe(fixture.recorded_format.selection_unit_id);
        expect(actual).toHaveLength(fixture.recorded_format.selection_count);
        for (const column of fixture.recorded_format.selection_columns) expect(table.schema.fields.map(field => field.name)).toContain(column);
        for (const [column, type] of Object.entries(fixture.recorded_format.selection_scalar_types)) {
          expect(table.schema.fields.find(field => field.name === column)!.type.toString()).toBe(type);
        }
        expect(actual.map(row => row.editorial_rank)).toEqual([1, 2]);
      } else {
        expect(file.unit_id).toBe(fixture.recorded_format.rejection_unit_id);
        expect(actual).toHaveLength(fixture.recorded_format.rejection_count);
        expect(actual[0]!.drop_reason).toBe(fixture.recorded_format.rejection_reason);
      }
    }
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}, 30_000);

test("empty writes have no invented files and real failures cannot report completion", async () => {
  const { fixture, planning } = await inputs();
  const root = await mkdtemp(join(tmpdir(), "portfolio-empty-failure-"));
  try {
    const context = await persistenceContext(root, fixture);
    const empty = run(planning, fixture, []);
    expect(await persistPortfolio(empty, context)).toEqual({
      selections: { status: "empty", files: [] }, rejections: { status: "empty", files: [] },
    });
    await writeFile(join(root, "state"), "real filesystem obstruction");
    await expect(persistPortfolio(run(planning, fixture), context)).rejects.toThrow();
    await expect(persistPortfolio(run(planning, fixture), {
      ...context, writerContext: { ...context.writerContext, shard: 1 },
    })).rejects.toThrow("Unsharded");
    await expect(persistPortfolio(run(planning, fixture), {
      ...context, ledgerSettings: { ...context.ledgerSettings, format: "json" },
    })).rejects.toThrow("Parquet");
    const paused = {
      ...context,
      registrations: { ...context.registrations, rejections: { ...context.registrations.rejections, lifecycle_status: "paused" as const } },
    };
    await expect(persistPortfolio(run(planning, fixture), paused)).rejects.toThrow("unavailable");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}, 30_000);
