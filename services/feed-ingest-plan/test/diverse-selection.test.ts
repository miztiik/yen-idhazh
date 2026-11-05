/** Does each complete numerical sweep choose the exact best unseen URL and account for every identity? */
import { expect, test } from "bun:test";
import { z } from "zod";
import { FeedDiversityPolicySchema, NumericalSelectionInputSchema } from "@idhazh/common-contracts";
import type { NumericalSelectionInput } from "@idhazh/common-contracts";
import { selectDiverseArticles } from "../src/curate-article-portfolio/select-diverse-articles";
import type { FeedDiversityPolicy } from "../src/curate-article-portfolio/select-diverse-articles";

const FixtureSchema = z.object({
  absolute_tolerance: z.number().positive(),
  diversity: FeedDiversityPolicySchema,
  website_deductions: z.array(z.number()),
  feed_deductions: z.array(z.number()),
  repeat_scores: z.array(z.number()),
  alternative_score: z.number(),
  cases: z.array(z.object({
    name: z.string(),
    limit: z.int().nonnegative(),
    records: z.array(z.object({
      id: z.int().positive(), url: z.int().positive(),
      feed_id: z.string(), website_group: z.string(), base_score: z.number(),
    })),
    chosen: z.array(z.int()), duplicates: z.array(z.int()), capacity: z.array(z.int()),
  })),
  single_feed: z.object({ count: z.int(), limit: z.int(), base_score: z.number() }),
  large_pool: z.object({ count: z.int(), limit: z.int(), base_score: z.number(), strongest_base_score: z.number() }),
  rounded_tie: z.object({
    prior_winners: z.int(), prior_base_score: z.number(),
    lower_base: z.number(), higher_base: z.number(), expected_marginal: z.number(),
  }),
});

async function fixture() {
  return FixtureSchema.parse(await Bun.file(
    new URL("../../../tests/fixtures/feed-ingest-plan/diverse-selection-cases.json", import.meta.url),
  ).json());
}

function identity(ordinal: number): string { return `00000000-0000-4000-8000-${ordinal.toString(16).padStart(12, "0")}`; }
function candidate(
  id: number, base_score: number, feed_id = "main", website_group = "main.example", url = id,
): NumericalSelectionInput {
  return NumericalSelectionInputSchema.parse({
    candidate_id: identity(id), url_key: url.toString(16).padStart(64, "0"), feed_id, website_group, base_score,
  });
}

function freeze(records: NumericalSelectionInput[]): readonly NumericalSelectionInput[] {
  records.forEach(Object.freeze);
  return Object.freeze(records);
}

function ids(records: readonly NumericalSelectionInput[]): string[] {
  return records.map((record) => record.candidate_id);
}

function expectNear(actual: number, expected: number, tolerance: number): void {
  expect(Number.isFinite(actual)).toBe(true);
  expect(Math.abs(actual - expected)).toBeLessThanOrEqual(tolerance);
}

// Check each emitted choice against every remaining record, without selecting another sequence.
function assertWinnerProperties(
  records: readonly NumericalSelectionInput[], limit: number, policy: FeedDiversityPolicy,
  result: ReturnType<typeof selectDiverseArticles>,
): void {
  const seenUrls = new Set<string>();
  const feedCounts = new Map<string, number>();
  const websiteCounts = new Map<string, number>();
  const chosenIds = new Set<string>();
  expect(result.chosen.length).toBe(Math.min(limit, new Set(records.map((record) => record.url_key)).size));
  for (const winner of result.chosen) {
    expect(records.includes(winner.record)).toBe(true);
    expect(seenUrls.has(winner.record.url_key)).toBe(false);
    const domain = policy.lambda_domain * ((websiteCounts.get(winner.record.website_group) ?? 0) ** 2);
    const feed = policy.lambda_feed * ((feedCounts.get(winner.record.feed_id) ?? 0) ** 2);
    const bonus = feedCounts.has(winner.record.feed_id) ? 0 : policy.novelty_bonus;
    expect(winner.score).toBe(((winner.record.base_score - domain) - feed) + bonus);
    expect(winner.domain_diversity_penalty).toBe(-domain);
    expect(winner.feed_diversity_penalty).toBe(-feed);
    expect(winner.novelty_bonus).toBe(bonus);
    for (const contender of records) {
      if (seenUrls.has(contender.url_key)) continue;
      const score = ((contender.base_score
        - policy.lambda_domain * ((websiteCounts.get(contender.website_group) ?? 0) ** 2))
        - policy.lambda_feed * ((feedCounts.get(contender.feed_id) ?? 0) ** 2))
        + (feedCounts.has(contender.feed_id) ? 0 : policy.novelty_bonus);
      expect(winner.score >= score).toBe(true);
      if (winner.score === score) expect(winner.record.candidate_id <= contender.candidate_id).toBe(true);
    }
    chosenIds.add(winner.record.candidate_id);
    seenUrls.add(winner.record.url_key);
    feedCounts.set(winner.record.feed_id, (feedCounts.get(winner.record.feed_id) ?? 0) + 1);
    websiteCounts.set(winner.record.website_group, (websiteCounts.get(winner.record.website_group) ?? 0) + 1);
  }
  expect(result.chosen.length + result.losses.length).toBe(records.length);
  expect(new Set([...chosenIds, ...result.losses.map(({ record }) => record.candidate_id)]).size).toBe(records.length);
  expect(result.losses.map(({ record }) => record)).toEqual(records.filter((record) => !chosenIds.has(record.candidate_id)));
  for (const loss of result.losses) {
    expect(records.includes(loss.record)).toBe(true);
    expect(chosenIds.has(loss.record.candidate_id)).toBe(false);
    expect(loss.reason).toBe(seenUrls.has(loss.record.url_key)
      ? "REJECTED_DUPLICATE_CANONICAL_CARRIER" : "REJECTED_GLOBAL_CAPACITY_REACHED");
  }
}

test("K2-K6: fixed sequences, saved winner counters, duplicates and input permutations", async () => {
  const data = await fixture();
  for (const entry of data.cases) {
    const records = entry.records.map(({ id, url, feed_id, website_group, base_score }) =>
      candidate(id, base_score, feed_id, website_group, url));
    const rotations = records.map((_, index) => [...records.slice(index), ...records.slice(0, index)]);
    for (const order of [records, [...records].reverse(), ...rotations]) {
      const frozen = freeze(order);
      const before = JSON.stringify(frozen);
      const result = selectDiverseArticles(frozen, entry.limit, data.diversity);
      expect(ids(result.chosen.map(({ record }) => record)), entry.name).toEqual(entry.chosen.map(identity));
      for (const [reason, expected] of [
        ["REJECTED_DUPLICATE_CANONICAL_CARRIER", entry.duplicates],
        ["REJECTED_GLOBAL_CAPACITY_REACHED", entry.capacity],
      ] as const) {
        expect(new Set(ids(result.losses.filter((loss) => loss.reason === reason).map(({ record }) => record))))
          .toEqual(new Set(expected.map(identity)));
      }
      assertWinnerProperties(frozen, entry.limit, data.diversity, result);
      expect(JSON.stringify(frozen)).toBe(before);
    }
  }
});

test("K1 P7 P8 P10 P12: fill 100 one-feed slots, including negative scores, with exact saved terms", async () => {
  const data = await fixture();
  const entry = data.single_feed;
  const records = freeze(Array.from({ length: entry.count }, (_, index) => candidate(index + 1, entry.base_score)));
  for (const limit of [entry.limit, entry.count + 3]) {
    const result = selectDiverseArticles(records, limit, data.diversity);
    expect(ids(result.chosen.map(({ record }) => record))).toEqual(
      Array.from({ length: Math.min(entry.count, limit) }, (_, index) => identity(index + 1)),
    );
    expect(result.chosen.at(-1)!.score).toBeLessThan(0);
    for (const [index, points] of data.website_deductions.entries()) {
      expectNear(result.chosen[index]!.domain_diversity_penalty, points, data.absolute_tolerance);
      expectNear(result.chosen[index]!.feed_diversity_penalty, data.feed_deductions[index]!, data.absolute_tolerance);
      expect(result.chosen[index]!.novelty_bonus).toBe(index === 0 ? data.diversity.novelty_bonus : 0);
    }
    for (const [index, points] of data.repeat_scores.entries()) {
      expectNear(result.chosen[index]!.score, points, data.absolute_tolerance);
    }
    assertWinnerProperties(records, limit, data.diversity, result);
  }
});

test("P11: the unchanged cached base yields the alternative's 2.74-point score", async () => {
  const data = await fixture();
  const result = selectDiverseArticles(freeze([
    candidate(1, 2.6), candidate(2, 2.6), candidate(3, 2.59, "other", "other.example"),
  ]), 2, data.diversity);
  expectNear(result.chosen[1]!.score, data.alternative_score, data.absolute_tolerance);
  expect(result.chosen[1]!.record.base_score).toBe(2.59);
});

test("K5: a resolved hostname key receives growing penalties across different feeds", async () => {
  const data = await fixture();
  const records = freeze([
    candidate(1, 3, "alpha", "localhost"),
    candidate(2, 3, "beta", "localhost"),
    candidate(3, 3, "gamma", "localhost"),
    candidate(4, 3, "delta", "localhost"),
  ]);
  const result = selectDiverseArticles(records, records.length, data.diversity);
  for (const [index, winner] of result.chosen.entries()) {
    expectNear(winner.domain_diversity_penalty, data.website_deductions[index]!, data.absolute_tolerance);
    expect(winner.feed_diversity_penalty).toBe(-0);
    expect(winner.novelty_bonus).toBe(data.diversity.novelty_bonus);
  }
  assertWinnerProperties(records, records.length, data.diversity, result);
});

test("K11: the full frozen pool beyond 1500 includes its strongest last record without mutation", async () => {
  const data = await fixture();
  const entry = data.large_pool;
  const records = freeze(Array.from({ length: entry.count }, (_, index) =>
    candidate(index + 1, index === entry.count - 1 ? entry.strongest_base_score : entry.base_score)));
  const before = JSON.stringify(records);
  const result = selectDiverseArticles(records, entry.limit, data.diversity);
  expect(result.chosen[0]!.record).toBe(records.at(-1)!);
  expect(ids(result.chosen.map(({ record }) => record))).toEqual([
    identity(entry.count), ...Array.from({ length: entry.limit - 1 }, (_, index) => identity(index + 1)),
  ]);
  assertWinnerProperties(records, entry.limit, data.diversity, result);
  expect(JSON.stringify(records)).toBe(before);
});

test("K14 P13: ten real winners make unequal bases round to equal marginal scores", async () => {
  const data = await fixture();
  const entry = data.rounded_tie;
  const lower = candidate(1, entry.lower_base);
  const higher = candidate(2, entry.higher_base);
  const prior = Array.from({ length: entry.prior_winners }, (_, index) =>
    candidate(index + 3, entry.prior_base_score));
  expect(lower.base_score).toBeLessThan(higher.base_score);
  for (const order of [[higher, ...prior, lower], [lower, ...prior.toReversed(), higher]]) {
    const records = freeze(order);
    const result = selectDiverseArticles(records, entry.prior_winners + 1, data.diversity);
    expect(ids(result.chosen.slice(0, entry.prior_winners).map(({ record }) => record))).toEqual(ids(prior));
    expect(result.chosen.at(-1)!.record).toBe(lower);
    expect(result.chosen.at(-1)!.score).toBe(entry.expected_marginal);
    const higherMarginal = ((higher.base_score - data.diversity.lambda_domain * (entry.prior_winners ** 2))
      - data.diversity.lambda_feed * (entry.prior_winners ** 2)) + 0;
    expect(higherMarginal).toBe(entry.expected_marginal);
    expect(result.losses).toEqual([{ record: higher, reason: "REJECTED_GLOBAL_CAPACITY_REACHED" }]);
    assertWinnerProperties(records, entry.prior_winners + 1, data.diversity, result);
  }
});

test("exact unequal scores never use the fixture tolerance as a tie rule", async () => {
  const data = await fixture();
  const records = freeze([candidate(1, 1), candidate(2, 1.0000000000000002)]);
  const policy = { ...data.diversity, novelty_bonus: 0 };
  const result = selectDiverseArticles(records, 1, policy);
  expect(result.chosen[0]!.record).toBe(records[1]!);
  assertWinnerProperties(records, 1, policy, result);
});

test("empty, zero-limit and duplicate-only exhausted supply have complete terminal accounting", async () => {
  const data = await fixture();
  expect(selectDiverseArticles([], 5, data.diversity)).toEqual({ chosen: [], losses: [] });
  const records = freeze([candidate(2, -2, "main", "main.example", 1), candidate(1, -1)]);
  const zero = selectDiverseArticles(records, 0, data.diversity);
  expect(zero.chosen).toEqual([]);
  expect(zero.losses.every(({ reason }) => reason === "REJECTED_GLOBAL_CAPACITY_REACHED")).toBe(true);
  assertWinnerProperties(records, 0, data.diversity, zero);
  const exhausted = selectDiverseArticles(records, 5, data.diversity);
  expect(exhausted.chosen[0]!.record).toBe(records[1]!);
  expect(exhausted.losses).toEqual([{
    record: records[0]!, reason: "REJECTED_DUPLICATE_CANONICAL_CARRIER",
  }]);
  assertWinnerProperties(records, 5, data.diversity, exhausted);
});

test("each diversity coefficient changes its own term and is read on a new invocation", async () => {
  const data = await fixture();
  const records = freeze([candidate(1, 3), candidate(2, 3)]);
  for (const policy of [
    { ...data.diversity, lambda_domain: 0.5 },
    { ...data.diversity, lambda_feed: 0.7 },
    { ...data.diversity, novelty_bonus: 0.9 },
    { lambda_domain: 0, lambda_feed: 0, novelty_bonus: 0 },
  ]) {
    const result = selectDiverseArticles(records, 2, policy);
    expect(result.chosen[0]!.score).toBe(3 + policy.novelty_bonus);
    expect(result.chosen[1]!.score).toBe((3 - policy.lambda_domain) - policy.lambda_feed);
    assertWinnerProperties(records, 2, policy, result);
  }
});

test("non-finite computed scores, invalid limits and invalid policies fail explicitly", async () => {
  const data = await fixture();
  for (const base_score of [Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY]) {
    expect(() => selectDiverseArticles([{ ...candidate(1, 1), base_score }], 1, data.diversity))
      .toThrow("non-finite marginal score");
  }
  const large = freeze([candidate(1, 1), candidate(2, 1), candidate(3, 1)]);
  expect(() => selectDiverseArticles(large, 3, {
    lambda_domain: Number.MAX_VALUE, lambda_feed: 0, novelty_bonus: 0,
  })).toThrow("non-finite marginal score");
  expect(() => selectDiverseArticles(large, 3, {
    lambda_domain: 0, lambda_feed: Number.MAX_VALUE, novelty_bonus: 0,
  })).toThrow("non-finite marginal score");
  expect(() => selectDiverseArticles([candidate(1, Number.MAX_VALUE)], 1, {
    ...data.diversity, novelty_bonus: Number.MAX_VALUE,
  })).toThrow("non-finite marginal score");
  for (const limit of [-1, 0.5, Number.NaN, Number.POSITIVE_INFINITY, Number.MAX_SAFE_INTEGER + 1]) {
    expect(() => selectDiverseArticles([], limit, data.diversity)).toThrow("selection limit");
  }
  for (const policy of [
    { ...data.diversity, lambda_domain: -1 },
    { ...data.diversity, lambda_feed: Number.POSITIVE_INFINITY },
    { ...data.diversity, novelty_bonus: Number.NaN },
  ]) expect(() => selectDiverseArticles([], 1, policy)).toThrow();
});
