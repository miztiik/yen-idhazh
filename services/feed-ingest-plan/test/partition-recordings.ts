/** Screen and curate declared work-size vectors without writing files or reading history. */
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import {
  FeedIngestCandidateSchema, ParsedFeedBatchSchema, deriveCandidateId, deriveUrlKey,
} from "@idhazh/common-contracts";
import { loadPlanningConfig } from "../src/config/resolve-policy";
import { curateArticles } from "../src/curate-article-portfolio/editorial-selection";
import { screenArticleCandidates } from "../src/screen-article-candidates/triage-gates";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { resolveRunContext } from "../src/resolve-run-context";

export type HistoryFixture = {
  date: string; run_id: string; correlation_id: string; observed_at: string;
  word_work: number[]; bin_pack_workers: number[]; bin_pack_work: number[];
  round_robin_workers: number[]; round_robin_work: number[];
};
export async function fixtureInput(options: { count?: number; words?: number[] } = {}) {
  const [fixture, loaded] = await Promise.all([
    Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/ledger-history.json", import.meta.url)).json() as Promise<HistoryFixture>,
    loadPlanInputs(fileURLToPath(new URL("../../../", import.meta.url))),
  ]);
  const planning = loadPlanningConfig({
    ...loaded.harvest.config,
    triage: { ...loaded.harvest.config.triage, min_words: 1 },
    curate_articles: {
      ...loaded.harvest.config.curate_articles,
      article_limit: Math.max(1, options.words?.length ?? options.count ?? fixture.word_work.length), exploration_slot_share: 0,
      source_authority_weight: 0,
      source_based_quality_buckets: [{ id: "institutional", source_tier_id: 1, share_pct: 100, buffer_pct: 0, ladder_hours: [72] }],
      soft_caps: {
        ...loaded.harvest.config.curate_articles.soft_caps, max_source_share: 1,
        max_website_group_share: 1, min_distinct_sources: 1,
      },
      mmr_weights: { lambda_source: 0, lambda_website_group: 0 },
    },
  });
  const inputs = {
    ...loaded,
    harvest: { ...loaded.harvest, ...planning },
  };
  const context = resolveRunContext(
    loaded.settings, "a".repeat(40), new Date(fixture.observed_at),
    fixture.run_id.slice(11), "a2742c40-bc4e-461b-9f0f-5e8ab9c58c04",
  );
  const words = options.words ?? fixture.word_work.slice(0, options.count ?? fixture.word_work.length);
  const candidates = words.map((work, ordinal) => {
    const sourceId = `source-${ordinal}`;
    const url = `https://example.org/article-${ordinal}`;
    return FeedIngestCandidateSchema.parse({
      date: fixture.date, run_id: fixture.run_id, correlation_id: context.correlation_id,
      candidate_id: deriveCandidateId(fixture.run_id, sourceId, ordinal), entry_ordinal: ordinal,
      feed_id: sourceId,
      source: {
        feed_id: sourceId, feed_url: "https://example.org/feed", title: "Recorded source",
        tier: 1, status: "active",
        weight: 1, applied_tier_weight: 1,
      },
      canonical_url: url, url_key: deriveUrlKey(url), title: `Recorded article ${ordinal}`,
      article_text: Array(work).fill(`word${ordinal}`).join(" "), word_count: work,
      categories: [], author: null, fetched_at: fixture.observed_at,
      published_at: new Date(Date.parse(fixture.observed_at) - ordinal * 3_600_000).toISOString().replace(".000Z", "Z"),
    });
  });
  const screening = await screenArticleCandidates({
    candidates, observations: {}, discovered: { availability: "unavailable" }, planning,
    clock_config: { collect: { max_future_hours: 1 } },
    run: { now: fixture.observed_at, run_id: context.run_id, correlation_id: context.correlation_id },
  });
  const batch = ParsedFeedBatchSchema.parse({
    batch_id: randomUUID(), config_sha256: "b".repeat(64), context, request: {},
    candidates,
    observations: Object.fromEntries(candidates.map(candidate => [candidate.candidate_id, {
      candidate_id: candidate.candidate_id, http_status: 200, paywall: false, robots: "allowed",
      fetch_failure: null, extraction: "success", paywall_evidence: "none", observed_at: context.now,
    }])),
    discovered: { availability: "unavailable" },
    evidence: Object.fromEntries(candidates.map(candidate => [candidate.candidate_id, {
      website_group: null, estimated_work: candidate.word_count,
    }])),
    history_rows: [], history_days: [], work_rows: [], exclusions: [],
  });
  const curation = curateArticles({
    articles: screening.admitted, batch, inputs, health: new Map(), selectionStartedAt: context.now,
    publications: { day: fixture.date, availability: "unavailable", counts: new Map() },
  });
  return { fixture, context, planning, inputs, batch, candidates, screening, curation };
}
