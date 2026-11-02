/** Does real screening deliver the chosen identities, unchanged content and measured evidence? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { copyFile, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  FeedHealthStateRowSchema, FeedIngestCandidateSchema, ParsedFeedBatchSchema, PartitionedFeedBatchSchema, PlanRunRowContract, SelectedArticleRowContract,
  SelectedArticlesArtifactSchema, deriveCandidateId, deriveUrlKey, selectedArticleMetadata,
} from "@idhazh/common-contracts";
import type { FeedIngestConfig, PlannerArticleEvidence } from "@idhazh/common-contracts";
import { loadPlanningConfig, resolvePolicy } from "../src/config/resolve-policy";
import { curateArticles } from "../src/curate-article-portfolio/editorial-selection";
import { screenArticleCandidates } from "../src/screen-article-candidates/triage-gates";
import type { ScreenedCandidate } from "../src/screen-article-candidates/triage-gates";
import { calculateFreshness } from "../src/screen-article-candidates/freshness-decay";
import { createSubstanceScorer } from "../src/screen-article-candidates/score-article-substance";
import { countWords } from "../src/count-article-words";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { resolveRunContext } from "../src/resolve-run-context";
import type { SourceHistoryEvidence } from "../src/read-ledger-history/read-feed-history";
import { partitionArticles } from "../src/partition-article-shards/shard-packer";
import { selectArticles } from "../src/select-articles";
import { readRunHistory } from "../src/read-ledger-history/read-run-history";
import { endpointKey } from "../src/read-ledger-history/read-feed-history";
import { plannerRecordings } from "../../../packages/ledger-file-writer/test/planner-recordings";
import { source } from "./harvest-recordings";
import { recordedPlan } from "./plan-recordings";
import { stageConfigFingerprint } from "../src/api/operation-context";
import { summarizeRequestReport } from "../src/read-ledger-history/request-summary";
import { stageStore } from "../src/api/stage-store";
import { executePersistence } from "../src/api/persistence-operation";
import { executeFeedHealthState } from "../src/api/feed-health-state-operation";
import { compactRows, readWritten } from "./partition-fixtures";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { renderWorkflowPlanMarkdown } from "../scripts/feed-ingest-plan-report";

type CandidateCase = {
  name: string; source: string; ordinal: number;
  domain: string; publisher_id: string | null; title: string; published_at: string;
};
type OperationalEvidence = { success_fraction: number; attempted: number; window_days: number };
type Fixture = {
  observed_at: string; run_id: string; candidates: CandidateCase[];
  reliability_cases: {
    name: string; enabled: boolean; floor: number; alpha: OperationalEvidence | null; gamma: OperationalEvidence | null;
    winner: string; alpha_penalty: number | null; gamma_penalty: number | null;
  }[];
  expected: { baseline: string[]; base_scores: Record<string, number>; selected_ranks: number[] };
};
type Knobs = FeedIngestConfig["curate_articles"];
async function inputs(patch: Partial<Knobs> = {}) {
  const [fixture, loaded] = await Promise.all([
    Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/portfolio-cases.json", import.meta.url)).json() as Promise<Fixture>,
    loadPlanInputs(fileURLToPath(new URL("../../../", import.meta.url))),
  ]);
  const planning = loadPlanningConfig({
    ...loaded.harvest.config,
    triage: { ...loaded.harvest.config.triage, recency_half_life_hours: 18, recency_weight: 1 },
    curate_articles: {
      ...loaded.harvest.config.curate_articles, article_limit: 2, source_authority_weight: 0,
      diversity: { lambda_domain: 0, lambda_feed: 0, novelty_bonus: 0 }, ...patch,
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
  const article_text = "Recorded factual report. ".repeat(100).trim();
  const candidate = FeedIngestCandidateSchema.parse({
    date: context.date, run_id: context.run_id, correlation_id: context.correlation_id,
    candidate_id: deriveCandidateId(context.run_id, spec.source, spec.ordinal), entry_ordinal: spec.ordinal,
    feed_id: spec.source, source: {
      feed_id: spec.source, publisher_id: spec.publisher_id, feed_url: `https://${spec.domain}/feed`,
      title: `${spec.source} configured feed`, status: "active", weight: 1,
    },
    canonical_url: url, url_key: deriveUrlKey(url), title: spec.title, categories: ["feed-category"],
    article_text, word_count: countWords(article_text), author: null, published_at: spec.published_at, fetched_at: fixture.observed_at,
  });
  const policy = resolvePolicy(planning);
  const { substance_word_count, substance_score } = createSubstanceScorer(planning.config.curate_articles.substance)(
    candidate.title, candidate.article_text);
  return {
    candidate, policy, observation: null, discovered_availability: "unavailable",
    freshness: { ...calculateFreshness(candidate, undefined, fixture.observed_at, 6, policy), substance_word_count, substance_score },
  };
}
function selectionInput(setup: Setup, articles: ScreenedCandidate[], options: {
  health?: ReadonlyMap<string, SourceHistoryEvidence>; evidence?: Record<string, PlannerArticleEvidence>;
} = {}) {
  return {
    articles, inputs: setup.inputs, selectionStartedAt: setup.context.now,
    health: options.health ?? new Map<string, SourceHistoryEvidence>(),
    batch: ParsedFeedBatchSchema.parse({
      batch_id: randomUUID(), config_sha256: "b".repeat(64), context: setup.context, request: {},
      candidates: articles.map(value => value.candidate),
      observations: Object.fromEntries(articles.map(({ candidate }) => [candidate.candidate_id, {
        candidate_id: candidate.candidate_id, http_status: 200, paywall: false,
        fetch_failure: null, extraction: "success", paywall_evidence: "none", observed_at: setup.context.now,
      }])),
      discovered: { availability: "unavailable" },
      evidence: options.evidence ?? Object.fromEntries(articles.map(({ candidate }) => [candidate.candidate_id, {
        website_group: { value: new URL(candidate.canonical_url).hostname, origin: "canonical_url" },
        estimated_work: candidate.word_count,
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

test("article-pass evidence controls the adjustment without using opposite RSS ratios", async () => {
  const setup = await inputs({ article_limit: 1, source_authority_weight: 1, source_reliability_penalty_enabled: true });
  setup.inputs.clock_config.collect.reliability_floor = 0;
  const health = new Map<string, SourceHistoryEvidence>([
    ["alpha", { lifecycle: "eligible", endpoint_key: "a".repeat(64), strikes: 0,
      rest_until: null, first_confirmed_failure_at: null, failed_recovery_checks: 0,
      retired_at: null, retirement_reason: null, availability_updated_at: null, availability_complete: true,
      article_pass_rate: 0.25, reliability: { productive: 10, attempted: 10, success_fraction: 1,
        from_day: "2026-10-15", through_day: "2026-10-21", production_factor: 1, complete: true } }],
    ["gamma", { lifecycle: "eligible", endpoint_key: "b".repeat(64), strikes: 0,
      rest_until: null, first_confirmed_failure_at: null, failed_recovery_checks: 0,
      retired_at: null, retirement_reason: null, availability_updated_at: null, availability_complete: true,
      article_pass_rate: 0.75, reliability: { productive: 0, attempted: 10, success_fraction: 0,
        from_day: "2026-10-15", through_day: "2026-10-21", production_factor: 0, complete: true } }],
  ]);
  const specs = [setup.fixture.candidates[0]!, setup.fixture.candidates[2]!]
    .map(spec => ({ ...spec, published_at: setup.context.now }));
  const winner = run(setup, specs, { health }).articles[0]!;
  expect(winner.feed_id).toBe("gamma");
  expect(adjustment(winner, "article_pass_rate")).toBe(-0.25);
  health.set("alpha", { ...health.get("alpha")!, article_pass_rate: null });
  const unknown = run(setup, specs, { health }).articles[0]!;
  expect(unknown.feed_id).toBe("alpha");
  expect(adjustment(unknown, "article_pass_rate")).toBe(0);
  expect(health.get("alpha")!.article_pass_rate).toBeNull();
  setup.planning.config.curate_articles.source_reliability_penalty_enabled = false;
  expect(adjustment(run(setup, specs, { health }).articles[0]!, "article_pass_rate")).toBe(0);
});

test("real stage projects exact cached components and preserves the original population", async () => {
  const setup = await inputs();
  const supplied = selectionInput(setup, setup.fixture.candidates.map(spec => article(spec, setup)));
  const before = structuredClone(supplied.batch);
  const result = curateArticles(supplied);
  expect(names(result)).toEqual(setup.fixture.expected.baseline);
  expect(result.articles.map(row => row.editorial_rank)).toEqual(setup.fixture.expected.selected_ranks);
  for (const row of result.articles) {
    const original = supplied.articles.find(value => value.candidate.url_key === row.url_key)!;
    expect(row.ratings.base_article_score).toBeCloseTo(setup.fixture.expected.base_scores[new URL(row.canonical_url).pathname.slice(1)]!, 12);
    expect(row.ratings.adjustments.map(value => value.term)).toEqual([
      "article_pass_rate", "substance_quality_score", "domain_diversity_penalty", "feed_diversity_penalty", "novelty_bonus",
    ]);
    expect(row.ratings.base_article_score).toBe(
      ((row.ratings.feed_authority_score + row.ratings.recency_score) + adjustment(row, "article_pass_rate")!)
      + adjustment(row, "substance_quality_score")!);
    expect(row.ratings.marginal_score).toBe(
      ((row.ratings.base_article_score + adjustment(row, "domain_diversity_penalty")!)
      + adjustment(row, "feed_diversity_penalty")!) + adjustment(row, "novelty_bonus")!);
    expect(row.article_text).toBe(original.candidate.article_text);
    expect(row.word_count).toBe(original.candidate.word_count);
    expect(row.substance_word_count).toBe(original.freshness.substance_word_count);
    for (const field of ["labels", "policy", "tier", "applied_tier_weight", "feed_limit", "exploration_slot", "cap_relaxations"]) {
      expect(row).not.toHaveProperty(field);
    }
  }
  expect(result.losses.map(loss => loss.reason)).toEqual(["REJECTED_GLOBAL_CAPACITY_REACHED"]);
  expect(result.articles.length + result.losses.length).toBe(supplied.articles.length);
  expect(supplied.batch).toEqual(before);
});

test("missing history remains null evidence with numeric zero adjustment and canonical website penalties", async () => {
  const setup = await inputs();
  const offered = article(setup.fixture.candidates[0]!, setup);
  const absent = curateArticles(selectionInput(setup, [offered], { evidence: {} })).articles[0]!;
  expect(adjustment(absent, "domain_diversity_penalty")).toBe(0);
  expect(adjustment(absent, "article_pass_rate")).toBe(0);
  expect(absent.ratings.adjustments.every(value => Number.isFinite(value.value))).toBe(true);
  const known = run(setup).articles[0]!;
  expect(known.ratings.base_article_score).toBe(absent.ratings.base_article_score);
  expect(known.ratings.marginal_score).toBe(absent.ratings.marginal_score);
});

test("unknown timing stays unknown; first discovery keeps its own basis and timestamp", async () => {
  const setup = await inputs();
  const original = article(setup.fixture.candidates[0]!, setup);
  original.candidate.published_at = null;
  const firstSeenAt = "2026-10-20T11:00:00Z";
  for (const discovered of [undefined, { url_key: original.candidate.url_key, first_seen_at: firstSeenAt, date: "2026-10-20" }]) {
    const offered = { ...original, freshness: {
      ...original.freshness,
      ...calculateFreshness(original.candidate, discovered, setup.fixture.observed_at, 6, original.policy),
    } };
    const row = curateArticles(selectionInput(setup, [offered])).articles[0]!;
    expect(row.published_at).toBe(setup.context.now);
    expect(row.published_at_source).toBe("selection");
    expect(original.candidate.published_at).toBeNull();
    expect(row.timing_basis).toBe(discovered === undefined ? "unavailable" : "first_seen");
    expect(row.timing_at).toBe(discovered === undefined ? null : firstSeenAt);
    expect(row.age_hours).toBe(discovered === undefined ? null : 25);
    expect(row.ratings.recency_score).toBe(discovered === undefined ? 0 : 0.5 ** (25 / 18));
    expect(row.freshness_cutoff_at).toBe(new Date(Date.parse(setup.context.now) - 36 * 3_600_000).toISOString());
  }
});

test("admitted future timing preserves signed age and floors only the recency age", async () => {
  const setup = await inputs();
  const row = run(setup, [{ ...setup.fixture.candidates[0]!, published_at: "2026-10-21T13:00:00Z" }]).articles[0]!;
  expect(row.age_hours).toBe(-1);
  expect(row.ratings.recency_score).toBe(1);
  expect(row.timing_at).toBe(row.published_at);
  expect(row.published_at_source).toBe("source");
  const untrusted = run(setup, [{ ...setup.fixture.candidates[0]!, published_at: "2026-10-23T00:00:00Z" }]).articles[0]!;
  expect(untrusted).toMatchObject({
    published_at: setup.context.now, published_at_source: "selection", timing_basis: "unavailable", timing_at: null, age_hours: null,
  });
});

test("byline is independent of scores while technical pass evidence keeps its meaning", async () => {
  const setup = await inputs({ source_authority_weight: 2 });
  const original = article(setup.fixture.candidates[0]!, setup);
  const changed = { ...original, candidate: { ...original.candidate, author: "Recorded Writer" } };
  const a = curateArticles(selectionInput(setup, [original])).articles[0]!;
  const b = curateArticles(selectionInput(setup, [changed])).articles[0]!;
  expect(a.ratings).toEqual(b.ratings);
  expect(b).not.toHaveProperty("informative_verdict");
  expect(b).not.toHaveProperty("quality");
  for (const recorded of setup.fixture.reliability_cases) {
    const configured = await inputs({ article_limit: 1, source_authority_weight: 1, source_reliability_penalty_enabled: recorded.enabled });
    configured.inputs.clock_config.collect.reliability_floor = recorded.floor;
    const health = new Map<string, SourceHistoryEvidence>();
    for (const [feed, evidence] of [["alpha", recorded.alpha], ["gamma", recorded.gamma]] as const) {
      health.set(feed, {
        lifecycle: "unknown", endpoint_key: "a".repeat(64), strikes: null,
        rest_until: null, first_confirmed_failure_at: null, failed_recovery_checks: null,
        retired_at: null, retirement_reason: null, availability_updated_at: null, availability_complete: false,
        article_pass_rate: evidence?.success_fraction ?? null,
        reliability: evidence === null ? null : {
          productive: evidence.attempted * evidence.success_fraction, attempted: evidence.attempted,
          success_fraction: evidence.success_fraction, from_day: "2026-10-15", through_day: "2026-10-21",
          production_factor: Math.max(recorded.floor, evidence.success_fraction), complete: false,
        },
      });
    }
    const specs = [configured.fixture.candidates[0]!, configured.fixture.candidates[2]!]
      .map(spec => ({ ...spec, published_at: configured.fixture.observed_at }));
    expect(run(configured, specs, { health }).articles[0]!.feed_id, recorded.name).toBe(recorded.winner);
    for (const spec of specs) {
      const offered = article(spec, configured);
      const row = run(configured, [spec], { health }).articles[0]!;
      const penalty = (spec.source === "alpha" ? recorded.alpha_penalty : recorded.gamma_penalty) ?? 0;
      expect(adjustment(row, "article_pass_rate"), recorded.name).toBeCloseTo(-penalty, 12);
      expect(health.get(spec.source)!.article_pass_rate).toBe((spec.source === "alpha" ? recorded.alpha : recorded.gamma)?.success_fraction ?? null);
      expect(row.ratings.base_article_score).toBe(((1 + 1) - penalty) + offered.freshness.substance_score);
    }
  }
});

test("real screening joins the strongest duplicate body and preserves both counts through packing and native persistence", async () => {
  const setup = await inputs({ article_limit: 3, source_authority_weight: 1 });
  const recordedScreening = await Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/screening-cases.json", import.meta.url)).json();
  const original = article(setup.fixture.candidates[0]!, setup).candidate;
  original.source.weight = 0;
  const other = article({ ...setup.fixture.candidates[2]!, published_at: setup.context.now }, setup).candidate;
  const strongerText: string = recordedScreening.candidate.article_text;
  const stronger = { ...original, feed_id: "strong-carrier", entry_ordinal: 99,
    candidate_id: deriveCandidateId(original.run_id, "strong-carrier", 99),
    article_text: strongerText, word_count: recordedScreening.candidate.word_count,
    source: { ...original.source, feed_id: "strong-carrier", feed_url: "https://one.example/strong-feed", weight: 1 } };
  const short = { ...original, entry_ordinal: 100, candidate_id: deriveCandidateId(original.run_id, original.feed_id, 100),
    canonical_url: "https://one.example/short", url_key: deriveUrlKey("https://one.example/short"),
    word_count: 3, article_text: "Too little substance" };
  const emptyView = recordedScreening.substance_cases.find((entry: { name: string }) =>
    entry.name === "technically admitted empty retained view");
  if (emptyView === undefined) throw new Error("The measured-zero retained recording is required");
  const emptyText = Array.from({ length: emptyView.repetitions }, () => emptyView.block).join("\n");
  const zero = { ...original, entry_ordinal: 101, candidate_id: deriveCandidateId(original.run_id, original.feed_id, 101),
    canonical_url: "https://one.example/zero", url_key: deriveUrlKey("https://one.example/zero"),
    article_text: emptyText, word_count: countWords(emptyText), title: emptyView.title, published_at: null };
  const screened = await screenArticleCandidates({
    candidates: [original, other, stronger, short, zero], observations: {}, discovered: { availability: "unavailable" },
    planning: setup.planning, clock_config: { collect: { max_future_hours: 0 } },
    run: { now: setup.context.now, run_id: setup.context.run_id, correlation_id: setup.context.correlation_id },
  });
  expect(screened.rejections.map(row => row.drop_reason)).toEqual(["REJECTED_SCREENING_MIN_WORDS"]);
  const before = structuredClone(screened.admitted);
  const result = curateArticles(selectionInput(setup, screened.admitted));
  const packed = partitionArticles(result.articles, { strategy: "bin-pack", dispatch_count: 1 });
  const chosen = packed.articles.find(row => row.url_key === original.url_key)!;
  expect(chosen.feed_id).toBe(stronger.feed_id);
  expect(chosen.weight).toBe(stronger.source.weight);
  expect(chosen.article_text).toBe(strongerText);
  expect(chosen.word_count).toBe(stronger.word_count);
  expect(chosen.substance_word_count).toBe(screened.admitted.find(row => row.candidate.candidate_id === stronger.candidate_id)!.freshness.substance_word_count);
  expect(chosen.estimated_work).toBe(stronger.word_count);
  expect(result.losses.map(loss => [loss.article.candidate.candidate_id, loss.reason]))
    .toEqual([[original.candidate_id, "REJECTED_DUPLICATE_CANONICAL_CARRIER"]]);
  expect(result.articles.length + result.losses.length + screened.rejections.length).toBe(5);
  expect(screened.admitted).toEqual(before);
  const fixture = await recordedPlan();
  try {
    const candidates = [original, other, stronger, short, zero];
    fixture.inputs.harvest = {
      ...fixture.inputs.harvest, ...setup.planning,
      sources: [...new Map(candidates.map(candidate => [candidate.feed_id, source({
        id: candidate.feed_id, url: candidate.source.feed_url, title: candidate.source.title,
        weight: candidate.source.weight, publisher_id: candidate.source.publisher_id,
      })])).values()],
      publishers: [...new Set(candidates.flatMap(candidate =>
        candidate.source.publisher_id === null ? [] : [candidate.source.publisher_id]))]
        .map(id => ({ id, display_name: "Recorded publisher" })),
    };
    const parsed = ParsedFeedBatchSchema.parse({
      ...selectionInput(setup, screened.admitted).batch, candidates,
      observations: Object.fromEntries(candidates.map(candidate => [candidate.candidate_id, {
        candidate_id: candidate.candidate_id, http_status: 200, paywall: false,
        fetch_failure: null, extraction: "success", paywall_evidence: "none", observed_at: setup.context.now,
      }])),
    });
    const currentHealth = {
      sources: new Map<string, SourceHistoryEvidence>(),
      request_report: summarizeRequestReport({
        rows: [], days: [], sources: [...new Map(candidates.map(candidate =>
          [candidate.feed_id, candidate.source])).values()], now: setup.context.now,
        request_report_closed_days: fixture.inputs.harvest.config.feedback.request_report_closed_days,
      }),
    };
    const selection = await selectArticles(parsed, fixture.inputs, setup.context.now, currentHealth,
      setup.context, await readRunHistory(fixture.inputs, setup.context));
    expect(selection.articles).toEqual(result.articles);
    expect(selection.rejected_articles.map(row => row.reason_code).sort()).toEqual([
      "REJECTED_DUPLICATE_CANONICAL_CARRIER", "REJECTED_SCREENING_MIN_WORDS",
    ]);
    const batch = stageStore(fixture.inputs).write("partitioned", PartitionedFeedBatchSchema, {
      batch_id: randomUUID(), parsed_batch_id: randomUUID(), context: setup.context,
      selection_batch_id: randomUUID(),
      config_sha256: stageConfigFingerprint(fixture.inputs, fixture.runtime),
      evaluated_at: setup.context.now, selection_started_at_utc: setup.context.now,
      ...selection, ...packed,
    });
    const health = await executeFeedHealthState({ batch_id: batch.batch_id, action: "record" },
      fixture.inputs, fixture.runtime);
    const persisted = await executePersistence({ batch_id: batch.batch_id }, fixture.inputs, fixture.runtime);
    const raw = await readWritten(fixture.inputs.outputRoot, "selected-articles", setup.context.date,
      SelectedArticleRowContract, persisted.files);
    const compact = await compactRows(fixture.inputs.outputRoot, "selected-articles", setup.context.date,
      SelectedArticleRowContract, raw.rows, "daily");
    const reopened = await readPlannerParquet(compact.path!, "selected-articles", SelectedArticleRowContract);
    const artifact = SelectedArticlesArtifactSchema.parse(await Bun.file(join(fixture.inputs.root, persisted.artifact)).json());
    const ordered = <T extends { editorial_rank: number }>(rows: readonly T[]) => [...rows].sort((a, b) => a.editorial_rank - b.editorial_rank);
    const expected = ordered(packed.articles).map(row => ({
      ...selectedArticleMetadata(row), run_id: setup.context.run_id, attempt: setup.context.writer.attempt, date: setup.context.date,
    }));
    expect(ordered(raw.rows)).toEqual(expected);
    expect(ordered(reopened.rows)).toEqual(expected);
    expect(ordered(artifact.articles).map(row => [row.url_key, row.article_text, row.word_count, row.substance_word_count]))
      .toEqual(ordered(packed.articles).map(row => [row.url_key, row.article_text, row.word_count, row.substance_word_count]));
    const persistedZero = reopened.rows.find(row => row.url_key === zero.url_key)!;
    expect(persistedZero).toMatchObject({
      word_count: zero.word_count, substance_word_count: 0, timing_at: null, age_hours: null, timing_basis: "unavailable",
      ratings: { recency_score: 0 },
    });
    expect(persistedZero.freshness_cutoff_at).toBe(new Date(Date.parse(setup.context.now) - 36 * 3_600_000).toISOString());
    const capture = process.env.IDHAZH_CURATION_EVIDENCE_DIRECTORY;
    if (capture !== undefined) {
      await mkdir(capture, { recursive: true });
      if (persisted.run_files === undefined) throw new Error("The real standalone run must have a saved outcome");
      const savedRun = await readWritten(fixture.inputs.outputRoot, "plan-runs", setup.context.date,
        PlanRunRowContract, persisted.run_files);
      const policy = {
        config: fixture.inputs.harvest.config, request: { shards: packed.dispatch_count, partition_strategy: packed.strategy },
        history: fixture.inputs.clock_config.collect,
        parser_concurrency: fixture.inputs.settings.listener.parser_concurrency,
      };
      const report = renderWorkflowPlanMarkdown({
        response: {
          ...savedRun.rows[0], planning_complete: persisted.run_status === "completed",
          correlation_id: setup.context.correlation_id, batches: { selection_batch_id: batch.batch_id },
          files: {
            selected_articles: persisted.files, rejected_articles: persisted.rejected_files,
            feed_health_state: health.files, plan_runs: persisted.run_files,
          },
          selected_url_keys: packed.articles.map(row => row.url_key),
          assignments: packed.articles.map(({ url_key, editorial_rank, worker_assignment }) =>
            ({ url_key, editorial_rank, worker_assignment })),
        },
        selected: raw.rows, health, policy, failures: { articles: selection.rejected_articles },
      });
      await Promise.all([
        writeFile(join(capture, "selected-evidence.md"), report.markdown),
        writeFile(join(capture, "selection.json"), JSON.stringify({
          artifact, rows: raw.rows, screening_rejections: screened.rejections,
          losses: result.losses.map(loss => ({ candidate_id: loss.article.candidate.candidate_id, reason: loss.reason })),
        }, null, 2)),
        copyFile(compact.path!, join(capture, "selected-articles.compact.parquet")),
        ...persisted.files.files.map((file, index) => copyFile(join(fixture.inputs.outputRoot, file.path),
          join(capture, `selected-articles.raw-${index}.parquet`))),
      ]);
    }
  } finally { await fixture.close(); }
}, 120000);

test("real selection keeps source pass denominators and isolates a later run's health", async () => {
  const setup = await inputs();
  const first = article(setup.fixture.candidates[0]!, setup);
  const short = { ...first.candidate, entry_ordinal: 99,
    candidate_id: deriveCandidateId(first.candidate.run_id, first.candidate.feed_id, 99),
    canonical_url: "https://one.example/short", url_key: deriveUrlKey("https://one.example/short"),
    word_count: 3, article_text: "Too little substance" };
  const configured = source({
    id: first.candidate.feed_id, url: first.candidate.source.feed_url, title: first.candidate.source.title,
    weight: first.candidate.source.weight, publisher_id: first.candidate.source.publisher_id,
  });
  const publishers = first.candidate.source.publisher_id === null ? [] : [{
    id: first.candidate.source.publisher_id, display_name: "Recorded publisher",
  }];
  const recorded = await recordedPlan([configured], publishers);
  try {
    setup.inputs.root = recorded.directory;
    setup.inputs.harvest.sources = [configured];
    setup.inputs.harvest.retired_sources = [];
    setup.inputs.harvest.publishers = publishers;
    const pair = selectionInput(setup, [first, { ...first, candidate: short }]).batch;
    pair.work_rows = [FeedHealthStateRowSchema.parse({
      ...plannerRecordings(setup.context.date).find(record => record.name === "feed-health-state")!.row,
      run_id: setup.context.run_id, attempt: setup.context.writer.attempt, feed_id: first.candidate.feed_id,
      endpoint_key: endpointKey(first.candidate.source.feed_url), checked_at: setup.context.now,
      items: 2, article_candidates: 1, articles_selected: 0,
    })];
    const baseline = await readRunHistory(setup.inputs, pair.context);
    const selected = await selectArticles(pair, setup.inputs, setup.context.now, undefined, setup.context, baseline);
    expect(selected.health_rows[0]).toMatchObject({ article_candidates: 1, articles_selected: 1 });
    expect(selected.exclusions).toContainEqual({
      feed_id: first.candidate.feed_id, subject: "article", stage: "screen-article-candidates",
      reason_code: "REJECTED_SCREENING_MIN_WORDS", attribution: null, count: 1,
    });
    const originalBatch = structuredClone(pair);
    const runContext = resolveRunContext(setup.inputs.settings, "a".repeat(40), new Date("2026-10-22T00:01:00Z"));
    const fresh = await selectArticles(pair, setup.inputs, runContext.now, undefined, runContext, baseline);
    expect(fresh.articles[0]).toMatchObject({
      run_id: runContext.run_id, date: runContext.date, attempt: runContext.writer.attempt,
      age_hours: selected.articles[0]!.age_hours, timing_at: selected.articles[0]!.timing_at,
    });
    expect(fresh.health_rows[0]).toMatchObject({
      run_id: runContext.run_id, date: runContext.date, checked_at: null, outcome: null, items: null,
      feed_reads: 0, productive_reads: 0, failed_reads: 0, feed_requests: 0,
      article_requests: 0, article_candidates: 0, articles_selected: 1,
    });
    expect(pair).toEqual(originalBatch);
  } finally { await recorded.close(); }
}, 120000);

test("screening and packing retain the owning run day across UTC midnight", async () => {
  const setup = await inputs();
  const original = article(setup.fixture.candidates[0]!, setup).candidate;
  for (const now of [setup.context.now, "2026-10-22T00:00:00Z"]) {
    const screened = await screenArticleCandidates({
      candidates: [original], observations: {}, discovered: { availability: "unavailable" }, planning: setup.planning,
      clock_config: { collect: { max_future_hours: 0 } },
      run: { now, run_id: setup.context.run_id, correlation_id: setup.context.correlation_id },
    });
    const selected = curateArticles(selectionInput(setup, screened.admitted)).articles;
    const row = partitionArticles(selected, { strategy: "none", dispatch_count: 1 }).articles[0]!;
    expect(row.date).toBe(setup.context.date);
    expect(row.run_id).toBe(setup.context.run_id);
    expect(row.article_text).toBe(original.article_text);
    expect(row.word_count).toBe(original.word_count);
    expect(row.substance_word_count).toBe(screened.admitted[0]!.freshness.substance_word_count);
    expect(row.age_hours).toBe(now === setup.context.now ? 0 : 12);
    expect(row.timing_at).toBe(original.published_at);
  }
});

test("selected metadata excludes text while the artifact retains the same chosen counts and body", async () => {
  const setup = await inputs();
  const chosen = run(setup).articles;
  const before = structuredClone(chosen);
  const rows = chosen.map(row => ({ ...selectedArticleMetadata(row), run_id: row.run_id, attempt: row.attempt, date: row.date }));
  expect(SelectedArticleRowContract.schema.array().parse(rows)).toEqual(rows);
  expect(rows.every(row => !("article_text" in row))).toBe(true);
  const artifact = SelectedArticlesArtifactSchema.parse({
    schema_version: SelectedArticleRowContract.schemaVersion, run_id: setup.context.run_id, attempt: setup.context.writer.attempt,
    date: setup.context.date, evaluated_at: setup.context.now,
    articles: chosen.map(row => ({ ...selectedArticleMetadata(row), article_text: row.article_text })),
  });
  expect(artifact.articles.map(row => [row.url_key, row.word_count, row.substance_word_count, row.article_text]))
    .toEqual(chosen.map(row => [row.url_key, row.word_count, row.substance_word_count, row.article_text]));
  expect(chosen).toEqual(before);
});
