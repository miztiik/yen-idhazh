/** Which authored inputs and resolved source policies govern this harvest? */
import { createHash } from "node:crypto";
import { z } from "zod";
import {
  DateStampSchema, LifecycleStatusSchema, NonEmptySchema, PolicyIdentitySchema,
  PositiveCountSchema, SlugSchema, SourceFormSchema, SourceSnapshotSchema, UrlSchema,
} from "@idhazh/common-contracts";
import type { PlanningRunOverrides, PolicyIdentity, SourceSnapshot } from "@idhazh/common-contracts";
import { loadPlanningConfig, resolvePolicy } from "../config/resolve-policy";

const LifecycleSchema = z.object({
  status: LifecycleStatusSchema, retired_on: DateStampSchema.nullable(),
}).refine(value => (value.status === "retired") === (value.retired_on !== null), {
  message: "retired_on must be present only for retired entries",
});
const WeightSchema = z.number().finite().min(0).max(1);
const SourceConfigSchema = z.object({
  id: SlugSchema, url: UrlSchema, title: NonEmptySchema, vertical: SlugSchema,
  kind: SlugSchema, tier: PositiveCountSchema, form: SourceFormSchema, weight: WeightSchema,
  ...LifecycleSchema.shape,
}).superRefine((value, ctx) => {
  if ((value.status === "retired") !== (value.retired_on !== null)) {
    ctx.addIssue({ code: "custom", message: "source lifecycle and retired_on disagree" });
  }
});
const SourcesSchema = z.object({ feeds: z.array(SourceConfigSchema) });
const RegistrySchema = z.object({
  verticals: z.array(z.object({ id: SlugSchema })),
  source_kinds: z.array(z.object({ id: SlugSchema, ...LifecycleSchema.shape })),
  source_tiers: z.array(z.object({ id: PositiveCountSchema, weight: WeightSchema, ...LifecycleSchema.shape })),
});
const ExtractionSchema = z.object({
  extract: z.object({
    max_body_bytes: z.int().min(1024), max_retries: z.int().nonnegative(),
    backoff_initial_seconds: z.number().finite().nonnegative(),
    backoff_multiplier: z.number().finite().min(1),
    paywall_markers: z.array(NonEmptySchema).min(1),
  }),
});
export type ConfiguredSource = z.infer<typeof SourceConfigSchema>;
export type ExtractionControls = z.infer<typeof ExtractionSchema>["extract"];
export type HarvestInputs = ReturnType<typeof loadHarvestInputs>;

export function loadHarvestInputs(raw: {
  config: unknown; taxonomy: unknown; sources: unknown; extraction: unknown;
}) {
  const planning = loadPlanningConfig(raw.config, raw.taxonomy);
  const registry = RegistrySchema.parse(raw.taxonomy);
  const sources = SourcesSchema.parse(raw.sources).feeds;
  const extraction = ExtractionSchema.parse(raw.extraction).extract;
  for (const [name, ids] of [
    ["source", sources.map(source => source.id)],
    ["source kind", registry.source_kinds.map(kind => kind.id)],
    ["source tier", registry.source_tiers.map(tier => tier.id)],
  ] as const) {
    if (new Set<string | number>(ids).size !== ids.length) throw new Error(`${name} ids must be distinct`);
  }
  for (const source of sources) {
    if (!registry.verticals.some(vertical => vertical.id === source.vertical)) {
      throw new Error(`source.${source.id}.vertical: unknown registry entry`);
    }
    if (!registry.source_kinds.some(kind => kind.id === source.kind)) {
      throw new Error(`source.${source.id}.kind: unknown registry entry`);
    }
    if (!registry.source_tiers.some(tier => tier.id === source.tier)) {
      throw new Error(`source.${source.id}.tier: unknown registry entry`);
    }
  }
  // This digest covers every validated input that can change harvested content or provenance.
  const snapshot = { config: planning.config, registry, sources, extraction };
  const config_sha256 = createHash("sha256").update(JSON.stringify(snapshot)).digest("hex");
  return { ...planning, registry, sources, extraction, config_sha256 };
}

export async function readHarvestInputs(paths: {
  config: string; taxonomy: string; sources: string; extraction: string;
}): Promise<HarvestInputs> {
  const [config, taxonomy, sources, extraction] = await Promise.all([
    Bun.file(paths.config).json(), Bun.file(paths.taxonomy).json(),
    Bun.file(paths.sources).json(), Bun.file(paths.extraction).json(),
  ]);
  return loadHarvestInputs({ config, taxonomy, sources, extraction });
}

export function sourceSnapshot(inputs: HarvestInputs, source: ConfiguredSource): SourceSnapshot {
  const tier = inputs.registry.source_tiers.find(tier => tier.id === source.tier);
  if (!tier) throw new Error(`source.${source.id}.tier: unknown registry entry`);
  return SourceSnapshotSchema.parse({
    source_id: source.id, feed_url: source.url, title: source.title, vertical: source.vertical,
    kind: source.kind, tier: source.tier, form: source.form, status: source.status,
    weight: source.weight, applied_tier_weight: tier.weight,
  });
}

export function harvestPolicy(
  inputs: HarvestInputs, vertical: string, overrides: PlanningRunOverrides = {},
): PolicyIdentity {
  const resolved = resolvePolicy(inputs, vertical, overrides);
  const { mmr_weights, ...curate } = resolved.curate;
  return PolicyIdentitySchema.parse({
    policy_version: inputs.config.version, config_sha256: inputs.config_sha256,
    ...resolved.triage, ...curate, ...mmr_weights,
  });
}
