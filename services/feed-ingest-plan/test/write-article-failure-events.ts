/** Run real recorded article work and expose its native stderr and saved response to the parent test. */
import { z } from "zod";
import { PLANNER_API_PATHS, PLANNER_API_PREFIX, PlannerSavedResponseSchema } from "@idhazh/common-contracts";
import { join } from "node:path";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";
import { createPlanTestServer } from "./plan-test-server";

const input = z.strictObject({ directory: z.string() }).parse(await Bun.stdin.json());
const response = z.object({
  status: z.int().optional(), body: z.string().optional(), error: z.string().optional(),
  headers: z.record(z.string(), z.string()).optional(),
});
const fixture = z.object({
  cases: z.array(z.object({ name: z.string(), url: z.string(), responses: z.array(response) })),
  article_inputs: z.array(z.object({ name: z.string(), url: z.string(), responses: z.array(response) })),
}).parse(await Bun.file(new URL(
  "../../../tests/fixtures/feed-ingest-plan/article-terminal-failures.json", import.meta.url,
)).json());
const feed = source({ url: "https://news.example/terminal-diagnostics.xml" });
const recorded = await recordedPlan([feed]);
recorded.inputs.outputRoot = join(input.directory, "state");
recorded.inputs.harvest.config.harvest.request_headers.secondary = null;
recorded.runtime.attempt = 3;
delete recorded.runtime.log;
const cases = [...fixture.cases, ...fixture.article_inputs];
recorded.transport.recordings.responses[feed.url] = [{
  status: 200, body: `<rss version="2.0"><channel><title>Recorded failures</title>${cases.map(entry =>
    `<item><link>${entry.url}</link></item>`).join("")}</channel></rss>`,
}];
for (const entry of cases) recorded.transport.recordings.responses[entry.url] = entry.responses;
const app = createPlanTestServer(recorded.inputs, recorded.runtime);
try {
  const result = await app.request(`${PLANNER_API_PREFIX}${PLANNER_API_PATHS.plan}`, {
    method: "POST", headers: { "content-type": "application/json" }, body: "{}",
  });
  if (result.status !== 200) throw new Error("Recorded article run did not return its native successful HTTP result");
  console.log(JSON.stringify({ response: PlannerSavedResponseSchema.parse(await result.json()) }));
} finally {
  await app.close();
  await recorded.close();
}
