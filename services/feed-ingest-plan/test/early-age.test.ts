/** Do expired entries stop before page I/O while retaining discovery and grouped health losses? */
import { expect, test } from "bun:test";
import { mkdtemp, rm } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import {
  FeedHealthStateRowContract, FeedIngestCandidateSchema, SelectedArticlesArtifactSchema,
  deriveCandidateId, deriveUrlKey,
} from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import { harvestFeeds } from "../src/harvest-feeds/harvest-pool";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { readExclusionEvidence } from "../src/read-ledger-history/read-exclusion-evidence";
import { ItemHealthFailureProjectionContract, ItemHealthFailureProjectionSchema } from "../src/read-ledger-history/item-health-failure";
import { PUBLISHED_ROW_SCHEMA_VERSION, PublishedRowSchema } from "../src/metrics/publication-evidence";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { collectRecordedFeeds } from "./collection-recordings";
import { executeFeedHealthState } from "../src/api/feed-health-state-operation";
import { parseFeed } from "../src/harvest-feeds/parse-feed";
import { sourceSnapshot } from "../src/harvest-feeds/load-harvest-inputs";
import { readPlannerOutputRecording } from "./planner-output-recordings";
import { recordedPlan } from "./plan-recordings";
import { context, inputs, readRecordings, RecordedTransport } from "./harvest-recordings";
import type { ProgressRecord } from "../src/logging/progress-logger";

function feed(items: { title?: string; path: string; date: string | null }[]) {
  return `<rss version="2.0"><channel><title>Recorded age decisions</title>${items.map(item =>
    `<item>${item.title === undefined ? "" : `<title>${item.title}</title>`}<link>${item.path.startsWith("https://")
      ? item.path : `https://news.example/${item.path}`}</link>${
      item.date === null ? "" : `<pubDate>${item.date}</pubDate>`}</item>`).join("")}</channel></rss>`;
}

test("preflight uses the configured age ladder, strict boundary and future tolerance without fetching expired pages", async () => {
  const root = await mkdtemp(join(tmpdir(), "early-age-"));
  try {
    const recordings = await readRecordings();
    const loaded = await inputs();
    const run = { ...context(), clock: () => new Date("2026-10-22T12:00:00Z") };
    run.writer = { ...run.writer, run_id: "2026-10-22-700" };
    const items = [
      { title: "Expired", path: "stale", date: "2026-10-21T05:59:59Z" },
      { title: "Boundary", path: "boundary", date: "2026-10-22T00:00:00Z" },
      { title: "Undated", path: "undated", date: null },
      { title: "Beyond future tolerance", path: "future", date: "2026-10-23T00:00:00Z" },
      { title: "Within future tolerance", path: "near-future", date: "2026-10-22T13:00:00Z" },
      { path: "untitled-old", date: "2026-10-20T00:00:00Z" },
      { title: "Published", path: "published", date: "2026-10-22T11:00:00Z" },
      { title: "Settled failure", path: "settled", date: "2026-10-22T11:00:00Z" },
      { title: "Blocked marker", path: "https://fool.com/the-ascent/blocked", date: "2026-10-22T11:00:00Z" },
    ];
    recordings.bodies.rss = feed(items);
    for (const item of items.slice(1)) recordings.responses[
      item.path.startsWith("https://") ? item.path : `https://news.example/${item.path}`
    ] = [{ status: 200, fixture: "article" }];
    const transport = new RecordedTransport(recordings);
    const planner = await loadPlanInputs(fileURLToPath(new URL("../../../", import.meta.url)));
    const publishedUrl = "https://news.example/published";
    const settledUrl = "https://news.example/settled";
    const blockedUrl = "https://fool.com/the-ascent/blocked";
    const published = await persistLedger({
      ledger: "published", registryEntry: planner.registrations.published, outputRoot: root,
      ledgerSettings: planner.ledgerSettings,
      rowContract: { schema: PublishedRowSchema, schemaVersion: PUBLISHED_ROW_SCHEMA_VERSION },
      period: { tier: "raw", covers: "2026-10-21" }, writerContext: run.writer,
      rows: [PublishedRowSchema.parse({
        version: PUBLISHED_ROW_SCHEMA_VERSION, url_key: deriveUrlKey(publishedUrl),
        published_on: "2026-10-21", item_id: "published-01",
      })],
    });
    const settled = await persistLedger({
      ledger: "item-health", registryEntry: planner.registrations.item_health, outputRoot: root,
      ledgerSettings: planner.ledgerSettings, rowContract: ItemHealthFailureProjectionContract,
      period: { tier: "raw", covers: "2026-10-22" }, writerContext: run.writer,
      rows: [ItemHealthFailureProjectionSchema.parse({
        date: "2026-10-22", url_key: deriveUrlKey(settledUrl), outcome: "failed", code: "network_error",
      })],
    });
    const history = await readExclusionEvidence({
      root, now: "2026-10-22T12:00:00Z", publishedWindowDays: 1, settledFailureCodes: ["network_error"],
      publishedRegistration: planner.registrations.published, itemHealthRegistration: planner.registrations.item_health,
      publishedDays: [{ day: "2026-10-21", raw_files: published.files.map(file => file.path) }],
      settledFailureDays: [{ day: "2026-10-22", raw_files: settled.files.map(file => file.path) }],
    });
    run.exclusions = { ...history, published_window_days: 1 };
    const result = await harvestFeeds(loaded, run, { transport, resolve: transport.resolve });
    expect(result.rejections.map(row => row.drop_reason).sort()).toEqual([
      "ALREADY_PUBLISHED", "BLOCKED_URL_MARKER", "REJECTED_AGE_EXCEEDS_MAX_TIER_ENVELOPE", "SETTLED_FAILURE",
    ]);
    expect(history.history.published).toMatchObject({ required_day_count: 2, known_day_count: 1 });
    expect(history.history.published.missing_days).toHaveLength(1);
    expect(history.history.settled_failures).toMatchObject({ required_day_count: 1, known_day_count: 1 });
    for (const path of ["/stale", "/published", "/settled"]) expect(transport.requests.some(request => request.url.pathname === path)).toBe(false);
    expect(transport.requests.some(request => request.url.href === blockedUrl)).toBe(false);
    expect(result.rejections.find(row => row.drop_reason === "ALREADY_PUBLISHED")).toMatchObject({
      details: { matched_url_key: deriveUrlKey(publishedUrl), published_on: "2026-10-21", history_window_days: 1 },
    });
    expect(result.rejections.find(row => row.drop_reason === "SETTLED_FAILURE")).toMatchObject({
      details: { matched_url_key: deriveUrlKey(settledUrl), failure_code: "network_error" },
    });
    expect(result.rejections.find(row => row.drop_reason === "BLOCKED_URL_MARKER")).toMatchObject({
      url_key: deriveUrlKey(blockedUrl), details: { matched_url_key: deriveUrlKey(blockedUrl), matched_url_marker: "fool.com/the-ascent/" },
    });
    const early = result.articles[0]!;
    expect(early.rejection?.details.age_hours).toBeCloseTo(30 + 1 / 3600, 8);
    expect(early.rejection?.details.max_age_hours).toBe(30);
    expect(early.observation).toMatchObject({
      extraction: "not-attempted", http_status: null, paywall: null, robots: null,
      preflight_freshness: { timing_source: "published_at", timing_at: items[0]!.date },
    });
    expect(result.candidates.map(row => row.entry_ordinal)).toEqual([1, 2, 3, 4, 5]);
    expect(result.candidates.every(row => row.candidate_id === deriveCandidateId(run.writer.run_id, row.feed_id, row.entry_ordinal))).toBe(true);
    expect(result.discovered_candidates.map(row => row.url_key)).toContain(deriveUrlKey(publishedUrl));
    expect(result.discovered_candidates.map(row => row.url_key)).toContain(deriveUrlKey(settledUrl));
    expect(result.discovered_candidates.map(row => row.url_key)).not.toContain(deriveUrlKey(blockedUrl));
    expect(result.feed_outcomes[0]).toMatchObject({ parsed_count: 9, harvested_count: 5 });
    expect(result).not.toHaveProperty("rejection_files");
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("collection records early losses once in native health counters without fetching stale pages", async () => {
  const fixture = await recordedPlan();
  try {
    const progress: ProgressRecord[] = [];
    fixture.runtime.progress = event => { progress.push(event); };
    fixture.transport.recordings.bodies.rss = feed([
      { title: "Expired first", path: "stale-one", date: "2026-10-19T10:00:00Z" },
      { title: "Expired second", path: "stale-two", date: "2026-10-19T11:00:00Z" },
    ]);
    const { batch } = await collectRecordedFeeds(fixture.inputs, fixture.runtime);
    const summary = await executeFeedHealthState({ batch_id: batch.batch_id, action: "record" }, fixture.inputs, fixture.runtime);
    expect(fixture.transport.requests.some(request => request.url.pathname.startsWith("/stale-"))).toBe(false);
    expect(progress.filter(event => event.feed_id === "recorded-news"
      && ["ARTICLE_HARVEST_STARTED", "ARTICLE_HARVEST_COMPLETED"].includes(event.eventType))).toHaveLength(0);
    const rows = (await Promise.all(summary.files!.files.map(file =>
      readPlannerParquet(join(fixture.inputs.outputRoot, file.path), "feed-health-state", FeedHealthStateRowContract)))).flatMap(file => file.rows);
    const stale = rows.find(row => row.feed_id === "recorded-news")!;
    expect(stale).toMatchObject({ items: 2, outcome: "ok", feed_reads: 1, productive_reads: 1, article_candidates: 0, articles_selected: 0 });
    expect(stale.rejection_counts).toEqual([{
      subject: "article", stage: "harvest-feeds", reason_code: "REJECTED_AGE_EXCEEDS_MAX_TIER_ENVELOPE", attribution: null, count: 2,
    }]);
    const discoveries = batch.discovered.availability === "available" ? batch.discovered.rows : [];
    for (const path of ["stale-one", "stale-two"]) expect(discoveries.some(row =>
      row.url_key === deriveUrlKey(`https://news.example/${path}`))).toBe(true);
  } finally { await fixture.close(); }
});

test("empty RSS and Atom category labels stay valid through candidate and selected models", async () => {
    const recordings = await readRecordings();
    const rss = feed([
      { title: "Current", path: "second", date: "2026-10-21T12:00:00Z" },
    ]).replace("</item>", "<category/><category>  </category><category>Science</category></item>");
    const atom = recordings.bodies.atom.replace(
      "<entry>", '<entry><category term=" "/><category term=""/>',
    );
    const { artifact: recorded, response } = await readPlannerOutputRecording();
    const configured = await inputs();
    const article = recorded.articles[0]!;
    const entries = [...await parseFeed(rss), ...await parseFeed(atom)];
    const candidates = entries.map((entry, ordinal) => FeedIngestCandidateSchema.parse({
      date: recorded.date, run_id: recorded.run_id, correlation_id: response.correlation_id,
      candidate_id: deriveCandidateId(recorded.run_id, article.feed_id, ordinal), entry_ordinal: ordinal,
      feed_id: article.feed_id, source: sourceSnapshot(configured, configured.sources[0]!),
      canonical_url: article.canonical_url, url_key: article.url_key, title: entry.title ?? article.title,
      article_text: article.article_text, word_count: article.article_text.split(/\s+/).length,
      categories: entry.categories, author: entry.author, published_at: entry.published_at, fetched_at: recorded.evaluated_at,
    }));
    const artifact = SelectedArticlesArtifactSchema.parse({ ...recorded,
      articles: candidates.map(candidate => ({ ...article, categories: candidate.categories })),
    });
    const categories = artifact.articles.map(row => row.categories);
    expect(categories).toContainEqual(["Science"]);
    expect(categories.every(values => values.every(value => value.length > 0))).toBe(true);
});
