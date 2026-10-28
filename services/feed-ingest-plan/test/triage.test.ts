/** Does global screening preserve actual admission evidence without persisting rejection ledgers? */
import { expect, test } from "bun:test";
import { z } from "zod";
import {
  CandidateRejectionRecordSchema, DiscoveredArticleRowSchema, DropReasonSchema, FeedIngestCandidateSchema,
  HarvestDiagnosticsSchema, deriveCandidateId,
} from "@idhazh/common-contracts";
import { loadPlanningConfig } from "../src/config/resolve-policy";
import { harvestFeeds, HarvestObservationSchema } from "@idhazh/feed-ingest-plan/harvest-feeds";
import { screenArticleCandidates } from "../src/screen-article-candidates/triage-gates";
import type { ScreeningInput } from "../src/screen-article-candidates/triage-gates";
import { DiscoveredRowSchema, indexDiscoveredEvidence } from "../src/screen-article-candidates/discovered-evidence";
import {
  RecordedTransport, context, inputs as harvestInputs, readRecordings, source as recordedSource,
  readContentFilters,
} from "./harvest-recordings";
import { measureArticleContent } from "../src/harvest-feeds/content-evidence";
import { excludeArticleContent } from "../src/screen-article-candidates/content-filters";

const fixtureUrl = new URL("../../../tests/fixtures/feed-ingest-plan/screening-cases.json", import.meta.url);
const discoveredUrl = new URL("../../../tests/fixtures/feed-ingest-plan/discovered-evidence.json", import.meta.url);
const CaseSchema = z.object({
  name: z.string(), words: z.int().nonnegative().optional(),
  status: z.number().nullable().optional(), paywall: z.boolean().optional(),
  categories: z.array(z.string()).optional(), published_at: z.string().nullable().optional(),
  discovered: z.enum(["old", "new"]).optional(), reason: DropReasonSchema.nullable(),
  details: z.record(z.string(), z.number().nullable()).optional(),
  age: z.number().nullable().optional(), clock: z.enum(["published_at", "first_seen", "unknown"]).optional(),
  bonus: z.number().optional(),
});

async function inputs() {
  const [fixture, discoveryFixture, authored] = await Promise.all([
    Bun.file(fixtureUrl).json(), Bun.file(discoveredUrl).json(),
    Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json(),
  ]);
  // Build current strict payloads from recorded content, URLs and clocks only.
  const recorded = fixture.candidate;
  const candidate = FeedIngestCandidateSchema.parse({
    date: recorded.date, correlation_id: recorded.correlation_id, run_id: recorded.run_id,
    candidate_id: recorded.candidate_id, entry_ordinal: recorded.entry_ordinal, feed_id: recorded.feed_id,
    source: {
      feed_id: recorded.source.feed_id, publisher_id: recorded.source.publisher_id ?? null,
      feed_url: recorded.source.feed_url, title: recorded.source.title,
      tier: recorded.source.tier, status: recorded.source.status,
      weight: recorded.source.weight, applied_tier_weight: recorded.source.applied_tier_weight,
    },
    canonical_url: recorded.canonical_url, url_key: recorded.url_key, title: recorded.title,
    categories: recorded.categories, article_text: recorded.article_text, word_count: recorded.word_count,
    author: recorded.author, published_at: recorded.published_at, fetched_at: recorded.fetched_at,
  });
  expect(candidate.word_count).toBe(candidate.article_text.trim().split(/\s+/u).length);
  const observation = HarvestObservationSchema.parse(fixture.observation);
  const input: ScreeningInput = {
    candidates: [candidate], observations: { [candidate.candidate_id]: observation },
    discovered: { availability: "unavailable" },
    planning: loadPlanningConfig({
      ...authored,
      harvest: { ...authored.harvest, blocked_categories: ["links", "video"] },
      triage: { ...authored.triage, min_words: 180, blocked_http_statuses: [401, 403, 429],
        recency_half_life_hours: 18, recency_weight: 0.6 },
      curate_articles: { ...authored.curate_articles, article_quality_buckets: [
        { tier: candidate.source.tier, share_pct: 100, buffer_pct: 0, ladder_hours: [24] },
      ] },
    }),
    clock_config: { collect: { max_future_hours: 6 } },
    run: { now: fixture.now, run_id: candidate.run_id, correlation_id: candidate.correlation_id, overrides: {} },
  };
  const discovered = {
    old: DiscoveredRowSchema.parse({
      url_key: discoveryFixture.rows.old.url_key, first_seen_at: discoveryFixture.rows.old.first_seen_at,
      date: discoveryFixture.rows.old.first_seen_at.slice(0, 10),
    }),
    new: DiscoveredRowSchema.parse({
      url_key: discoveryFixture.rows.new.url_key, first_seen_at: discoveryFixture.rows.new.first_seen_at,
      date: discoveryFixture.rows.new.first_seen_at.slice(0, 10),
    }),
  };
  return { input, candidate, observation, cases: CaseSchema.array().parse(fixture.cases), discovered };
}

test("recorded word, blocking, precedence and exact freshness boundaries", async () => {
  const { input, candidate, cases, discovered, observation } = await inputs();
  const diagnostics = HarvestDiagnosticsSchema.parse({ http_status: 200, fetch_ms: 17, extract_ms: 3 });
  const boundaries = CaseSchema.array().parse([
    ...cases,
    { name: "zero extracted words", words: 0, reason: "REJECTED_SCREENING_MIN_WORDS", details: { words_found: 0, words_required: 180 } },
  ]);
  const before = structuredClone(input);
  for (const entry of boundaries) {
    const words = candidate.article_text.split(/\s+/u).slice(0, entry.words ?? candidate.word_count);
    const offered = FeedIngestCandidateSchema.parse({
      ...candidate,
      word_count: words.length, article_text: words.join(" "),
      categories: entry.categories ?? candidate.categories,
      published_at: entry.published_at === undefined ? candidate.published_at : entry.published_at,
    });
    const result = await screenArticleCandidates({
      ...input, candidates: [offered],
      observations: { [offered.candidate_id]: {
        ...observation, diagnostics,
        http_status: entry.status === undefined ? 200 : entry.status, paywall: entry.paywall ?? false,
      } },
      discovered: entry.discovered === undefined ? input.discovered
        : { availability: "available", rows: [discovered[entry.discovered]] },
    });
    expect(result.rejections[0]?.drop_reason ?? null, entry.name).toBe(entry.reason);
    expect(result.admitted.length + result.rejections.length, entry.name).toBe(1);
    if (entry.reason !== null) expect(result.rejections[0]?.details.diagnostics, entry.name).toEqual(diagnostics);
    if (entry.details) expect(result.rejections[0]?.details, entry.name).toMatchObject(entry.details);
    if (entry.age !== undefined) expect(result.admitted[0]?.freshness.age_hours, entry.name).toBe(entry.age);
    if (entry.clock !== undefined) expect(result.admitted[0]?.freshness.timing_source, entry.name).toBe(entry.clock);
    if (entry.bonus !== undefined) expect(result.admitted[0]?.freshness.recency_bonus, entry.name).toBe(entry.bonus);
    if (entry.name === "one second past cutoff") expect(result.rejections[0]?.details.age_hours).toBeCloseTo(24 + 1 / 3600, 10);
  }
  expect(input).toEqual(before);
  const filters = await readContentFilters();
  const config = input.planning.config.content_filters;
  for (const entry of filters.density_cases) {
    const link = `[${"x".repeat(entry.label_chars)}](https://references.example/evidence)`;
    const markdown = link.padEnd(entry.markdown_chars, " ");
    const measured = measureArticleContent(markdown, config.press_release);
    expect(measured).toMatchObject({
      markdown_chars: entry.markdown_chars, linked_label_chars: entry.label_chars, link_density: entry.density,
    });
    expect(excludeArticleContent(measured, candidate.word_count, config)?.drop_reason ?? null, entry.name)
      .toBe(entry.excluded ? "LINK_HEAVY" : null);
    expect(excludeArticleContent(measured, candidate.word_count, {
      ...config, link_heavy: { ...config.link_heavy, enabled: false },
    })).toBeNull();
    expect(excludeArticleContent(measured, candidate.word_count, {
      ...config, link_heavy: { ...config.link_heavy, max_link_density: entry.density },
    })).toBeNull();
  }
  for (const entry of filters.list_cases) {
    const measured = measureArticleContent(Array.from({ length: entry.items }, (_, index) => `- Item ${index}`).join("\n"), config.press_release);
    expect(measured.list_items).toBe(entry.items);
    expect(excludeArticleContent(measured, entry.words, config)?.drop_reason ?? null, entry.name)
      .toBe(entry.excluded ? "LINK_HEAVY" : null);
    const article = {
      ...candidate, article_text: candidate.article_text.split(/\s+/u).slice(0, entry.words).join(" "), word_count: entry.words,
    };
    const screened = await screenArticleCandidates({
      ...input, candidates: [article],
      observations: { [article.candidate_id]: { ...observation, content_evidence: measured } },
    });
    expect(screened.rejections[0]?.drop_reason ?? null).toBe(entry.excluded ? "LINK_HEAVY" : "REJECTED_SCREENING_MIN_WORDS");
    expect(excludeArticleContent(measured, entry.words, {
      ...config, link_heavy: { ...config.link_heavy, max_list_items: entry.items },
    })).toBeNull();
    expect(excludeArticleContent(measured, entry.words, {
      ...config, link_heavy: { ...config.link_heavy, list_word_limit: entry.words },
    })).toBeNull();
  }
  for (const entry of filters.markdown_cases) {
    const measured = measureArticleContent(entry.markdown, config.press_release);
    expect(measured.linked_label_chars, entry.name).toBe(entry.linked_label_chars);
    expect(measured.list_items, entry.name).toBe(entry.list_items);
    expect(Object.values(measured).every(value => typeof value === "number" || value === null)).toBe(true);
  }
  for (const [index, marker] of config.press_release.markers.entries()) {
    const measured = measureArticleContent(`${marker.toLowerCase()}. ${candidate.article_text}`, config.press_release);
    expect(measured.press_release_marker_index).toBe(index);
    expect(excludeArticleContent(measured, candidate.word_count, config)?.drop_reason).toBe("PRESS_RELEASE");
    expect(excludeArticleContent(measured, candidate.word_count, {
      ...config, press_release: { ...config.press_release, enabled: false },
    })).toBeNull();
    const beyond = measureArticleContent(`${" ".repeat(config.press_release.sample_chars)}${marker}`, config.press_release);
    expect(beyond.press_release_marker_index).toBeNull();
    expect(measureArticleContent(`X${marker}X`, config.press_release).press_release_marker_index).toBeNull();
    const edge = measureArticleContent(`${" ".repeat(config.press_release.sample_chars - marker.length)}${marker}`, config.press_release);
    expect(edge.press_release_marker_index).toBe(index);
    expect(measureArticleContent(`${" ".repeat(config.press_release.sample_chars - marker.length + 1)}${marker}`, config.press_release).press_release_marker_index).toBeNull();
  }
  expect(excludeArticleContent(undefined, candidate.word_count, config)).toBeNull();
  const customPress = { ...config.press_release, markers: ["Recorded announcement"] };
  expect(measureArticleContent("Recorded announcement.", customPress).press_release_marker_index).toBe(0);
  expect(measureArticleContent("Recorded announcement.", { ...customPress, sample_chars: 1 }).press_release_marker_index).toBeNull();
  const competing = measureArticleContent(`${config.press_release.markers[0]} [${"x".repeat(600)}](https://references.example/evidence)`, config.press_release);
  for (const [paywall, categories, reason] of [
    [true, [], "PAYWALL_OR_BLOCKED"],
    [false, [input.planning.config.harvest.blocked_categories[0]!], "CATEGORY_EXCLUDED"],
    [false, [], "PRESS_RELEASE"],
  ] as const) {
    const screened = await screenArticleCandidates({
      ...input, candidates: [{ ...candidate, categories: [...categories], word_count: 1, article_text: "Article." }],
      observations: { [candidate.candidate_id]: { ...observation, paywall, content_evidence: competing } },
    });
    expect(screened.rejections).toHaveLength(1);
    expect(screened.rejections[0]?.drop_reason).toBe(reason);
  }
});

test("global and run policies change only their declared gates for every feed", async () => {
  const { input, candidate } = await inputs();
  const change = async (
    words: number, published_at: string, overrides: ScreeningInput["run"]["overrides"] = {},
    feed_id = candidate.feed_id,
  ) => screenArticleCandidates({
    ...input, candidates: [FeedIngestCandidateSchema.parse({
      ...candidate, feed_id, source: { ...candidate.source, feed_id },
      candidate_id: deriveCandidateId(candidate.run_id, feed_id, candidate.entry_ordinal),
      word_count: words, article_text: candidate.article_text.split(/\s+/u).slice(0, words).join(" "), published_at,
    })], observations: {}, run: { ...input.run, overrides },
  });
  input.planning = loadPlanningConfig({
    ...input.planning.config,
    triage: { ...input.planning.config.triage, min_words: 190 },
    curate_articles: { ...input.planning.config.curate_articles, article_quality_buckets: [
      { tier: candidate.source.tier, share_pct: 100, buffer_pct: 0, ladder_hours: [12] },
    ] },
  });
  for (const feed of [candidate.feed_id, "another-configured-feed"]) {
    expect((await change(189, "2026-10-21T11:00:00Z", {}, feed)).rejections[0]?.details.words_required).toBe(190);
    expect((await change(190, "2026-10-21T11:00:00Z", {}, feed)).admitted).toHaveLength(1);
  }
  expect((await change(200, "2026-10-20T18:00:00Z")).rejections[0]?.drop_reason).toBe("REJECTED_AGE_EXCEEDS_MAX_TIER_ENVELOPE");
  expect((await change(200, "2026-10-20T18:00:00Z", { freshness_hours: 18 })).rejections[0]?.drop_reason)
    .toBe("REJECTED_AGE_EXCEEDS_MAX_TIER_ENVELOPE");
  const admitted = await change(200, "2026-10-21T00:00:00Z", { freshness_hours: 18 });
  expect(admitted.admitted[0]?.freshness.recency_bonus).toBeCloseTo(0.6 * 0.5 ** (12 / 18));
  expect(admitted.admitted[0]?.policy.triage.recency_half_life_hours).toBe(18);
  expect((await change(200, "2026-10-20T18:00:00Z", { freshness_hours: 17.99 })).rejections).toHaveLength(1);
  expect(input.planning.config.curate_articles.article_quality_buckets[0]!.ladder_hours).toEqual([12]);
  input.planning.config.triage.min_words = 200;
  expect((await change(199, "2026-10-21T11:00:00Z")).rejections[0]?.details.words_required).toBe(200);
  expect((await change(200, "2026-10-21T11:30:00Z", { freshness_hours: 0.5 })).admitted).toHaveLength(1);
  input.planning.config.triage.recency_weight = 0;
  input.planning.config.triage.recency_half_life_hours = 9;
  const zero = await change(200, "2026-10-21T11:00:00Z");
  expect(zero.admitted[0]?.freshness.recency_bonus).toBe(0);
  expect(zero.admitted[0]?.policy.triage.recency_half_life_hours).toBe(9);
});

test("classification labels are refused and unavailable observations do not invent eligibility rules", async () => {
  const { input, candidate, observation } = await inputs();
  expect(FeedIngestCandidateSchema.safeParse({
    ...candidate, source: { ...candidate.source, kind: `kind-${candidate.feed_id}`, form: `form-${candidate.feed_id}` },
  }).success).toBe(false);
  const unknown = { ...observation, http_status: null, paywall: null, paywall_evidence: "not-observed" as const };
  const result = await screenArticleCandidates({ ...input, observations: { [candidate.candidate_id]: unknown } });
  expect(result.admitted[0]?.observation).toEqual(unknown);
});

test("configured HTTP/category lists and future tolerance are read, not hardcoded", async () => {
  const { input, candidate, discovered, observation } = await inputs();
  input.planning.config.triage.blocked_http_statuses = [418];
  input.planning.config.harvest.blocked_categories = ["science"];
  input.observations = { [candidate.candidate_id]: { ...observation, http_status: 403, paywall: false } };
  expect((await screenArticleCandidates(input)).rejections[0]?.drop_reason).toBe("CATEGORY_EXCLUDED");
  input.planning.config.harvest.blocked_categories = [];
  expect((await screenArticleCandidates(input)).admitted).toHaveLength(1);
  input.observations = { [candidate.candidate_id]: { ...observation, http_status: 418, paywall: null } };
  expect((await screenArticleCandidates(input)).rejections[0]?.details.http_status).toBe(418);
  input.observations = {};
  input.candidates = [{ ...candidate, published_at: "2026-10-21T14:00:00Z" }];
  input.discovered = { availability: "available", rows: [discovered.old] };
  input.clock_config = { collect: { max_future_hours: 1 } };
  expect((await screenArticleCandidates(input)).rejections[0]?.details.age_hours).toBe(50);
  input.clock_config.collect.max_future_hours = 2;
  const future = await screenArticleCandidates(input);
  expect(future.admitted[0]?.freshness).toMatchObject({ timing_source: "published_at", age_hours: -2 });
  input.clock_config.collect.max_future_hours = 0;
  expect((await screenArticleCandidates(input)).rejections[0]?.details.age_hours).toBe(50);
});

test("repeated undated and far-future fetches keep the settled first discovery", async () => {
  const { input, candidate, discovered } = await inputs();
  for (const published_at of [null, "2026-11-01T00:00:00Z"]) {
    for (const run_id of ["2026-10-21-123", "2026-10-21-124"]) {
      const candidate_id = deriveCandidateId(run_id, candidate.feed_id, candidate.entry_ordinal);
      const result = await screenArticleCandidates({
        ...input, candidates: [{
          ...candidate, run_id, candidate_id, correlation_id: run_id, published_at,
          fetched_at: run_id.endsWith("-123") ? "2026-10-21T09:00:00Z" : "2026-10-21T12:00:00Z",
        }], observations: {}, run: { ...input.run, run_id, correlation_id: run_id },
        discovered: { availability: "available", rows: [discovered.old] },
      });
      expect(result.rejections[0]?.details.age_hours).toBe(50);
    }
  }
  const missing = { ...input, candidates: [{ ...candidate, published_at: null }] };
  const unknown = await screenArticleCandidates(missing);
  const empty = await screenArticleCandidates({ ...missing, discovered: { availability: "available", rows: [] } });
  expect(unknown.admitted[0]!.freshness).toEqual(empty.admitted[0]!.freshness);
  expect(unknown.admitted[0]!.freshness).toEqual({ timing_at: null, timing_source: "unknown", age_hours: null, recency_bonus: 0 });
  expect(unknown.admitted[0]?.discovered_availability).toBe("unavailable");
  expect(empty.admitted[0]?.discovered_availability).toBe("available");
  const differentUrl = await screenArticleCandidates({
    ...missing, discovered: { availability: "available", rows: [{ ...discovered.old, url_key: "a".repeat(64) }] },
  });
  expect(differentUrl.admitted[0]?.freshness.timing_source).toBe("unknown");
});

test("current discovery rows validate UTC dates and contain only planner-owned provenance", async () => {
  const { discovered } = await inputs();
  const row = discovered.old;
  expect(Object.keys(DiscoveredArticleRowSchema.shape).sort()).toEqual(["date", "first_seen_at", "url_key"]);
  expect(DiscoveredArticleRowSchema.parse(row)).toEqual(row);
  expect(() => indexDiscoveredEvidence({ availability: "available", rows: [row, discovered.new] })).toThrow("conflicting");
  expect(indexDiscoveredEvidence({ availability: "available", rows: [row, row] }).size).toBe(1);
  expect(() => DiscoveredArticleRowSchema.parse({ ...row, first_seen_run: "2026-10-19-2" })).toThrow("first_seen_run");
  expect(() => DiscoveredArticleRowSchema.parse({ ...row, version: "2026-08-31" })).toThrow("version");
  expect(() => DiscoveredArticleRowSchema.parse({ ...row, date: "2026-10-20" })).toThrow("date");
  expect(() => DiscoveredArticleRowSchema.parse({ ...row, first_seen_at: "2026-02-30T00:00:00Z" })).toThrow("first_seen_at");
  expect(() => DiscoveredArticleRowSchema.parse({ ...row, first_seen_at: "2026-10-19T10:00:00+02:00" })).toThrow("first_seen_at");
});

test("invalid overrides, config, observations and batch identities fail by name without mutation", async () => {
  const { input, candidate, observation } = await inputs();
  const before = structuredClone(input);
  for (const freshness_hours of [0, -1, NaN, Infinity, "12", null]) {
    await expect(screenArticleCandidates({
      ...input, run: { ...input.run, overrides: JSON.parse(JSON.stringify({ freshness_hours })) },
    })).rejects.toThrow("freshness_hours");
  }
  for (const freshness_hours of [NaN, Infinity]) {
    await expect(screenArticleCandidates({
      ...input, run: { ...input.run, overrides: { freshness_hours } },
    })).rejects.toThrow("freshness_hours");
  }
  await expect(screenArticleCandidates({
    ...input, observations: { [candidate.candidate_id]: { ...observation, http_status: 600, paywall: false } },
  })).rejects.toThrow("http_status");
  await expect(screenArticleCandidates({
    ...input, observations: { [deriveCandidateId(candidate.run_id, candidate.feed_id, 99)]: observation },
  })).rejects.toThrow("observations.");
  await expect(screenArticleCandidates({
    ...input, observations: { [candidate.candidate_id]: {
      ...observation, candidate_id: deriveCandidateId(candidate.run_id, candidate.feed_id, 99),
    } },
  })).rejects.toThrow("candidate_id");
  await expect(screenArticleCandidates({ ...input, candidates: [candidate, candidate] })).rejects.toThrow("candidate_id");
  await expect(screenArticleCandidates({
    ...input, run: { ...input.run, correlation_id: "another-run" },
  })).rejects.toThrow("correlation_id");
  await expect(screenArticleCandidates({
    ...input, run: { ...input.run, run_id: "2026-10-21-999" },
  })).rejects.toThrow("run_id");
  await expect(screenArticleCandidates({
    ...input, clock_config: { collect: { max_future_hours: NaN } },
  })).rejects.toThrow("max_future_hours");
  await expect(screenArticleCandidates({
    ...input, run: { ...input.run, now: "2026-02-30T12:00:00Z" },
  })).rejects.toThrow("now");
  await expect(screenArticleCandidates({
    ...input, run: { ...input.run, overrides: { vertical: "world" } as never },
  })).rejects.toThrow("vertical");
  await expect(screenArticleCandidates({
    ...input, planning: {
      config: { ...input.planning.config, triage: { ...input.planning.config.triage, min_words: 0 } },
    },
  })).rejects.toThrow("min_words");
  for (const removed of ["vertical", "policy", "labels"]) {
    await expect(screenArticleCandidates({
      ...input, candidates: [{ ...candidate, [removed]: removed === "vertical" ? "world" : {} }],
    }), `candidate.${removed} must be refused by the screening boundary`).rejects.toThrow(removed);
  }
  await expect(screenArticleCandidates({
    ...input, candidates: [{ ...candidate, date: "2026-10-20" }],
  })).rejects.toThrow("fetch day");
  expect(input).toEqual(before);
});

test("transient rejections preserve exact details, candidate identity and the UTC evaluation day", async () => {
  const { input, candidate, discovered, observation } = await inputs();
  const offers = [
    { ...candidate, fetched_at: "2026-10-20T23:59:59Z", date: "2026-10-20", word_count: 1, article_text: "Researchers" },
    { ...candidate, categories: ["video"] },
    { ...candidate, published_at: null },
    { ...candidate },
  ];
  input.candidates = offers.map((offer, entry_ordinal) => ({
    ...offer, entry_ordinal, candidate_id: deriveCandidateId(candidate.run_id, candidate.feed_id, entry_ordinal),
  }));
  input.discovered = { availability: "available", rows: [discovered.old] };
  const blockedId = input.candidates[3]!.candidate_id;
  input.observations = {
    ...input.observations, [blockedId]: { ...observation, candidate_id: blockedId, http_status: 403, paywall: null },
  };
  const before = structuredClone(input);
  const result = await screenArticleCandidates(input);
  expect(result.admitted).toEqual([]);
  expect(result.rejections.map(row => row.drop_reason)).toEqual([
    "REJECTED_SCREENING_MIN_WORDS", "CATEGORY_EXCLUDED", "REJECTED_AGE_EXCEEDS_MAX_TIER_ENVELOPE", "PAYWALL_OR_BLOCKED",
  ]);
  for (const [index, rejection] of result.rejections.entries()) {
    expect(CandidateRejectionRecordSchema.parse(rejection)).toEqual(rejection);
    expect(rejection).toMatchObject({
      candidate_id: input.candidates[index]!.candidate_id, feed_id: candidate.feed_id,
      url_key: candidate.url_key, canonical_url: candidate.canonical_url, date: "2026-10-21",
      rejected_at: input.run.now, stage: "screen-article-candidates",
    });
  }
  expect(result.rejections[0]?.details).toMatchObject({ words_found: 1, words_required: 180 });
  expect(result.rejections[2]?.details).toMatchObject({ age_hours: 50, max_age_hours: 24 });
  expect(result.rejections[3]?.details.http_status).toBe(403);
  expect(input.candidates[0]!.date).toBe("2026-10-20");
  expect(result).not.toHaveProperty("sealing");
  expect(input).toEqual(before);
  expect(await screenArticleCandidates({ ...input, candidates: [], observations: {} }))
    .toEqual({ admitted: [], rejections: [] });
});

test("public harvesting observations compose with screening without duplicating terminal harvest failures", async () => {
  const { input } = await inputs();
  const transport = new RecordedTransport(await readRecordings());
  const loaded = await harvestInputs([recordedSource()]);
  const fetchedAt = "2026-10-22T00:00:00Z";
  const recorded = context();
  const harvested = await harvestFeeds(loaded, {
    ...recorded, writer: { ...recorded.writer, run_id: input.run.run_id }, correlation_id: input.run.correlation_id,
    max_future_hours: input.clock_config.collect.max_future_hours,
    clock: () => new Date(input.run.now), observation_clock: () => new Date(fetchedAt),
  }, { transport, resolve: transport.resolve });
  const observations = Object.fromEntries(harvested.articles.flatMap(article =>
    article.candidate === null ? [] : [[article.candidate.candidate_id, article.observation]],
  ));
  const screened = await screenArticleCandidates({
    ...input, candidates: harvested.candidates, observations,
    planning: loadPlanningConfig({
      ...loaded.config, triage: { ...loaded.config.triage, min_words: 100 },
      harvest: { ...loaded.config.harvest, blocked_categories: ["science"] },
    }),
  });
  expect(harvested.candidates).toHaveLength(2);
  expect(screened.admitted).toHaveLength(1);
  expect(screened.rejections.map(row => row.drop_reason)).toEqual(["CATEGORY_EXCLUDED"]);
  expect(screened.admitted.length + screened.rejections.length).toBe(harvested.candidates.length);
  const terminalIds = new Set(harvested.rejections.map(row => row.candidate_id));
  expect(screened.rejections.every(row => !terminalIds.has(row.candidate_id))).toBe(true);
  for (const candidate of harvested.candidates) {
    expect(candidate.fetched_at).toBe(fetchedAt);
    expect(candidate.date).toBe("2026-10-22");
    expect(candidate.run_id).toBe(input.run.run_id);
    expect(observations[candidate.candidate_id]!.observed_at).toBe(fetchedAt);
  }
  for (const entry of screened.admitted) {
    const observation = observations[entry.candidate.candidate_id]!;
    const candidate = harvested.candidates.find(row => row.candidate_id === entry.candidate.candidate_id)!;
    expect(entry.observation).toEqual(observation);
    expect(entry.candidate).toEqual(candidate);
    if (candidate.published_at === null) {
      expect(entry.freshness).toMatchObject({ timing_source: "unknown", timing_at: null, age_hours: null });
    } else {
      expect(entry.freshness).toMatchObject({
        timing_source: "published_at", timing_at: candidate.published_at,
        age_hours: (Date.parse(input.run.now) - Date.parse(candidate.published_at)) / 3_600_000,
      });
    }
  }
  expect(harvested.rejections.some(row => row.drop_reason === "MISSING_REQUIRED_FIELDS")).toBe(true);
}, 30_000);
