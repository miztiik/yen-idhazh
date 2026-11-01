/** Run the production child lifecycle against recorded feed bytes and UTC clocks, without network access. */
import { runPlannerServer, restorePlannerStartup } from "../scripts/feed-ingest-plan-server";
import { readRecordings, RecordedTransport } from "./harvest-recordings";
import { appendFileSync, writeFileSync } from "node:fs";
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
  let completed = false;
  return {
    ...restored, runtime: {
      ...restored.runtime, boundary: { transport },
      log: event => {
        if (event.operation === "plan" && event.phase === "completed") completed = true;
        appendFileSync(join(process.cwd(), "recorded-events.jsonl"), `${JSON.stringify(event)}\n`);
      },
      progress: event => {
        if (event.eventType === "FEED_FETCH_COMPLETED") writeFileSync(
          join(process.cwd(), "recorded-progress.json"), JSON.stringify({ ...event, before_completion: !completed }),
        );
      },
      selection_clock: () => new Date("2026-10-22T00:00:00Z"),
      observation_clock: () => new Date("2026-10-21T23:59:59Z"),
    },
  };
});
