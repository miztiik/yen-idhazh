/** Materialize named authored inputs for a real child with only its external feed boundary recorded. */
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { recordedPlan } from "./plan-recordings";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { createPlannerStartup } from "../scripts/feed-ingest-plan-supervisor";

export async function recordedPlannerProcess() {
  const fixture = await recordedPlan();
  try {
    const configRoot = new URL("../../../config/", import.meta.url);
    await mkdir(join(fixture.directory, "config"));
    for (const name of ["taxonomy.json", "idhazh.json", "ledgers.json"]) {
      await writeFile(join(fixture.directory, "config", name), await Bun.file(new URL(name, configRoot)).text());
    }
    const settings = { ...fixture.inputs.settings, enabled: false };
    settings.listener.parser_concurrency = 2;
    const reservation = Bun.serve({ hostname: "127.0.0.1", port: 0, fetch: () => new Response() });
    settings.listener.port = reservation.port!;
    await reservation.stop(true);
    await writeFile(join(fixture.directory, "config", "feed-ingest-plan-service.json"), JSON.stringify(settings));
    await writeFile(join(fixture.directory, "config", "feed-ingest-plan.json"), JSON.stringify(fixture.inputs.harvest.config));
    await writeFile(join(fixture.directory, "config", "sources.json"), JSON.stringify({
      feeds: fixture.inputs.harvest.sources, retired: [], publishers: [],
    }));
    const inputs = await loadPlanInputs(fixture.directory);
    inputs.settings.enabled = true;
    const directory = join(fixture.directory, "evidence");
    await mkdir(directory);
    inputs.outputRoot = join(directory, "state");
    const startup = createPlannerStartup(inputs, {
      git_sha: fixture.runtime.git_sha, run_number: "700",
      correlation_id: fixture.runtime.correlation_id!, attempt: 3,
      captured_at: fixture.runtime.clock!().toISOString(),
    });
    return {
      ...fixture, inputs, startup, evidence: directory,
      serverEntry: fileURLToPath(new URL("./planner-server-recording.ts", import.meta.url)),
    };
  } catch (error) { await fixture.close(); throw error; }
}
