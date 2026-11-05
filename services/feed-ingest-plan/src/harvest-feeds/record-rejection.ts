/** Validate one transient harvest rejection and publish only its safe terminal diagnostic. */
import {
  ArticleFailureDiagnosticDetailsSchema, articleDiagnosticContentType,
  CandidateRejectionRecordSchema, HarvestArticleFailureReasonSchema, RejectionDetailsSchema,
} from "@idhazh/common-contracts";
import type { CandidateRejectionRecord, DropReason, HarvestDiagnostics, RejectionDetails, SourceSnapshot } from "@idhazh/common-contracts";
import type { HarvestContext } from "./harvest-types";
import { utcTimestamp } from "./harvest-types";
import type { FetchResult } from "./fetch-source";
import { operationMetadata } from "../api/operation-context";

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
    error_code: result.error_code ?? null,
    pacing_time_ms: result.pacing_time_ms ?? null, pacing_settings: result.pacing_settings ?? null,
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
    date: rejected_at.slice(0, 10), traceId: context.traceId,
    feed_id: source.feed_id, feed_url: source.feed_url,
    subject: article === null ? "feed" : "article",
    candidate_id: article?.candidate_id ?? null,
    canonical_url: article?.canonical_url ?? null, url_key: article?.url_key ?? null,
    title: article?.title ?? null, categories: article?.categories ?? [],
    stage: "harvest-feeds", drop_reason: reason, details: RejectionDetailsSchema.parse(details), rejected_at,
  });
  context.log?.(row);
  const diagnostics = row.details.diagnostics;
  if (context.document_activity !== undefined && row.subject === "article" && diagnostics !== null
    && (HarvestArticleFailureReasonSchema.safeParse(reason).success
      || (reason === "MISSING_REQUIRED_FIELDS" && diagnostics.extraction_failure === "missing-title"))) {
    const response = diagnostics.response_evidence;
    const details = ArticleFailureDiagnosticDetailsSchema.parse({
      attempt: context.writer.attempt, feed_id: row.feed_id, candidate_id: row.candidate_id, url_key: row.url_key,
      stage: row.stage, reason_code: row.drop_reason,
      diagnostics: { ...diagnostics, response_evidence: response === null ? null : {
        ...response, content_type: articleDiagnosticContentType(response.content_type),
        selected_headers: {}, headers_truncated: [],
      } },
    });
    const operation = reason === "FETCH_FAILED" || reason === "FETCH_FAILED_HTTP" || reason === "FETCH_TIMEOUT"
      ? "fetch" : diagnostics.quality?.rejected ? "quality" : "parse";
    context.document_activity(operation, "failed", details, undefined, undefined, undefined, operationMetadata(context));
  }
  return row;
}
