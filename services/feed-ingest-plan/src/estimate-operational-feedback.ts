/** Which measured request evidence qualifies for the configured source estimate? */
import type { FeedIngestConfig } from "@idhazh/common-contracts";
import type { readIngestEvidence } from "./read-ledger-history/read-ingest-evidence";

type ArticleEvidence = Awaited<ReturnType<typeof readIngestEvidence>>;
type SourceEvidence = ArticleEvidence["sources"][number];

export function estimateOperationalFeedback(
  evidence: ArticleEvidence,
  policy: FeedIngestConfig["feedback"],
) {
  return {
    window: evidence.window,
    availability: evidence.availability,
    minimum_measured_opportunities: policy.minimum_measured_opportunities,
    minimum_measured_coverage: policy.minimum_measured_coverage,
    component_weights: policy.component_weights,
    sources: evidence.sources.map(source => estimateSource(source, policy)),
  };
}

function estimateSource(source: SourceEvidence, policy: FeedIngestConfig["feedback"]) {
  const requests = source.measured_target_requests;
  const wastedRequests = source.measured_source_wasted_requests;
  const coverage = source.measured_coverage;
  const requestEvidenceAvailable = requests !== null && wastedRequests !== null;
  const hasPositiveRequests = requestEvidenceAvailable && requests > 0;
  const supportQualified =
    source.observed_measured_opportunities >= policy.minimum_measured_opportunities
    && coverage !== null && coverage >= policy.minimum_measured_coverage;
  const qualified = hasPositiveRequests && supportQualified;
  const wasteRatio = qualified ? wastedRequests / requests : null;

  return {
    source_id: source.source_id,
    qualification_status: qualified ? "qualified" as const
      : coverage === null || !requestEvidenceAvailable ? "unavailable" as const
        : "insufficient_support" as const,
    observed_attempted_opportunities: source.observed_attempted_opportunities,
    observed_measured_opportunities: source.observed_measured_opportunities,
    measured_coverage: coverage,
    measured_target_requests: requests,
    measured_source_wasted_requests: wastedRequests,
    request_waste_ratio: wasteRatio,
    request_component_weight: policy.component_weights.requests,
    request_component_penalty: wasteRatio === null
      ? null : wasteRatio * policy.component_weights.requests,
  };
}
