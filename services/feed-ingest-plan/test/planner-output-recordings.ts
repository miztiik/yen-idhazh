/** Validate captured planner output and rebuild its native files without planning. */
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  DiscoveredArticleRowContract, FeedHealthStateRowContract, PlanRunRowContract,
  RejectedArticleRowContract, SelectedArticleRowContract, SelectedArticlesArtifactSchema,
} from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRowContract, PersistLedgerResult } from "@idhazh/ledger-file-writer";
import { PlanResponseSchema } from "../src/api/plan-response.schema";
import { FeedHealthStateUpdateResponseSchema } from "../src/api/feed-health-state.schema";
import { loadPlanInputs } from "../src/load-plan-inputs";
import type { PlanInputs } from "../src/load-plan-inputs";
import { createExecutionOutputs } from "../scripts/feed-ingest-plan-outputs";

const recordings = new URL("../../../tests/fixtures/feed-ingest-plan/entry-points/", import.meta.url);

export async function readPlannerOutputRecording() {
  return {
    response: PlanResponseSchema.parse(await Bun.file(new URL("response.json", recordings)).json()),
    health: FeedHealthStateUpdateResponseSchema.parse(await Bun.file(new URL("health.json", recordings)).json()),
    artifact: SelectedArticlesArtifactSchema.parse(await Bun.file(new URL("selected-articles.json", recordings)).json()),
  };
}

export async function writePlannerOutputRecording(inputs: PlanInputs, partial = false) {
  const recorded = await readPlannerOutputRecording();
  async function write<T extends { date: string }>(
    ledger: keyof PlanInputs["registrations"], name: string, contract: LedgerRowContract<T>,
  ): Promise<PersistLedgerResult> {
    const rows = contract.schema.array().parse(await Bun.file(new URL(`${name}.rows.json`, recordings)).json())
      .map(row => name === "plan-runs" && partial ? contract.schema.parse({
        ...row, status: "partial", failure_code: "PERSIST_FAILED", selected_articles_artifact: null,
      }) : row);
    const results: PersistLedgerResult[] = [];
    for (const day of [...new Set(rows.map(row => row.date))]) {
      results.push(await persistLedger({
        ledger: name, outputRoot: inputs.outputRoot, registryEntry: inputs.registrations[ledger],
        ledgerSettings: inputs.ledgerSettings, rowContract: contract,
        period: { tier: "raw", covers: day }, rows: rows.filter(row => row.date === day),
        ...(name === "feed-health-state" ? { updatedAt: `${day}T23:59:59.123Z` } : {}),
      }));
    }
    if (results.some(result => result.status === "skipped")) throw new Error(`Recorded ${name} write was refused`);
    return rows.length === 0 ? { status: "empty", files: [] }
      : { status: "written", files: results.flatMap(result => result.files) };
  }
  const files = {
    discovered_articles: await write("discovered_articles", "discovered-articles", DiscoveredArticleRowContract),
    selected_articles: await write("selected_articles", "selected-articles", SelectedArticleRowContract),
    rejected_articles: await write("rejected_articles", "rejected-articles", RejectedArticleRowContract),
    feed_health_state: await write("feed_health_state", "feed-health-state", FeedHealthStateRowContract),
    plan_runs: await write("plan_runs", "plan-runs", PlanRunRowContract),
  };
  const response = PlanResponseSchema.parse({ ...recorded.response, files,
    ...(partial ? { status: "partial", failure_code: "PERSIST_FAILED", planning_complete: false, selected_articles_artifact: null } : {}),
  });
  const artifactPath = join(inputs.root, recorded.response.selected_articles_artifact!);
  await mkdir(dirname(artifactPath), { recursive: true });
  await writeFile(artifactPath, JSON.stringify(recorded.artifact));
  return { ...recorded, response, summary: response,
    outputs: createExecutionOutputs(response, inputs.registrations) };
}

export async function plannerOutputRecording() {
  const directory = await mkdtemp(join(tmpdir(), "planner-output-"));
  try {
    const loaded = await loadPlanInputs(fileURLToPath(new URL("../../../", import.meta.url)));
    const inputs = { ...loaded, root: directory, outputRoot: join(directory, "state") };
    const result = await writePlannerOutputRecording(inputs);
    return { ...result, inputs, directory, close: () => rm(directory, { recursive: true, force: true }) };
  } catch (error) {
    await rm(directory, { recursive: true, force: true });
    throw error;
  }
}
