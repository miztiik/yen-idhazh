/** Do named UTC history sets produce hand-computable overlap and novelty without invented coverage? */
import { expect, test } from "bun:test";
import { deriveUrlKey } from "@idhazh/common-contracts";
import {
  buildHistoryWindow, eventOverlap, eventRepetitionRate, novelSourceContribution, requiredHistoryDays, shiftUtcDay, sourceOverlap, unavailableEvents,
} from "../src/metrics/history-window";
import type { PublicationDay } from "../src/metrics/history-window";
import { groupPublishedEvents, recordedPairKey, uniquePublishedArticles } from "../src/metrics/fingerprint-dedup";
import type { PublishedArticle } from "../src/metrics/fingerprint-dedup";
import { RecordedEventPairSchema } from "../src/metrics/publication-evidence";
import type { RecordedEventEvidence } from "../src/metrics/publication-evidence";

const asOf = "2026-10-21T12:00:00Z";
function article(date: string, source: string, n = 1, kind = "reporting"): PublishedArticle {
  return { date, run_id: `${date}-${n}`, item_id: `ai-${source}-${n}0`, url_key: deriveUrlKey(`https://example.org/${date}/${source}/${n}`),
    source_id: source, source_kind: kind, lead: false };
}
function days(settings = { rolling_window_days: 2, overlap_windows_days: [1, 3] }, through = "2026-10-20"): PublicationDay[] {
  return requiredHistoryDays(asOf, settings, through).map(day => ({ day, status: "empty", articles: [] }));
}
function hold(input: PublicationDay[], day: string, articles: PublishedArticle[]): void {
  input[input.findIndex(held => held.day === day)] = { day, status: articles.length > 0 ? "rows" : "empty", articles };
}
test("default seven-day measurement plus seven-day reference names exactly fourteen UTC days", () => {
  const named = requiredHistoryDays(asOf, { rolling_window_days: 7, overlap_windows_days: [1, 3, 7] });
  expect(named).toHaveLength(14);
  expect(named[0]).toBe("2026-10-08");
  expect(named.at(-1)).toBe("2026-10-21");
  expect(shiftUtcDay("2024-03-01", -1)).toBe("2024-02-29");
  expect(() => shiftUtcDay("2026-02-30", 0)).toThrow("calendar");
  expect(() => requiredHistoryDays(asOf, { rolling_window_days: 7, overlap_windows_days: [] })).toThrow();
});

async function eventEvidence(
  articles: readonly PublishedArticle[], events: readonly string[],
): Promise<RecordedEventEvidence> {
  const fixture = await Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/publication-evidence.json", import.meta.url)).json();
  const items = articles.map((article, index) => ({
    item_id: article.item_id, source_url: `https://example.org/${article.date}/${article.source_id}/${article.run_id.split("-").at(-1)}`,
    title: `Recorded event ${events[index]}`, source_name: article.source_id,
  }));
  const pairs = articles.flatMap((left, index) => articles.slice(index + 1).map((right, offset) => {
    const [a, b] = [left.url_key, right.url_key].sort();
    const verdict = events[index] === events[index + offset + 1] ? "YES" : "NO";
    return RecordedEventPairSchema.parse({
      ...fixture.event_stamp, left_url_key: a, right_url_key: b,
      pair_key: recordedPairKey(a!, b!), verdict, verdict_swapped: verdict, usable: true,
    });
  }));
  return { items, pairs };
}
test("complete compatible recorded pairs yield true repetition and union-first event overlap", async () => {
  const input = days();
  const articles = [
    article("2026-10-18", "a"), article("2026-10-19", "b"),
    article("2026-10-19", "c"), article("2026-10-20", "d"),
  ];
  hold(input, "2026-10-18", [articles[0]!]);
  hold(input, "2026-10-19", articles.slice(1, 3));
  hold(input, "2026-10-20", articles.slice(3));
  const window = buildHistoryWindow(asOf, { rolling_window_days: 2, overlap_windows_days: [1, 3] }, input, "2026-10-20");
  const evidence = await eventEvidence(articles, ["fire", "fire", "flood", "fire"]);
  const current = articles.slice(1);
  expect(eventRepetitionRate(window, [...current, current[0]!], 1, evidence)).toMatchObject({
    numerator: 2, denominator: 3, value: 2 / 3, unavailable_reason: null,
  });
  expect(eventOverlap(window, current, 1, evidence)).toMatchObject({
    numerator: 2, denominator: 2, value: 1, unavailable_reason: null,
  });
  const sameDayInput = days();
  hold(sameDayInput, "2026-10-19", articles.slice(1, 3));
  const sameDay = buildHistoryWindow(asOf, { rolling_window_days: 2, overlap_windows_days: [1, 3] }, sameDayInput, "2026-10-20");
  const sameEvent = await eventEvidence(articles.slice(1, 3), ["fire", "fire"]);
  expect(eventRepetitionRate(sameDay, articles.slice(1, 3), 1, sameEvent, ["2026-10-19"]).value).toBe(0);
});
test("missing, unclear and incompatible complete-pair evidence cannot turn into zero repetition", async () => {
  const articles = [article("2026-10-19", "a"), article("2026-10-20", "b"), article("2026-10-20", "c")];
  const input = days();
  hold(input, "2026-10-19", articles.slice(0, 1));
  hold(input, "2026-10-20", articles.slice(1));
  const window = buildHistoryWindow(asOf, { rolling_window_days: 2, overlap_windows_days: [1, 3] }, input, "2026-10-20");
  const evidence = await eventEvidence(articles, ["fire", "fire", "flood"]);
  const variants: (RecordedEventEvidence | undefined)[] = [
    undefined, { ...evidence, pairs: evidence.pairs.slice(1) },
    { ...evidence, pairs: evidence.pairs.map((pair, i) => i === 0 ? { ...pair, verdict: "UNCLEAR", verdict_swapped: "UNCLEAR" } : pair) },
    { ...evidence, pairs: evidence.pairs.map((pair, i) => i === 0 ? { ...pair, prompt_digest: "c".repeat(64) } : pair) },
    { ...evidence, pairs: evidence.pairs.map((pair, i) => i === 0 ? { ...pair, usable: false } : pair) },
  ];
  for (const variant of variants) {
    expect(eventRepetitionRate(window, articles.slice(1), 1, variant, ["2026-10-20"])).toMatchObject({
      value: null, numerator: null, denominator: null, unavailable_reason: "missing_event_evidence",
    });
    expect(eventOverlap(window, articles.slice(1), 1, variant, ["2026-10-20"]).unavailable_reason).toBe("missing_event_evidence");
  }
  const bad = { ...evidence.pairs[0]!, pair_key: "a".repeat(64) };
  expect(() => groupPublishedEvents(articles, { ...evidence, pairs: [bad] })).toThrow("pair identity");
});
test("figure conflicts, same-outlet rules and complete-link groups constrain positive recorded matches", async () => {
  const articles = [article("2026-10-19", "a"), article("2026-10-20", "b"), article("2026-10-20", "c")];
  const evidence = await eventEvidence(articles, ["fire", "fire", "fire"]);
  const chain = { ...evidence, pairs: evidence.pairs.map(pair =>
    pair.pair_key === recordedPairKey(articles[0]!.url_key, articles[2]!.url_key)
      ? { ...pair, verdict: "NO" as const, verdict_swapped: "NO" as const } : pair) };
  const grouped = groupPublishedEvents(articles, chain);
  expect(grouped.availability).toBe("available");
  expect(grouped.groups.get(articles[0]!.url_key)).not.toBe(grouped.groups.get(articles[2]!.url_key));
  const two = articles.slice(0, 2);
  const pair = await eventEvidence(two, ["fire", "fire"]);
  for (const titles of [["Budget 2025", "Budget 2026"], ["Budget 25 million", "Budget 50 million"]]) {
    const result = groupPublishedEvents(two, { ...pair, items: pair.items.map((item, i) => ({ ...item, title: titles[i]! })) });
    expect(new Set(result.groups.values()).size).toBe(2);
  }
  const sameOutlet = groupPublishedEvents(two, { ...pair, items: pair.items.map(item => ({ ...item, source_name: "One outlet" })) });
  expect(new Set(sameOutlet.groups.values()).size).toBe(2);
  const unsupported = groupPublishedEvents(two, { ...pair, items: pair.items.map(item => ({ ...item, title: "\u0ba4\u0bae\u0bbf\u0bb4\u0bcd" })) });
  expect(unsupported.availability).toBe("unavailable");
});
test("rolling overlap unions current/reference source sets instead of averaging day ratios", () => {
  const input = days();
  hold(input, "2026-10-18", [article("2026-10-18", "a")]);
  hold(input, "2026-10-19", [article("2026-10-19", "a"), article("2026-10-19", "b")]);
  hold(input, "2026-10-20", [article("2026-10-20", "c")]);
  const window = buildHistoryWindow(asOf, { rolling_window_days: 2, overlap_windows_days: [1, 3] }, input, "2026-10-20");
  const current = window.measured.flatMap(day => day.articles);
  const reading = sourceOverlap(window, current, 1);
  expect(reading).toMatchObject({ value: 2 / 3, numerator: 2, denominator: 3, unavailable_reason: null });
  // Daily overlaps are 1/2 and 0/3. Their average, 1/4, is not the window reading.
  expect(reading.value).not.toBe(1 / 4);
  expect(window.availability).toBe("available");
  expect(window.required_days).toBe(5);
});
test("novel sources use history before the publishing day, deduplicate retries, and preserve kind snapshots", () => {
  const input = days();
  const one = article("2026-10-19", "a");
  const sameDayLater = article("2026-10-19", "a", 2);
  const nextDay = article("2026-10-20", "a", 1, "vendor");
  hold(input, "2026-10-19", [one, sameDayLater]);
  hold(input, "2026-10-20", [nextDay]);
  const window = buildHistoryWindow(asOf, { rolling_window_days: 2, overlap_windows_days: [1, 3] }, input, "2026-10-20");
  expect(novelSourceContribution(window, [one, one, sameDayLater, nextDay], 1)).toMatchObject({
    numerator: 2, denominator: 3, value: 2 / 3, unavailable_reason: null,
  });
  expect(uniquePublishedArticles([one, one, nextDay]).map(row => row.source_kind)).toEqual(["reporting", "vendor"]);
});
test("known-empty contributes zero, missing/lost invalidates coverage, and today stays partial", () => {
  const settings = { rolling_window_days: 2, overlap_windows_days: [1, 3] };
  const input = days(settings);
  const current = article("2026-10-20", "a");
  hold(input, current.date, [current]);
  const complete = buildHistoryWindow(asOf, settings, input, current.date);
  expect(sourceOverlap(complete, [current], 1, [current.date])).toMatchObject({ value: 0, numerator: 0, denominator: 1 });
  expect(novelSourceContribution(complete, [current], 1, [current.date]).value).toBe(1);
  for (const status of ["missing", "lost"] as const) {
    const unavailable = input.map(day => day.day === "2026-10-19" ? { ...day, status } : day);
    const window = buildHistoryWindow(asOf, settings, unavailable, current.date);
    expect(sourceOverlap(window, [current], 1, [current.date])).toMatchObject({
      value: null, numerator: null, denominator: null, coverage_days: 1, required_days: 2, unavailable_reason: "incomplete_history",
    });
  }
  const partial = buildHistoryWindow(asOf, settings, days(settings, "2026-10-21"));
  expect(partial.availability).toBe("unavailable");
  expect(partial.coverage_days).toBe(4);
  expect(sourceOverlap(partial, [], 1).unavailable_reason).toBe("incomplete_history");
});
test("empty denominators and absent event evidence remain unavailable; no input outside named days is read", () => {
  const settings = { rolling_window_days: 2, overlap_windows_days: [1, 3] };
  const window = buildHistoryWindow(asOf, settings, days(), "2026-10-20");
  expect(sourceOverlap(window, [], 1).unavailable_reason).toBe("empty_denominator");
  expect(novelSourceContribution(window, [], 1).unavailable_reason).toBe("empty_denominator");
  expect(unavailableEvents(window.days, asOf).unavailable_reason).toBe("missing_event_evidence");
  expect(() => buildHistoryWindow(asOf, settings, [...days(), { day: "1900-01-01", status: "empty", articles: [] }], "2026-10-20")).toThrow("outside");
  expect(() => sourceOverlap(window, [], 8)).toThrow("exceeds");
});
