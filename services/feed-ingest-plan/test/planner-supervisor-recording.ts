/** Run the production supervisor as a real parent process over generated inputs and recorded feed transport. */
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { PlannerStartupSchema } from "../src/config/planner-startup";
import { restorePlannerStartup } from "../scripts/feed-ingest-plan-server";
import { invokePlannerHttp } from "../scripts/feed-ingest-plan-supervisor";

const startup = PlannerStartupSchema.parse(JSON.parse(await Bun.stdin.text()));
const { inputs } = await restorePlannerStartup(startup);
try {
  await invokePlannerHttp(inputs, startup, {}, join(process.cwd(), "evidence"), {
    serverEntry: fileURLToPath(new URL("./planner-server-recording.ts", import.meta.url)),
  });
} catch (error) {
  console.error(JSON.stringify({ event: "recorded_supervisor_failed", message: error instanceof Error ? error.message : "Unknown failure" }));
  process.exitCode = 2;
}
