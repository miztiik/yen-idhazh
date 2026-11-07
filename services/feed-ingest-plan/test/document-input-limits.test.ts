/** Prove the real fetch and parse APIs expose limits without fallback or false extraction measurements. */
import { expect, test } from "bun:test";
import {
  ParsedFeedBatchSchema, PLANNER_API_PATHS, PLANNER_API_PREFIX, createCandidateId, createRootContext, deriveUrlKey,
} from "@idhazh/common-contracts";
import { FetchResponseSchema, ParseResponseSchema } from "../src/api/document-response.schema";
import { operationLink } from "../src/api/operation-context";
import { countWords } from "../src/count-article-words";
import { extractArticle } from "../src/harvest-feeds/dom-extractor";
import { stageStore } from "../src/api/stage-store";
import { createPlanTestServer } from "./plan-test-server";
import { recordedPlan } from "./plan-recordings";

const target = "https://news.example/second";
const json = (body: unknown) => ({
  method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
});

test("fetch response carries the configured byte limit only for the actual source-size failure", async () => {
  const f = await recordedPlan();
  f.inputs.harvest.extraction.max_body_bytes = 1024;
  f.inputs.harvest.config.harvest.request_headers.secondary = null;
  const app = createPlanTestServer(f.inputs, f.runtime);
  try {
    for (const bytes of [1023, 1024, 1025]) {
      f.transport.recordings.responses[target] = [{ status: 200, body: "x".repeat(bytes) }];
      const response = await app.request(`${PLANNER_API_PREFIX}${PLANNER_API_PATHS.fetch}`,
        json({ fetch_item_type: "article", feed_id: "recorded-news", url: target }));
      expect(response.status).toBe(200);
      const wire: unknown = await response.json();
      const fetched = FetchResponseSchema.parse(wire);
      expect(wire).toHaveProperty("body_limit");
      expect(fetched.http_status).toBe(200);
      expect(fetched.failure).toBe(bytes > 1024 ? "body-too-large" : null);
      expect(fetched.body_limit).toEqual(bytes > 1024
        ? { configured_limit_bytes: 1024, observed_at_least_bytes: bytes } : null);
      if (bytes > 1024) {
        expect(fetched.body_sha256).toBeNull();
        expect(stageStore(f.inputs).fetchedDocument(fetched)).toBeUndefined();
        const unavailable = await app.request(`${PLANNER_API_PREFIX}${PLANNER_API_PATHS.parse}`,
          json({ links: [operationLink(fetched)] }));
        expect(unavailable.status).toBe(404);
      }
    }
  } finally { await app.close(); await f.close(); }
});

test("fetch response schema requires explicit evidence and rejects evidence on other failures", () => {
  const response = {
    ...createRootContext(), run_id: "2026-10-21-700", feed_id: "recorded-news",
    canonical_url: target, http_status: 200, failure: "body-too-large", body_sha256: null,
    body_limit: { configured_limit_bytes: 1024, observed_at_least_bytes: 1025 },
    fetch_item_type: "article", article_id: deriveUrlKey(target), candidate_id: createCandidateId(),
  };
  expect(FetchResponseSchema.safeParse(response).success).toBe(true);
  const { body_limit: _limit, ...missing } = response;
  expect(FetchResponseSchema.safeParse(missing).success).toBe(false);
  expect(FetchResponseSchema.safeParse({ ...response, failure: "network" }).success).toBe(false);
  expect(FetchResponseSchema.safeParse({
    ...response, body_limit: { configured_limit_bytes: 1024, observed_at_least_bytes: 1024 },
  }).success).toBe(false);
});

test("article parse responses require explicit word-limit evidence and feed responses do not accept it", () => {
  const identity = { ...createRootContext(), run_id: "2026-10-21-700", parsed_count: 1, failure: null };
  const response = {
    ...identity, fetch_item_type: "article", article_id: deriveUrlKey(target), candidate_id: createCandidateId(),
    pending_offers: 0, warnings: [],
    word_limit: { max_input_words: 2, original_word_count: 3, returned_word_count: 2, truncated: true },
  };
  expect(ParseResponseSchema.safeParse(response).success).toBe(true);
  const { word_limit: _words, ...missing } = response;
  expect(ParseResponseSchema.safeParse(missing).success).toBe(false);
  expect(ParseResponseSchema.safeParse({ ...response, word_limit: null, parsed_count: 0, failure: "EXTRACT_EMPTY" }).success)
    .toBe(true);
  const feed = {
    ...identity, fetch_item_type: "feed", feed_id: "recorded-news", document_id: deriveUrlKey(target), offers: [],
  };
  expect(ParseResponseSchema.safeParse(feed).success).toBe(true);
  expect(ParseResponseSchema.safeParse({ ...feed, word_limit: response.word_limit }).success).toBe(false);
});

test("real article parsing shortens 20001 extracted words before candidate capture and keeps source quality intact", async () => {
  const f = await recordedPlan();
  const text = Array.from({ length: 20001 }, () => "word").join(" ");
  const html = `<html><head><title>Bounded report</title></head><body><article><p>${text}</p></article></body></html>`;
  f.transport.recordings.responses[target] = [{ status: 200, body: html }];
  const original = await extractArticle(html, target, f.inputs.harvest.extraction);
  expect(original.word_count).toBe(20001);
  const app = createPlanTestServer(f.inputs, f.runtime);
  try {
    const fetched = FetchResponseSchema.parse(await (await app.request(
      `${PLANNER_API_PREFIX}${PLANNER_API_PATHS.fetch}`,
      json({ fetch_item_type: "article", feed_id: "recorded-news", url: target }),
    )).json());
    expect(fetched.body_limit).toBeNull();
    const response = await app.request(`${PLANNER_API_PREFIX}${PLANNER_API_PATHS.parse}`,
      json({ links: [operationLink(fetched)] }));
    expect(response.status).toBe(200);
    const wire: unknown = await response.json();
    expect(wire).toHaveProperty("word_limit");
    const parsed = ParseResponseSchema.parse(wire);
    expect(parsed.fetch_item_type).toBe("article");
    if (parsed.fetch_item_type !== "article") throw new Error("Article input must produce an article response");
    expect(parsed.failure).toBeNull();
    expect(parsed.word_limit).toEqual({
      max_input_words: 20000, original_word_count: 20001, returned_word_count: 20000, truncated: true,
    });
    const batch = stageStore(f.inputs).read("parsed", parsed, ParsedFeedBatchSchema);
    const candidate = batch.candidates[0];
    if (candidate === undefined) throw new Error("Successful article parsing must capture its prepared candidate");
    expect(candidate.article_text).toBe(Array.from({ length: 20000 }, () => "word").join(" "));
    expect(candidate.word_count).toBe(20000);
    expect(countWords(candidate.article_text)).toBe(20000);
    expect(batch.observations[candidate.candidate_id]?.diagnostics?.quality).toEqual(original.quality);
    expect(original.quality?.truncated).toBeNull();
    expect(original.quality?.truncated_at_tokens).toBeNull();
  } finally { await app.close(); await f.close(); }
});

test("a substituted API ceiling changes preparation but not feed parsing or extraction measurements", async () => {
  const f = await recordedPlan();
  f.inputs.harvest.config.harvest.max_input_words = 50;
  const original = await extractArticle(f.transport.recordings.bodies.article, target, f.inputs.harvest.extraction);
  const app = createPlanTestServer(f.inputs, f.runtime);
  try {
    const fetched = FetchResponseSchema.parse(await (await app.request(
      `${PLANNER_API_PREFIX}${PLANNER_API_PATHS.fetch}`,
      json({ fetch_item_type: "article", feed_id: "recorded-news", url: target }),
    )).json());
    const parsed = ParseResponseSchema.parse(await (await app.request(
      `${PLANNER_API_PREFIX}${PLANNER_API_PATHS.parse}`, json({ links: [operationLink(fetched)] }),
    )).json());
    if (parsed.fetch_item_type !== "article") throw new Error("Article input must produce an article response");
    expect(parsed.word_limit).toEqual({
      max_input_words: 50, original_word_count: original.word_count, returned_word_count: 50, truncated: true,
    });
    const batch = stageStore(f.inputs).read("parsed", parsed, ParsedFeedBatchSchema);
    expect(batch.candidates[0]?.word_count).toBe(50);
    expect(batch.observations[parsed.candidate_id]?.diagnostics?.quality).toEqual(original.quality);
    const feed = FetchResponseSchema.parse(await (await app.request(
      `${PLANNER_API_PREFIX}${PLANNER_API_PATHS.fetch}`, json({ fetch_item_type: "feed", feed_id: "recorded-news" }),
    )).json());
    const feedResponse = await (await app.request(
      `${PLANNER_API_PREFIX}${PLANNER_API_PATHS.parse}`, json({ links: [operationLink(feed)] }),
    )).json();
    expect(ParseResponseSchema.safeParse(feedResponse).success).toBe(true);
    expect(feedResponse.fetch_item_type).toBe("feed");
    expect(feedResponse).not.toHaveProperty("word_limit");
  } finally { await app.close(); await f.close(); }
});
