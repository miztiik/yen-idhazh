/** Do original source captures retain one technical outcome through replay and recovery? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  FeedIngestCandidateSchema, FetchedDocumentSchema, PlannerOperationSchema, PlannerStageContextSchema,
  SourceArticleOutcomeSchema, SourceSnapshotSchema, deriveCandidateId, deriveUrlKey,
} from "@idhazh/common-contracts";
import { HarvestArticleResultSchema } from "../src/harvest-feeds/harvest-types";
import { resolveArticleSourceOutcome } from "../src/article-source-outcome";
import { createRunHealth } from "../src/run-health";
import { summarizeHealth } from "../src/read-ledger-history/health-summary";
import { openOperationStore, sha256 } from "../src/api/operation-store";

function recording() {
  const at = "2026-10-27T12:00:00Z";
  const run = "2026-10-27-1";
  const source = SourceSnapshotSchema.parse({
    feed_id: "recorded", publisher_id: null, feed_url: "https://example.org/feed",
    title: "Recorded source", tier: 1, status: "active", weight: 1, applied_tier_weight: 1,
  });
  const context = PlannerStageContextSchema.parse({
    now: at, captured_at: at, date: at.slice(0, 10), run_id: run, correlation_id: randomUUID(),
    writer: { run_id: run, attempt: 1, job: null, pipeline_name: "feed-ingest-plan",
      task_name: "plan", shard: 0, producer: "tests.source-outcome", git_sha: "a".repeat(40) },
  });
  const article = (words: number) => HarvestArticleResultSchema.parse({
    candidate: FeedIngestCandidateSchema.parse({
      date: context.date, run_id: run, correlation_id: context.correlation_id,
      feed_id: source.feed_id, source, candidate_id: deriveCandidateId(run, source.feed_id, 0), entry_ordinal: 0,
      canonical_url: "https://example.org/article", url_key: deriveUrlKey("https://example.org/article"),
      title: "Recorded article", article_text: Array(words).fill("evidence").join(" "), word_count: words,
      author: null, categories: [], published_at: "2020-01-01T00:00:00Z", fetched_at: at,
    }),
    rejection: null,
    observation: { candidate_id: deriveCandidateId(run, source.feed_id, 0), http_status: 200, robots: "allowed",
      fetch_failure: null, paywall: false, paywall_evidence: "none", extraction: "success", observed_at: at, diagnostics: null },
  });
  return { at, source, context, article };
}

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

test("the source rate stays eight out of ten when only three articles are selected", () => {
  const { context, source, at } = recording();
  const captures = Array.from({ length: 10 }, (_, index) => ({
    id: randomUUID(), outcome: SourceArticleOutcomeSchema.parse(index < 8
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
  const summarize = (facts = rows, complete = true) => summarizeHealth({
    rows: facts, days: [{ day: context.date, complete }], sources: [source], now: at,
    policy: { availability_strikes_before_rest: 3, reliability_window_days: 1, reliability_floor: 0 },
    lifecycle_window_days: 1, request_report_closed_days: 1,
  }).sources.get(source.feed_id)!;
  expect(rows[0]!.article_candidates).toBe(8);
  expect(rows[0]!.rejection_counts.reduce((total, reason) => total + reason.count, 0)).toBe(2);
  expect(summarize().article_pass_rate).toBe(0.8);
  expect(summarize([], true).article_pass_rate).toBeNull();
  expect(summarize(rows, false).article_pass_rate).toBeNull();
  const recovered = createRunHealth(context, [source], new Map(), { min_words: 10, blocked_http_statuses: [] }, rows);
  for (const capture of captures) recovered.captureArticle(capture.id, source.feed_id, at, capture.outcome);
  expect(recovered.rows()).toEqual(rows);
  recovered.captureArticle(randomUUID(), source.feed_id, at, null);
  expect(summarize(recovered.rows()).article_pass_rate).toBeNull();
});

test("the existing operation journal preserves the first outcome and bounded feed membership after reopening", async () => {
  const directory = await mkdtemp(join(tmpdir(), "article-source-outcome-"));
  const { at, context, source } = recording();
  let store: Awaited<ReturnType<typeof openOperationStore>> | undefined;
  try {
    store = await openOperationStore(directory);
    const operation = () => PlannerOperationSchema.parse({
      request_id: randomUUID(), operation: "fetch", input_sha256: "b".repeat(64), config_sha256: "c".repeat(64),
      run_id: context.run_id, correlation_id: context.correlation_id, created_at: at,
      state: "started", response_json: null, artifact: null,
    });
    const artifact = (kind: "feed" | "article", parent: string | null = null) => {
      const url = kind === "feed" ? source.feed_url : "https://example.org/article";
      const body = kind === "feed" ? '<rss version="2.0"><channel><title>Recorded feed</title></channel></rss>'
        : "<article><h1>Recorded report</h1><p>Recorded article evidence.</p></article>";
      return FetchedDocumentSchema.parse({
        fetch_item_type: kind, canonical_url: url, article_id: deriveUrlKey(url), feed_id: source.feed_id,
        body, http_status: 200, failure: null, robots: "allowed", error_code: null, robots_failure: null,
        robots_http_status: null, attempts: [], attempt_observations: [], body_sha256: sha256(body),
        observation: { event_id: "5ee218d4-8bf2-5d1b-bc69-c23fb7261a60", caused_by_event_id: null,
          run_id: context.run_id, correlation_id: context.correlation_id, feed_id: source.feed_id,
          article_id: deriveUrlKey(url), occurred_at: at, operation: "fetch" },
        parent_fetch_request_id: parent,
      });
    };
    const parent = await store.execute(operation(), async () => ({ artifact: artifact("feed"), response_json: "{}" }));
    const proposed = operation();
    const original = artifact("article", parent.request_id);
    const capture = await store.execute(proposed, async () => ({ artifact: original, response_json: "{}" }));
    let replayed = false;
    await store.execute(proposed, async () => {
      replayed = true;
      return { artifact: original, response_json: "{}" };
    });
    expect(replayed).toBe(false);
    expect(store.get(parent.request_id)!.article_capture_request_ids).toEqual([capture.request_id]);
    const admitted = SourceArticleOutcomeSchema.parse({ disposition: "admitted", reason_code: null, settled_at: at });
    expect(store.settleSourceOutcome(capture.request_id, admitted)).toEqual(admitted);
    expect(store.settleSourceOutcome(capture.request_id, {
      disposition: "source_refused", reason_code: "EXTRACT_EMPTY", settled_at: "2026-10-28T00:00:00Z",
    })).toEqual(admitted);
    store.close();
    store = await openOperationStore(directory);
    expect(store.get(capture.request_id)!.source_outcome).toEqual(admitted);
    expect(store.get(capture.request_id)!.artifact).toEqual(original);
    await store.execute(operation(), async () => ({ artifact: artifact("article", parent.request_id), response_json: "{}" }));
    expect(store.get(parent.request_id)!.article_capture_request_ids).toHaveLength(2);
  } finally { store?.close(); await rm(directory, { recursive: true, force: true }); }
});
