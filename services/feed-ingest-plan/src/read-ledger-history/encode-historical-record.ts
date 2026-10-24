/** Preserve exactly the measurements each historical logical-proof schema could represent. */
import {
  ArticleAssessmentContract, CandidateRejectionContract, CONTRACT_VERSION,
  FEED_INGEST_AUDIT_VERSION, HARVEST_DIAGNOSTICS_VERSION, PLANNER_EXCLUSIONS_VERSION,
  EXTRACTION_QUALITY_VERSION, PLANNING_OBSERVATIONS_VERSION, PUBLISHER_IDENTITY_VERSION,
  SOURCE_RELIABILITY_VERSION,
  EditorialSelectionRowSchema, FeedIngestDispatchSchema,
} from "@idhazh/common-contracts";
import type { HarvestDiagnostics, LedgerCompletionEvidence, ScoreEvidence } from "@idhazh/common-contracts";

function encodeDiagnostics(diagnostics: HarvestDiagnostics | null, version: string) {
  if (version === EXTRACTION_QUALITY_VERSION || version === SOURCE_RELIABILITY_VERSION) return diagnostics;
  if (version === CONTRACT_VERSION || version === FEED_INGEST_AUDIT_VERSION) {
    if (diagnostics !== null) throw new Error("Historical proof cannot omit measured diagnostics");
    return undefined;
  }
  if (version !== HARVEST_DIAGNOSTICS_VERSION && version !== PLANNER_EXCLUSIONS_VERSION) {
    throw new Error(`Historical diagnostic encoding is not declared for ${version}`);
  }
  if (diagnostics === null) return null;
  const { quality, ...original } = diagnostics;
  if (quality !== null) throw new Error("Historical proof cannot omit measured extraction quality");
  return original;
}

function encodeSource<T extends { publisher_id: string | null }>(source: T, version: string): object {
  if (version === PUBLISHER_IDENTITY_VERSION) return source;
  if (source.publisher_id !== null) {
    throw new Error("Historical proof cannot omit curated publisher identity");
  }
  const { publisher_id: _publisherId, ...original } = source;
  return original;
}

function encodeScores(scores: ScoreEvidence | null, version: string) {
  if (scores === null) return null;
  if (version === PUBLISHER_IDENTITY_VERSION || version === SOURCE_RELIABILITY_VERSION) return scores;
  const { source_reliability, ...original } = scores;
  if (source_reliability !== null) throw new Error("Historical proof cannot omit source reliability evidence");
  return original;
}

function encodeCandidate(
  candidate: ReturnType<typeof FeedIngestDispatchSchema.parse>["content"], version: string,
) {
  const { planning_observations, ...content } = candidate;
  const hasPlanningObservations = version === PLANNING_OBSERVATIONS_VERSION
    || version === SOURCE_RELIABILITY_VERSION || version === PUBLISHER_IDENTITY_VERSION;
  if (!hasPlanningObservations && planning_observations !== null) {
    throw new Error("Historical proof cannot omit planning observations");
  }
  const candidateVersion = version === PLANNING_OBSERVATIONS_VERSION
    || version === SOURCE_RELIABILITY_VERSION ? PLANNING_OBSERVATIONS_VERSION : CONTRACT_VERSION;
  return {
    ...content, version: version === PUBLISHER_IDENTITY_VERSION ? PUBLISHER_IDENTITY_VERSION : candidateVersion,
    source: encodeSource(candidate.source, version),
    ...(hasPlanningObservations ? { planning_observations } : {}),
  };
}

export function encodeHistoricalRecord(
  ledger: LedgerCompletionEvidence["ledger"], row: object, version: string,
): object {
  if (ledger === "dispatches") {
    const current = FeedIngestDispatchSchema.parse(row);
    if (version === PUBLISHER_IDENTITY_VERSION) return current;
    if (version === PLANNING_OBSERVATIONS_VERSION) {
      return { ...current, version,
        content: encodeCandidate(current.content, version),
        selection: encodeHistoricalRecord("editorial-selections", current.selection, CONTRACT_VERSION),
      };
    }
    if (version === SOURCE_RELIABILITY_VERSION) {
      return { ...current, version,
        content: encodeCandidate(current.content, version),
        selection: encodeHistoricalRecord("editorial-selections", current.selection, version),
      };
    }
    if (version !== CONTRACT_VERSION && version !== FEED_INGEST_AUDIT_VERSION) {
      throw new Error(`Historical dispatch encoding is not declared for ${version}`);
    }
    return { ...current, version, content: encodeCandidate(current.content, version),
      selection: encodeHistoricalRecord("editorial-selections", current.selection, CONTRACT_VERSION),
    };
  }
  if (ledger === "editorial-selections") {
    if (version === PUBLISHER_IDENTITY_VERSION) return EditorialSelectionRowSchema.parse(row);
    if (version !== CONTRACT_VERSION && version !== FEED_INGEST_AUDIT_VERSION
      && version !== SOURCE_RELIABILITY_VERSION) {
      throw new Error(`Historical selection encoding is not declared for ${version}`);
    }
    const current = EditorialSelectionRowSchema.parse(row);
    return {
      ...current, version, source: encodeSource(current.source, version),
      ratings: encodeScores(current.ratings, version),
    };
  }
  if (ledger === "rejections") {
    const current = CandidateRejectionContract.schema.parse(row);
    const { diagnostics, published_on, failure_code, matched_url_marker, ...previous } = current.details;
    const originalDiagnostics = encodeDiagnostics(diagnostics, version);
    if (version !== PLANNER_EXCLUSIONS_VERSION
      && [published_on, failure_code, matched_url_marker].some(value => value !== null)) {
      throw new Error("Historical rejection proof cannot omit measured exclusion details");
    }
    return { ...current, version, details: {
      ...previous,
      ...(version === PLANNER_EXCLUSIONS_VERSION ? { published_on, failure_code, matched_url_marker } : {}),
      ...(originalDiagnostics === undefined ? {} : { diagnostics: originalDiagnostics }),
    } };
  }
  if (ledger === "article-assessments") {
    if (version === PUBLISHER_IDENTITY_VERSION) return ArticleAssessmentContract.schema.parse(row);
    const { diagnostics, ...current } = ArticleAssessmentContract.schema.parse(row);
    const originalDiagnostics = encodeDiagnostics(diagnostics, version);
    const encoded = {
      ...current, version, source: encodeSource(current.source, version),
      score_evidence: encodeScores(current.score_evidence, version),
      ...(originalDiagnostics === undefined ? {} : { diagnostics: originalDiagnostics }),
    };
    if (version === CONTRACT_VERSION) {
      const { timing_at, timing_basis, ...original } = encoded;
      if (timing_basis === "first_seen") throw new Error("Historical assessment proof cannot represent first sight");
      return { ...original, effective_published_at: timing_at, publication_clock: timing_basis };
    }
    return encoded;
  }
  throw new Error(`${ledger}: historical logical record encoding is not declared`);
}
