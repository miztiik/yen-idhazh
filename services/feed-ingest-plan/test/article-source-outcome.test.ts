/** Do original source captures retain one technical outcome through replay and recovery? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  FeedIngestCandidateSchema, FetchedDocumentSchema, PlannerOperationSchema, PlannerStageContextSchema,
  SourceArticleOutcomeSchema, SourceSnapshotSchema, deriveCandidateId, deriveUrlKey,
  LEGACY_OPERATION_VERSION, LEGACY_PLANNER_OPERATION_VERSION, PLANNER_OPERATION_VERSION,
} from "@idhazh/common-contracts";
import { HarvestArticleResultSchema } from "../src/harvest-feeds/harvest-types";
import { resolveArticleSourceOutcome } from "../src/article-source-outcome";
import { createRunHealth } from "../src/run-health";
import { summarizePlanningHealth } from "../src/read-ledger-history/health-summary";
import { projectFeedHealthFields } from "../src/read-ledger-history/read-feed-health-fields";
import { openOperationStore, sha256 } from "../src/api/operation-store";
import { recordedPlan } from "./plan-recordings";
import { deriveLegacyArticleIdentity } from "../src/harvest-feeds/legacy-article-identity";
import { checkFetchedDocument } from "../src/api/document-state";
import { parseFetchedDocument } from "../src/api/parse-operation";
import { operationConfigFingerprint } from "../src/api/operation-context";
import { executeDocumentOperation } from "../src/api/document-operations";
import { FIRST_RUN_ATTEMPT, DEFAULT_PLANNER_PRODUCER } from "../src/resolve-run-context";

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

test("saved article receipts retain their old identity but cannot create current-policy candidates", async () => {
  const held = await recordedPlan();
  const store = await openOperationStore(held.inputs.outputRoot);
  try {
    const { at, context } = recording();
    const identity = deriveLegacyArticleIdentity("https://news.example/second?edition=old");
    const body = held.transport.recordings.bodies.article;
    const artifact = FetchedDocumentSchema.parse({
      version: LEGACY_OPERATION_VERSION, fetch_item_type: "article", canonical_url: identity.canonical_url,
      article_id: identity.url_key, feed_id: "recorded-news", body, http_status: 200,
      failure: null, robots: "allowed", error_code: null, robots_failure: null,
      robots_http_status: null, attempts: [], attempt_observations: [], body_sha256: sha256(body),
      observation: { event_id: "5ee218d4-8bf2-5d1b-bc69-c23fb7261a60", caused_by_event_id: null,
        run_id: context.run_id, correlation_id: context.correlation_id, feed_id: "recorded-news",
        article_id: identity.url_key, occurred_at: at, operation: "fetch" },
      parent_fetch_request_id: null,
    });
    const request = {
      request_id: randomUUID(), correlation_id: context.correlation_id,
      feed_id: "recorded-news", fetch_item_type: "article" as const, url: identity.canonical_url,
    };
    const { digest_root, ...originalInputs } = held.inputs.settings.inputs;
    const legacyFingerprint = sha256(JSON.stringify({
      harvest: held.inputs.harvest.config_sha256, settings: { ...held.inputs.settings, inputs: originalInputs },
      clock: held.inputs.clock_config, ledger: held.inputs.ledgerSettings, registrations: held.inputs.registrations,
      attempt: held.runtime.attempt ?? FIRST_RUN_ATTEMPT,
      producer: held.runtime.producer ?? DEFAULT_PLANNER_PRODUCER, git_sha: held.runtime.git_sha,
    }));
    expect(legacyFingerprint).not.toBe(operationConfigFingerprint(held.inputs, held.runtime));
    const proposed = PlannerOperationSchema.parse({
      version: LEGACY_PLANNER_OPERATION_VERSION,
      request_id: request.request_id, operation: "fetch", input_sha256: sha256(JSON.stringify(request)),
      config_sha256: legacyFingerprint,
      run_id: context.run_id, correlation_id: context.correlation_id, created_at: at,
      state: "started", response_json: null, artifact: null,
    });
    const response = JSON.stringify({
      fetch_request_id: request.request_id, batch_id: request.request_id, run_id: context.run_id,
      correlation_id: context.correlation_id, fetch_item_type: "article", feed_id: request.feed_id,
      article_id: identity.url_key, canonical_url: identity.canonical_url,
      http_status: 200, failure: null, body_sha256: artifact.body_sha256,
    }, null, 2);
    const fetched = await store.execute(proposed, async () => ({ artifact, response_json: response }));
    expect(await executeDocumentOperation("fetch", request, held.inputs, held.runtime)).toBe(response);
    await expect(executeDocumentOperation("fetch", { ...request, url: "https://news.example/other" }, held.inputs, held.runtime))
      .rejects.toMatchObject({ code: "REQUEST_CONFLICT" });
    await expect(executeDocumentOperation("fetch", request, held.inputs, { ...held.runtime, git_sha: "f".repeat(40) }))
      .rejects.toMatchObject({ code: "REQUEST_CONFLICT" });
    const parseRequest = {
      request_id: randomUUID(), fetch_request_id: fetched.request_id,
      article_id: identity.url_key, correlation_id: context.correlation_id,
    };
    const parseResponse = JSON.stringify({
      fetch_item_type: "article", batch_id: randomUUID(), fetch_request_id: fetched.request_id,
      run_id: context.run_id, parsed_count: 1, failure: null, pending_offers: 0,
    });
    await store.execute({ ...proposed, operation: "parse", request_id: parseRequest.request_id,
      input_sha256: sha256(JSON.stringify(parseRequest)) }, async () => ({ artifact: null, response_json: parseResponse }));
    expect(await executeDocumentOperation("parse", parseRequest, held.inputs, held.runtime)).toBe(parseResponse);
    for (const version of [LEGACY_PLANNER_OPERATION_VERSION, PLANNER_OPERATION_VERSION]) {
      const mixedRequest = { ...request, request_id: randomUUID() };
      const currentIdentity = deriveLegacyArticleIdentity("https://news.example/second");
      const mixedArtifact = version === PLANNER_OPERATION_VERSION ? artifact : FetchedDocumentSchema.parse({
        ...artifact, version: PLANNER_OPERATION_VERSION, canonical_url: currentIdentity.canonical_url,
        article_id: currentIdentity.url_key, observation: { ...artifact.observation, article_id: currentIdentity.url_key },
      });
      await store.execute({ ...proposed, version, request_id: mixedRequest.request_id,
        input_sha256: sha256(JSON.stringify(mixedRequest)) }, async () => ({ artifact: mixedArtifact, response_json: response }));
      await expect(executeDocumentOperation("fetch", mixedRequest, held.inputs, held.runtime))
        .rejects.toMatchObject({ code: "REQUEST_CONFLICT" });
    }
    const incompleteRequest = { ...request, request_id: randomUUID() };
    await expect(store.execute({ ...proposed, request_id: incompleteRequest.request_id,
      input_sha256: sha256(JSON.stringify(incompleteRequest)) }, async () => {
      throw new Error("interrupted recorded receipt");
    })).rejects.toThrow("interrupted recorded receipt");
    await expect(executeDocumentOperation("fetch", incompleteRequest, held.inputs, held.runtime))
      .rejects.toMatchObject({ code: "REQUEST_CONFLICT" });
    expect(checkFetchedDocument(fetched, held.inputs)).toMatchObject({
      version: LEGACY_OPERATION_VERSION, canonical_url: identity.canonical_url, article_id: identity.url_key,
    });
    await expect(parseFetchedDocument({
      request_id: randomUUID(), fetch_request_id: fetched.request_id,
      article_id: identity.url_key, correlation_id: context.correlation_id,
    }, { ...proposed, operation: "parse" }, fetched, held.inputs, held.runtime, store))
      .rejects.toMatchObject({ code: "REQUEST_CONFLICT" });
    expect(held.transport.requests).toHaveLength(0);
    expect(store.get(fetched.request_id)?.artifact?.canonical_url).toBe(identity.canonical_url);
  } finally { store.close(); await held.close(); }
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

test("the source rate stays eight out of ten when only three articles are selected", () => {
  const { context, source, at } = recording();
  const captures = Array.from({ length: 10 }, (_, index) => ({
    id: randomUUID(), outcome: SourceArticleOutcomeSchema.parse(index < 8
      ? { disposition: "admitted", reason_code: null, settled_at: at }
      : { disposition: "source_refused", reason_code: "REJECTED_SCREENING_MIN_WORDS", settled_at: at }),
  }));
  const work = createRunHealth(context, [source], new Map(), { min_words: 10, blocked_http_statuses: [401, 403], tidy_urls: true });
  for (const capture of captures) {
    work.captureArticle(capture.id, source.feed_id, at, capture.outcome);
    work.captureArticle(capture.id, source.feed_id, at, capture.outcome);
  }
  const rows = work.rows();
  rows[0]!.articles_selected = 3;
  const summarize = (facts = rows, complete = true) => summarizePlanningHealth({
    uses: projectFeedHealthFields(context.date, facts),
    days: [{ day: context.date, complete }], sources: [source], now: at,
    policy: { availability_strikes_before_rest: 3, reliability_window_days: 1, reliability_floor: 0 },
    lifecycle_window_days: 1,
  }).sources.get(source.feed_id)!;
  expect(rows[0]!.article_candidates).toBe(8);
  expect(rows[0]!.rejection_counts.reduce((total, reason) => total + reason.count, 0)).toBe(2);
  expect(summarize().article_pass_rate).toBe(0.8);
  expect(summarize([], true).article_pass_rate).toBeNull();
  expect(summarize(rows, false).article_pass_rate).toBeNull();
  const recovered = createRunHealth(context, [source], new Map(), { min_words: 10, blocked_http_statuses: [], tidy_urls: true }, rows);
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
