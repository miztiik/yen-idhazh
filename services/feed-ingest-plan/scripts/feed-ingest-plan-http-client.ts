/** Call an enabled planner listener and verify its retained output before returning commit paths. */
import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import type { PlanInputs } from "../src/load-plan-inputs";
import type { PlanRequest } from "../src/api/plan-request";
import { PlanResponseSchema } from "../src/api/plan-response.schema";
import { FeedHealthStateUpdateResponseSchema } from "../src/api/feed-health-state.schema";
import { createExecutionOutputs } from "./feed-ingest-plan-outputs";
import { verifyPlanningCompletion } from "./feed-ingest-plan-verification";
import { PlanError } from "../src/api/plan-request";

export async function requestPlannerHttp(base: string, inputs: PlanInputs, request: PlanRequest, directory: string, signal?: AbortSignal) {
  const healthResponse = await fetch(`${base}/health`, { signal: signal ?? null });
  const listener: unknown = await healthResponse.json();
  if (healthResponse.status !== 200 || typeof listener !== "object" || listener === null
    || !("planner_enabled" in listener) || listener.planner_enabled !== true) throw new Error("Planner listener is not enabled and responsive");
  const response = await fetch(`${base}/plan`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(request), timeout: false, signal: signal ?? null,
  });
  const body: unknown = await response.json();
  const parsed = PlanResponseSchema.safeParse(body);
  if (!parsed.success && response.status !== 200) {
    const code = typeof body === "object" && body !== null && "code" in body && typeof body.code === "string"
      ? body.code : "PLANNER_HTTP_FAILED";
    throw new PlanError(code, `Planner returned HTTP ${response.status}: ${code}`);
  }
  const summary = parsed.success ? parsed.data : PlanResponseSchema.parse(body);
  await writeFile(join(directory, "response.json"), JSON.stringify(summary));
  await verifyPlanningCompletion(inputs.outputRoot, summary, inputs.registrations, inputs.root);
  let health: ReturnType<typeof FeedHealthStateUpdateResponseSchema.parse> | undefined;
  const batch = summary.batches.selection_batch_id ?? summary.batches.parsed_batch_id;
  if (batch !== undefined) {
    const result = await fetch(`${base}/feed-health-state`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ batch_id: batch, action: "summarize" }),
      signal: signal ?? null, timeout: false,
    });
    if (result.status !== 200) throw new Error("Recorded health summary could not be read");
    health = FeedHealthStateUpdateResponseSchema.parse(await result.json());
    await writeFile(join(directory, "health.json"), JSON.stringify(health));
  }
  return { summary, health, outputs: createExecutionOutputs(summary, inputs.registrations), http_status: response.status };
}
