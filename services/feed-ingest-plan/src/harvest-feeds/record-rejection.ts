/** Validate one transient harvest rejection without writing or logging its article population. */
import {
  CandidateRejectionRecordSchema, RejectionDetailsSchema,
} from "@idhazh/common-contracts";
import type { CandidateRejectionRecord, DropReason, HarvestDiagnostics, RejectionDetails, SourceSnapshot } from "@idhazh/common-contracts";
import type { HarvestContext } from "./harvest-types";
import { utcTimestamp } from "./harvest-types";
import type { FetchResult } from "./robots-policy";

export function fetchRejection(result: FetchResult, timeout_ms: number, diagnostics: HarvestDiagnostics | null): {
  reason: DropReason; details: Partial<RejectionDetails>;
} {
  const details = { ...fetchEvidence(result), diagnostics };
  if (result.failure === "timeout") return { reason: "FETCH_TIMEOUT", details: { ...details, timeout_ms } };
  if (result.failure === "http") {
    if (result.http_status === null) throw new Error("HTTP rejection requires an observed status");
    return { reason: "FETCH_FAILED_HTTP", details };
  }
  return { reason: "FETCH_FAILED", details };
}

export function fetchEvidence(result: FetchResult) {
  return {
    http_status: result.http_status, fetch_failure: result.failure,
    error_code: result.error_code ?? null, robots: result.robots,
    robots_http_status: result.robots_http_status ?? null, robots_failure: result.robots_failure ?? null,
  };
}

export function recordRejection(
  source: Pick<SourceSnapshot, "feed_id" | "feed_url">, context: HarvestContext, reason: DropReason,
  details: Partial<RejectionDetails> = {},
  article: {
    candidate_id: string; canonical_url: string | null; url_key: string | null;
    title: string | null; categories: string[];
  } | null = null,
): CandidateRejectionRecord {
  const rejected_at = utcTimestamp(context.observation_clock ?? context.clock);
  const row = CandidateRejectionRecordSchema.parse({
    date: rejected_at.slice(0, 10), correlation_id: context.correlation_id,
    feed_id: source.feed_id, feed_url: source.feed_url,
    subject: article === null ? "feed" : "article",
    candidate_id: article?.candidate_id ?? null,
    canonical_url: article?.canonical_url ?? null, url_key: article?.url_key ?? null,
    title: article?.title ?? null, categories: article?.categories ?? [],
    stage: "harvest-feeds", drop_reason: reason, details: RejectionDetailsSchema.parse(details), rejected_at,
  });
  context.log?.(row);
  return row;
}
