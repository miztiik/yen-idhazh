/** Which source-based article age windows govern one isolated request? */
import { z } from "zod";
import { FeedIngestConfigSchema, PositiveSchema } from "@idhazh/common-contracts";
import type { FeedIngestConfig } from "@idhazh/common-contracts";

export const AgeWindowsSchema = z.array(PositiveSchema).min(1).refine(
  hours => hours.every((hour, index) => index === 0 || hour > hours[index - 1]!),
  "article age windows must be strictly increasing",
);
export const RunPolicyOverridesSchema = z.object({
  institutional_age_hours: AgeWindowsSchema.optional(),
  trade_press_age_hours: AgeWindowsSchema.optional(),
  community_age_hours: AgeWindowsSchema.optional(),
});
export type RunPolicyOverrides = z.infer<typeof RunPolicyOverridesSchema>;

export function parseAgeWindows(value: string | undefined): number[] | undefined {
  if (value === undefined || value.trim() === "") return undefined;
  const parts = value.split(",").map(part => part.trim());
  if (parts.some(part => !/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(part))) {
    throw new Error("article age windows require comma-separated positive numbers");
  }
  return AgeWindowsSchema.parse(parts.map(Number));
}

export function resolveRunPolicy(config: FeedIngestConfig, raw: RunPolicyOverrides): FeedIngestConfig {
  const overrides = RunPolicyOverridesSchema.parse(raw);
  // Named request controls address stable bucket IDs, never source-tier ranks.
  const byBucket = {
    institutional: overrides.institutional_age_hours,
    "trade-press": overrides.trade_press_age_hours,
    community: overrides.community_age_hours,
  };
  for (const [id, hours] of Object.entries(byBucket)) {
    if (hours !== undefined && !config.curate_articles.source_based_quality_buckets.some(rule => rule.id === id)) {
      throw new Error(`source_based_quality_buckets: age override has no matching bucket ${id}`);
    }
  }
  return FeedIngestConfigSchema.parse({
    ...config,
    curate_articles: {
      ...config.curate_articles,
      source_based_quality_buckets: config.curate_articles.source_based_quality_buckets.map(rule => ({
        ...rule, ladder_hours: byBucket[rule.id as keyof typeof byBucket] ?? rule.ladder_hours,
      })),
    },
  });
}
