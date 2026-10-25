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
import type { summarizePlan } from "../src/run-feed-plan";
import type { NamedPlanningHistory } from "../src/metrics/planning-populations";
import type { PersistedLedgerFile } from "@idhazh/ledger-file-writer";

export function namedPlanningFiles(summary: ReturnType<typeof summarizePlan>, root: string): NamedPlanningHistory {
  if (summary.metrics === undefined || summary.files.source_runs === undefined) throw new Error("Missing actual planner files");
  const named = (files: readonly { files: readonly { path: string }[] }[]) => ({
    day: summary.date, rawFiles: files.flatMap(result => result.files.map(file => join(root, ...file.path.split("/")))),
  });
  return {
    sources: named([]), feed_runs: named([summary.files.source_runs]),
    ledgers: {
      "article-assessments": named([summary.metrics.files.assessments]), diversity: named([]),
      "editorial-selections": named([summary.files.selections]), dispatches: named([]),
      rejections: named([]),
    },
    renamed: {
      "article-selection-diversity": named([summary.metrics.files.diversity]),
      "article-dispatches": named([summary.files.dispatches]),
      "ingest-rejections": named([summary.files.harvest_rejections, summary.files.screening_rejections,
        summary.files.curation_rejections]),
    },
  };
}

export async function recordedPlan(
  sources: ConfiguredSource[] = [source()], publishers: unknown = [],
) {
  const root = fileURLToPath(new URL("../../../", import.meta.url));
  const directory = await mkdtemp(join(tmpdir(), "feed-plan-"));
  try {
    const [loaded, harvest, recordings] = await Promise.all([
      loadPlanInputs(root), inputs(sources, { publishers }), readRecordings(),
    ]);
    const transport = new RecordedTransport(recordings);
    harvest.config.triage.min_words_article = 100;
    const events: FeedIngestEvent[] = [];
    const observation_files: PersistedLedgerFile[] = [];
    const context = {
      ...loaded, root: directory, outputRoot: join(directory, "state"),
      settings: { ...loaded.settings, enabled: true },
      harvest,
    };
    const runtime: PlanRuntime = {
      git_sha: "a".repeat(40), run_number: "700",
      correlation_id: "7cef34e3-dd9f-40ce-9a56-4d01ff5115cc", progress: () => {},
      clock: () => new Date("2026-10-21T23:59:59.999Z"),
      observation_clock: () => new Date("2026-10-21T23:59:59.000Z"),
      on_document_observations_persisted: files => { observation_files.push(...files); },
      boundary: { transport, resolve: transport.resolve }, log: event => { events.push(event); },
    };
    return {
      inputs: context, runtime, transport, events, directory, observation_files,
      close: () => rm(directory, { recursive: true, force: true }),
    };
  } catch (error) {
    await rm(directory, { recursive: true, force: true });
    throw error;
  }
}
