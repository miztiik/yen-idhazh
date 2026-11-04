/** Do live source captures retain one technical outcome independently of selection? */
import { expect, test } from "bun:test";
import {
  createChildContext, createRootContext, FeedIngestCandidateSchema, PlannerStageContextSchema,
  HarvestDiagnosticsSchema, SourceArticleOutcomeSchema, SourceSnapshotSchema, createCandidateId, deriveUrlKey,
} from "@idhazh/common-contracts";
import { HarvestArticleResultSchema } from "../src/harvest-feeds/harvest-types";
import { resolveArticleSourceOutcome } from "../src/article-source-outcome";
import { recordRejection } from "../src/harvest-feeds/record-rejection";
import { attributeIngestOutcome } from "../src/attribute-ingest-outcomes";
import { createRunHealth } from "../src/run-health";
import { summarizePlanningHealth } from "../src/read-ledger-history/health-summary";
import { projectFeedHealthFields } from "../src/read-ledger-history/read-feed-health-fields";
import { createSourceFetcher } from "@idhazh/feed-ingest-plan/fetch-source";
import { documentWork } from "../src/harvest-feeds/document-work";
import { createIngestObservations } from "../src/ingest-observations";
import { RecordedTransport, inputs, readRecordings } from "./harvest-recordings";
import { operationKey, operationMetadata } from "../src/api/operation-context";

function recording() {
  const at = "2026-10-27T12:00:00Z";
  const run = "2026-10-27-1";
  const source = SourceSnapshotSchema.parse({
    feed_id: "recorded", publisher_id: null, feed_url: "https://example.org/feed",
    title: "Recorded source", status: "active", weight: 1,
  });
  const context = { ...createRootContext(), ...PlannerStageContextSchema.parse({
    now: at, captured_at: at, date: at.slice(0, 10), run_id: run,
    writer: { run_id: run, attempt: 1, job: null, pipeline_name: "feed-ingest-plan",
      task_name: "plan", shard: 0, producer: "tests.source-outcome", git_sha: "a".repeat(40) },
  }) };
  const article = (words: number) => {
    const candidate_id = createCandidateId();
    return HarvestArticleResultSchema.parse({
      candidate: FeedIngestCandidateSchema.parse({
        date: context.date, run_id: run, traceId: context.traceId,
        feed_id: source.feed_id, source, candidate_id, entry_ordinal: 0,
        canonical_url: "https://example.org/article", url_key: deriveUrlKey("https://example.org/article"),
        title: "Recorded article", article_text: Array(words).fill("evidence").join(" "), word_count: words,
        author: null, categories: [], published_at: "2020-01-01T00:00:00Z", fetched_at: at,
      }),
      rejection: null,
      observation: { candidate_id, http_status: 200,
        fetch_failure: null, paywall: false, paywall_evidence: "none", extraction: "success", observed_at: at, diagnostics: null },
    });
  };
  return { at, source, context, article };
}

test("retries and redirects count once on their dispatch UTC day, not the later settlement day", async () => {
  const { context, source } = recording();
  const loaded = await inputs([], { extraction: { max_retries: 1 } });
  const recordings = await readRecordings();
  const target = "https://news.example/retry";
  recordings.responses[target] = [
    { status: 503, body: "" }, { status: 302, body: "", location: "https://atom.example/entry" },
  ];
  const transport = new RecordedTransport(recordings);
  let at = "2026-10-27T23:59:59Z";
  const clock = () => new Date(at);
  transport.on_request = () => { at = "2026-10-28T00:00:00Z"; };
  const fetcher = createSourceFetcher({
    ...loaded.config.harvest, request_headers: { ...loaded.config.harvest.request_headers, secondary: null },
  }, loaded.extraction, { transport }, clock);
  const health = createRunHealth(context, [source], new Map(), {
    min_words: 10, blocked_http_statuses: [],
  });
  const candidate_id = createCandidateId();
  const work = documentWork({
    ...operationMetadata(context),
    observation_clock: clock, observations: createIngestObservations(health.observe),
  }, {
    run_id: context.run_id,
    article_id: deriveUrlKey(target), feed_id: source.feed_id, candidate_id,
  }, createChildContext(operationMetadata(context)), {
    document_kind: "article", publisher_id: null, candidate_id,
    observed_run_id: context.run_id, observed_attempt: context.writer.attempt, feed_id: source.feed_id,
  });
  try {
    expect((await work.fetch(fetcher, target)).fetched.failure).toBeNull();
    expect(transport.requests.map(request => request.url.href)).toEqual([target, target, "https://atom.example/entry"]);
    expect(health.rows().map(row => ({
      date: row.date, feed_requests: row.feed_requests, article_requests: row.article_requests,
      counts_complete: row.counts_complete,
    }))).toEqual([
      { date: "2026-10-27", feed_requests: 0, article_requests: 1, counts_complete: true },
      { date: "2026-10-28", feed_requests: 0, article_requests: 2, counts_complete: true },
    ]);
  } finally { await fetcher.close(); }
});

test("technical admission uses access and words, not publication age or selection", () => {
  const { at, article } = recording();
  expect(resolveArticleSourceOutcome(article(10), 10, [401, 403], at)).toEqual({
    disposition: "admitted", reason_code: null, settled_at: at,
  });
  expect(resolveArticleSourceOutcome(article(9), 10, [401, 403], at)?.reason_code).toBe("REJECTED_SCREENING_MIN_WORDS");
  const paywall = article(10);
  paywall.observation.paywall = true;
  expect(resolveArticleSourceOutcome(paywall, 10, [401, 403], at)?.reason_code).toBe("PAYWALL_OR_BLOCKED");
  expect(SourceArticleOutcomeSchema.safeParse({ disposition: "admitted", reason_code: "EXTRACT_EMPTY", settled_at: at }).success).toBe(false);
  expect(SourceArticleOutcomeSchema.safeParse({ disposition: "source_refused", reason_code: null, settled_at: at }).success).toBe(false);
});

test("measured quality rejection stays unresolved and is counted once without a source refusal", () => {
  const { at, context: plannerContext, source, article } = recording();
  const candidate = article(10).candidate!;
  const diagnostics = HarvestDiagnosticsSchema.parse({
    http_status: 200, failure_code: "too_short", stopped_stage: "extract",
    detail: "too_short",
    quality: {
      source_word_count: 10, word_count: 10, corroborated_word_count: null,
      token_count: null, truncated: null, truncated_at_tokens: null, truncation_cap_tokens: 256,
      too_short: true, not_prose: false, boilerplate: null, contaminated: null,
      failure_code: "too_short", rejected: true, extractor_version: "recorded", sanitizer_version: "recorded",
    },
  });
  const harvestContext = {
    ...operationMetadata(plannerContext), writer: plannerContext.writer, max_future_hours: 6,
    clock: () => new Date(at), observation_clock: () => new Date(at),
  };
  const rejection = recordRejection(source, harvestContext, "EXTRACT_FAILED", {
    http_status: 200, diagnostics,
  }, {
    candidate_id: candidate.candidate_id, canonical_url: candidate.canonical_url,
    url_key: candidate.url_key, title: candidate.title, categories: candidate.categories,
  });
  const rejected = HarvestArticleResultSchema.parse({
    candidate: null, rejection,
    observation: {
      candidate_id: candidate.candidate_id, http_status: 200, fetch_failure: null,
      paywall: false, paywall_evidence: "none", extraction: "success", observed_at: at, diagnostics,
    },
  });
  expect(attributeIngestOutcome({
    document_kind: "article", operation: "quality", outcome: "failed",
    failure_code: "too_short", http_status: 200, request_phase: null,
  })).toBe("unresolved");
  expect(resolveArticleSourceOutcome(rejected, 10, [], at)).toBeNull();
  const work = createRunHealth(plannerContext, [source], new Map(), {
    min_words: 10, blocked_http_statuses: [],
  });
  work.article(rejected);
  const row = work.rows()[0]!;
  expect(row.article_candidates).toBeNull();
  expect(row.rejection_counts).toContainEqual({
    subject: "article", stage: "harvest-feeds", reason_code: "EXTRACT_FAILED",
    attribution: "unknown", count: 1,
  });
  expect(row.rejection_counts.some(value => value.subject === "article" && value.attribution === "feed")).toBe(false);
});

test("the source rate stays eight out of ten when only three articles are selected", async () => {
  const { readLifecyclePolicy } = await import("./health-field-fixtures");
  const lifecycle_policy = await readLifecyclePolicy();
  const { context, source, at } = recording();
  const captures = Array.from({ length: 10 }, (_, index) => ({
    id: operationKey(createChildContext(operationMetadata(context))), outcome: SourceArticleOutcomeSchema.parse(index < 8
      ? { disposition: "admitted", reason_code: null, settled_at: at }
      : { disposition: "source_refused", reason_code: "REJECTED_SCREENING_MIN_WORDS", settled_at: at }),
  }));
  const work = createRunHealth(context, [source], new Map(), { min_words: 10, blocked_http_statuses: [401, 403] });
  for (const capture of captures) {
    work.captureArticle(capture.id, source.feed_id, at, capture.outcome);
    work.captureArticle(capture.id, source.feed_id, at, capture.outcome);
  }
  const rows = work.rows();
  rows[0]!.articles_selected = 3;
  const summarize = (facts = rows, complete = true) => summarizePlanningHealth({
    uses: projectFeedHealthFields(context.date, facts),
    days: [{ day: context.date, complete }], sources: [source], now: at,
    policy: { reliability_window_days: 1, reliability_floor: 0 },
    lifecycle_window_days: 1, lifecycle_policy,
  }).sources.get(source.feed_id)!;
  expect(rows[0]!.article_candidates).toBe(8);
  expect(rows[0]!.rejection_counts.reduce((total, reason) => total + reason.count, 0)).toBe(2);
  expect(summarize().article_pass_rate).toBe(0.8);
  expect(summarize([], true).article_pass_rate).toBeNull();
  expect(summarize(rows, false).article_pass_rate).toBeNull();
});
