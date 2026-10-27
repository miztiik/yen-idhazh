/** Build a bounded real planner run from the named offline RSS, HTML and transport recordings. */
import { existsSync } from "node:fs";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { RecordedTransport, contentFilterPage, inputs, readContentFilters, readRecordings, source } from "./harvest-recordings";
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
    harvest.config.curate_articles.feed_quality_tiers = harvest.registry.source_tiers
      .filter(tier => tier.status === "active").map(tier => ({
        tier: tier.id, share_pct: fixtureTiers.has(tier.id) ? 100 / fixtureTiers.size : 0, buffer_pct: 0, ladder_hours: [48],
      }));
    const events: FeedIngestEvent[] = [];
    const context = {
      ...loaded, root: directory, outputRoot: join(directory, "state"),
      settings: { ...loaded.settings, enabled: true }, harvest,
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

export async function recordedContentFilterPlan() {
  const cases = await readContentFilters();
  const recorded = await recordedPlan();
  try {
    const mediaUrl = `https://${recorded.inputs.harvest.config.content_filters.media.url_rules[0]!.host}/watch`;
    const mimeUrl = "https://news.example/filter-media";
    const entries = [
      `<item><link>${mediaUrl}</link></item>`,
      `<item><title>Recorded audio offer</title><link>${mimeUrl}</link><enclosure url="https://resources.example/audio" type="audio/mpeg" length="100"/></item>`,
      ...cases.article_cases.map(entry => `<item><title>${entry.title}</title><link>https://news.example/${entry.path}</link></item>`),
    ];
    recorded.transport.recordings.responses["https://news.example/feed.xml"] = [{
      status: 200, body: `<rss version="2.0"><channel><title>Recorded content exclusions</title>${entries.join("")}</channel></rss>`,
    }];
    for (const entry of cases.article_cases) {
      recorded.transport.recordings.responses[`https://news.example/${entry.path}`] = [{
        status: 200, body: contentFilterPage(recorded.transport.recordings.bodies.article, entry, cases.list_prose),
      }];
    }
    return { ...recorded, cases, mediaUrl, mimeUrl };
  } catch (error) {
    await recorded.close();
    throw error;
  }
}
