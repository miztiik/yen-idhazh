/** Call the actual awaited CLI with native startup controls and recorded source transport. */
import { appendFileSync } from "node:fs";
import { join } from "node:path";
import { PlannerStartupSchema } from "../src/config/planner-startup";
import { restorePlannerStartup } from "../scripts/feed-ingest-plan-server";
import { main } from "../src/index";
import { describePlanError } from "../src/api/plan-request";
import { writeJsonLine } from "../src/logging/structured-logger";
import { RecordedTransport, readRecordings } from "./harvest-recordings";

try {
  const startup = PlannerStartupSchema.parse(await Bun.stdin.json());
  const { inputs, runtime } = await restorePlannerStartup(startup);
  const transport = new RecordedTransport(await readRecordings());
  const result = await main(Bun.argv.slice(2), {
    inputs, runtime: {
      ...runtime, boundary: { transport },
      selection_clock: () => new Date("2026-10-22T00:00:00Z"),
      observation_clock: () => new Date("2026-10-21T23:59:59Z"),
      log: event => appendFileSync(join(process.cwd(), "recorded-events.jsonl"), `${JSON.stringify(event)}\n`),
    },
  });
  if ("planning_complete" in result && !result.planning_complete) process.exitCode = 2;
} catch (error) {
  writeJsonLine({ event: "planner_error", ...describePlanError(error, process.cwd()) });
  process.exitCode = 1;
}
