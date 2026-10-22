/** Which harvested candidates pass the configured evidence-backed screening gates? */
import { CandidateRejectionRecordSchema, WriterIdentitySchema } from "@idhazh/common-contracts";
import type { CandidateRejectionRecord, EffectiveFeedPolicy, FeedIngestCandidate, RejectionDetails } from "@idhazh/common-contracts";
import { resolvePolicy } from "../config/resolve-policy";
import { findBlockedCategory } from "./category-guard";
import { calculateFreshness } from "./freshness-decay";
import type { FreshnessEvidence } from "./freshness-decay";
import { validateScreeningInput } from "./screening-input";
import type { HarvestObservation, ScreeningInput } from "./screening-input";
import { indexSeenEvidence } from "./seen-evidence";
import { sealRejections } from "./rejection-sealer";
import type { RejectionLedgerContext } from "./rejection-sealer";

export type ScreenedCandidate = {
  candidate: FeedIngestCandidate;
  policy: EffectiveFeedPolicy;
  freshness: FreshnessEvidence;
  observation: HarvestObservation | null;
  seen_availability: ScreeningInput["seen"]["availability"];
};
export type ScreeningResult = {
  admitted: ScreenedCandidate[];
  rejections: CandidateRejectionRecord[];
  sealing: Awaited<ReturnType<typeof sealRejections>>;
};
export type { ScreeningInput, HarvestObservation } from "./screening-input";
export type { RejectionLedgerContext } from "./rejection-sealer";
export type { FreshnessEvidence } from "./freshness-decay";

export async function screenArticleCandidates(
  input: ScreeningInput, ledger: RejectionLedgerContext,
): Promise<ScreeningResult> {
  const { candidates, observations, seen, planning, run, maxFutureHours } = validateScreeningInput(input);
  const writer = WriterIdentitySchema.parse(ledger.writerContext);
  if (writer.run_id !== run.run_id) throw new Error("writerContext.run_id must match run.run_id");
  if (JSON.stringify(ledger.registryEntry.prefix) !== JSON.stringify(planning.config.seal.rejections_prefix)) {
    throw new Error("registryEntry.prefix must match config.seal.rejections_prefix");
  }
  if (ledger.ledgerSettings.compression_raw !== planning.config.seal.compression) {
    throw new Error("ledgerSettings.compression_raw must match config.seal.compression");
  }
  const seenByUrl = indexSeenEvidence(seen);
  const admitted: ScreenedCandidate[] = [];
  const rejections: CandidateRejectionRecord[] = [];
  for (const candidate of candidates) {
    const policy = resolvePolicy(planning, candidate.vertical, run.overrides);
    const observation = observations[candidate.candidate_id] ?? null;
    const freshness = calculateFreshness(candidate, seenByUrl.get(candidate.url_key), run.now, maxFutureHours, policy);
    const required = candidate.source.form === "article" ? policy.triage.min_words_article : policy.triage.min_words_abstract;
    const blockedStatus = observation?.http_status != null &&
      planning.config.triage.blocked_http_statuses.includes(observation.http_status);
    let rejection: Pick<CandidateRejectionRecord, "drop_reason"> & { details: Partial<RejectionDetails> } | null = null;
    if (observation?.paywall === true || blockedStatus) {
      rejection = { drop_reason: "PAYWALL_OR_BLOCKED", details: { http_status: observation?.http_status ?? null } };
    } else if (findBlockedCategory(candidate.categories, planning.config.harvest.blocked_categories) !== null) {
      rejection = { drop_reason: "CATEGORY_EXCLUDED", details: {} };
    } else if (candidate.word_count < required) {
      rejection = { drop_reason: "STUB_CONTENT", details: { words_found: candidate.word_count, words_required: required } };
    } else if (freshness.age_hours !== null && freshness.age_hours > policy.triage.max_age_hours) {
      rejection = {
        drop_reason: "STALE_MAX_AGE_EXCEEDED",
        details: { age_hours: freshness.age_hours, max_age_hours: policy.triage.max_age_hours },
      };
    }
    if (rejection === null) {
      admitted.push({ candidate, policy, freshness, observation, seen_availability: seen.availability });
    } else {
      rejections.push(CandidateRejectionRecordSchema.parse({
        date: run.now.slice(0, 10), correlation_id: candidate.correlation_id,
        source_id: candidate.source_id, feed_url: candidate.source.feed_url, subject: "article",
        candidate_id: candidate.candidate_id, url_key: candidate.url_key, canonical_url: candidate.canonical_url,
        title: candidate.title, categories: candidate.categories, stage: "screen-article-candidates",
        ...rejection, details: { ...rejection.details, diagnostics: observation?.diagnostics ?? null },
        rejected_at: run.now,
      }));
    }
  }
  const sealing = await sealRejections(rejections, run.now.slice(0, 10), ledger);
  return { admitted, rejections, sealing };
}
