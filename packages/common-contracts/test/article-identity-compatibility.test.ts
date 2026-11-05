/** Do current planner formats round-trip while older formats refuse without migration? */
import { expect, test } from "bun:test";
import {
  DISCOVERED_ARTICLE_VERSION, SELECTED_ARTICLE_VERSION, PLANNER_ENVELOPE_VERSION,
  DiscoveredArticleRowSchema, SelectedArticleRowSchema, SelectedArticleMetadataSchema, PlannerFileEnvelopeSchema,
  FeedIngestCandidateSchema, FeedOutcomePayloadSchema, PlannerFeedOfferSchema,
  SourceSnapshotSchema, FEED_OUTCOME_PAYLOAD_VERSION, CandidateIdSchema, createCandidateId, FetchRequestSchema,
  readSelectedArticlesArtifact, createRootContext, deriveUrlKey, FetchedDocumentSchema,
} from "../src";

const day = "2026-10-28";
const at = `${day}T12:00:00.123Z`;
const url = "https://example.org/article";
const run = `${day}-1`;
function metadata() {
  return SelectedArticleMetadataSchema.parse({
    url_key: deriveUrlKey(url), feed_id: "fixture-feed", publisher_id: null,
    canonical_url: url, title: "Recorded article", categories: [], author: null,
    published_at: at, published_at_source: "selection", weight: 1,
    word_count: 3, substance_word_count: 0,
    editorial_rank: 1, estimated_work: 3, worker_assignment: null,
    timing_at: at, timing_basis: "first_seen", age_hours: 0, freshness_cutoff_at: at,
    ratings: { base_article_score: 1, marginal_score: 1, adjustments: [
      { term: "article_pass_rate", value: 0 }, { term: "substance_quality_score", value: 0 },
      { term: "domain_diversity_penalty", value: 0 }, { term: "feed_diversity_penalty", value: 0 },
      { term: "novelty_bonus", value: 0 },
    ], recency_score: 1, feed_authority_score: 0 },
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
  for (const schema_version of ["2026-10-25", "2026-10-27", "2026-10-29", "2026-11-02"]) {
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
    }
    for (const stamp of ["2026-10-25", "2026-10-27", "2026-10-29", "2026-10-31", "2026-11-02"]) {
      expect(PlannerFileEnvelopeSchema.safeParse({ ...envelope, row_schema_version: stamp }).success).toBe(false);
    }
  }
});

test("current source, candidate, offer and outcome projections refuse retired source fields and versions", () => {
  const source = SourceSnapshotSchema.parse({
    feed_id: "fixture-feed", publisher_id: null, feed_url: "https://example.org/feed",
    title: "Recorded feed", status: "active", weight: 1,
  });
  const candidate = FeedIngestCandidateSchema.parse({
    date: day, traceId: createRootContext().traceId, run_id: run,
    candidate_id: createCandidateId(), entry_ordinal: 0,
    feed_id: source.feed_id, source, canonical_url: url, url_key: deriveUrlKey(url),
    title: "Recorded article", categories: [], article_text: "Unchanged body.", word_count: 2,
    author: null, published_at: null, fetched_at: `${day}T12:00:00Z`,
  });
  const canonical_url = `${url}?a=x%26b%3Dy&a=two&empty=&plus=a+b`;
  const queried = { ...candidate, canonical_url, url_key: deriveUrlKey(canonical_url) };
  expect(FeedIngestCandidateSchema.parse(queried)).toEqual(queried);
  for (const version of ["2026-11-02", "2026-11-03"]) {
    expect(FeedIngestCandidateSchema.safeParse({ ...queried, version }).success).toBe(false);
  }
  expect(FeedIngestCandidateSchema.safeParse({ ...queried, url_key: candidate.url_key }).success).toBe(false);
  const fragment = `${canonical_url}#section`;
  expect(FeedIngestCandidateSchema.safeParse({
    ...queried, canonical_url: fragment, url_key: deriveUrlKey(fragment),
  }).success).toBe(false);
  const offer = PlannerFeedOfferSchema.parse({
    candidate_id: candidate.candidate_id, source, entry: {
      entry_ordinal: 0, title: null, link: url, categories: [], author: null, published_at: null,
    }, state: "pending", links: [],
  });

  const outcome = FeedOutcomePayloadSchema.parse({
    kind: "feed_outcome", source, fetch_status: "success", parse_status: "success",
    parsed_count: 1, harvested_count: 1, fetch_duration_ms: 0, parse_duration_ms: 0,
    rejection_reason: null,
  });
  expect(outcome.version).toBe(FEED_OUTCOME_PAYLOAD_VERSION);
  for (const [schema, value] of [
    [FeedIngestCandidateSchema, candidate], [FeedOutcomePayloadSchema, outcome],
  ] as const) {
    expect(schema.parse(JSON.parse(JSON.stringify(value)))).toEqual(value);
    expect(schema.safeParse({ ...value, version: "2026-10-31" }).success).toBe(false);
  }
  for (const patch of [{ tier: 1 }, { applied_tier_weight: 1 }]) {
    const retired = { ...source, ...patch };
    expect(SourceSnapshotSchema.safeParse(retired).success).toBe(false);
    expect(FeedIngestCandidateSchema.safeParse({ ...candidate, source: retired }).success).toBe(false);
    expect(PlannerFeedOfferSchema.safeParse({ ...offer, source: retired }).success).toBe(false);
    expect(FeedOutcomePayloadSchema.safeParse({ ...outcome, source: retired }).success).toBe(false);
  }
  expect(PlannerFeedOfferSchema.parse(JSON.parse(JSON.stringify(offer)))).toEqual(offer);
  expect(FeedIngestCandidateSchema.parse({ ...candidate, entry_ordinal: null }).candidate_id).toBe(candidate.candidate_id);
  const link = createRootContext();
  const fetch = { fetch_item_type: "article", links: [{ traceId: link.traceId, spanId: link.spanId }],
    candidate_id: offer.candidate_id };
  expect<unknown>(FetchRequestSchema.parse(fetch)).toEqual(fetch);
  const { candidate_id, ...retired } = offer;
  expect(PlannerFeedOfferSchema.safeParse({ ...retired, offer_id: candidate_id }).success).toBe(false);
  expect(FetchRequestSchema.safeParse({ ...fetch, offer_id: candidate_id }).success).toBe(false);
  for (const invalid of ["a".repeat(64), "ABCDEFAB-0000-4000-8000-000000000001", candidate_id.replaceAll("-", ""),
    "00000000-0000-5000-8000-000000000001", "00000000-0000-4000-7000-000000000001", null]) {
    expect(CandidateIdSchema.safeParse(invalid).success).toBe(false);
    expect(FeedIngestCandidateSchema.safeParse({ ...candidate, candidate_id: invalid }).success).toBe(false);
    expect(PlannerFeedOfferSchema.safeParse({ ...offer, candidate_id: invalid }).success).toBe(false);
    expect(FetchRequestSchema.safeParse({ ...fetch, candidate_id: invalid }).success).toBe(false);
  }
});

test("current feed and article documents preserve queries, refuse fragments and reject the retired stamp", async () => {
  const recorded = FetchedDocumentSchema.parse(await Bun.file(new URL(
    "../../../tests/fixtures/contracts/fetched-document/refused.json", import.meta.url,
  )).json());
  for (const fetch_item_type of ["feed", "article"] as const) {
    const candidate_id = fetch_item_type === "article" ? createCandidateId() : null;
    const documentAt = (canonical_url: string) => {
      const article_id = deriveUrlKey(canonical_url);
      return {
        ...recorded, fetch_item_type, canonical_url, article_id, candidate_id,
        observation: { ...recorded.observation, article_id, candidate_id },
        attempt_observations: recorded.attempt_observations.map(observation => ({ ...observation, article_id, candidate_id })),
      };
    };
    const queried = documentAt(`${url}?a=x%26b%3Dy&a=two&empty=&plus=a+b`);
    expect(FetchedDocumentSchema.parse(queried)).toEqual(queried);
    expect(FetchedDocumentSchema.safeParse(documentAt(`${queried.canonical_url}#section`)).success).toBe(false);
    expect(FetchedDocumentSchema.safeParse({ ...queried, version: "2026-11-03" }).success).toBe(false);
    expect(FetchedDocumentSchema.safeParse({
      ...queried, candidate_id: fetch_item_type === "article" ? null : createCandidateId(),
    }).success).toBe(false);
    expect(FetchedDocumentSchema.safeParse({
      ...queried, observation: { ...queried.observation, candidate_id: createCandidateId() },
    }).success).toBe(false);
  }
});
