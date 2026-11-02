/** Which global known-age ceiling governs one isolated request? */
import { z } from "zod";
import { FeedIngestConfigSchema, PositiveSchema } from "@idhazh/common-contracts";
import type { FeedIngestConfig } from "@idhazh/common-contracts";

export const RunPolicyOverridesSchema = z.strictObject({
  global_age_ceiling_hours: PositiveSchema.optional(),
});
export type RunPolicyOverrides = z.infer<typeof RunPolicyOverridesSchema>;

export function parseGlobalAgeCeiling(value: string | undefined): number | undefined {
  if (value === undefined || value.trim() === "") return undefined;
  if (!/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(value.trim())) {
    throw new Error("global_age_ceiling_hours requires one positive number of hours");
  }
  return PositiveSchema.parse(Number(value));
}

export function resolveRunPolicy(config: FeedIngestConfig, raw: RunPolicyOverrides): FeedIngestConfig {
  const overrides = RunPolicyOverridesSchema.parse(raw);
  return FeedIngestConfigSchema.parse({
    ...config,
    curate_articles: {
      ...config.curate_articles,
      global_age_ceiling_hours: overrides.global_age_ceiling_hours ?? config.curate_articles.global_age_ceiling_hours,
    },
  });
}
