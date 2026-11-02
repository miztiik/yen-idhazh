/** How old is the trusted publication time, and what recency bonus does it earn? */
import type { EffectiveFeedPolicy, FeedIngestCandidate, RawArticleFreshness } from "@idhazh/common-contracts";
import type { DiscoveredRow } from "./discovered-evidence";
import { UtcInstantSchema } from "../utc-instant";

const MILLISECONDS_PER_HOUR = 60 * 60 * 1000;

export type FreshnessEvidence = RawArticleFreshness;

export function calculateFreshness(
  candidate: Pick<FeedIngestCandidate, "published_at">,
  discovered: DiscoveredRow | undefined,
  now: string,
  maxFutureHours: number,
  policy: EffectiveFeedPolicy,
): FreshnessEvidence {
  const clock = Date.parse(UtcInstantSchema.parse(now));
  const published = candidate.published_at === null ? null : UtcInstantSchema.parse(candidate.published_at);
  const trusted = published !== null && (Date.parse(published) - clock) / MILLISECONDS_PER_HOUR <= maxFutureHours;
  const effective = trusted ? published : discovered?.first_seen_at ?? null;
  const age = effective === null ? null : (clock - Date.parse(effective)) / MILLISECONDS_PER_HOUR;
  return {
    timing_at: effective,
    timing_source: trusted ? "published_at" : effective === null ? "unknown" : "first_seen",
    age_hours: age,
    recency_bonus: age === null ? 0 : policy.triage.recency_weight *
      0.5 ** (Math.max(0, age) / policy.triage.recency_half_life_hours),
  };
}
