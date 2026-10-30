/** Bound actual feed and article workers without network access or substitute parsers. */
import { expect, test } from "bun:test";
import { FeedHarvestConfigSchema } from "@idhazh/common-contracts";
import { ArticleParserPool } from "../src/harvest-feeds/article-parser-pool";
import { parseDocument } from "../src/harvest-feeds/parse-document";
import { ParserError } from "../src/harvest-feeds/parser-error";
import { documentWork, describeFeedParse } from "../src/harvest-feeds/document-work";
import { inputs, context, readRecordings } from "./harvest-recordings";
import { attributeIngestOutcome } from "../src/attribute-ingest-outcomes";
import type { DocumentWorkFact } from "@idhazh/common-contracts";

test("parse deadlines are configurable and separate from each HTTP attempt", async () => {
  const loaded = await inputs();
  const { parse_timeout_ms: omitted, ...withoutDeadline } = loaded.config.harvest;
  expect(omitted).toBe(10000);
  expect(FeedHarvestConfigSchema.parse(withoutDeadline).parse_timeout_ms).toBe(10000);
  expect(FeedHarvestConfigSchema.parse({ ...withoutDeadline, parse_timeout_ms: 37 }).parse_timeout_ms).toBe(37);
  expect(FeedHarvestConfigSchema.safeParse({ ...withoutDeadline, parse_timeout_ms: 0 }).success).toBe(false);
  const config = await Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json();
  expect(config.harvest.fetch_timeout_ms).toBe(6000);
});

test("feed and HTML workers return finished work without waiting for the deadline", async () => {
  const [loaded, recordings] = await Promise.all([inputs(), readRecordings()]);
  const pool = new ArticleParserPool(1);
  const controller = new AbortController();
  try {
    const feed = await parseDocument("feed", recordings.bodies.rss, "https://news.example/feed",
      undefined, pool, { signal: controller.signal, timeout_ms: 10000 });
    expect(feed).toHaveLength(3);
    expect(feed[0]?.title).toBe("Measured progress & public evidence");
    const article = await parseDocument("article", recordings.bodies.article, "https://news.example/story",
      loaded.extraction, pool, { timeout_ms: 10000 });
    expect(article.word_count).toBeGreaterThan(0);
    controller.abort();
    expect(await pool.parseFeed(recordings.bodies.atom)).toHaveLength(2);
  } finally { pool.close(); }
}, 5000);

test("queued expiry removes only that request and leaves caller-owned workers usable", async () => {
  const { bodies } = await readRecordings();
  const pool = new ArticleParserPool(1);
  const controller = new AbortController();
  const first = pool.parseFeed(bodies.rss, { signal: controller.signal, timeout_ms: 10000 });
  const firstResult = first.catch(error => error);
  let queuedStarted = false;
  try {
    await expect(pool.parseFeed(bodies.atom, {
      timeout_ms: 1, activity: phase => { if (phase === "started") queuedStarted = true; },
    })).rejects.toMatchObject({ reason: "parser-timeout" });
    expect(queuedStarted).toBe(false);
    await firstResult;
    expect(await pool.parseFeed(bodies.rss)).toHaveLength(3);
  } finally { controller.abort(); pool.close(); await firstResult; }
});

test("expiry terminates an assigned feed worker and a replacement handles later work", async () => {
  const { bodies } = await readRecordings();
  const pool = new ArticleParserPool(1);
  try {
    await expect(pool.parseFeed(bodies.rss, { timeout_ms: 1 })).rejects.toMatchObject({ reason: "parser-timeout" });
    expect(await pool.parseFeed(bodies.rss)).toHaveLength(3);
  } finally { pool.close(); }
});

test("queued cancellation removes its request without closing another caller's pool", async () => {
  const { bodies } = await readRecordings();
  const pool = new ArticleParserPool(1);
  const controller = new AbortController();
  const first = pool.parseFeed(bodies.rss);
  const queued = pool.parseFeed(bodies.atom, { signal: controller.signal });
  try {
    controller.abort();
    await expect(queued).rejects.toMatchObject({ reason: "parser-cancelled" });
    expect(await first).toHaveLength(3);
    await expect(pool.parseFeed("<not-a-feed>")).rejects.toMatchObject({ message: "malformed-feed" });
    expect(await pool.parseFeed(bodies.rss)).toHaveLength(3);
  } finally { pool.close(); await first.catch(() => {}); }
});

test("a running HTML parser can be cancelled without cancelling another request", async () => {
  const [loaded, { bodies }] = await Promise.all([inputs(), readRecordings()]);
  const pool = new ArticleParserPool(1);
  const controller = new AbortController();
  try {
    await expect(pool.parse(bodies.article, "https://news.example/story", loaded.extraction, {
      signal: controller.signal, activity: phase => { if (phase === "started") controller.abort(); },
    })).rejects.toMatchObject({ reason: "parser-cancelled" });
    expect(await pool.parseFeed(bodies.rss)).toHaveLength(3);
    const cancelled = new AbortController();
    cancelled.abort();
    await expect(pool.parseFeed(bodies.rss, { signal: cancelled.signal })).rejects.toMatchObject({ reason: "parser-cancelled" });
  } finally { pool.close(); }
});

test("native XML and HTML execution cannot hold the listener loop past their deadlines", async () => {
  const [loaded, { bodies }] = await Promise.all([inputs(), readRecordings()]);
  const item = bodies.rss.match(/<item>[\s\S]*?<\/item>/)?.[0];
  if (item === undefined) throw new Error("Recorded RSS must contain an item for the bounded large-input case");
  const prose = bodies.article.match(/<article>([\s\S]*?)<\/article>/)?.[1];
  if (prose === undefined) throw new Error("Recorded HTML must contain article prose for the bounded large-input case");
  const feed = bodies.rss.replace(item, item.repeat(20000));
  const html = bodies.article.replace("</article>", `${prose.repeat(2000)}</article>`);
  const pool = new ArticleParserPool(1);
  try {
    for (const kind of ["feed", "article"] as const) {
      await pool.parseFeed(bodies.rss);
      let started = false;
      let loopAdvanced = false;
      const options = { timeout_ms: 100, activity: (phase: "started" | "completed" | "failed") => {
        if (phase === "started") {
          started = true;
          setTimeout(() => { loopAdvanced = true; }, 0);
        }
      } };
      const pending = kind === "feed" ? pool.parseFeed(feed, options)
        : pool.parse(html, "https://news.example/story", loaded.extraction, options);
      await expect(pending).rejects.toMatchObject({ reason: "parser-timeout" });
      expect(started).toBe(true);
      expect(loopAdvanced).toBe(true);
      expect(await pool.parseFeed(bodies.rss)).toHaveLength(3);
    }
  } finally { pool.close(); }
});

test("actual worker deadlines persist explicit pipeline work failures, not source refusals", async () => {
  const { bodies } = await readRecordings();
  const facts: DocumentWorkFact[] = [];
  const pool = new ArticleParserPool(1);
  const harvestContext = context();
  const work = documentWork({
    ...harvestContext, observations: {
      save: async rows => { facts.push(...rows); },
    },
  }, {
    run_id: harvestContext.writer.run_id, correlation_id: harvestContext.correlation_id,
    article_id: null, feed_id: "recorded-news",
  }, "parser-request", {
    document_kind: "feed", feed_id: "recorded-news", publisher_id: null, candidate_id: null,
    observed_run_id: harvestContext.writer.run_id, observed_attempt: harvestContext.writer.attempt,
  });
  try {
    const result = await work.parse(() => pool.parseFeed(bodies.rss, { timeout_ms: 1 }), "fetch-event", describeFeedParse);
    expect(result.parsed).toBeNull();
    expect(result.failure).toBe("parser-timeout");
    expect(facts).toMatchObject([{ operation: "parse", outcome: "failed", failure_code: "parser-timeout" }]);
    expect(facts[0]?.attribution).not.toBe("source");
    for (const reason of ["parser-timeout", "parser-cancelled", "parser-failed"] as const) {
      expect(new ParserError(reason).reason).toBe(reason);
      expect(attributeIngestOutcome({ document_kind: "feed", operation: "parse", outcome: "failed",
        failure_code: reason, http_status: null, request_phase: null })).not.toBe("source");
    }
  } finally { pool.close(); }
});
