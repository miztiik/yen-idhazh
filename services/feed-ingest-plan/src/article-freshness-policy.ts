/** Which global known-age ceiling applies to this captured evaluation clock? */
import type { FeedIngestConfig } from "@idhazh/common-contracts";

const millisecondsPerHour = 3_600_000;

export function freshnessCutoff(evaluatedAt: string, hours: number): string {
  return new Date(Date.parse(evaluatedAt) - hours * millisecondsPerHour).toISOString();
}

export function rejectArticleAge(config: FeedIngestConfig, ageHours: number | null) {
  const maximum = config.curate_articles.global_age_ceiling_hours;
  if (ageHours === null || ageHours <= maximum) return null;
  return {
    drop_reason: "REJECTED_SCREENING_AGE_CEILING" as const,
    details: { age_hours: ageHours, max_age_hours: maximum },
  };
}
