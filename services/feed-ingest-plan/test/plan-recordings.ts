/** Build one bounded real planner input from existing recorded harvest responses. */
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { RecordedTransport, inputs, readRecordings, source } from "./harvest-recordings";
import type { ConfiguredSource } from "../src/harvest-feeds/load-harvest-inputs";
import type { FeedIngestEvent } from "@idhazh/common-contracts";
import type { PlanRuntime } from "../src/run-feed-plan";

export async function recordedPlan(sources: ConfiguredSource[] = [source()]) {
  const root = fileURLToPath(new URL("../../../", import.meta.url));
  const directory = await mkdtemp(join(tmpdir(), "feed-plan-"));
  try {
    const [loaded, harvest, recordings] = await Promise.all([
      loadPlanInputs(root), inputs(sources), readRecordings(),
    ]);
    const transport = new RecordedTransport(recordings);
    harvest.config.triage.min_words_article = 100;
    const events: FeedIngestEvent[] = [];
    const context = {
      ...loaded, root: directory, outputRoot: join(directory, "state"),
      settings: { ...loaded.settings, enabled: true },
      harvest,
    };
    const runtime: PlanRuntime = {
      git_sha: "a".repeat(40), run_number: "700",
      clock: () => new Date("2026-10-21T23:59:59.999Z"),
      boundary: { transport, resolve: transport.resolve }, log: event => { events.push(event); },
    };
    return {
      inputs: context, runtime, transport, events, directory,
      close: () => rm(directory, { recursive: true, force: true }),
    };
  } catch (error) {
    await rm(directory, { recursive: true, force: true });
    throw error;
  }
}
