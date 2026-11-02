/** Do real paragraph and headline measurements implement the configured soft score? */
import { expect, test } from "bun:test";
import nlp from "compromise";
import { z } from "zod";
import { FeedIngestConfigSchema, FeedSubstancePolicySchema } from "@idhazh/common-contracts";
import { countWords } from "../src/count-article-words";
import { measureSubstantiveParagraphs } from "../src/screen-article-candidates/measure-substantive-paragraphs";
import { normalizeArticleTerms, readArticleTerms } from "../src/screen-article-candidates/normalize-article-terms";
import { createSubstanceScorer } from "../src/screen-article-candidates/score-article-substance";

const FixtureSchema = z.object({
  absolute_tolerance: z.number().positive(),
  length_cases: z.array(z.object({ words: z.int().nonnegative(), points: z.number() })),
  headlines: z.array(z.object({ title: z.string(), shouting: z.boolean() })),
  questions: z.array(z.object({ text: z.string(), terms: z.array(z.string()) })),
  paragraphs: z.array(z.object({
    name: z.string(), text: z.string(), words: z.int(), sentences: z.int(),
    names: z.int(), numbers: z.int(), retained: z.boolean(),
  })),
});

async function inputs() {
  const [config, recording] = await Promise.all([
    Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json(),
    Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/substance-score-cases.json", import.meta.url)).json(),
  ]);
  return { policy: FeedIngestConfigSchema.parse(config).curate_articles.substance, fixture: FixtureSchema.parse(recording) };
}
// Generated exact-length input isolates the curve from language recognition.
function words(count: number) { return Array.from({ length: count }, () => "water").join(" "); }

test("every declared soft-ramp, full-band and taper endpoint uses measured retained words", async () => {
  const { policy, fixture } = await inputs();
  const score = createSubstanceScorer(policy);
  for (const entry of fixture.length_cases) {
    const result = score("water", words(entry.words));
    expect(result.substance_word_count, `${entry.words} retained words`).toBe(entry.words);
    expect(Math.abs(result.length_score - entry.points)).toBeLessThanOrEqual(fixture.absolute_tolerance);
    expect(result.density_score).toBe(0);
    expect(Math.abs(result.substance_score - entry.points)).toBeLessThanOrEqual(fixture.absolute_tolerance);
  }
  const changed = createSubstanceScorer({
    ...policy, word_count_ramp_end: 100, word_count_sweet_spot_max: 200, word_count_plateau_start: 300,
    length_scores: { full: 2 }, long_form_floor_score: 0.5,
  });
  for (const [count, points] of [[50, 1], [100, 2], [200, 2], [250, 1.25], [300, 0.5], [301, 0.5]]) {
    expect(changed("water", words(count!)).length_score).toBe(points!);
  }
});

test("recorded library sentences, names and quantities are retained once by inclusive OR", async () => {
  const { policy, fixture } = await inputs();
  for (const entry of fixture.paragraphs) {
    expect(countWords(entry.text), entry.name).toBe(entry.words);
    const actual = nlp(entry.text);
    expect(actual.sentences().length, entry.name).toBe(entry.sentences);
    expect(actual.match("#ProperNoun+").length, entry.name).toBe(entry.names);
    expect(actual.numbers().not("#ProperNoun").length, entry.name).toBe(entry.numbers);
    const result = measureSubstantiveParagraphs(entry.text, policy);
    expect(result).toEqual({
      substance_word_count: entry.retained ? entry.words : 0,
      sentence_count: entry.retained ? entry.sentences : 0,
      name_count: entry.retained ? entry.names : 0,
      number_count: entry.retained ? entry.numbers : 0,
      opening_text: entry.retained ? entry.text : "",
    });
    expect(JSON.parse(JSON.stringify(result))).toEqual(result);
  }
  const footer = "Subscribe now. Terms apply.";
  expect(measureSubstantiveParagraphs(words(24), policy).substance_word_count).toBe(0);
  expect(measureSubstantiveParagraphs(words(25), policy).substance_word_count).toBe(25);
  expect(measureSubstantiveParagraphs(`\n \r\n${words(25)}\r\n\n${footer}\r\n`, policy)).toEqual({
    substance_word_count: 29, sentence_count: 3, name_count: 0, number_count: 0,
    opening_text: `${words(25)}\n\n${footer}`,
  });
  expect(measureSubstantiveParagraphs(words(24), { ...policy, substantive_paragraph_min_words: 24 }).substance_word_count).toBe(24);
  expect(measureSubstantiveParagraphs(footer, { ...policy, substantive_paragraph_min_sentences: 3 }).substance_word_count).toBe(0);
  expect(measureSubstantiveParagraphs("Alice reviewed 12 samples", {
    ...policy, substantive_paragraph_min_sentences: 1,
  }).substance_word_count).toBe(4);
  expect(measureSubstantiveParagraphs(` \t\r\n\n`, policy).substance_word_count).toBe(0);
  expect(measureSubstantiveParagraphs(`\u00a0${words(25).replaceAll(" ", "\u2003")}\u00a0`, policy).substance_word_count).toBe(25);
  const softWrap = words(50).match(/(?:\S+\s*){1,10}/gu)!.join("\n");
  expect(measureSubstantiveParagraphs(softWrap, policy).substance_word_count).toBe(0);
  const disclaimer = "This disclaimer describes general limits and does not provide specific advice about individual circumstances or replace independent assessment of the complete recorded material, related supporting evidence, and further information needed to decide whether these conditions apply.";
  expect(measureSubstantiveParagraphs(disclaimer, policy).substance_word_count).toBe(countWords(disclaimer));
});

test("discarded padding never changes retained length or density, even beyond full credit", async () => {
  const { policy } = await inputs();
  const score = createSubstanceScorer(policy);
  const paddingBlock = "Alice London 12 25 samples";
  for (const paddingWords of [250, 1000]) {
    const body = [words(150), ...Array.from({ length: paddingWords / 5 }, () => paddingBlock)].join("\n");
    const result = score("water", body);
    expect(countWords(body)).toBe(150 + paddingWords);
    expect(result.substance_word_count).toBe(150);
    expect(result.length_score).toBe(0.2);
    expect(result.density_score).toBe(0);
  }
  for (const paddingWords of [1000, 5000]) {
    const retained = Array.from({ length: 50 }, () => words(50));
    const body = [...retained, ...Array.from({ length: paddingWords / 5 }, () => paddingBlock)].join("\n");
    const result = score("water", body);
    expect(countWords(body)).toBe(2500 + paddingWords);
    expect(result.substance_word_count).toBe(2500);
    expect(result.length_score).toBe(1);
    expect(result.density_score).toBe(0);
  }
  const tail = "Alice collected 12 samples. Bob reviewed twenty five records.";
  const result = measureSubstantiveParagraphs(`${words(750)}\n${tail}`, policy);
  expect(result).toMatchObject({ substance_word_count: 759, sentence_count: 3, name_count: 2, number_count: 2 });
  expect(result.opening_text).not.toContain("Alice");
});

test("density normalizes sentence evidence and caps the contribution", async () => {
  const { policy } = await inputs();
  const body = "Alice counted 12 samples. The team reviewed them. They published results. Further work continues.";
  expect(measureSubstantiveParagraphs(body, policy)).toMatchObject({ sentence_count: 4, name_count: 1, number_count: 1 });
  expect(createSubstanceScorer(policy)("", body).density_score).toBe(0.15);
  expect(createSubstanceScorer(policy)("", "Alice counted 12 samples. Bob reviewed 3 records.").density_score).toBe(0.3);
  expect(createSubstanceScorer({ ...policy, entity_density_weight: 0.8, entity_density_full_credit: 2 })("", body).density_score).toBe(0.2);
});

test("headline-wide shouting includes short grammar words and acronym denominator terms", async () => {
  const { policy, fixture } = await inputs();
  const score = createSubstanceScorer(policy);
  for (const entry of fixture.headlines) {
    const result = score(entry.title, "");
    expect(result.shouting, entry.title).toBe(entry.shouting);
    expect(result.headline_deduction, entry.title).toBeCloseTo(
      (entry.shouting ? 0.1 : 0) + (entry.title === "!! ?!" ? 0.1 : 0), 12);
  }
  for (const [patch, expected] of [
    [{ shouting_min_uppercase_fraction: 0.4 }, true],
    [{ shouting_min_letters: 4 }, false],
    [{ shouting_min_words: 3 }, false],
  ] as const) {
    expect(createSubstanceScorer({ ...policy, headline: { ...policy.headline, ...patch } })("BIG NEWS calm words today", "").shouting).toBe(expected);
  }
});

test("punctuation, bounded inflection overlap, signed deductions and cap use the actual settings", async () => {
  const { policy } = await inputs();
  const score = createSubstanceScorer(policy);
  for (const title of ["Report!!", "Report?!", "Report!?"]) expect(score(title, "").headline_deduction).toBe(0.1);
  expect(score("Report!", "").punctuation).toBe(false);
  const custom = createSubstanceScorer({ ...policy, headline: { ...policy.headline, punctuation_patterns: ["~{2}"] } });
  expect(custom("Report!!", "").punctuation).toBe(false);
  expect(custom("Report~~", "").punctuation).toBe(true);
  const opening = "The researchers studied rivers. The team measured samples.";
  expect(score("Researchers study river", opening).opening_mismatch).toBe(false);
  expect(score("A river!", opening).opening_mismatch).toBe(false);
  expect(score("the and or", opening).opening_mismatch).toBe(false);
  expect(score("riverbed", opening).opening_mismatch).toBe(true);
  expect(score("Unrelated events", "").opening_mismatch).toBe(false);
  expect(score("Unrelated events", words(24)).opening_mismatch).toBe(false);
  expect(score("Unrelated events", opening).headline_deduction).toBe(0.05);
  for (const [patch, title, body, expected] of [
    [{ shouting_weight: 0.07 }, "BIG NEWS", "", 0.07],
    [{ punctuation_weight: 0.08 }, "Report!!", "", 0.08],
    [{ opening_mismatch_weight: 0.09 }, "Unrelated events", opening, 0.09],
  ] as const) {
    expect(createSubstanceScorer({ ...policy, headline: { ...policy.headline, ...patch } })(title, body).headline_deduction).toBe(expected);
  }
  const allFlagsBody = `Alice counted 12 samples ${words(746)}`;
  expect(countWords(allFlagsBody)).toBe(750);
  expect(score("BIG NEWS!!", allFlagsBody)).toMatchObject({
    length_score: 1, density_score: 0.3, headline_deduction: 0.25, substance_score: 1.05,
    shouting: true, punctuation: true, opening_mismatch: true,
  });
  expect(score("BIG NEWS!!", words(24))).toMatchObject({
    substance_word_count: 0, substance_score: -0.2, length_score: 0, density_score: 0, opening_mismatch: false,
  });
  const capped = createSubstanceScorer({
    ...policy, headline_hype_penalty: 0.12,
    headline: { ...policy.headline, shouting_weight: 0.7, punctuation_weight: 0.6, opening_mismatch_weight: 0.5 },
  });
  expect(capped("BIG NEWS!!", allFlagsBody).headline_deduction).toBe(0.12);
  const changedKeywords = createSubstanceScorer({
    ...policy, headline: { ...policy.headline, keyword_min_letters: 20 },
  });
  expect(changedKeywords("Unrelated events", opening).opening_mismatch).toBe(false);
  const stopped = createSubstanceScorer({ ...policy, headline: { ...policy.headline, stop_words: ["unrelated", "event"] } });
  expect(stopped("Unrelated events", opening).opening_mismatch).toBe(false);
  const bounded = createSubstanceScorer({ ...policy, headline: { ...policy.headline, opening_text_max_characters: 3 } });
  expect(bounded("researchers", opening).opening_mismatch).toBe(true);
  const unicode = measureSubstantiveParagraphs(`\u{1f30a} ${words(25)}`, {
    ...policy, headline: { ...policy.headline, opening_text_max_characters: 2 },
  });
  expect(unicode.opening_text).toBe("\u{1f30a} ");
  const separator = measureSubstantiveParagraphs("Subscribe now. Terms apply.\nAlice collected 12 samples. Bob reviewed 3 records.", {
    ...policy, headline: { ...policy.headline, opening_text_max_characters: 28 },
  });
  expect([...separator.opening_text]).toHaveLength(28);
  expect(separator.opening_text).toBe("Subscribe now. Terms apply.\n");
});

test("question headlines and retained openings normalize and receive their measured score", async () => {
  const { policy, fixture } = await inputs();
  const score = createSubstanceScorer(policy);
  for (const entry of fixture.questions) {
    expect([...normalizeArticleTerms(entry.text)], entry.text).toEqual(entry.terms);
    const body = `${entry.text} ${fixture.paragraphs[2]!.text}`;
    expect(measureSubstantiveParagraphs(body, policy).opening_text, entry.text).toBe(body);
    for (const title of [entry.text, "Team reviews samples"]) {
      const result = score(title, body);
      expect(result, title).toMatchObject({
        substance_word_count: countWords(body), headline_deduction: 0, opening_mismatch: false,
      });
      expect(result.length_score, title).toBe(policy.length_scores.full * (countWords(body) / policy.word_count_ramp_end));
      expect(result.substance_score, title).toBe(result.length_score + result.density_score);
    }
  }
});

test("public JSON is validated and normalization is local, inflection-only and state-isolated", async () => {
  const { policy } = await inputs();
  const original = "Researchers STUDIED rivers!";
  const terms = normalizeArticleTerms(original);
  expect(terms.has("researcher")).toBe(true);
  expect(terms.has("study")).toBe(true);
  expect(terms.has("river")).toBe(true);
  expect(terms.has("rivers!")).toBe(false);
  expect(original).toBe("Researchers STUDIED rivers!");
  expect(normalizeArticleTerms("scrutiny").has("scrutinize")).toBe(false);
  expect([...normalizeArticleTerms("The happier children walked quickly.")])
    .toEqual(["the", "happier", "child", "walk", "quickly"]);
  expect(normalizeArticleTerms("The fastest runners went home.").has("fastest")).toBe(true);
  expect(readArticleTerms([{ terms: [{ text: "River", normal: "river", tags: ["Noun"], unused: 1 }], unused: true }]))
    .toEqual([{ text: "River", normal: "river", tags: ["Noun"] }]);
  expect(readArticleTerms([{ terms: [{ text: "Rivers", normal: "rivers", root: "river", tags: ["Noun", "Plural"], unused: 1 }], unused: true }]))
    .toEqual([{ text: "Rivers", normal: "rivers", root: "river", tags: ["Noun", "Plural"] }]);
  expect(readArticleTerms([{ terms: [{ text: "better", normal: "better", root: null, tags: ["Adverb"], unused: 1 }] }]))
    .toEqual([{ text: "better", normal: "better", root: null, tags: ["Adverb"] }]);
  for (const value of [null, {}, [{ terms: [{}] }], [{ terms: [{ text: 1, normal: "x", tags: [] }] }],
    [{ terms: [{ text: "x", normal: null, tags: [] }] }], [{ terms: [{ text: "x", normal: "x", tags: "Noun" }] }]]) {
    expect(() => readArticleTerms(value)).toThrow();
  }
  for (const root of [1, {}, []]) {
    expect(() => readArticleTerms([{ terms: [{ text: "rivers", normal: "rivers", tags: ["Noun", "Plural"], root }] }]))
      .toThrow("root");
  }
  const score = createSubstanceScorer(policy);
  const body = "Alice counted 12 samples. Bob studied rivers.";
  const before = score("Researchers study river", body);
  score("BIG NEWS!!", "Unrelated content. Nothing connects.");
  expect(score("Researchers study river", body)).toEqual(before);
  const copied = structuredClone(policy);
  const isolated = createSubstanceScorer(copied);
  copied.length_scores.full = 99;
  expect(isolated("water", words(750)).length_score).toBe(1);
});

test("invalid settings fail by field name rather than producing a zero score", async () => {
  const { policy } = await inputs();
  for (const [patch, field] of [
    [{ word_count_ramp_end: 0 }, "word_count_ramp_end"],
    [{ word_count_sweet_spot_max: 749 }, "word_count_sweet_spot_max"],
    [{ word_count_plateau_start: 3500 }, "word_count_plateau_start"],
    [{ long_form_floor_score: 2 }, "long_form_floor_score"],
    [{ entity_density_full_credit: 0 }, "entity_density_full_credit"],
    [{ entity_density_weight: Infinity }, "entity_density_weight"],
    [{ headline_hype_penalty: -1 }, "headline_hype_penalty"],
    [{ substantive_paragraph_min_words: 0 }, "substantive_paragraph_min_words"],
    [{ substantive_paragraph_min_sentences: 1.5 }, "substantive_paragraph_min_sentences"],
  ] as const) expect(() => createSubstanceScorer({ ...policy, ...patch })).toThrow(field);
  const invalidHeadlines: [Partial<typeof policy.headline>, string][] = [
    [{ punctuation_patterns: ["["] }, "punctuation_patterns"],
    [{ stop_words: ["the", "the"] }, "stop_words"],
    [{ stop_words: ["THE"] }, "stop_words"],
    [{ shouting_min_uppercase_fraction: 1.1 }, "shouting_min_uppercase_fraction"],
    [{ opening_text_max_characters: 0 }, "opening_text_max_characters"],
    [{ shouting_weight: NaN }, "shouting_weight"],
  ];
  for (const [patch, field] of invalidHeadlines) {
    expect(() => createSubstanceScorer({ ...policy, headline: { ...policy.headline, ...patch } })).toThrow(field);
  }
  expect(FeedSubstancePolicySchema.safeParse({ ...policy, word_count_ramp_end: undefined }).success).toBe(false);
});
