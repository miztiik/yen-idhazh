/** Run the production child lifecycle against recorded feed bytes and UTC clocks, without network access. */
import { runPlannerServer, restorePlannerStartup } from "../scripts/feed-ingest-plan-server";
import { readRecordings, RecordedTransport } from "./harvest-recordings";
import { writeFileSync } from "node:fs";
import { join } from "node:path";

await runPlannerServer(async startup => {
  const restored = await restorePlannerStartup(startup);
  const transport = new RecordedTransport(await readRecordings());
  writeFileSync(join(process.cwd(), "recorded-startup.json"), JSON.stringify({
    pid: process.pid, parser_concurrency: restored.inputs.settings.listener.parser_concurrency,
    enabled: restored.inputs.settings.enabled, history_gap: restored.inputs.settings.inputs.feed_health_input_gap,
    history_days: restored.inputs.settings.inputs.feed_health_days,
  }));
  transport.on_request = request => {
    if (request.url.pathname === "/timeout") {
      writeFileSync(join(process.cwd(), "recorded-request.json"), JSON.stringify({ url: request.url.href }));
    }
  };
  return {
    ...restored, runtime: {
      ...restored.runtime, boundary: { transport, resolve: transport.resolve },
      log: () => {},
      selection_clock: () => new Date("2026-10-22T00:00:00Z"),
      observation_clock: () => new Date("2026-10-21T23:59:59Z"),
    },
  };
});
