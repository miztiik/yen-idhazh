/** Which named authored files supply one validated planner invocation? */
import { resolve } from "node:path";
import { z } from "zod";
import { ItemHealthFailureCodeSchema, NonNegativeSchema } from "@idhazh/common-contracts";
import { readHarvestInputs } from "./harvest-feeds/load-harvest-inputs";
import { ServiceSettingsSchema } from "./config/service-settings";
import { FeedHistoryPolicySchema } from "./read-ledger-history/read-feed-history";

const LedgerSettingsSchema = z.object({
  format: z.literal("parquet"),
  compression_raw: z.enum(["snappy", "zstd", "none"]),
  compression_compact: z.enum(["snappy", "zstd", "none"]),
});
const RegistrySchema = z.object({
  families: z.array(z.object({
    name: z.string().min(1), lifecycle_status: z.enum(["active", "paused", "retired"]),
    ledgers: z.array(z.object({
      name: z.string().min(1), grain: z.string().min(1),
      prefix: z.array(z.string().min(1)).min(1),
    })),
  })),
});
const ExtractionSettingsSchema = z.object({
  ledger: LedgerSettingsSchema,
  collect: FeedHistoryPolicySchema.extend({
    max_future_hours: NonNegativeSchema,
    published_window_days: z.int().nonnegative(),
    settled_failure_codes: z.array(ItemHealthFailureCodeSchema),
  }),
});

export async function loadPlanInputs(root: string, settingsPath = "config/feed-ingest-plan-service.json") {
  const settings = ServiceSettingsSchema.parse(await Bun.file(resolve(root, settingsPath)).json());
  const paths = settings.inputs;
  const [harvest, extraction, registry] = await Promise.all([
    readHarvestInputs({
      config: resolve(root, paths.planning), taxonomy: resolve(root, paths.taxonomy),
      sources: resolve(root, paths.sources), extraction: resolve(root, paths.extraction),
    }),
    Bun.file(resolve(root, paths.extraction)).json().then(value => ExtractionSettingsSchema.parse(value)),
    Bun.file(resolve(root, paths.registrations)).json().then(value => RegistrySchema.parse(value)),
  ]);
  const registrations = Object.fromEntries(registry.families.flatMap(family => family.ledgers.map(ledger => [
    ledger.name, { ...ledger, family: family.name, lifecycle_status: family.lifecycle_status },
  ])));
  function registration(name: string) {
    const matches = registry.families.flatMap(family => family.ledgers.filter(ledger => ledger.name === name));
    if (matches.length !== 1) throw new Error(`registrations.${name}: exactly one registered ledger is required`);
    const entry = registrations[name]!;
    return { ...entry, grain: z.literal("raw-and-compact").parse(entry.grain) };
  }
  const selected = {
    discovered_articles: registration("discovered-articles"),
    selected_articles: registration("selected-articles"),
    rejected_articles: registration("rejected-articles"),
    feed_health_state: registration("feed-health-state"),
    plan_runs: registration("plan-runs"),
    published: registration("published"), item_health: registration("item-health"),
  };
  for (const entry of [selected.discovered_articles, selected.selected_articles, selected.rejected_articles, selected.feed_health_state, selected.plan_runs]) {
    if (entry.family !== "feed-ingest-plan" || entry.lifecycle_status !== "active"
      || JSON.stringify(entry.prefix) !== JSON.stringify(["feed-ingest-plan", entry.name])) {
      throw new Error(`registrations.${entry.name}: requires its active planner-family prefix`);
    }
  }
  if (extraction.ledger.compression_raw !== harvest.config.seal.compression) {
    throw new Error("ledger.compression_raw differs from planning config.seal.compression");
  }
  return {
    root, settings, harvest, clock_config: { collect: extraction.collect },
    ledgerSettings: extraction.ledger, registrations: selected,
    outputRoot: resolve(root, paths.output_root),
  };
}
export type PlanInputs = Awaited<ReturnType<typeof loadPlanInputs>>;
