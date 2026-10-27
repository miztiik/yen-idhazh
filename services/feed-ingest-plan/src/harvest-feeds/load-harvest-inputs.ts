/** Which authored inputs and resolved source policies govern this harvest? */
import { createHash } from "node:crypto";
import { z } from "zod";
import {
  DateStampSchema, LifecycleStatusSchema, NonEmptySchema,
  PositiveCountSchema, SlugSchema, SourceSnapshotSchema, UrlSchema,
} from "@idhazh/common-contracts";
import type { SourceSnapshot } from "@idhazh/common-contracts";
import { loadPlanningConfig } from "../config/resolve-policy";
import { ExtractionControlsSchema } from "./extraction-controls";
import { EXTRACTOR_VERSION, SANITIZER_FINGERPRINT } from "./extraction-provenance";
import { PublisherDefinitionSchema, validatePublisherReferences } from "../publisher-catalog";
import { validateSemanticSelectors } from "./semantic-extractor";
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
  id: SlugSchema, url: ConfiguredUrlSchema, title: NonEmptySchema,
  tier: PositiveCountSchema, weight: WeightSchema,
  added_on: DateStampSchema.nullable().default(null),
  publisher_id: SlugSchema.nullable().default(null),
  retirement_reason: z.string().min(1).nullable().default(null).refine(
    value => value === null || (value.trim().length > 0 && value === value.toLowerCase()),
    "feed retirement_reason must be nonempty lowercase text",
  ),
}).superRefine((source, ctx) => {
  if (source.retirement_reason !== null && source.status !== "retired") {
    ctx.addIssue({
      code: "custom", path: ["retirement_reason"],
      message: "retirement_reason is only meaningful on a retired feed",
    });
  }
  if (source.status === "retired" && source.added_on !== null && source.retirement_reason === null) {
    ctx.addIssue({
      code: "custom", path: ["retirement_reason"],
      message: "a newly retired feed needs retirement_reason",
    });
  }
  if (source.retired_on !== null && source.added_on !== null && source.retired_on < source.added_on) {
    ctx.addIssue({
      code: "custom", path: ["retired_on"], message: "retired_on cannot precede added_on",
    });
  }
});
const SourcesSchema = z.object({
  feeds: z.array(SourceConfigSchema),
  retired: z.array(SourceConfigSchema.refine(source => source.status === "retired", {
    message: "retired entries must have retired status and a retirement date",
  })).default([]),
  publishers: z.array(PublisherDefinitionSchema).default([]),
});
const RegistrySchema = z.object({
  source_tiers: z.array(LifecycleSchema.safeExtend({ id: PositiveCountSchema, weight: WeightSchema })),
});
const ExtractionSchema = z.object({
  extract: ExtractionControlsSchema.omit({ semantic_fallback: true, press_release_filter: true }),
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
  config: unknown; taxonomy: unknown; sources: unknown; extraction: unknown;
}) {
  const planning = loadPlanningConfig(raw.config);
  const registry = RegistrySchema.parse(raw.taxonomy);
  const rules = new Set(planning.config.curate_articles.feed_quality_tiers.map(rule => rule.tier));
  const active = registry.source_tiers.filter(tier => tier.status === "active");
  if (active.some(tier => !rules.has(tier.id)) || [...rules].some(id => !active.some(tier => tier.id === id))) {
    throw new Error("curate_articles.feed_quality_tiers: rules must name every active taxonomy tier exactly once");
  }
  const { feeds: sources, retired, publishers } = SourcesSchema.parse(raw.sources);
  validatePublisherReferences(publishers, [...sources, ...retired]);
  const extraction_settings = ExtractionSchema.parse(raw.extraction);
  const extraction = ExtractionControlsSchema.parse({
    ...extraction_settings.extract, semantic_fallback: planning.config.harvest.semantic_fallback,
    press_release_filter: planning.config.content_filters.press_release,
  });
  validateSemanticSelectors(extraction.semantic_fallback);
  for (const [name, ids] of [
    ["source", [...sources, ...retired].map(source => source.id)],
    ["source tier", registry.source_tiers.map(tier => tier.id)],
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
    if (!registry.source_tiers.some(tier => tier.id === source.tier && tier.status === "active")) {
      throw new Error(`source.${source.id}.tier: source tier must be active and registered`);
    }
  }
  // This digest covers every validated input that can change harvested content or provenance.
  const { workflow_reporting, ...contentConfig } = planning.config;
  const snapshot = {
    config: contentConfig, registry, sources, retired, publishers, extraction,
    extractor_version: EXTRACTOR_VERSION, sanitizer_version: SANITIZER_FINGERPRINT,
  };
  const config_sha256 = createHash("sha256").update(JSON.stringify(snapshot)).digest("hex");
  return { ...planning, registry, sources, retired_sources: retired, publishers, extraction, extraction_settings, config_sha256 };
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
    source_id: source.id, feed_url: source.url, title: source.title,
    publisher_id: source.publisher_id, tier: source.tier, status: source.status,
    weight: source.weight, applied_tier_weight: tier.weight,
  });
}
