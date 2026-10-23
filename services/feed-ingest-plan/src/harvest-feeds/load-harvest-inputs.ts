/** Which authored inputs and resolved source policies govern this harvest? */
import { createHash } from "node:crypto";
import { z } from "zod";
import {
  DateStampSchema, LifecycleStatusSchema, NonEmptySchema, PolicyIdentitySchema,
  PositiveCountSchema, SlugSchema, SourceFormSchema, SourceSnapshotSchema, UrlSchema,
} from "@idhazh/common-contracts";
import type { PlanningRunOverrides, PolicyIdentity, SourceSnapshot } from "@idhazh/common-contracts";
import { loadPlanningConfig, resolvePolicy } from "../config/resolve-policy";
import { ExtractionControlsSchema } from "./extraction-controls";
import { EXTRACTOR_VERSION, SANITIZER_FINGERPRINT } from "./extraction-provenance";
export type { ExtractionControls } from "./extraction-controls";

const LifecycleSchema = z.object({
  status: LifecycleStatusSchema, retired_on: DateStampSchema.nullable(),
}).refine(value => (value.status === "retired") === (value.retired_on !== null), {
  message: "retired_on must be present only for retired entries",
});
const WeightSchema = z.number().finite().min(0).max(1);
const ConfiguredUrlSchema = UrlSchema.refine(value => {
  try { const url = new URL(value); return !url.username && !url.password; }
  catch { return false; }
}, { message: "configured feed URL must be valid and contain no credentials" });
const SourceConfigSchema = LifecycleSchema.safeExtend({
  id: SlugSchema, url: ConfiguredUrlSchema, title: NonEmptySchema, vertical: SlugSchema,
  kind: SlugSchema, tier: PositiveCountSchema, form: SourceFormSchema, weight: WeightSchema,
});
const SalienceConfigSchema = LifecycleSchema.safeExtend({
  id: SlugSchema, url: ConfiguredUrlSchema, title: NonEmptySchema,
});
const SourcesSchema = z.object({
  feeds: z.array(SourceConfigSchema),
  salience: z.array(SalienceConfigSchema).nullable().default(null),
  retired: z.array(SourceConfigSchema.refine(source => source.status === "retired", {
    message: "retired entries must have retired status and a retirement date",
  })).default([]),
});
const WatchlistSchema = z.object({
  entities: z.array(LifecycleSchema.safeExtend({
    id: SlugSchema, aliases: z.array(z.string()).default([]),
  })),
});
const RegistrySchema = z.object({
  verticals: z.array(z.object({ id: SlugSchema })),
  source_kinds: z.array(LifecycleSchema.safeExtend({ id: SlugSchema })),
  source_tiers: z.array(LifecycleSchema.safeExtend({ id: PositiveCountSchema, weight: WeightSchema })),
  lenses: z.array(LifecycleSchema.safeExtend({
    id: SlugSchema, keywords: z.array(z.string().min(2).regex(/^[A-Za-z0-9][A-Za-z0-9 '/&.-]*$/)).default([]),
    weight: z.number().finite().nonnegative().default(0),
  })).optional(),
});
const ExtractionSchema = z.object({
  extract: ExtractionControlsSchema,
  summarize: z.object({ bands: z.array(z.object({ target_words_min: z.int().min(1) })).min(1) }),
  evaluation: z.object({ brief_compression_ceiling: z.number().finite().gt(0).max(1) }),
}).superRefine((value, ctx) => {
  const floor = Math.ceil(value.summarize.bands[0]!.target_words_min / value.evaluation.brief_compression_ceiling);
  if (value.extract.min_source_words !== floor) ctx.addIssue({
    code: "custom", path: ["extract", "min_source_words"],
    message: "extract.min_source_words must equal ceil(summarize.bands[0].target_words_min / evaluation.brief_compression_ceiling)",
  });
});
export type ConfiguredSource = z.infer<typeof SourceConfigSchema>;
export type HarvestInputs = ReturnType<typeof loadHarvestInputs>;

export function loadHarvestInputs(raw: {
  config: unknown; taxonomy: unknown; sources: unknown; extraction: unknown; watchlist?: unknown;
}) {
  const planning = loadPlanningConfig(raw.config, raw.taxonomy);
  const registry = RegistrySchema.parse(raw.taxonomy);
  const { feeds: sources, salience, retired } = SourcesSchema.parse(raw.sources);
  const watchlist = raw.watchlist === undefined ? null : WatchlistSchema.parse(raw.watchlist);
  const extraction_settings = ExtractionSchema.parse(raw.extraction);
  const extraction = extraction_settings.extract;
  for (const [name, ids] of [
    ["source", [...sources, ...retired, ...salience ?? []].map(source => source.id)],
    ["source kind", registry.source_kinds.map(kind => kind.id)],
    ["source tier", registry.source_tiers.map(tier => tier.id)],
    ["lens", (registry.lenses ?? []).map(lens => lens.id)],
    ["entity", (watchlist?.entities ?? []).map(entity => entity.id)],
  ] as const) {
    if (new Set<string | number>(ids).size !== ids.length) throw new Error(`${name} ids must be distinct`);
  }
  for (const source of sources) {
    if (source.status === "retired") {
      if (!registry.source_tiers.some(tier => tier.id === source.tier)) {
        throw new Error(`source.${source.id}.tier: missing registered snapshot weight`);
      }
      continue;
    }
    if (!registry.verticals.some(vertical => vertical.id === source.vertical)) {
      throw new Error(`source.${source.id}.vertical: unknown registry entry`);
    }
    if (!registry.source_kinds.some(kind => kind.id === source.kind && kind.status === "active")) {
      throw new Error(`source.${source.id}.kind: source kind must be active and registered`);
    }
    if (!registry.source_tiers.some(tier => tier.id === source.tier && tier.status === "active")) {
      throw new Error(`source.${source.id}.tier: source tier must be active and registered`);
    }
  }
  // This digest covers every validated input that can change harvested content or provenance.
  const { workflow_reporting, ...contentConfig } = planning.config;
  const snapshot = {
    config: contentConfig, registry, sources, retired, salience, watchlist, extraction,
    extractor_version: EXTRACTOR_VERSION, sanitizer_version: SANITIZER_FINGERPRINT,
  };
  const config_sha256 = createHash("sha256").update(JSON.stringify(snapshot)).digest("hex");
  return { ...planning, registry, sources, retired_sources: retired, salience, watchlist, extraction, extraction_settings, config_sha256 };
}

export async function readHarvestInputs(paths: {
  config: string; taxonomy: string; sources: string; extraction: string; watchlist: string;
}): Promise<HarvestInputs> {
  const [config, taxonomy, sources, extraction, watchlist] = await Promise.all([
    Bun.file(paths.config).json(), Bun.file(paths.taxonomy).json(),
    Bun.file(paths.sources).json(), Bun.file(paths.extraction).json(),
    Bun.file(paths.watchlist).json(),
  ]);
  return loadHarvestInputs({ config, taxonomy, sources, extraction, watchlist });
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
