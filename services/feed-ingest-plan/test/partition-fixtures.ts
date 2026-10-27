/** Build a bounded real screening -> curation -> metadata write from recorded work sizes. */
import { randomUUID } from "node:crypto";
import { relative, resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  FeedIngestCandidateSchema, ParsedFeedBatchSchema, SelectedArticleRowContract,
  WriterIdentitySchema, deriveCandidateId, deriveUrlKey, selectedArticleMetadata,
} from "@idhazh/common-contracts";
import type { WriterIdentity } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, LedgerRowContract, LedgerSettings, PersistLedgerResult } from "@idhazh/ledger-file-writer";
import { loadPlanningConfig } from "../src/config/resolve-policy";
import { curateArticles } from "../src/curate-article-portfolio/editorial-selection";
import { screenArticleCandidates } from "../src/screen-article-candidates/triage-gates";
import { readPlannerDay } from "../src/read-ledger-history/read-planner-history";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { resolveRunContext } from "../src/resolve-run-context";
import { fixtureGit } from "./publication-recordings";

export type HistoryFixture = {
  date: string; run_id: string; correlation_id: string; observed_at: string;
  word_work: number[]; bin_pack_workers: number[]; bin_pack_work: number[];
  round_robin_workers: number[]; round_robin_work: number[];
};
export const settings: LedgerSettings = { format: "parquet", compression_raw: "snappy", compression_compact: "zstd" };
export function registration(name: string): LedgerRegistration {
  const planner = ["discovered-articles", "selected-articles", "feed-health-state", "plan-runs"].includes(name);
  return {
    name, family: planner ? "feed-ingest-plan" : name, grain: "raw-and-compact",
    lifecycle_status: "active", prefix: planner ? ["feed-ingest-plan", name] : [name],
  };
}
export function writer(runId: string, attempt = 1, shard = 0): WriterIdentity {
  return WriterIdentitySchema.parse({
    run_id: runId, attempt, job: null, pipeline_name: "plan", task_name: "persist-selected-articles",
    shard, producer: "tests.partition", git_sha: "a".repeat(40),
  });
}
export async function fixtureInput(root: string, options: { count?: number; freshness?: number; words?: number[] } = {}) {
  const [fixture, loaded] = await Promise.all([
    Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/ledger-history.json", import.meta.url)).json() as Promise<HistoryFixture>,
    loadPlanInputs(fileURLToPath(new URL("../../../", import.meta.url))),
  ]);
  const planning = loadPlanningConfig({
    ...loaded.harvest.config,
    triage: { ...loaded.harvest.config.triage, min_words_article: 1 },
    curate: {
      ...loaded.harvest.config.curate, article_limit: null, exploration_slot_share: 0,
      source_authority_weight: 0, base_source_allowance: 20, bonus_unique_evidence: 0,
      soft_caps: {
        ...loaded.harvest.config.curate.soft_caps, max_source_share: 1,
        max_parent_domain_share: 1, min_distinct_sources: 1,
      },
      mmr_weights: { lambda_source: 0, lambda_source_kind: 0, lambda_domain: 0 },
    },
  });
  const inputs = {
    ...loaded, root, outputRoot: root,
    harvest: { ...loaded.harvest, ...planning },
  };
  const context = resolveRunContext(
    loaded.settings, "a".repeat(40), new Date(fixture.observed_at),
    fixture.run_id.slice(11), "a2742c40-bc4e-461b-9f0f-5e8ab9c58c04",
  );
  const overrides = options.freshness === undefined ? {} : { freshness_hours: options.freshness };
  const words = options.words ?? fixture.word_work.slice(0, options.count ?? fixture.word_work.length);
  const candidates = words.map((work, ordinal) => {
    const sourceId = `source-${ordinal}`;
    const url = `https://example.org/article-${ordinal}`;
    return FeedIngestCandidateSchema.parse({
      date: fixture.date, run_id: fixture.run_id, correlation_id: context.correlation_id,
      candidate_id: deriveCandidateId(fixture.run_id, sourceId, ordinal), entry_ordinal: ordinal,
      source_id: sourceId,
      source: {
        source_id: sourceId, feed_url: "https://example.org/feed", title: "Recorded source",
        kind: "reporting", tier: 1, form: "article", status: "active",
        weight: 1, applied_tier_weight: 1,
      },
      canonical_url: url, url_key: deriveUrlKey(url), title: `Recorded article ${ordinal}`,
      article_text: Array(work).fill(`word${ordinal}`).join(" "), word_count: work,
      categories: [], author: null, fetched_at: fixture.observed_at,
      published_at: new Date(Date.parse(fixture.observed_at) - ordinal * 3_600_000).toISOString().replace(".000Z", "Z"),
    });
  });
  const screening = await screenArticleCandidates({
    candidates, observations: {}, seen: { availability: "unavailable" }, planning,
    clock_config: { collect: { max_future_hours: 1 } },
    run: { now: fixture.observed_at, run_id: context.run_id, correlation_id: context.correlation_id, overrides },
  });
  const batch = ParsedFeedBatchSchema.parse({
    batch_id: randomUUID(), config_sha256: "b".repeat(64), context, request: overrides,
    candidates,
    observations: Object.fromEntries(candidates.map(candidate => [candidate.candidate_id, {
      candidate_id: candidate.candidate_id, http_status: 200, paywall: false, robots: "allowed",
      fetch_failure: null, extraction: "success", paywall_evidence: "none", observed_at: context.now,
    }])),
    seen: { availability: "unavailable" },
    evidence: Object.fromEntries(candidates.map(candidate => [candidate.candidate_id, {
      parent_domain: null, primary_evidence: null, estimated_work: candidate.word_count,
    }])),
    history_rows: [], history_days: [], work_rows: [], exclusions: [],
  });
  const curation = curateArticles({
    articles: screening.admitted, batch, inputs, health: new Map(), selectionStartedAt: context.now,
    publications: { day: fixture.date, availability: "unavailable", counts: new Map() },
  });
  const written = await persistLedger({
    ledger: "selected-articles", outputRoot: root, writerContext: context.writer,
    registryEntry: inputs.registrations.selected_articles, ledgerSettings: settings,
    rowContract: SelectedArticleRowContract, period: { tier: "raw", covers: fixture.date },
    rows: curation.articles.map(article => ({
      ...selectedArticleMetadata(article), run_id: context.run_id, attempt: context.writer.attempt, date: context.date,
    })),
  });
  return { fixture, context, planning, inputs, batch, candidates, screening, curation, written };
}

export async function readWritten<T extends object>(
  root: string, ledger: string, day: string, contract: LedgerRowContract<T>, written: PersistLedgerResult,
) {
  if (written.status === "skipped") throw new Error("Fixture ledger was skipped");
  return readPlannerDay(root, registration(ledger), {
    day, raw_files: written.files.map(file => join(root, file.path)),
  }, contract);
}
export async function writeRows<T extends object>(
  root: string, ledger: string, day: string, contract: LedgerRowContract<T>, rows: readonly T[],
  identity: WriterIdentity | null = null,
) {
  return persistLedger({
    ledger, outputRoot: root, ...(identity === null ? {} : { writerContext: identity }), registryEntry: registration(ledger),
    ledgerSettings: settings, rowContract: contract, period: { tier: "raw", covers: day }, rows,
    ...(ledger === "feed-health-state" ? { updatedAt: `${day}T23:59:59.123Z` } : {}),
  });
}

export async function commitFixtureFiles(repositoryRoot: string, paths: readonly string[]) {
  if (paths.length === 0) return;
  try {
    const top = await fixtureGit(repositoryRoot, ["rev-parse", "--show-toplevel"]);
    if (resolve(top) !== resolve(repositoryRoot)) {
      await fixtureGit(repositoryRoot, ["init", "--initial-branch=main"]);
    }
  } catch { await fixtureGit(repositoryRoot, ["init", "--initial-branch=main"]); }
  await fixtureGit(repositoryRoot, ["add", "--", ...paths]);
  await fixtureGit(repositoryRoot, ["commit", "--allow-empty", "-m", "Record planner fixture files"]);
}

export async function compactRows<T extends object>(
  root: string, ledger: string, day: string, contract: LedgerRowContract<T>, rows: readonly T[],
  period: "daily" | "monthly" | "yearly", repositoryRoot = root,
) {
  const covers = day.slice(0, period === "daily" ? 10 : period === "monthly" ? 7 : 4);
  const written = await persistLedger({
    ledger, outputRoot: root, registryEntry: registration(ledger),
    ledgerSettings: settings, rowContract: contract, period: { tier: "compact", period, covers, builtFrom: 1 }, rows,
    ...(ledger === "feed-health-state" ? { updatedAt: `${day}T23:59:59.123Z` } : {}),
  });
  const file = written.files[0];
  if (file !== undefined) {
    const path = relative(repositoryRoot, join(root, file.path)).replaceAll("\\", "/");
    await commitFixtureFiles(repositoryRoot, [path]);
  }
  return { written, path: file === undefined ? undefined : join(root, file.path) };
}
