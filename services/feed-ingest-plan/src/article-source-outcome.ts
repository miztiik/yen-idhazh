/** Does one original article capture pass deterministic technical admission? */
import { SourceArticleRefusalReasonSchema } from "@idhazh/common-contracts";
import type { DropReason, SourceArticleOutcome } from "@idhazh/common-contracts";
import type { HarvestArticleResult } from "./harvest-feeds/harvest-types";
import { attributeIngestOutcome } from "./attribute-ingest-outcomes";

export function resolveArticleSourceOutcome(
  article: HarvestArticleResult, minWords: number, blockedStatuses: readonly number[], settledAt: string,
): SourceArticleOutcome | null {
  const refusal = (reason_code: DropReason): SourceArticleOutcome =>
    ({ disposition: "source_refused", reason_code: SourceArticleRefusalReasonSchema.parse(reason_code), settled_at: settledAt });
  if (article.candidate !== null) {
    if (article.observation.paywall === true
      || (article.observation.http_status !== null && blockedStatuses.includes(article.observation.http_status))) {
      return refusal("PAYWALL_OR_BLOCKED");
    }
    return article.candidate.word_count < minWords ? refusal("REJECTED_SCREENING_MIN_WORDS")
      : { disposition: "admitted", reason_code: null, settled_at: settledAt };
  }
  const rejection = article.rejection;
  if (rejection === null) return null;
  if (rejection.drop_reason === "EXTRACT_EMPTY"
    || (rejection.drop_reason === "MISSING_REQUIRED_FIELDS" && article.observation.extraction !== "not-attempted")) {
    return refusal(rejection.drop_reason);
  }
  const qualityFailure = rejection.details.diagnostics?.quality?.rejected
    ? rejection.details.diagnostics.quality.failure_code : null;
  const failure = rejection.details.diagnostics?.fetch_failure ?? rejection.details.diagnostics?.extraction_failure
    ?? qualityFailure ?? article.observation.fetch_failure;
  const attribution = attributeIngestOutcome({
    document_kind: "article", operation: qualityFailure === null
      ? article.observation.extraction === "not-attempted" ? "fetch" : "parse" : "quality",
    outcome: "failed", failure_code: failure, http_status: article.observation.http_status, request_phase: null,
  });
  return attribution === "source" ? refusal(rejection.drop_reason) : null;
}

export function hasArticleCapture(article: HarvestArticleResult) {
  return article.candidate !== null || article.observation.extraction !== "not-attempted"
    || article.observation.fetch_failure !== null || article.observation.http_status !== null
    || article.observation.robots !== null;
}
