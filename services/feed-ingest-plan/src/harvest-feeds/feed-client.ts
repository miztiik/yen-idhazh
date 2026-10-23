/** Read the complete RSS/Atom entries offered by one configured source. */
import { FeedOutcomePayloadSchema } from "@idhazh/common-contracts";
import type { CandidateRejectionRecord, FeedOutcomePayload, SourceSnapshot } from "@idhazh/common-contracts";
import type { FeedEntry, HarvestContext } from "./harvest-types";
import type { PermittedFetcher } from "./robots-policy";
import { fetchRejection, recordRejection } from "./record-rejection";
import { fetchDiagnostics } from "./fetch-diagnostics";
import { parseDocument } from "./parse-document";
import { canonicalizeUrl } from "./url-cleaner";
import { emitDocumentObservations } from "./document-observation";
import { utcTimestamp } from "./harvest-types";

export { parseFeed } from "./parse-feed";

export async function readFeed(
  source: SourceSnapshot, fetcher: PermittedFetcher, context: HarvestContext, timeout_ms: number,
): Promise<{ entries: FeedEntry[]; rejection: CandidateRejectionRecord | null; outcome: FeedOutcomePayload }> {
  const outcome: FeedOutcomePayload = {
    kind: "feed_outcome", source,
    fetch_status: "not_requested", parse_status: "not_attempted",
    parsed_count: null, harvested_count: null, fetch_duration_ms: null, parse_duration_ms: null,
    rejection_reason: null,
    diagnostics: null,
  };
  if (source.status !== "active") {
    outcome.rejection_reason = "SOURCE_INACTIVE";
    return { entries: [], rejection: recordRejection(source, context, "SOURCE_INACTIVE"), outcome: FeedOutcomePayloadSchema.parse(outcome) };
  }
  const fetchStarted = performance.now();
  const identity = {
    run_id: context.writer.run_id, correlation_id: context.correlation_id,
    article_id: canonicalizeUrl(source.feed_url).url_key, source_id: source.source_id,
  };
  const key = `${context.writer.run_id}\n${source.source_id}\nfeed`;
  const response = await fetcher.fetch(source.feed_url);
  const fetched = emitDocumentObservations(context, identity, key, "fetch", null, utcTimestamp(context.clock), response.attempts);
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
  try { entries = await parseDocument("feed", response.body, source.feed_url); }
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
  } finally {
    emitDocumentObservations(context, identity, key, "parse", fetched.event_id, utcTimestamp(context.clock));
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
