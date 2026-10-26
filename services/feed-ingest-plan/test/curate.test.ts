/** Do numeric portfolio controls choose one content population with compact, truthful explanations? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  FeedHealthStateRowSchema, FeedIngestCandidateSchema, ParsedFeedBatchSchema, SelectedArticleRowContract,
  SelectedArticlesArtifactSchema, deriveCandidateId, deriveUrlKey, selectedArticleMetadata,
} from "@idhazh/common-contracts";
import type { FeedIngestConfig, PlannerArticleEvidence } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import { tableFromIPC } from "apache-arrow";
import initializeParquet, { readParquet } from "parquet-wasm/esm";
import { loadPlanningConfig, resolvePolicy } from "../src/config/resolve-policy";
import { curateArticles } from "../src/curate-article-portfolio/editorial-selection";
import { screenArticleCandidates } from "../src/screen-article-candidates/triage-gates";
import type { ScreenedCandidate } from "../src/screen-article-candidates/triage-gates";
import { calculateFreshness } from "../src/screen-article-candidates/freshness-decay";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { resolveRunContext } from "../src/resolve-run-context";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import type { SourceHistoryEvidence } from "../src/read-ledger-history/read-feed-history";
import type { PublisherPublicationHistory } from "../src/curate-article-portfolio/publisher-exposure";
import { partitionArticles } from "../src/partition-article-shards/shard-packer";
import { selectArticles } from "../src/select-articles";
import { endpointKey } from "../src/read-ledger-history/read-feed-history";
import { plannerRecordings } from "../../../packages/ledger-file-writer/test/planner-recordings";
import { source } from "./harvest-recordings";

type CandidateCase = {
  name: string; source: string; ordinal: number; kind: string;
  domain: string; publisher_id: string | null; title: string; published_at: string;
};
type OperationalEvidence = { success_fraction: number; attempted: number; window_days: number };
type Fixture = {
  observed_at: string; run_id: string; reliability_floor: number; candidates: CandidateCase[];
  publisher_exposure_cases: {
    name: string; availability: "available" | "unavailable"; published: number; coefficient: number; first_penalty: number;
  }[];
  reliability_cases: {
    name: string; enabled: boolean; floor: number; alpha: OperationalEvidence | null; gamma: OperationalEvidence | null;
    winner: string; alpha_penalty: number | null; gamma_penalty: number | null;
  }[];
  expected: { baseline: string[]; base_scores: Record<string, number>; selected_ranks: number[] };
};
type Knobs = FeedIngestConfig["curate"];
async function inputs(patch: Partial<Knobs> = {}) {
  const [fixture, loaded] = await Promise.all([
    Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/portfolio-cases.json", import.meta.url)).json() as Promise<Fixture>,
    loadPlanInputs(fileURLToPath(new URL("../../../", import.meta.url))),
  ]);
  const planning = loadPlanningConfig({
    ...loaded.harvest.config,
    triage: { ...loaded.harvest.config.triage, max_age_hours: 72, recency_half_life_hours: 18, recency_weight: 1 },
    curate: {
      ...loaded.harvest.config.curate, article_limit: 2, base_source_allowance: 3, bonus_unique_evidence: 0,
      source_authority_weight: 0, exploration_slot_share: 0,
      soft_caps: {
        ...loaded.harvest.config.curate.soft_caps, max_source_share: 1, max_parent_domain_share: 1, min_distinct_sources: 1,
      },
      mmr_weights: { lambda_source: 0, lambda_source_kind: 0, lambda_domain: 0 }, ...patch,
    },
  });
  const context = resolveRunContext(loaded.settings, "a".repeat(40), new Date(fixture.observed_at),
    fixture.run_id.slice(11), "c6fc0434-baaa-4b34-937a-fe2412f3a720");
  return { fixture, planning, context, inputs: { ...loaded, harvest: { ...loaded.harvest, ...planning } } };
}
type Setup = Awaited<ReturnType<typeof inputs>>;
function article(spec: CandidateCase, setup: Setup): ScreenedCandidate {
  const { fixture, planning, context } = setup;
  const url = `https://${spec.domain}/${spec.name}`;
  const candidate = FeedIngestCandidateSchema.parse({
    date: context.date, run_id: context.run_id, correlation_id: context.correlation_id,
    candidate_id: deriveCandidateId(context.run_id, spec.source, spec.ordinal), entry_ordinal: spec.ordinal,
    source_id: spec.source,
    source: {
      source_id: spec.source, publisher_id: spec.publisher_id, feed_url: `https://${spec.domain}/feed`,
      title: `${spec.source} configured feed`, kind: spec.kind,
      tier: 1, form: "article", status: "active", weight: 1, applied_tier_weight: 1,
    },
    canonical_url: url, url_key: deriveUrlKey(url), title: spec.title, categories: ["feed-category"],
    article_text: "Recorded factual report. ".repeat(100).trim(), word_count: 300,
    author: null, published_at: spec.published_at, fetched_at: fixture.observed_at,
  });
  const policy = resolvePolicy(planning);
  return {
    candidate, policy, observation: null, seen_availability: "unavailable",
    freshness: calculateFreshness(candidate, undefined, fixture.observed_at, 6, policy),
  };
}
function selectionInput(setup: Setup, articles: ScreenedCandidate[], options: {
  health?: ReadonlyMap<string, SourceHistoryEvidence>; publications?: PublisherPublicationHistory;
  evidence?: Record<string, PlannerArticleEvidence>;
} = {}) {
  return {
    articles, inputs: setup.inputs, health: options.health ?? new Map<string, SourceHistoryEvidence>(),
    publications: options.publications ?? { day: setup.context.date, availability: "unavailable" as const, counts: new Map<string, number>() },
    batch: ParsedFeedBatchSchema.parse({
      batch_id: randomUUID(), config_sha256: "b".repeat(64), context: setup.context, request: {},
      candidates: articles.map(value => value.candidate),
      observations: Object.fromEntries(articles.map(({ candidate }) => [candidate.candidate_id, {
        candidate_id: candidate.candidate_id, http_status: 200, paywall: false, robots: "allowed",
        fetch_failure: null, extraction: "success", paywall_evidence: "none", observed_at: setup.context.now,
      }])),
      seen: { availability: "unavailable" },
      evidence: options.evidence ?? Object.fromEntries(articles.map(({ candidate }) => [candidate.candidate_id, {
        parent_domain: { value: new URL(candidate.canonical_url).hostname, origin: "recorded-parent-domain" },
        primary_evidence: null, estimated_work: candidate.word_count,
      }])),
      history_rows: [], history_days: [], work_rows: [], exclusions: [],
    }),
  };
}
function run(setup: Setup, specs = setup.fixture.candidates, options: Parameters<typeof selectionInput>[2] = {}) {
  return curateArticles(selectionInput(setup, specs.map(spec => article(spec, setup)), options));
}
function names(result: ReturnType<typeof run>) { return result.articles.map(row => new URL(row.canonical_url).pathname.slice(1)); }
function adjustment(row: ReturnType<typeof run>["articles"][number], term: string) {
  return row.ratings.adjustments.find(value => value.term === term)?.value;
}

test("fixed real stage selects exact identities, ranks, components and preserves content", async () => {
  const setup = await inputs();
  const supplied = selectionInput(setup, setup.fixture.candidates.map(spec => article(spec, setup)));
  const before = structuredClone(supplied.batch);
  const result = curateArticles(supplied);
  expect(names(result)).toEqual(setup.fixture.expected.baseline);
  expect(result.articles.map(row => row.editorial_rank)).toEqual(setup.fixture.expected.selected_ranks);
  for (const row of result.articles) {
    expect(row.ratings.base_article_score).toBe(setup.fixture.expected.base_scores[new URL(row.canonical_url).pathname.slice(1)]!);
    expect(row.ratings.marginal_score).toBe(row.ratings.base_article_score);
    expect(row.ratings.feed_authority_score).toBe(0);
    expect(row.article_text).toBe(supplied.articles.find(value => value.candidate.url_key === row.url_key)!.candidate.article_text);
    expect(row).not.toHaveProperty("labels");
    expect(row).not.toHaveProperty("policy");
  }
  expect(result.losses.map(loss => loss.reason)).toEqual(["PORTFOLIO_CUTOFF"]);
  expect(result.articles.length + result.losses.length).toBe(supplied.articles.length);
  expect(supplied.batch).toEqual(before);
});

test("every retained saturation coefficient substitutes independently at each actual choice", async () => {
  for (const term of ["source_kind", "domain"] as const) {
    const setup = await inputs();
    setup.planning.config.curate.mmr_weights[`lambda_${term}`] = 1;
    expect(names(run(setup))).toEqual(["first", "alternative"]);
    setup.planning.config.curate.article_limit = 3;
    const final = run(setup).articles.find(row => new URL(row.canonical_url).pathname === "/middle")!;
    expect(adjustment(final, term)).toBe(-0.5);
    expect(final.ratings.marginal_score).toBe(0);
    setup.planning.config.curate.mmr_weights[`lambda_${term}`] = 0;
    expect(names(run(setup)).slice(0, 2)).toEqual(["first", "middle"]);
  }
  const setup = await inputs();
  for (const recorded of setup.fixture.publisher_exposure_cases) {
    setup.planning.config.curate.mmr_weights.lambda_source = recorded.coefficient;
    const result = run(setup, setup.fixture.candidates, {
      publications: { day: setup.context.date, availability: recorded.availability, counts: new Map([["one-news", recorded.published]]) },
    });
    const first = result.articles.find(row => new URL(row.canonical_url).pathname === "/first")!;
    const term = recorded.availability === "available" ? "publisher_exposure" : "publisher_exposure_current_run";
    expect(adjustment(first, term), recorded.name).toBe(recorded.first_penalty === 0 ? 0 : -recorded.first_penalty);
    if (recorded.name === "unequal known publication") expect(names(result)[0]).toBe("alternative");
    if (recorded.availability === "unavailable") {
      const middle = result.articles.find(row => new URL(row.canonical_url).pathname === "/middle")!;
      expect(adjustment(middle, term)).toBe(-recorded.coefficient / 2);
    }
  }
});

test("unavailable numeric evidence stays null while a measured zero stays zero", async () => {
  const setup = await inputs();
  const offered = article(setup.fixture.candidates[0]!, setup);
  const absent = curateArticles(selectionInput(setup, [offered], { evidence: {} })).articles[0]!;
  expect(adjustment(absent, "domain")).toBeNull();
  expect(adjustment(absent, "feed_reliability")).toBeNull();
  const known = run(setup).articles[0]!;
  expect(adjustment(known, "domain") === 0).toBe(true);
  const unknownPublisher = run(setup, [{ ...setup.fixture.candidates[0]!, publisher_id: null }]).articles[0]!;
  expect(adjustment(unknownPublisher, "publisher_exposure_current_run")).toBeNull();
  expect(known.ratings.base_article_score).toBe(absent.ratings.base_article_score);
  expect(known.ratings.marginal_score).toBe(absent.ratings.marginal_score);
});

test("kind relabel changes no allowance, viability, or authority; zero disables its influence", async () => {
  const setup = await inputs();
  const baseline = run(setup);
  const relabelled = run(setup, setup.fixture.candidates.map(spec => ({ ...spec, kind: "new-configured-kind" })));
  expect(relabelled.articles).toEqual(baseline.articles);
  expect(relabelled.losses.map(loss => loss.reason)).toEqual(baseline.losses.map(loss => loss.reason));
  expect(relabelled.articles.every(row => row.feed_allowance === 3)).toBe(true);
});

test("flooding duplicates cannot buy allowance or displace another qualifying source", async () => {
  const setup = await inputs({ article_limit: null, base_source_allowance: 1 });
  const articles = setup.fixture.candidates.map(spec => article(spec, setup));
  const baseline = curateArticles(selectionInput(setup, articles));
  const original = articles[0]!;
  const copies = Array.from({ length: 20 }, (_, index) => ({
    ...structuredClone(original), candidate: {
      ...original.candidate, candidate_id: deriveCandidateId(setup.context.run_id, "alpha", index + 10), entry_ordinal: index + 10,
    },
  }));
  const flooded = curateArticles(selectionInput(setup, [...articles, ...copies]));
  expect(flooded.articles).toEqual(baseline.articles);
  expect(flooded.articles.map(row => row.feed_id).sort()).toEqual(["alpha", "gamma"]);
  expect(flooded.losses.filter(loss => loss.reason === "DUPLICATE_URL")).toHaveLength(20);
  expect(flooded.losses.filter(loss => loss.reason === "SOURCE_QUOTA_EXCEEDED")).toHaveLength(1);
  expect(flooded.articles.every(row => row.feed_allowance === 1)).toBe(true);
});

test("the explicit unique-evidence bonus requires an unshared witness and is granted at most once", async () => {
  const setup = await inputs({ article_limit: null, base_source_allowance: 1, bonus_unique_evidence: 1 });
  const specs = Array.from({ length: 5 }, (_, ordinal) => ({ ...setup.fixture.candidates[0]!, name: `alpha-${ordinal}`, ordinal }));
  const articles = specs.map(spec => article(spec, setup));
  const supplied = selectionInput(setup, articles);
  for (const [index, value] of articles.entries()) supplied.batch.evidence[value.candidate.candidate_id]!.primary_evidence = {
    ids: [`record-${index}`], origin: "recorded-primary-document",
  };
  const bonus = curateArticles(supplied);
  expect(bonus.articles).toHaveLength(2);
  expect(bonus.articles.every(row => row.feed_allowance === 2 && JSON.stringify(row.allowance_reasons) === '["unique_evidence"]')).toBe(true);
  expect(run(setup, specs).articles).toHaveLength(1);
  const sibling = article(setup.fixture.candidates[2]!, setup);
  const shared = selectionInput(setup, [...articles, sibling]);
  for (const evidence of Object.values(shared.batch.evidence)) evidence.primary_evidence = { ids: ["same-document"], origin: "recorded-primary-document" };
  const noBonus = curateArticles(shared);
  expect(noBonus.articles).toHaveLength(2);
  expect(noBonus.articles.every(row => row.feed_allowance === 1 && row.allowance_reasons.length === 0)).toBe(true);
  setup.planning.config.curate.bonus_unique_evidence = 0;
  for (const value of supplied.articles) value.policy = resolvePolicy(setup.planning);
  expect(curateArticles(supplied).articles).toHaveLength(1);
});

test("soft caps relax only in configured order and parent-domain limits remain effective", async () => {
  const setup = await inputs({ article_limit: null });
  setup.planning.config.curate.soft_caps = {
    max_source_share: 0.2, max_parent_domain_share: 1, min_distinct_sources: 3,
    relaxation_order: ["distinct_sources", "source_share"],
  };
  const result = run(setup);
  expect(names(result)).toEqual(["first", "alternative", "middle"]);
  expect(result.articles[2]!.cap_relaxations).toEqual(["distinct_sources", "source_share"]);
  setup.planning.config.curate.soft_caps.max_parent_domain_share = 0.2;
  expect(run(setup).articles).toHaveLength(2);
  setup.planning.config.curate.soft_caps.max_parent_domain_share = 1;
  setup.planning.config.curate.soft_caps.relaxation_order = ["source_share", "distinct_sources"];
  expect(run(setup).articles[2]!.cap_relaxations).toEqual(["source_share", "distinct_sources"]);
});

test("exploration reserves configured slots only for viable unseen sources", async () => {
  const setup = await inputs({ exploration_slot_share: 0.5 });
  expect(names(run(setup))).toEqual(["first", "alternative"]);
  expect(run(setup).articles.map(row => row.exploration_slot)).toEqual([false, true]);
  setup.planning.config.curate.exploration_slot_share = 1;
  expect(names(run(setup))).toEqual(["first", "alternative"]);
  setup.planning.config.curate.exploration_slot_share = 0;
  expect(names(run(setup))).toEqual(["first", "middle"]);
});

test("unknown timing stays unknown; first-seen keeps its own basis and timestamp", async () => {
  const setup = await inputs();
  const original = article(setup.fixture.candidates[0]!, setup);
  original.candidate.published_at = null;
  const firstSeenAt = "2026-10-20T11:00:00Z";
  for (const seen of [undefined, { url_key: original.candidate.url_key, first_seen_at: firstSeenAt, date: "2026-10-20" }]) {
    const offered = { ...original, freshness: calculateFreshness(original.candidate, seen, setup.fixture.observed_at, 6, original.policy) };
    const row = curateArticles(selectionInput(setup, [offered])).articles[0]!;
    expect(row.timing_basis).toBe(seen === undefined ? "unavailable" : "first_seen");
    expect(row.timing_at).toBe(seen === undefined ? null : firstSeenAt);
    expect(row.age_hours).toBe(seen === undefined ? null : 25);
    expect(row.ratings.recency_score).toBe(seen === undefined ? 0 : 0.5 ** (25 / 18));
  }
});

test("admitted future timing preserves its signed observation and floors only the recency age", async () => {
  const setup = await inputs();
  const row = run(setup, [{ ...setup.fixture.candidates[0]!, published_at: "2026-10-21T13:00:00Z" }]).articles[0]!;
  expect(row.age_hours).toBe(-1);
  expect(row.ratings.recency_score).toBe(1);
  expect(row.timing_at).toBe("2026-10-21T13:00:00Z");
});

test("operational history, length, byline and kind never become model verdicts or a quality product", async () => {
  const setup = await inputs({ source_authority_weight: 2 });
  const original = article(setup.fixture.candidates[0]!, setup);
  const changed = { ...original, candidate: { ...original.candidate, word_count: 600, author: "Recorded Writer" } };
  const a = curateArticles(selectionInput(setup, [original])).articles[0]!;
  const b = curateArticles(selectionInput(setup, [changed])).articles[0]!;
  expect(a.ratings).toEqual(b.ratings);
  expect(b.ratings.base_article_score).toBe(3);
  expect(b).not.toHaveProperty("informative_verdict");
  expect(b).not.toHaveProperty("quality");
  for (const recorded of setup.fixture.reliability_cases) {
    const configured = await inputs({ article_limit: 1, source_authority_weight: 1, source_reliability_penalty_enabled: recorded.enabled });
    const health = new Map<string, SourceHistoryEvidence>();
    for (const [feed, evidence] of [["alpha", recorded.alpha], ["gamma", recorded.gamma]] as const) {
      health.set(feed, {
        lifecycle: "unknown", endpoint_key: "a".repeat(64), strikes: null, rested_runs: null,
        reliability: evidence === null ? null : {
          productive: evidence.attempted * evidence.success_fraction, attempted: evidence.attempted,
          success_fraction: evidence.success_fraction, from_day: "2026-10-15", through_day: "2026-10-21",
          production_factor: Math.max(recorded.floor, evidence.success_fraction), complete: false,
        },
      });
    }
    const specs = [configured.fixture.candidates[0]!, configured.fixture.candidates[2]!]
      .map(spec => ({ ...spec, published_at: configured.fixture.observed_at }));
    const winner = run(configured, specs, { health }).articles[0]!;
    expect(winner.feed_id, recorded.name).toBe(recorded.winner);
    for (const spec of specs) {
      const row = run(configured, [spec], { health }).articles[0]!;
      const penalty = spec.source === "alpha" ? recorded.alpha_penalty : recorded.gamma_penalty;
      expect(row.ratings.base_article_score, recorded.name).toBe(2);
      expect(row.ratings.marginal_score, recorded.name).toBe(2 - (penalty ?? 0));
      if (penalty === null) expect(adjustment(row, "feed_reliability"), recorded.name).toBeNull();
      else expect(adjustment(row, "feed_reliability"), recorded.name).toBeCloseTo(-penalty);
    }
  }
});

test("stable ties, null article limit and global source authority substitution use the actual stage", async () => {
  const setup = await inputs({ article_limit: null, base_source_allowance: 40 });
  const specs = Array.from({ length: 40 }, (_, ordinal) => ({ ...setup.fixture.candidates[0]!, name: `tie-${ordinal}`, ordinal }));
  const forward = run(setup, specs);
  expect(forward.articles).toHaveLength(40);
  expect(run(setup, [...specs].reverse()).articles).toEqual(forward.articles);
  const ordered = specs.map(spec => article(spec, setup).candidate).sort((a, b) => a.candidate_id.localeCompare(b.candidate_id));
  expect(forward.articles.map(row => row.url_key)).toEqual(ordered.map(row => row.url_key));
  setup.planning.config.curate.source_authority_weight = 2;
  expect(run(setup).articles.map(row => row.ratings.base_article_score)).toEqual([3, 2.5, 2.25]);
});

test("run freshness overrides remain separate from the unchanged harvested content", async () => {
  const setup = await inputs();
  const candidates = setup.fixture.candidates.map(spec => article(spec, setup).candidate);
  const before = structuredClone(candidates);
  const screened = await screenArticleCandidates({
    candidates, observations: {}, seen: { availability: "unavailable" }, planning: setup.planning,
    clock_config: { collect: { max_future_hours: 0 } },
    run: { now: setup.context.now, run_id: setup.context.run_id, correlation_id: setup.context.correlation_id, overrides: { freshness_hours: 6 } },
  });
  expect(screened.admitted.map(value => value.policy.triage.max_age_hours)).toEqual([6]);
  expect(screened.rejections.map(row => row.drop_reason)).toEqual(["STALE_MAX_AGE_EXCEEDED", "STALE_MAX_AGE_EXCEEDED"]);
  expect(curateArticles(selectionInput(setup, screened.admitted)).articles[0]!.article_text).toBe(candidates[0]!.article_text);
  expect(candidates).toEqual(before);
});

test("real screening results compose into exact curation without losing harvested content", async () => {
  const setup = await inputs();
  const candidates = setup.fixture.candidates.map(spec => article(spec, setup).candidate);
  const short = { ...article({ ...setup.fixture.candidates[0]!, name: "short", ordinal: 99 }, setup).candidate,
    word_count: 3, article_text: "Too little substance" };
  const screened = await screenArticleCandidates({
    candidates: [...candidates, short], observations: {}, seen: { availability: "unavailable" }, planning: setup.planning,
    clock_config: { collect: { max_future_hours: 0 } },
    run: { now: setup.context.now, run_id: setup.context.run_id, correlation_id: setup.context.correlation_id, overrides: {} },
  });
  expect(screened.rejections.map(row => row.drop_reason)).toEqual(["STUB_CONTENT"]);
  expect(screened).not.toHaveProperty("sealing");
  const result = curateArticles(selectionInput(setup, screened.admitted));
  expect(names(result)).toEqual(setup.fixture.expected.baseline);
  expect(result.articles.map(row => row.article_text)).toEqual(candidates.slice(0, 2).map(row => row.article_text));
  expect(result.articles.length + result.losses.length + screened.rejections.length).toBe(4);
  const root = await mkdtemp(join(tmpdir(), "screened-health-counts-"));
  try {
    setup.inputs.root = root;
    const first = article(setup.fixture.candidates[0]!, setup);
    setup.inputs.harvest.sources = [source({
      id: first.candidate.source_id, url: first.candidate.source.feed_url,
      title: first.candidate.source.title, kind: first.candidate.source.kind,
      tier: first.candidate.source.tier, weight: first.candidate.source.weight,
      publisher_id: first.candidate.source.publisher_id,
    })];
    if (first.candidate.source.publisher_id !== null) setup.inputs.harvest.publishers = [{
      id: first.candidate.source.publisher_id, display_name: "Recorded publisher",
    }];
    const pair = selectionInput(setup, [first, { ...first, candidate: short }]).batch;
    pair.work_rows = [FeedHealthStateRowSchema.parse({
      ...plannerRecordings(setup.context.date).find(record => record.name === "feed-health-state")!.row,
      run_id: setup.context.run_id, attempt: setup.context.writer.attempt, feed_id: first.candidate.source_id,
      endpoint_key: endpointKey(first.candidate.source.feed_url), checked_at: setup.context.now,
      items: 2, article_candidates: 0, articles_selected: 0,
    })];
    const selected = await selectArticles(pair, setup.inputs, setup.context.now);
    expect(selected.health_rows[0]).toMatchObject({ article_candidates: 1, articles_selected: 1 });
    expect(selected.exclusions).toContainEqual({
      feed_id: first.candidate.source_id, subject: "article", stage: "screen-article-candidates",
      reason_code: "STUB_CONTENT", attribution: null, count: 1,
    });
    expect(selected.articles).toHaveLength(1);
    const originalBatch = structuredClone(pair);
    const owner = resolveRunContext(setup.inputs.settings, "a".repeat(40), new Date("2026-10-22T00:01:00Z"));
    const fresh = await selectArticles(pair, setup.inputs, owner.now, undefined, owner);
    expect(fresh.articles[0]).toMatchObject({
      run_id: owner.run_id, date: owner.date, attempt: owner.writer.attempt,
      age_hours: selected.articles[0]!.age_hours, timing_at: selected.articles[0]!.timing_at,
    });
    expect(fresh.health_rows[0]).toMatchObject({
      run_id: owner.run_id, date: owner.date, checked_at: null, outcome: null, items: null,
      feed_reads: 0, productive_reads: 0, failed_reads: 0, feed_requests: 0,
      article_requests: 0, robots_requests: 0, article_candidates: 1, articles_selected: 1,
    });
    expect(pair).toEqual(originalBatch);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("screening and packing retain the owning run day even when evaluation happens on a later UTC day", async () => {
  const setup = await inputs();
  const original = article(setup.fixture.candidates[0]!, setup).candidate;
  for (const now of [setup.context.now, "2026-10-22T00:00:00Z"]) {
    const screened = await screenArticleCandidates({
      candidates: [original], observations: {}, seen: { availability: "unavailable" }, planning: setup.planning,
      clock_config: { collect: { max_future_hours: 0 } },
      run: { now, run_id: setup.context.run_id, correlation_id: setup.context.correlation_id, overrides: {} },
    });
    const selected = curateArticles(selectionInput(setup, screened.admitted)).articles;
    const row = partitionArticles(selected, { strategy: "none", dispatch_count: 1 }).articles[0]!;
    expect(row.date).toBe(setup.context.date);
    expect(row.run_id).toBe(setup.context.run_id);
    expect(row.article_text).toBe(original.article_text);
    expect(row.age_hours).toBe(now === setup.context.now ? 0 : 12);
    expect(row.timing_at).toBe(original.published_at);
  }
});

test("actual selected Parquet has exactly metadata columns while the same choice retains artifact text", async () => {
  const setup = await inputs();
  const chosen = run(setup).articles;
  const before = structuredClone(chosen);
  const root = await mkdtemp(join(tmpdir(), "portfolio-parquet-"));
  try {
    const rows = chosen.map(row => ({
      ...selectedArticleMetadata(row), run_id: row.run_id, attempt: row.attempt, date: row.date,
    }));
    const written = await persistLedger({
      ledger: "selected-articles", registryEntry: setup.inputs.registrations.selected_articles,
      outputRoot: root, ledgerSettings: setup.inputs.ledgerSettings,
      rowContract: SelectedArticleRowContract, period: { tier: "raw", covers: setup.context.date }, rows,
    });
    expect(written.status).toBe("written");
    expect(written.files).toHaveLength(1);
    const file = written.files[0]!;
    const actual = await readPlannerParquet(join(root, file.path), "selected-articles", SelectedArticleRowContract);
    expect(actual.rows).toEqual(rows);
    await initializeParquet();
    const table = tableFromIPC(readParquet(await readFile(join(root, file.path))).intoIPCStream());
    expect(table.schema.fields.map(field => field.name).sort()).toEqual(Object.keys(rows[0]!).sort());
    expect(actual.envelope).not.toHaveProperty("identity");
    expect(actual.envelope).not.toHaveProperty("unit_id");
    const artifact = SelectedArticlesArtifactSchema.parse({
      run_id: setup.context.run_id, attempt: setup.context.writer.attempt,
      date: setup.context.date, evaluated_at: setup.context.now,
      articles: chosen.map(row => ({ ...selectedArticleMetadata(row), article_text: row.article_text })),
    });
    expect(artifact.articles.map(row => row.article_text)).toEqual(chosen.map(row => row.article_text));
    expect(chosen).toEqual(before);
  } finally { await rm(root, { recursive: true, force: true }); }
}, 30_000);

test("empty writes have no invented files and real failures cannot report completion", async () => {
  const setup = await inputs();
  const root = await mkdtemp(join(tmpdir(), "portfolio-empty-failure-"));
  try {
    const request = {
      ledger: "selected-articles", registryEntry: setup.inputs.registrations.selected_articles,
      outputRoot: join(root, "state"), ledgerSettings: setup.inputs.ledgerSettings,
      rowContract: SelectedArticleRowContract, period: { tier: "raw" as const, covers: setup.context.date },
    };
    expect(await persistLedger({ ...request, rows: [] })).toEqual({ status: "empty", files: [] });
    const rows = run(setup).articles.map(row => ({
      ...selectedArticleMetadata(row), run_id: row.run_id, attempt: row.attempt, date: row.date,
    }));
    await writeFile(join(root, "state"), "real filesystem obstruction");
    await expect(persistLedger({ ...request, rows })).rejects.toThrow();
    const paused = await persistLedger({
      ...request, rows, registryEntry: { ...request.registryEntry, lifecycle_status: "paused" },
    });
    expect(paused.status).toBe("skipped");
    expect(paused.files).toEqual([]);
  } finally { await rm(root, { recursive: true, force: true }); }
});
