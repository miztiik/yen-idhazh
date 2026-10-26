/** Decode one RSS, Atom, RDF or JSON feed into sanitized discovery data. */
import { parseFeed as decodeFeed, type AnyFeed, type RssFeed, type RdfFeed } from "feedsmith";
import { TimestampSchema } from "@idhazh/common-contracts";
import type { FeedEntry } from "./harvest-types";
import { cleanText } from "./dom-extractor";

export class FeedParseError extends Error {
  constructor(cause: unknown) { super("malformed-feed", { cause }); }
}
function text(value: string | undefined): string | null {
  return cleanText(value ?? "") || null;
}
function categories(values: readonly (string | undefined)[]): string[] {
  return values.flatMap(value => text(value) ?? []);
}
// ISO 8601 offsets and RFC 822 named zones are protocol values, never host-local time.
const EXPLICIT_TIME_ZONE = /(?:Z|[+-]\d{2}:?\d{2}|GMT|UTC|UT|EST|EDT|CST|CDT|MST|MDT|PST|PDT)$/i;
function publishedTimestamp(values: readonly (string | undefined)[]): string | null {
  const value = values.find(value => value !== undefined
    && EXPLICIT_TIME_ZONE.test(value.trim()) && Number.isFinite(Date.parse(value)));
  if (value === undefined) return null;
  const timestamp = new Date(value).toISOString().replace(/\.\d{3}Z$/, "Z");
  const parsed = TimestampSchema.safeParse(timestamp);
  return parsed.success ? parsed.data : null;
}
function address(value: string | undefined): string | null {
  return value?.trim() || null;
}
function identifierAddress(value: string | undefined): string | null {
  return value && /^https?:\/\//i.test(value) ? address(value) : null;
}
function rssEntry(entry: RssFeed.Item<string> | RdfFeed.Item<string>, entry_ordinal: number): FeedEntry {
  const guid = "guid" in entry && entry.guid?.isPermaLink !== false ? entry.guid?.value : undefined;
  return {
    entry_ordinal, title: text(entry.title),
    link: address(entry.link) ?? identifierAddress(guid),
    categories: categories([
      ...("categories" in entry ? entry.categories?.map(category => category.name) ?? [] : []),
      ...entry.media?.categories?.map(category => category.name) ?? [], ...entry.dc?.subjects ?? [],
    ]),
    author: text(entry.dc?.creators?.[0] ?? ("authors" in entry ? entry.authors?.[0]?.name : undefined)),
    published_at: publishedTimestamp([
      "pubDate" in entry ? entry.pubDate : undefined, ...entry.dc?.dates ?? [],
    ]),
  };
}
export async function parseFeed(body: string): Promise<FeedEntry[]> {
  let parsed: AnyFeed<string>;
  try { parsed = decodeFeed(body); }
  catch (error) { throw new FeedParseError(error); }
  if (parsed.format === "atom") {
    return (parsed.feed.entries ?? []).map((entry, entry_ordinal) => ({
      entry_ordinal, title: text(entry.title?.value),
      link: address((entry.links?.find(link => !link.rel || link.rel === "alternate") ?? entry.links?.[0])?.href)
        ?? identifierAddress(entry.id),
      categories: categories([
        ...entry.categories?.map(category => category.term) ?? [],
        ...entry.media?.categories?.map(category => category.name) ?? [], ...entry.dc?.subjects ?? [],
      ]),
      author: text(entry.authors?.[0]?.name ?? entry.dc?.creators?.[0]),
      published_at: publishedTimestamp([entry.published, entry.updated, ...entry.dc?.dates ?? []]),
    }));
  }
  if (parsed.format === "json") {
    return (parsed.feed.items ?? []).map((entry, entry_ordinal) => ({
      entry_ordinal, title: text(entry.title), link: address(entry.url) ?? identifierAddress(entry.id),
      categories: categories(entry.tags ?? []), author: text(entry.authors?.[0]?.name),
      published_at: publishedTimestamp([entry.date_published, entry.date_modified]),
    }));
  }
  return (parsed.feed.items ?? []).map(rssEntry);
}
