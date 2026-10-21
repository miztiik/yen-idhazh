/** Read the complete RSS/Atom entries offered by one configured source. */
import Parser from "rss-parser";
import { TimestampSchema } from "@idhazh/common-contracts";
import type { CandidateRejectionRecord, SourceSnapshot } from "@idhazh/common-contracts";
import type { FeedEntry, HarvestContext } from "./harvest-types";
import type { PermittedFetcher } from "./robots-policy";
import { cleanText } from "./dom-extractor";
import { fetchRejection, recordRejection } from "./record-rejection";

function scalar(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (value && typeof value === "object" && "_" in value && typeof value._ === "string") return value._;
  return null;
}

function categories(value: unknown): string[] {
  if (value === undefined) return [];
  if (typeof value === "string") return [cleanText(value)];
  if (Array.isArray(value)) return value.flatMap(categories);
  if (value && typeof value === "object") {
    if ("$" in value && value.$ && typeof value.$ === "object" &&
      "term" in value.$ && typeof value.$.term === "string") return [cleanText(value.$.term)];
    return Object.entries(value).filter(([key]) => key !== "$").flatMap(([, child]) => categories(child));
  }
  throw new Error("category element is not XML text");
}

function publishedTimestamp(value: unknown): string | null {
  if (typeof value !== "string" || !Number.isFinite(Date.parse(value))) return null;
  const timestamp = new Date(value).toISOString().replace(/\.\d{3}Z$/, "Z");
  const parsed = TimestampSchema.safeParse(timestamp);
  return parsed.success ? parsed.data : null;
}

export async function parseFeed(body: string): Promise<FeedEntry[]> {
  const parser = new Parser<Record<string, unknown>, Record<string, unknown>>({
    customFields: {
      feed: ["lastBuildDate", "pubDate"],
      item: [["category", "allCategories", { keepArray: true }], "author"],
    },
    xml2js: {
      // Namespace-qualified categories and prefixed Atom documents carry the same fields.
      tagNameProcessors: [(name: string) => name.replace(/^atom:/, "").replace(/^[^:]+:category$/, "category")],
      valueProcessors: [(value: unknown, name: string) =>
        ["published", "updated"].includes(name) && typeof value === "string" && !Number.isFinite(Date.parse(value)) ? "" : value],
    },
  });
  const parsed = await parser.parseString(body);
  return parsed.items.map((entry, entry_ordinal) => ({
    entry_ordinal,
    title: cleanText(scalar(entry.title) ?? "") || null,
    link: scalar(entry.link)?.trim() || null,
    categories: categories(entry.allCategories),
    author: cleanText(scalar(entry.creator) ?? scalar(entry.author) ?? "") || null,
    published_at: publishedTimestamp(entry.isoDate ?? entry.pubDate)
      ?? publishedTimestamp(parsed.lastBuildDate ?? parsed.pubDate),
  }));
}

export async function readFeed(
  source: SourceSnapshot, fetcher: PermittedFetcher, context: HarvestContext, timeout_ms: number,
): Promise<{ entries: FeedEntry[]; rejection: CandidateRejectionRecord | null }> {
  if (source.status !== "active") {
    return { entries: [], rejection: recordRejection(source, context, "SOURCE_INACTIVE") };
  }
  const response = await fetcher.fetch(source.feed_url);
  if (response.body === null) {
    const { reason, details } = fetchRejection(response, timeout_ms);
    return { entries: [], rejection: recordRejection(source, context, reason, details) };
  }
  let entries: FeedEntry[];
  try { entries = await parseFeed(response.body); }
  catch {
    return { entries: [], rejection: recordRejection(source, context, "FEED_PARSE_FAILED") };
  }
  return {
    entries,
    rejection: entries.length ? null : recordRejection(source, context, "FEED_EMPTY"),
  };
}
