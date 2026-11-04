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
  let persisted = false;
  const result = await main(Bun.argv.slice(2), {
    inputs, runtime: {
      ...runtime, boundary: { transport },
      selection_clock: () => new Date("2026-10-22T00:00:00Z"),
      observation_clock: () => new Date(persisted && process.env.IDHAZH_TEST_REPORT_CLOCK_FAILURE === "1"
        ? Number.NaN : "2026-10-21T23:59:59Z"),
      log: event => {
        if (event.data.operation === "persist" && event.data.phase === "completed") persisted = true;
        appendFileSync(join(process.cwd(), "recorded-events.jsonl"), `${JSON.stringify(event)}\n`);
      },
    },
  });
  if ("planning_complete" in result && (!result.planning_complete || result.failure !== null)) process.exitCode = 2;
} catch (error) {
  writeJsonLine({ event: "planner_error", ...describePlanError(error, process.cwd()) });
  process.exitCode = 1;
}
