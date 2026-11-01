/** Load bounded offline source inputs without starting stages or creating unused Git history. */
import { existsSync } from "node:fs";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { RecordedTransport, inputs, readRecordings, source } from "./harvest-recordings";
import type { ConfiguredSource } from "../src/harvest-feeds/load-harvest-inputs";
import type { FeedIngestEvent } from "@idhazh/common-contracts";
import type { PlanRuntime } from "../src/run-feed-plan";

export async function recordedPlan(sources: ConfiguredSource[] = [source()], publishers: unknown = []) {
  const root = fileURLToPath(new URL("../../../", import.meta.url));
  const directory = await mkdtemp(join(tmpdir(), "feed-plan-"));
  try {
    const [loaded, harvest, recordings] = await Promise.all([
      loadPlanInputs(root), inputs(sources, { publishers }), readRecordings(),
    ]);
    const transport = new RecordedTransport(recordings);
    harvest.config.triage.min_words = 100;
    harvest.config.discovered_articles.lookback_days = 3;
    harvest.config.curate_articles.soft_caps.max_website_group_share = 1;
    const fixtureTiers = new Set(harvest.sources.filter(source => source.status === "active").map(source => source.tier));
    harvest.config.curate_articles.source_based_quality_buckets = harvest.registry.source_tiers
      .filter(tier => tier.status === "active").map(tier => ({
        id: `source-tier-${tier.id}`, source_tier_id: tier.id,
        share_pct: fixtureTiers.has(tier.id) ? 100 / fixtureTiers.size : 0, buffer_pct: 0, ladder_hours: [48],
      }));
    const events: FeedIngestEvent[] = [];
    const context = {
      ...loaded, root: directory, outputRoot: join(directory, "state"),
      settings: {
        ...loaded.settings, enabled: true,
        listener: { ...loaded.settings.listener, parser_concurrency: harvest.config.harvest.concurrency },
      }, harvest,
    };
    const runtime: PlanRuntime = {
      git_sha: "a".repeat(40), run_number: "700", correlation_id: "7cef34e3-dd9f-40ce-9a56-4d01ff5115cc",
      clock: () => new Date("2026-10-21T23:59:59.999Z"),
      observation_clock: () => new Date("2026-10-21T23:59:59.000Z"),
      boundary: { transport, resolve: transport.resolve }, log: event => { events.push(event); },
    };
    return {
      inputs: context, runtime, transport, events, directory,
      close: () => removeRecordedDirectory(directory),
    };
  } catch (error) {
    await removeRecordedDirectory(directory);
    throw error;
  }
}

async function removeRecordedDirectory(directory: string) {
  // Retry only transient locks; persistent and unrelated cleanup failures remain visible.
  for (let attempt = 0; attempt < 30; attempt++) {
    try {
      await rm(directory, { recursive: true, force: true });
      return;
    } catch (error) {
      if (!(error && typeof error === "object" && "code" in error && error.code === "EBUSY")) throw error;
      if (!existsSync(directory)) return;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }
  await rm(directory, { recursive: true, force: true });
}
