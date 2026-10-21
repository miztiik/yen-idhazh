/** Which bounded real articles, curation decisions and ledger writes exercise partition replay? */
import { join } from "node:path";
import {
  CONTRACT_VERSION, FeedIngestCandidateSchema, WriterIdentitySchema, deriveCandidateId, deriveUrlKey,
} from "@idhazh/common-contracts";
import type { WriterIdentity } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, LedgerRowContract, LedgerSettings, PersistLedgerResult } from "@idhazh/ledger-file-writer";
import { loadPlanningConfig, resolvePolicy } from "../src/config/resolve-policy";
import { curateArticles, persistPortfolio } from "../src/curate-article-portfolio/editorial-selection";
import { screenArticleCandidates } from "../src/screen-article-candidates/triage-gates";
import { readLedgerDay } from "../src/read-ledger-history/read-period";

export type HistoryFixture = {
  date: string; run_id: string; correlation_id: string; observed_at: string;
  word_work: number[]; bin_pack_workers: number[]; bin_pack_work: number[];
  round_robin_workers: number[]; round_robin_work: number[];
};
export const settings: LedgerSettings = { format: "parquet", compression_raw: "snappy", compression_compact: "zstd" };
export function registration(name: string): LedgerRegistration {
  return { name, family: "feed-ingest-plan", grain: "raw-and-compact", lifecycle_status: "active", prefix: ["feed-ingest-plan", name] };
}
export function writer(runId: string, attempt = 1, shard = 0): WriterIdentity {
  return WriterIdentitySchema.parse({
    run_id: runId, attempt, job: null, pipeline_name: "plan", task_name: "seal-article-ledger",
    shard, producer: "tests.partition", git_sha: "a".repeat(40),
  });
}
export async function fixtureInput(root: string, options: { count?: number; freshness?: number; words?: number[] } = {}) {
  const [fixture, authored, taxonomy] = await Promise.all([
    Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/ledger-history.json", import.meta.url)).json() as Promise<HistoryFixture>,
    Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json(),
    Bun.file(new URL("../../../config/taxonomy.json", import.meta.url)).json(),
  ]);
  const planning = loadPlanningConfig({
    ...authored, vertical_overrides: {},
    triage: { ...authored.triage, min_words_article: 1 },
    curate: {
      ...authored.curate, article_limit: null, exploration_slot_share: 0, source_authority_weight: 0,
      base_source_allowance: 20, bonus_uncovered_event_cluster: 0,
      bonus_underrepresented_vertical: 0, bonus_unique_evidence: 0,
      soft_caps: { ...authored.curate.soft_caps, max_source_share: 1, max_parent_domain_share: 1, min_distinct_sources: 1, max_event_cluster_items: 20 },
      mmr_weights: Object.fromEntries(Object.keys(authored.curate.mmr_weights).map(key => [key, 0])),
    },
  }, taxonomy);
  const context = { date: fixture.date, run_id: fixture.run_id, correlation_id: fixture.correlation_id };
  const overrides = options.freshness === undefined ? {} : { freshness_hours: options.freshness };
  const policy = resolvePolicy(planning, "ai", overrides);
  const { mmr_weights, ...curate } = policy.curate;
  const words = options.words ?? fixture.word_work.slice(0, options.count ?? fixture.word_work.length);
  const candidates = words.map((work, ordinal) => {
    const sourceId = `source-${ordinal}`;
    const url = `https://example.org/article-${ordinal}`;
    return FeedIngestCandidateSchema.parse({
      date: fixture.date, run_id: fixture.run_id, correlation_id: fixture.correlation_id,
      candidate_id: deriveCandidateId(fixture.run_id, sourceId, ordinal), entry_ordinal: ordinal,
      source_id: sourceId, vertical: "ai",
      source: {
        source_id: sourceId, feed_url: "https://example.org/feed", title: "Recorded source",
        vertical: "ai", kind: "reporting", tier: 1, form: "article", status: "active",
        weight: 1, applied_tier_weight: 1,
      },
      canonical_url: url, url_key: deriveUrlKey(url), title: `Recorded article ${ordinal}`,
      article_text: Array(work).fill(`word${ordinal}`).join(" "), word_count: work,
      categories: [], author: null, fetched_at: fixture.observed_at,
      published_at: new Date(Date.parse(fixture.observed_at) - ordinal * 3_600_000).toISOString().replace(".000Z", "Z"),
      labels: { assigned_desk: null, lenses: null, event_types: null, event_cluster_id: null, entities: null, origin: null, matcher_version: null },
      policy: { policy_version: "fixture", config_sha256: "b".repeat(64), ...policy.triage, ...curate, ...mmr_weights },
    });
  });
  const screening = await screenArticleCandidates({
    candidates, observations: {}, seen: { availability: "unavailable" },
    planning, clock_config: { collect: { max_future_hours: 1 } },
    run: { now: fixture.observed_at, run_id: context.run_id, correlation_id: context.correlation_id, overrides },
  }, {
    outputRoot: root, writerContext: writer(fixture.run_id),
    registryEntry: registration("rejections"), ledgerSettings: settings,
  });
  const curation = curateArticles({
    articles: screening.admitted.map(article => ({
      ...article, evidence: {
        publisher: null, parent_domain: null, operational: null, primary_evidence: null,
        estimated_work: article.candidate.word_count,
      },
    })),
    planning, opportunity: { covered_event_clusters: null, underrepresented_verticals: null, origin: null },
    observed_at: fixture.observed_at,
  });
  const persisted = await persistPortfolio(curation, {
    outputRoot: root, writerContext: writer(fixture.run_id), ledgerSettings: settings, date: fixture.date,
    registrations: { selections: registration("editorial-selections"), rejections: registration("rejections") },
  });
  return { fixture, context, planning, candidates, screening, curation, persisted };
}

export async function readWritten<T extends object>(
  root: string, ledger: Parameters<typeof readLedgerDay>[0]["ledger"], day: string,
  contract: LedgerRowContract<T>, written: PersistLedgerResult,
) {
  if (written.status === "skipped") throw new Error("Fixture ledger was skipped");
  return readLedgerDay({ ledger, day, contract, rawFiles: written.files.map(file => join(root, file.path)) });
}
export async function writeRows<T extends object>(
  root: string, ledger: string, day: string, schema: LedgerRowContract<T>["schema"],
  rows: readonly T[], identity: WriterIdentity,
) {
  return persistLedger({
    ledger, outputRoot: root, writerContext: identity, registryEntry: registration(ledger),
    ledgerSettings: settings, rowContract: { schema, schemaVersion: CONTRACT_VERSION },
    period: { tier: "raw", covers: day }, rows,
  });
}
