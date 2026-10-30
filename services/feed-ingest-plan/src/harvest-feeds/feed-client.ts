/** Read the complete RSS/Atom entries offered by one configured source. */
import { FEED_OUTCOME_PAYLOAD_VERSION, FeedOutcomePayloadSchema } from "@idhazh/common-contracts";
import type { CandidateRejectionRecord, FeedOutcomePayload, SourceSnapshot } from "@idhazh/common-contracts";
import type { FeedEntry, HarvestContext } from "./harvest-types";
import type { PermittedFetcher } from "./robots-policy";
import { fetchRejection, recordRejection } from "./record-rejection";
import { fetchDiagnostics } from "./fetch-diagnostics";
import { parseDocument } from "./parse-document";
import { deriveFeedIdentity } from "./feed-identity";
import { documentWork, describeFeedParse } from "./document-work";

export { parseFeed } from "./parse-feed";

export function feedDocumentWork(source: SourceSnapshot, context: HarvestContext) {
  return documentWork(context, {
    run_id: context.writer.run_id, correlation_id: context.correlation_id,
    article_id: deriveFeedIdentity(source.feed_url).url_key, feed_id: source.feed_id,
  }, `${context.writer.run_id}\n${source.feed_id}\nfeed`, {
    document_kind: "feed", feed_id: source.feed_id, publisher_id: source.publisher_id,
    candidate_id: null, observed_run_id: context.writer.run_id, observed_attempt: context.writer.attempt,
  });
}

export async function readFeed(
  source: SourceSnapshot, fetcher: PermittedFetcher, context: HarvestContext, timeout_ms: number,
): Promise<{ entries: FeedEntry[]; rejection: CandidateRejectionRecord | null; outcome: FeedOutcomePayload }> {
  const outcome: FeedOutcomePayload = {
    version: FEED_OUTCOME_PAYLOAD_VERSION, kind: "feed_outcome", source,
    fetch_status: "not_requested", parse_status: "not_attempted",
    parsed_count: null, harvested_count: null, fetch_duration_ms: null, parse_duration_ms: null,
    rejection_reason: null,
    diagnostics: null,
    history: null,
  };
  const work = feedDocumentWork(source, context);
  if (source.status !== "active") {
    await work.skip();
    outcome.rejection_reason = "SOURCE_INACTIVE";
    return { entries: [], rejection: recordRejection(source, context, "SOURCE_INACTIVE"), outcome: FeedOutcomePayloadSchema.parse(outcome) };
  }
  const fetchStarted = performance.now();
  const { fetched: response, observation: fetched } = await work.fetch(fetcher, source.feed_url);
  outcome.fetch_duration_ms = Math.round(performance.now() - fetchStarted);
  outcome.diagnostics = fetchDiagnostics(response, outcome.fetch_duration_ms);
  if (response.body === null) {
    await work.skipParse(fetched.event_id);
    const { reason, details } = fetchRejection(response, timeout_ms, outcome.diagnostics);
    outcome.fetch_status = response.failure === "timeout" ? "timeout"
      : response.failure === "http" ? "http_failure" : "network_failure";
    outcome.rejection_reason = reason;
    return { entries: [], rejection: recordRejection(source, context, reason, details), outcome: FeedOutcomePayloadSchema.parse(outcome) };
  }
  outcome.fetch_status = "success";
  const parseStarted = performance.now();
  const body = response.body;
  const parsed = await work.parse(() => parseDocument("feed", body, source.feed_url, undefined,
    context.parser_pool, context.parser_options), fetched.event_id, describeFeedParse);
  if (parsed.parsed === null) {
    outcome.parse_duration_ms = Math.round(performance.now() - parseStarted);
    outcome.parse_status = "failure";
    outcome.rejection_reason = "FEED_PARSE_FAILED";
    outcome.diagnostics = { ...outcome.diagnostics, stopped_stage: "parse", failure_code: "unknown", detail: parsed.failure };
    return {
      entries: [], rejection: recordRejection(source, context, "FEED_PARSE_FAILED", {
        http_status: response.http_status, diagnostics: outcome.diagnostics,
      }), outcome: FeedOutcomePayloadSchema.parse(outcome),
    };
  }
  const entries = parsed.parsed;
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
