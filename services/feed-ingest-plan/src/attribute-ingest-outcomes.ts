/** Which observed ingestion failures have enough evidence for source or pipeline attribution? */
import type { DocumentWorkFact, ExtractionQuality } from "@idhazh/common-contracts";

type IngestFailureEvidence = Omit<Pick<DocumentWorkFact,
  "document_kind" | "operation" | "outcome" | "failure_code" | "http_status" | "request_phase">,
  "operation" | "failure_code"> & {
    operation: DocumentWorkFact["operation"] | "quality";
    failure_code: DocumentWorkFact["failure_code"] | NonNullable<ExtractionQuality["failure_code"]>;
  };

function isHttpRefusal(status: number | null): boolean {
  // Protocol access/absence responses, not transient or rate-limit outcomes.
  return status === 401 || status === 403 || status === 404 || status === 410;
}

export function attributeIngestOutcome(
  evidence: IngestFailureEvidence,
): DocumentWorkFact["attribution"] {
  if (evidence.outcome !== "failed") return null;
  if (evidence.operation === "quality") return "unresolved";

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
    && evidence.failure_code === "empty-content") {
    return "source";
  }

  return "unresolved";
}
