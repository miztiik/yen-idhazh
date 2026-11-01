/** Run a real recorded HTTP collection with native historical files and no Git executable. */
import assert from "node:assert/strict";
import { mkdtemp, readFile, realpath, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import {
  DiscoveredArticleRowContract, FeedHealthStateRowContract, ItemHealthFailureCodeSchema,
  ParsedFeedBatchSchema, SelectedFeedBatchSchema, SelectedArticleRowContract, SelectedArticlesArtifactSchema,
  selectedArticleMetadata, PLANNER_API_PREFIX,
} from "@idhazh/common-contracts";
import { persistLedger, readPlannerParquet } from "@idhazh/ledger-file-writer";
import { loadPlanInputs } from "../src/load-plan-inputs";
import type { PlanRuntime } from "../src/run-feed-plan";
import { deriveArticleIdentity } from "../src/harvest-feeds/article-identity";
import { inputEndpointKey } from "../src/read-ledger-history/health-summary";
import { ItemHealthPublicationSchema, PublishedRowSchema, PUBLISHED_ROW_SCHEMA_VERSION } from "../src/metrics/publication-evidence";
import { ITEM_HEALTH_ROW_SCHEMA_VERSION } from "../src/read-ledger-history/item-health-version";
import { stageStore } from "../src/api/stage-store";
import { getCollection } from "../src/api/collection-operation";
import { currentExecutionState } from "../src/api/document-state";
import { CollectionResponseSchema, CompletedCollectionSchema } from "../src/api/collection-contracts";
import { FetchResponseSchema, ParseResponseSchema } from "../src/api/document-response.schema";
import { SelectionResponseSchema, PersistenceResponseSchema } from "../src/api/stage-response.schema";
import { FeedHealthStateUpdateResponseSchema } from "../src/api/feed-health-state.schema";
import { plannerRecordings } from "../../../packages/ledger-file-writer/test/planner-recordings";
import { settings, registration, writer, writeRows } from "./partition-fixtures";
import { createPlanTestServer } from "./plan-test-server";
import { inputs as harvestInputs, readRecordings, RecordedTransport, source } from "./harvest-recordings";
import { rewriteHealthFields } from "./health-field-fixtures";
import { randomUUID } from "node:crypto";

async function runRecording() {
  const root = await mkdtemp(join(tmpdir(), "planner-file-baseline-"));
  try { return await runRecordingAt(root); }
  finally { await rm(root, { recursive: true, force: true }); }
}

async function runRecordingAt(root: string) {
  assert.equal(Bun.which("git"), null, "Git must be unavailable throughout the real execution");
  const sourceRoot = fileURLToPath(new URL("../../../", import.meta.url));
  assert.equal(await realpath(sourceRoot), await realpath(process.env.IDHAZH_ORACLE_SOURCE_ROOT!));
  for (const name of ["common-contracts", "ledger-file-writer"]) {
    assert.equal(await realpath(fileURLToPath(import.meta.resolve(`@idhazh/${name}`))),
      await realpath(join(sourceRoot, "packages", name, "src", "index.ts")));
  }
  const stateRoot = join(root, "state");
  const day = "2026-10-21";
  const prior = "2026-10-20";
  const now = `${day}T12:00:00Z`;
  const publishers = [{ id: "recorded-publisher", display_name: "Recorded publisher" }];
  const sources = [source({ publisher_id: publishers[0]!.id }),
    source({ id: "recorded-atom", url: "https://atom.example/feed.xml", publisher_id: publishers[0]!.id }),
    source({ id: "recorded-resting", url: "https://news.example/gone.xml" })];
  const [loaded, harvest, recordings] = await Promise.all([
    loadPlanInputs(sourceRoot), harvestInputs(sources, { publishers }), readRecordings(),
  ]);
  harvest.config.triage.min_words = 100;
  harvest.config.discovered_articles.lookback_days = 3;
  harvest.config.curate_articles.soft_caps.max_source_share = 1;
  harvest.config.curate_articles.soft_caps.max_website_group_share = 1;
  harvest.config.curate_articles.source_based_quality_buckets = harvest.registry.source_tiers
    .filter(tier => tier.status === "active").map(tier => ({
      id: `source-tier-${tier.id}`, source_tier_id: tier.id,
      share_pct: tier.id === harvest.sources[0]!.tier ? 100 : 0, buffer_pct: 0, ladder_hours: [48],
    }));
  harvest.config.partition.enabled = false;
  const transport = new RecordedTransport(recordings);
  const runtime: PlanRuntime = { git_sha: "a".repeat(40), run_number: "7300", clock: () => new Date(now),
    observation_clock: () => new Date(now), boundary: { transport } };
  const key = (url: string) => deriveArticleIdentity(url, harvest.config.harvest).url_key;
  const discovery = { url_key: key("https://news.example/second"), first_seen_at: `${prior}T10:00:00Z`, date: prior };
  const seed = FeedHealthStateRowContract.schema.parse(
    plannerRecordings(prior).find(record => record.name === "feed-health-state")!.row,
  );
  assert(seed.feed_requests !== null && seed.article_requests !== null);
  const healthRows = sources.map(feed => FeedHealthStateRowContract.schema.parse({
    ...seed, feed_id: feed.id, endpoint_key: inputEndpointKey(feed.url),
    availability: feed.id === "recorded-resting" ? "resting" : "eligible",
    strikes: feed.id === "recorded-resting" ? 5 : 0,
    rest_until: feed.id === "recorded-resting" ? "2026-10-22T10:00:00Z" : null,
    first_confirmed_failure_at: feed.id === "recorded-resting" ? `${prior}T06:00:00Z` : null,
    reliability: { productive: 4, attempted: 5, success_fraction: 0.8, production_factor: 0.8,
      from_day: prior, through_day: prior, complete: true },
  }));
  const selectedSeed = plannerRecordings(day).find(record => record.name === "selected-articles")!.row;
  const snapshot = SelectedArticleRowContract.schema.parse({
    ...selectedSeed, feed_id: sources[0]!.id, publisher_id: publishers[0]!.id,
    canonical_url: "https://news.example/story/", url_key: key("https://news.example/story/"),
  });
  const published = { version: PUBLISHED_ROW_SCHEMA_VERSION, published_on: day,
    url_key: snapshot.url_key, item_id: "recorded-item-01" };
  const publicationHealth = { date: day, run_id: snapshot.run_id, item_id: published.item_id,
    url_key: snapshot.url_key, source_id: snapshot.feed_id, stage: "publish" as const, outcome: "ok" as const, code: null };
  const failure = { ...publicationHealth, item_id: "recorded-item-02",
    url_key: key("https://atom.example/undated"), source_id: sources[1]!.id, outcome: "failed" as const, code: "no_text" as const };
  const healthContract = { schema: ItemHealthPublicationSchema.extend({ code: ItemHealthFailureCodeSchema.nullable() }),
    schemaVersion: ITEM_HEALTH_ROW_SCHEMA_VERSION };
  const publishedContract = { schema: PublishedRowSchema, schemaVersion: PUBLISHED_ROW_SCHEMA_VERSION };
  const rawHealth = await writeRows(stateRoot, "feed-health-state", prior, FeedHealthStateRowContract, healthRows);
  await writeRows(stateRoot, "discovered-articles", prior, DiscoveredArticleRowContract, [discovery]);
  const compact = async <T extends object>(ledger: string, contract: import("@idhazh/ledger-file-writer").LedgerRowContract<T>,
    rows: T[], covers: string, period: "daily" | "monthly") => persistLedger({
      ledger, rowContract: contract, rows, registryEntry: registration(ledger), outputRoot: stateRoot,
      ledgerSettings: settings, period: { tier: "compact", period, covers, builtFrom: 1 },
      ...(ledger === "feed-health-state" ? { updatedAt: `${prior}T23:59:59.123Z` } : {}),
    });
  await compact("feed-health-state", FeedHealthStateRowContract, healthRows, "2026-10", "monthly");
  await compact("discovered-articles", DiscoveredArticleRowContract, [discovery], prior, "daily");
  const selections = await writeRows(stateRoot, "selected-articles", day, SelectedArticleRowContract, [snapshot]);
  const publications = await writeRows(stateRoot, "published", day, publishedContract, [published], writer(snapshot.run_id));
  const itemHealth = await writeRows(stateRoot, "item-health", day, healthContract, [publicationHealth, failure], writer(snapshot.run_id));
  const inputs = { ...loaded, root, outputRoot: join(root, "output", "state"), harvest, settings: {
    ...loaded.settings, enabled: true, listener: { ...loaded.settings.listener, parser_concurrency: 2 },
    inputs: { ...loaded.settings.inputs, published_days: [{ day, raw_files: publications.files.map(file => `state/${file.path}`) }],
      settled_failure_days: [{ day, raw_files: itemHealth.files.map(file => `state/${file.path}`) }],
      feed_health_days: [{ day: prior }] },
  } };
  inputs.clock_config.collect.reliability_window_days = 1;
  inputs.harvest.config.feedback.lifecycle_window_days = 1;
  const app = createPlanTestServer(inputs, runtime);
  const post = async <T>(path: string, body: unknown, schema: z.ZodType<T>) => {
    const response = await app.request(`${PLANNER_API_PREFIX}/${path}`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
    });
    const result: unknown = await response.json();
    assert.equal(response.status, 200, JSON.stringify(result));
    return schema.parse(result);
  };
  try {
    const collectionId = randomUUID();
    const begun = await post("collections", { collection_id: collectionId, request: {} }, CollectionResponseSchema);
    assert.deepEqual(begun.feeds.sort(), ["recorded-atom", "recorded-news"]);
    assert.equal(transport.requests.length, 0, "All history must load before the first source request");
    const collection = getCollection(inputs, collectionId);
    const baseline = structuredClone(collection.state.baseline);
    assert.equal(baseline.publications.get(day)!.counts.get("recorded-publisher"), 1);
    assert.equal(baseline.discovered.rows.find(row => row.url_key === discovery.url_key)!.first_seen_at, discovery.first_seen_at);
    const changedHealth = healthRows.map(row => ({ ...row, availability: "eligible" as const, strikes: 0,
      rest_until: null, first_confirmed_failure_at: null,
      feed_requests: 99, article_requests: 99, robots_requests: 99,
      reliability: { ...row.reliability!, productive: 1, attempted: 1, success_fraction: 1, production_factor: 1 } }));
    await rewriteHealthFields(join(stateRoot, rawHealth.files[0]!.path), changedHealth, z.object(FeedHealthStateRowContract.schema.shape));
    await compact("feed-health-state", FeedHealthStateRowContract, changedHealth, "2026-10", "monthly");
    await writeRows(stateRoot, "feed-health-state", prior, FeedHealthStateRowContract,
      changedHealth.map(row => ({ ...row, attempt: 2 })));
    const earlierDiscovery = await writeRows(stateRoot, "discovered-articles", "2026-10-18", DiscoveredArticleRowContract,
      [{ ...discovery, date: "2026-10-18", first_seen_at: "2026-10-18T00:00:00Z" }]);
    await compact("discovered-articles", DiscoveredArticleRowContract,
      [{ ...discovery, first_seen_at: `${prior}T01:00:00Z` }], prior, "daily");
    await rm(join(stateRoot, selections.files[0]!.path));
    await writeRows(stateRoot, "selected-articles", day, SelectedArticleRowContract,
      [{ ...snapshot, attempt: 2, publisher_id: "changed-publisher" }]);
    const newPublication = await writeRows(stateRoot, "published", day, publishedContract,
      [{ ...published, url_key: key("https://atom.example/entry") }], writer(`${day}-44`));
    for (const file of publications.files) await rm(join(stateRoot, file.path));
    for (const file of itemHealth.files) await rm(join(stateRoot, file.path));
    for (const feedId of begun.feeds) {
      const fetched = await post("fetch", { request_id: randomUUID(), collection_id: collectionId,
        feed_id: feedId, correlation_id: begun.context.correlation_id, fetch_item_type: "feed" }, FetchResponseSchema);
      const parsed = await post("parse", { request_id: randomUUID(), fetch_request_id: fetched.fetch_request_id,
        article_id: fetched.article_id, correlation_id: begun.context.correlation_id }, ParseResponseSchema);
      assert(parsed.fetch_item_type === "feed");
      for (const offer of parsed.offers) {
        const article = await post("fetch", { request_id: randomUUID(), batch_id: parsed.batch_id, offer_id: offer.offer_id,
          feed_id: feedId, correlation_id: begun.context.correlation_id, fetch_item_type: "article" }, FetchResponseSchema);
        await post("parse", { request_id: randomUUID(), fetch_request_id: article.fetch_request_id,
          article_id: article.article_id, correlation_id: begun.context.correlation_id }, ParseResponseSchema);
      }
    }
    const completed = await post("collections/complete", { collection_id: collectionId }, CompletedCollectionSchema);
    const parsed = stageStore(inputs).read("parsed", completed.batch_id, ParsedFeedBatchSchema);
    assert.equal(parsed.discovered.availability, "available");
    if (parsed.discovered.availability === "available") {
      assert.equal(parsed.discovered.rows.find(row => row.url_key === discovery.url_key)!.first_seen_at, discovery.first_seen_at);
    }
    const selected = await post("select-articles", { batch_id: completed.batch_id }, SelectionResponseSchema);
    assert.equal(selected.articles.length, 2);
    assert.equal(selected.request_report.feeds.find(feed => feed.feed_id === "recorded-news")!.feed_requests, seed.feed_requests);
    assert.equal(selected.request_report.feeds.find(feed => feed.feed_id === "recorded-news")!.article_requests, seed.article_requests);
    assert.deepEqual(collection.state.baseline, baseline, "Current work and disk changes must not mutate baseline records");
    const recordedHealth = await post("feed-health-state", { batch_id: selected.batch_id, action: "record" },
      FeedHealthStateUpdateResponseSchema);
    assert.equal(recordedHealth.status, "recorded");
    assert(recordedHealth.files?.status === "written");
    const nativeHealth = await readPlannerParquet(join(inputs.outputRoot, recordedHealth.files.files[0]!.path),
      "feed-health-state", FeedHealthStateRowContract);
    assert(nativeHealth.rows.some(row => row.feed_id === "recorded-news" && (row.feed_requests ?? 0) > 0));
    const persisted = await post("persist-selected-articles", { batch_id: selected.batch_id }, PersistenceResponseSchema);
    assert(persisted.files.status === "written");
    const metadata = await readPlannerParquet(join(inputs.outputRoot, persisted.files.files[0]!.path),
      "selected-articles", SelectedArticleRowContract);
    assert.deepEqual(metadata.rows.map(row => row.canonical_url).sort(),
      ["https://atom.example/entry", "https://news.example/second"]);
    assert.equal(metadata.rows.find(row => row.url_key === discovery.url_key)!.timing_at, discovery.first_seen_at);
    assert(metadata.rows.every(row => row.ratings.adjustments.some(term => term.term === "publisher_exposure" && term.value !== null)));
    const first = metadata.rows.find(row => row.editorial_rank === 1)!;
    const exposure = -harvest.config.curate_articles.mmr_weights.lambda_source
      / harvest.config.curate_articles.article_limit;
    assert.equal(first.ratings.adjustments.find(term => term.term === "publisher_exposure")!.value, exposure === 0 ? 0 : exposure);
    const summary = await post("feed-health-state", { batch_id: selected.batch_id, action: "summarize" },
      FeedHealthStateUpdateResponseSchema);
    assert(summary.rows.some(row => row.feed_id === "recorded-news" && (row.feed_requests ?? 0) > 0));
    assert.deepEqual(collection.state.baseline, baseline);
    assert.equal(transport.requests.filter(request => request.url.pathname === "/story/").length, 0);
    assert.equal(transport.requests.filter(request => request.url.pathname === "/undated").length, 0);
    runtime.selection_clock = () => new Date("2026-10-22T00:01:00Z");
    const nextDaySelection = await post("select-articles", { batch_id: completed.batch_id }, SelectionResponseSchema);
    assert.equal(nextDaySelection.articles.length, 2);
    assert.equal(nextDaySelection.request_report.through_day, day);
    const currentRequests = collection.state.work.rows().filter(row => row.feed_id === "recorded-news" && row.date === day)
      .reduce((total, row) => total + (row.feed_requests ?? 0), 0);
    assert.equal(nextDaySelection.request_report.feeds.find(feed => feed.feed_id === "recorded-news")!.feed_requests,
      seed.feed_requests + currentRequests);
    assert(nextDaySelection.articles.every(row => row.ratings.adjustments.some(term =>
      term.term === "publisher_exposure_current_run")));
    assert.deepEqual(collection.state.baseline, baseline);
    const freshInputs = { ...inputs, settings: { ...inputs.settings, inputs: { ...inputs.settings.inputs,
      published_days: [{ day, raw_files: newPublication.files.map(file => `state/${file.path}`) }],
      settled_failure_days: [{ day, raw_files: [] }],
    } } };
    const freshApp = createPlanTestServer(freshInputs, { ...runtime, run_number: "7301" });
    try {
      const id = randomUUID();
      const response = await freshApp.request(`${PLANNER_API_PREFIX}/collections`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ collection_id: id, request: {} }),
      });
      assert.equal(response.status, 200, await response.clone().text());
      const newRun = CollectionResponseSchema.parse(await response.json());
      assert(newRun.feeds.includes("recorded-resting"), "An independent execution must load current local evidence");
      assert.notDeepEqual(getCollection(freshInputs, id).state.baseline, baseline);
      await freshApp.request(`${PLANNER_API_PREFIX}/collections/cancel`, {
        method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ collection_id: id }),
      });
      const correlation = randomUUID();
      const standalone = await freshApp.request(`${PLANNER_API_PREFIX}/fetch`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ request_id: randomUUID(), feed_id: "recorded-news", correlation_id: correlation,
          fetch_item_type: "article", url: "https://news.example/second" }),
      });
      assert.equal(standalone.status, 200, await standalone.clone().text());
      const document = FetchResponseSchema.parse(await standalone.json());
      const state = await currentExecutionState(freshInputs, document.run_id);
      assert(state?.kind === "document");
      const standaloneBaseline = structuredClone(state.baseline);
      for (const file of earlierDiscovery.files) await rm(join(stateRoot, file.path));
      await compact("discovered-articles", DiscoveredArticleRowContract,
        [{ ...discovery, first_seen_at: `${prior}T11:00:00Z` }], prior, "daily");
      const parsedResponse = await freshApp.request(`${PLANNER_API_PREFIX}/parse`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ request_id: randomUUID(), fetch_request_id: document.fetch_request_id,
          article_id: document.article_id, correlation_id: correlation }),
      });
      assert.equal(parsedResponse.status, 200, await parsedResponse.clone().text());
      const standaloneParsed = ParseResponseSchema.parse(await parsedResponse.json());
      const choice = await freshApp.request(`${PLANNER_API_PREFIX}/select-articles`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ batch_id: standaloneParsed.batch_id }),
      });
      assert.equal(choice.status, 200, await choice.clone().text());
      const choiceResult = SelectionResponseSchema.parse(await choice.json());
      assert.equal(choiceResult.articles.length, 0, "Standalone selection must retain the captured old first sight");
      assert.deepEqual(state.baseline, standaloneBaseline);
    } finally { await freshApp.close(); }
    assert.equal(Bun.which("git"), null);
    const artifact = SelectedArticlesArtifactSchema.parse(JSON.parse(await readFile(join(root, persisted.artifact), "utf8")));
    const heldSelection = stageStore(inputs).read("selected", selected.batch_id, SelectedFeedBatchSchema);
    assert.deepEqual(artifact.articles.map(article => article.article_text),
      heldSelection.articles.map(article => article.article_text));
    assert(artifact.articles.every(article => article.article_text.trim().length > 0));
    assert.deepEqual(artifact.articles.map(article => ({
      ...selectedArticleMetadata(article), run_id: artifact.run_id, attempt: artifact.attempt, date: artifact.date,
    })).sort((left, right) => left.editorial_rank - right.editorial_rank),
    [...metadata.rows].sort((left, right) => left.editorial_rank - right.editorial_rank));
    return { git_unavailable: true, source_matches_requested: true, loaded_before_fetch: true,
      raw_and_compact: true, baseline_unchanged: true, historical_edits_and_additions: true,
      independent_capture_changed: true, selected_count: metadata.rows.length, native_output_readback: true,
      selection_retained: stageStore(inputs).has(selected.batch_id), standalone_baseline_unchanged: true,
      utc_boundary_reused: true, selected_metadata_readback: true, selected_text_readback: true, health_readback: true };
  } finally { await app.close(); }
}

if (import.meta.main) console.log(JSON.stringify(await runRecording()));
