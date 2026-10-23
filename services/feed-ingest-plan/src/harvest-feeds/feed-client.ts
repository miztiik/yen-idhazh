/** Read the complete RSS/Atom entries offered by one configured source. */
import Parser from "rss-parser";
import { FeedOutcomePayloadSchema, TimestampSchema } from "@idhazh/common-contracts";
import type { CandidateRejectionRecord, FeedOutcomePayload, SourceSnapshot } from "@idhazh/common-contracts";
import type { FeedEntry, HarvestContext } from "./harvest-types";
import type { PermittedFetcher } from "./robots-policy";
import { cleanText } from "./dom-extractor";
import { fetchRejection, recordRejection } from "./record-rejection";
import { fetchDiagnostics } from "./fetch-diagnostics";

function scalar(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (value && typeof value === "object" && "_" in value && typeof value._ === "string") return value._;
  return null;
}

function categories(value: unknown): string[] {
  if (value === undefined) return [];
  if (typeof value === "string") {
    const text = cleanText(value);
    return text ? [text] : [];
  }
  if (Array.isArray(value)) return value.flatMap(categories);
  if (value && typeof value === "object") {
    if ("$" in value && value.$ && typeof value.$ === "object" &&
      "term" in value.$ && typeof value.$.term === "string") return categories(value.$.term);
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
): Promise<{ entries: FeedEntry[]; rejection: CandidateRejectionRecord | null; outcome: FeedOutcomePayload }> {
  const outcome: FeedOutcomePayload = {
    kind: "feed_outcome", source,
    fetch_status: "not_requested", parse_status: "not_attempted",
    parsed_count: null, harvested_count: null, fetch_duration_ms: null, parse_duration_ms: null,
    rejection_reason: null,
    diagnostics: null,
    history: null,
  };
  if (source.status !== "active") {
    outcome.rejection_reason = "SOURCE_INACTIVE";
    return { entries: [], rejection: recordRejection(source, context, "SOURCE_INACTIVE"), outcome: FeedOutcomePayloadSchema.parse(outcome) };
  }
  const fetchStarted = performance.now();
  const response = await fetcher.fetch(source.feed_url);
  outcome.fetch_duration_ms = Math.round(performance.now() - fetchStarted);
  outcome.diagnostics = fetchDiagnostics(response, outcome.fetch_duration_ms);
  if (response.body === null) {
    const { reason, details } = fetchRejection(response, timeout_ms, outcome.diagnostics);
    outcome.fetch_status = response.failure === "timeout" ? "timeout"
      : response.failure === "http" ? "http_failure" : "network_failure";
    outcome.rejection_reason = reason;
    return { entries: [], rejection: recordRejection(source, context, reason, details), outcome: FeedOutcomePayloadSchema.parse(outcome) };
  }
  outcome.fetch_status = "success";
  const parseStarted = performance.now();
  let entries: FeedEntry[];
  try { entries = await parseFeed(response.body); }
  catch {
    outcome.parse_duration_ms = Math.round(performance.now() - parseStarted);
    outcome.parse_status = "failure";
    outcome.rejection_reason = "FEED_PARSE_FAILED";
    outcome.diagnostics = { ...outcome.diagnostics, stopped_stage: "parse", failure_code: "unknown", detail: "malformed-feed" };
    return {
      entries: [], rejection: recordRejection(source, context, "FEED_PARSE_FAILED", {
        http_status: response.http_status, diagnostics: outcome.diagnostics,
      }), outcome: FeedOutcomePayloadSchema.parse(outcome),
    };
  }
  outcome.parse_duration_ms = Math.round(performance.now() - parseStarted);
  outcome.parse_status = entries.length ? "success" : "empty";
  outcome.parsed_count = entries.length;
  outcome.harvested_count = 0;
  outcome.rejection_reason = entries.length ? null : "FEED_EMPTY";
  if (!entries.length) outcome.diagnostics = {
    ...outcome.diagnostics, stopped_stage: "parse", failure_code: "unknown", detail: "empty-feed",
  };
  return {
    entries,
    rejection: entries.length ? null : recordRejection(source, context, "FEED_EMPTY", {
      http_status: response.http_status, diagnostics: outcome.diagnostics,
    }),
    outcome: FeedOutcomePayloadSchema.parse(outcome),
  };
}
