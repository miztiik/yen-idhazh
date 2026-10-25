/** Which observed ingestion failures have enough evidence for source or pipeline attribution? */
import type { DocumentObservationRecord } from "@idhazh/common-contracts";

type IngestFailureEvidence = Pick<DocumentObservationRecord,
  "document_kind" | "operation" | "outcome" | "failure_code" | "http_status" | "request_phase">;

function isHttpRefusal(status: number | null): boolean {
  return status !== null && status >= 400 && status < 500;
}

export function attributeIngestOutcome(
  evidence: IngestFailureEvidence,
): DocumentObservationRecord["attribution"] {
  if (evidence.outcome !== "failed") return null;

  if (evidence.failure_code === "unsafe-target"
    || evidence.failure_code === "body-too-large"
    || evidence.failure_code === "dom-depth-exceeded") {
    return "pipeline";
  }

  if (evidence.failure_code === "robots-denied"
    || evidence.failure_code === "malformed-feed"
    || ((evidence.operation === "fetch" || (
      evidence.operation === "attempt" && evidence.request_phase === "target"
    )) && evidence.failure_code === "http" && isHttpRefusal(evidence.http_status))) {
    return "source";
  }

  if (evidence.document_kind === "article" && evidence.operation === "parse"
    && (evidence.failure_code === "missing-document-root"
      || evidence.failure_code === "empty-content"
      || evidence.failure_code === "missing-title")) {
    return "source";
  }

  return "unresolved";
}
