/** Do current planner formats round-trip while older formats refuse without migration? */
import { expect, test } from "bun:test";
import {
  DISCOVERED_ARTICLE_VERSION, SELECTED_ARTICLE_VERSION, PLANNER_ENVELOPE_VERSION,
  OPERATION_VERSION, PLANNER_OPERATION_VERSION, PARSED_FEED_BATCH_VERSION,
  DiscoveredArticleRowSchema, SelectedArticleRowSchema, SelectedArticleMetadataSchema, PlannerFileEnvelopeSchema,
  FetchedDocumentSchema, PlannerOperationSchema, ParsedFeedBatchSchema,
  readSelectedArticlesArtifact, readFeedIngestEvent, FEED_INGEST_EVENT_VERSION, deriveUrlKey,
} from "../src";

const day = "2026-10-28";
const at = `${day}T12:00:00.123Z`;
const url = "https://example.org/article";
const run = `${day}-1`;
function metadata() {
  return SelectedArticleMetadataSchema.parse({
    url_key: deriveUrlKey(url), feed_id: "fixture-feed", publisher_id: null,
    canonical_url: url, title: "Recorded article", categories: [], author: null,
    published_at: at, published_at_source: "selection", tier: 1, weight: 1,
    applied_tier_weight: 1, editorial_rank: 1, estimated_work: 3, worker_assignment: null,
    feed_limit: 1, exploration_slot: false, cap_relaxations: [], timing_at: at,
    timing_basis: "first_seen", age_hours: 0, freshness_cutoff_at: null,
    ratings: { base_article_score: 1, marginal_score: 1, adjustments: [], recency_score: 1, feed_authority_score: 0 },
  });
}

test("current discovery, selection, artifacts and envelopes keep their exact identities", () => {
  const discovery = { url_key: deriveUrlKey(url), date: day, first_seen_at: at };
  expect(DiscoveredArticleRowSchema.parse(discovery)).toEqual(discovery);
  const row = { ...metadata(), run_id: run, attempt: 1, date: day };
  expect(SelectedArticleRowSchema.parse(row)).toEqual(row);
  const artifact = { schema_version: SELECTED_ARTICLE_VERSION, run_id: run, attempt: 1,
    date: day, evaluated_at: at, articles: [{ ...metadata(), article_text: "Recorded sanitized text." }] };
  expect(readSelectedArticlesArtifact(artifact)).toEqual(artifact);
  for (const schema_version of ["2026-10-25", "2026-10-27", "2026-10-29"]) {
    expect(() => readSelectedArticlesArtifact({ ...artifact, schema_version })).toThrow();
  }
  for (const [ledger, row_schema_version] of [
    ["discovered-articles", DISCOVERED_ARTICLE_VERSION], ["selected-articles", SELECTED_ARTICLE_VERSION],
  ] as const) {
    const envelope = { version: PLANNER_ENVELOPE_VERSION, row_schema_version, ledger, tier: "raw",
      covers: day, file_id: "0199ba8e-9920-8000-8000-000000000001", content_sha256: "a".repeat(64),
      writer: "idhazh_typescript.ledger.parquet", writer_version: "recording", compression: "snappy",
      period: null, updated_at: null };
    expect<unknown>(PlannerFileEnvelopeSchema.parse(envelope)).toEqual(envelope);
    for (const stamp of ["2026-10-25", "2026-10-27", "2026-10-29"]) {
      expect(PlannerFileEnvelopeSchema.safeParse({ ...envelope, version: stamp }).success).toBe(false);
      expect(PlannerFileEnvelopeSchema.safeParse({ ...envelope, row_schema_version: stamp }).success).toBe(false);
    }
  }
});

test("current receipt construction succeeds and old documents and operations refuse", async () => {
  const document = await Bun.file(new URL("../../../tests/fixtures/contracts/fetched-document/refused.json", import.meta.url)).json();
  const operation = await Bun.file(new URL("../../../tests/fixtures/contracts/planner-operation/started.json", import.meta.url)).json();
  const currentDocument = FetchedDocumentSchema.parse({ ...document, version: OPERATION_VERSION });
  expect(currentDocument.version).toBe(OPERATION_VERSION);
  expect(PlannerOperationSchema.parse({ ...operation, version: PLANNER_OPERATION_VERSION }).version).toBe(PLANNER_OPERATION_VERSION);
  for (const version of ["2026-10-28", "2026-10-29", "2026-10-30"]) {
    expect(FetchedDocumentSchema.safeParse({ ...currentDocument, version }).success).toBe(false);
    expect(PlannerOperationSchema.safeParse({ ...operation, version }).success).toBe(false);
  }
  const recordedBatch = await Bun.file(new URL("../../../tests/fixtures/contracts/parsed-feed-batch/empty.json", import.meta.url)).json();
  const current = ParsedFeedBatchSchema.parse({
    batch_id: recordedBatch.batch_id, config_sha256: recordedBatch.config_sha256, context: recordedBatch.context,
    request: {}, candidates: [], observations: {}, discovered: { availability: "available", rows: [] },
    evidence: {}, history_rows: [], history_days: [], work_rows: [], exclusions: [],
  });
  expect(current.version).toBe(PARSED_FEED_BATCH_VERSION);
  expect(ParsedFeedBatchSchema.safeParse({ ...current, version: "2026-10-30" }).success).toBe(false);
});

test("event readers require the current recorded version instead of rewriting older progress", () => {
  const event = { version: FEED_INGEST_EVENT_VERSION, run_id: run,
    correlation_id: "7cef34e3-dd9f-40ce-9a56-4d01ff5115cc", occurred_at: at,
    operation: "fetch" as const, phase: "completed" as const, details: { output_count: 1 } };
  expect(readFeedIngestEvent(event)).toEqual(event);
  for (const version of ["2026-10-29T08:00", "2026-10-30T22:25", "2026-10-30T22:48", undefined]) {
    expect(() => readFeedIngestEvent({ ...event, version })).toThrow();
  }
});
