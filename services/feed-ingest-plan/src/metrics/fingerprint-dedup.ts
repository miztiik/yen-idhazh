/** Which exact article copies and compatible recorded event groups remain in a bounded set? */
import { isDeepStrictEqual } from "node:util";
import { deriveUrlKey } from "@idhazh/common-contracts";
import { compareHeadlineFigures } from "../curate-article-portfolio/headline-figures";
import { DigestEventItemSchema, RecordedEventPairSchema } from "./publication-evidence";
import type { RecordedEventEvidence, RecordedEventPair } from "./publication-evidence";

export function uniqueRecorded<T>(
  rows: readonly T[], identity: (row: T) => string, same: (left: T, right: T) => boolean,
): T[] {
  const held = new Map<string, T>();
  for (const row of rows) {
    const key = identity(row);
    const previous = held.get(key);
    if (previous !== undefined && !same(previous, row)) throw new Error(`Conflicting recorded identity: ${key}`);
    if (previous === undefined) held.set(key, row);
  }
  return [...held.values()];
}

export type PublishedArticle = Readonly<{
  date: string; run_id: string; item_id: string; url_key: string;
  source_id: string; source_kind: string | null; lead: boolean;
}>;

export function uniquePublishedArticles(rows: readonly PublishedArticle[]): PublishedArticle[] {
  const chronological = [...rows].sort((a, b) => a.date.localeCompare(b.date)
    || a.run_id.localeCompare(b.run_id) || a.item_id.localeCompare(b.item_id));
  const held = new Map<string, PublishedArticle>();
  for (const row of chronological) {
    const previous = held.get(row.url_key);
    if (previous === undefined) held.set(row.url_key, row);
    else if (previous.date === row.date && previous.item_id === row.item_id) {
      if (previous.run_id !== row.run_id || previous.source_id !== row.source_id || previous.source_kind !== row.source_kind) {
        throw new Error("Retry changed a published article's recorded attribution");
      }
      held.set(row.url_key, { ...previous, lead: previous.lead || row.lead });
    }
  }
  return [...held.values()];
}

export type PublishedEvents = Readonly<{
  availability: "available" | "unavailable";
  groups: ReadonlyMap<string, string>;
  matches: ReadonlyMap<string, boolean>;
  matcher_stamp: string | null;
}>;
export function recordedPairKey(left: string, right: string): string {
  return deriveUrlKey([left, right].sort().join(""));
}
function matcherStamp(pair: RecordedEventPair): string | null {
  if (!pair.usable || pair.verdict === null || pair.verdict === "UNCLEAR" || pair.verdict !== pair.verdict_swapped
    || pair.judge_model === null || pair.prompt_digest === null || pair.grammar_digest === null
    || pair.judge_temperature === null || pair.grammar_applied !== true) return null;
  return JSON.stringify([pair.version, pair.scorer_model, pair.cosine_weight, pair.judge_id,
    pair.judge_model, pair.prompt_digest, pair.grammar_digest, pair.judge_temperature, pair.grammar_applied]);
}
export function groupPublishedEvents(articles: readonly PublishedArticle[], evidence?: RecordedEventEvidence): PublishedEvents {
  const unavailable: PublishedEvents = { availability: "unavailable", groups: new Map(), matches: new Map(), matcher_stamp: null };
  const items = uniquePublishedArticles(articles).toSorted((a, b) => a.url_key.localeCompare(b.url_key));
  if (items.length === 0) return { ...unavailable, availability: "available" };
  if (evidence === undefined) return unavailable;
  const records = uniqueRecorded(evidence.items.map(item => DigestEventItemSchema.parse(item)),
    item => deriveUrlKey(item.source_url), (a, b) => a.title === b.title && a.source_name === b.source_name);
  const byUrl = new Map(records.map(item => [deriveUrlKey(item.source_url), item]));
  if (items.some(item => !byUrl.has(item.url_key))) return unavailable;
  const pairs = uniqueRecorded(evidence.pairs.map(pair => RecordedEventPairSchema.parse(pair)),
    pair => pair.pair_key, isDeepStrictEqual);
  const indexed = new Map(pairs.map(pair => [pair.pair_key, pair]));
  const matches = new Map<string, boolean>();
  let stamp: string | null = null;
  for (const [index, left] of items.entries()) {
    for (const right of items.slice(index + 1)) {
      const key = recordedPairKey(left.url_key, right.url_key);
      const a = byUrl.get(left.url_key)!;
      const b = byUrl.get(right.url_key)!;
      const figures = compareHeadlineFigures(a.title, b.title);
      if (a.source_name === b.source_name || figures.clash) { matches.set(key, false); continue; }
      const pair = indexed.get(key);
      if (pair === undefined) return unavailable;
      const recordedStamp = matcherStamp(pair);
      if (recordedStamp === null || (stamp !== null && stamp !== recordedStamp)) return unavailable;
      stamp = recordedStamp;
      if (pair.verdict === "YES" && !figures.available) return unavailable;
      matches.set(key, pair.verdict === "YES");
    }
  }
  // The group name is local to this bounded calculation, never a stored event ID.
  const groups: string[][] = [];
  for (const item of items) {
    const group = groups.find(group => group.every(key => matches.get(recordedPairKey(key, item.url_key)) === true));
    if (group === undefined) groups.push([item.url_key]);
    else group.push(item.url_key);
  }
  return { availability: "available", groups: new Map(groups.flatMap(group => group.map(key => [key, group[0]!] as const))),
    matches, matcher_stamp: stamp };
}
