/** Do compatible article generations retain their original identities and captured output? */
import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import {
  DISCOVERED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS, DISCOVERED_ARTICLE_VERSION,
  DiscoveredArticleRowContract, DiscoveredArticleRowSchema,
  FEED_INGEST_CANDIDATE_VERSION, FeedIngestCandidateSchema, FetchedDocumentSchema,
  LEGACY_DISCOVERED_ARTICLE_VERSION, LEGACY_OPERATION_VERSION,
  LEGACY_PLANNER_OPERATION_VERSION, LEGACY_SELECTED_ARTICLE_VERSION,
  OPERATION_VERSION, PARSED_FEED_BATCH_VERSION, PLANNER_ENVELOPE_ACCEPTED_SCHEMA_VERSIONS,
  PLANNER_ENVELOPE_VERSION, PLANNER_LEDGER_VERSION, PLANNER_OPERATION_VERSION,
  ParsedFeedBatchSchema, PlannerFileEnvelopeSchema, PlannerOperationSchema,
  SELECTED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS, SELECTED_ARTICLE_VERSION,
  SelectedArticleRowContract, SelectedArticleRowSchema, readSelectedArticlesArtifact,
  deriveUrlKey,
} from "../src";
import type { SelectedArticleRow } from "../src";

const day = "2026-10-28";
const at = `${day}T12:00:00.123Z`;
const url = "https://example.org/article?edition=morning&utm_source=feed";
const run = `${day}-1`;
function selectedRow(): SelectedArticleRow {
  return {
    run_id: run, attempt: 1, date: day, url_key: deriveUrlKey(url), feed_id: "fixture-feed",
    publisher_id: null, canonical_url: url, title: "Recorded article", categories: [],
    author: null, published_at: at, published_at_source: "selection",
    tier: 1, weight: 1, applied_tier_weight: 1, editorial_rank: 1,
    estimated_work: 3, worker_assignment: null, feed_limit: 1, exploration_slot: false,
    cap_relaxations: [], timing_at: at, timing_basis: "first_seen", age_hours: 0,
    freshness_cutoff_at: null,
    ratings: {
      base_article_score: 1, marginal_score: 1, adjustments: [],
      recency_score: 1, feed_authority_score: 0,
    },
  };
}
function envelope(ledger: "discovered-articles" | "selected-articles", stamp: string, version: string) {
  return {
    version, row_schema_version: stamp, ledger, tier: "raw", covers: day,
    file_id: "0199ba8e-9920-8000-8000-000000000001", content_sha256: "a".repeat(64),
    writer: "idhazh_typescript.ledger.parquet", writer_version: "recording", compression: "snappy",
    period: null, updated_at: null,
  };
}

test("discovery and selected generations keep opaque keys, exact URLs and text", () => {
  expect(PLANNER_LEDGER_VERSION).toBe("2026-10-25");
  expect(DiscoveredArticleRowContract.schemaVersion).toBe(DISCOVERED_ARTICLE_VERSION);
  expect(DiscoveredArticleRowContract.acceptedSchemaVersions).toEqual(DISCOVERED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS);
  expect(SelectedArticleRowContract.schemaVersion).toBe(SELECTED_ARTICLE_VERSION);
  expect(SelectedArticleRowContract.acceptedSchemaVersions).toEqual(SELECTED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS);
  const discovery = { url_key: deriveUrlKey(url), date: day, first_seen_at: at };
  expect(DiscoveredArticleRowSchema.parse(discovery)).toEqual(discovery);
  const row = selectedRow();
  expect(SelectedArticleRowSchema.parse(row)).toEqual(row);
  const { run_id, attempt, date, ...metadata } = row;
  for (const schema_version of SELECTED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS) {
    const artifact = {
      schema_version, run_id, attempt, date, evaluated_at: at,
      articles: [{ ...metadata, article_text: "Saved text.\nKeep these bytes." }],
    };
    expect(readSelectedArticlesArtifact(artifact)).toEqual(artifact);
    expect(() => readSelectedArticlesArtifact({
      ...artifact, articles: [{ ...artifact.articles[0], url_key: deriveUrlKey("https://example.org/article") }],
    })).toThrow();
    expect(() => readSelectedArticlesArtifact({ ...artifact, schema_version: "2026-10-26" })).toThrow();
    expect(() => readSelectedArticlesArtifact({ ...artifact, schema_version: "2026-10-25" })).toThrow();
  }
});

test("both envelope checks admit only the declared per-ledger generations", () => {
  for (const version of PLANNER_ENVELOPE_ACCEPTED_SCHEMA_VERSIONS) {
    const stamp = LEGACY_DISCOVERED_ARTICLE_VERSION;
    const original = envelope("discovered-articles", stamp, version);
    expect<unknown>(original).toEqual(PlannerFileEnvelopeSchema.parse(original));
  }
  for (const version of ["2026-10-27", PLANNER_ENVELOPE_VERSION]) {
    expect(PlannerFileEnvelopeSchema.parse(envelope("selected-articles", LEGACY_SELECTED_ARTICLE_VERSION, version))
      .row_schema_version).toBe(LEGACY_SELECTED_ARTICLE_VERSION);
  }
  for (const [ledger, stamp] of [
    ["discovered-articles", DISCOVERED_ARTICLE_VERSION],
    ["selected-articles", SELECTED_ARTICLE_VERSION],
  ] as const) {
    expect(PlannerFileEnvelopeSchema.parse(envelope(ledger, stamp, PLANNER_ENVELOPE_VERSION)).version)
      .toBe(PLANNER_ENVELOPE_VERSION);
    expect(PlannerFileEnvelopeSchema.safeParse(envelope(ledger, stamp, "2026-10-27")).success).toBe(false);
    expect(PlannerFileEnvelopeSchema.safeParse(envelope(ledger, "2026-10-26", PLANNER_ENVELOPE_VERSION)).success).toBe(false);
  }
  expect(PlannerFileEnvelopeSchema.safeParse(envelope("selected-articles", "2026-10-25", PLANNER_ENVELOPE_VERSION)).success).toBe(false);
  expect(PlannerFileEnvelopeSchema.safeParse(envelope("discovered-articles", "2026-10-27", PLANNER_ENVELOPE_VERSION)).success).toBe(false);
});

test("completed legacy feed and article receipts retain their version, body and serialized response", async () => {
  const recording = await Bun.file(new URL("../../../tests/fixtures/contracts/fetched-document/refused.json", import.meta.url)).json();
  const journal = await Bun.file(new URL("../../../tests/fixtures/contracts/planner-operation/started.json", import.meta.url)).json();
  const body = "Recorded response.\nNo replacement or cleanup.";
  for (const fetch_item_type of ["feed", "article"]) {
    const document = {
      ...recording, version: LEGACY_OPERATION_VERSION, fetch_item_type,
      canonical_url: url, article_id: deriveUrlKey(url), body,
      body_sha256: createHash("sha256").update(body).digest("hex"),
      failure: null, robots: "allowed", http_status: 200,
      observation: { ...recording.observation, article_id: deriveUrlKey(url) },
      parent_fetch_request_id: null, parent_batch_id: null, entry_ordinal: null,
    };
    const response_json = `{"url":${JSON.stringify(url)}, "saved": true}\n`;
    const receipt = {
      ...journal, version: LEGACY_PLANNER_OPERATION_VERSION, state: "complete",
      artifact: document, response_json,
    };
    expect(FetchedDocumentSchema.parse(document)).toEqual({ ...document, body_limit: null });
    expect(PlannerOperationSchema.parse(receipt)).toEqual({
      ...receipt, artifact: { ...document, body_limit: null },
    });
    const currentUrl = fetch_item_type === "article" ? url.split("?")[0]! : url;
    const robotsCutoff = FetchedDocumentSchema.parse({
      ...document, version: OPERATION_VERSION, canonical_url: currentUrl,
      article_id: deriveUrlKey(currentUrl), body: null, body_sha256: null,
      failure: "robots-unknown", robots: "unknown", robots_failure: "body-too-large",
      robots_http_status: 200,
      body_limit: { configured_limit_bytes: 30, observed_at_least_bytes: 55 },
      observation: { ...document.observation, article_id: deriveUrlKey(currentUrl) },
    });
    expect(robotsCutoff.body_limit).toEqual({
      configured_limit_bytes: 30, observed_at_least_bytes: 55,
    });
    expect(FetchedDocumentSchema.safeParse({ ...robotsCutoff, body_limit: null }).success).toBe(false);
    expect(FetchedDocumentSchema.parse({
      ...document, version: undefined, canonical_url: currentUrl, article_id: deriveUrlKey(currentUrl),
      observation: { ...document.observation, article_id: deriveUrlKey(currentUrl) },
    }).version).toBe(OPERATION_VERSION);
    if (fetch_item_type === "article") {
      expect(FetchedDocumentSchema.safeParse({ ...document, version: undefined }).success).toBe(false);
    }
    expect(PlannerOperationSchema.parse({ ...receipt, version: undefined }).version).toBe(PLANNER_OPERATION_VERSION);
    expect(FetchedDocumentSchema.safeParse({ ...document, version: "2026-10-27" }).success).toBe(false);
    expect(PlannerOperationSchema.safeParse({ ...receipt, version: "2026-10-27" }).success).toBe(false);
  }
});

test("new candidate and parsed stages emit the cleanup generation and refuse older stages", async () => {
  const candidate = await Bun.file(new URL("../../../tests/fixtures/contracts/feed-ingest-candidate/one-article.json", import.meta.url)).json();
  expect(FeedIngestCandidateSchema.safeParse(candidate).success).toBe(false);
  expect(FeedIngestCandidateSchema.parse({ ...candidate, version: undefined }).version).toBe(FEED_INGEST_CANDIDATE_VERSION);
  expect(FeedIngestCandidateSchema.safeParse({
    ...candidate, version: undefined, canonical_url: url, url_key: deriveUrlKey(url),
  }).success).toBe(false);
  const recording = await Bun.file(new URL("../../../tests/fixtures/contracts/parsed-feed-batch/empty.json", import.meta.url)).json();
  const batch = {
    batch_id: recording.batch_id, config_sha256: recording.config_sha256, context: recording.context,
    request: {}, candidates: [], observations: {}, discovered: { availability: "available", rows: [] },
    evidence: {}, history_rows: [], history_days: [], work_rows: [], exclusions: [],
  };
  expect(ParsedFeedBatchSchema.parse(batch).version).toBe(PARSED_FEED_BATCH_VERSION);
  expect(ParsedFeedBatchSchema.safeParse({ ...batch, version: "2026-10-27T18:30" }).success).toBe(false);
});
