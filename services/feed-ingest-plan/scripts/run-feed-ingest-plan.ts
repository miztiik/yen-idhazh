/** Run one workflow plan while retaining completed diagnostics and closing its listener. */
import { mkdir } from "node:fs/promises";
import type { PlanInputs } from "../src/load-plan-inputs";
import type { PlanRuntime } from "../src/run-feed-plan";
import { describePlanError } from "../src/api/plan-request";
import type { PlanRequest } from "../src/api/plan-request";
import { servePlan } from "../src/api/server";
import { writeGitHubOutputs } from "./feed-ingest-plan-outputs";
import { collectWorkflowFiles } from "./feed-ingest-plan-current-files";
import { requestPlannerHttp } from "./feed-ingest-plan-http-client";
import { preparePlannerWorkflow } from "./feed-ingest-plan-workflow-inputs";

export async function invokePlannerHttp(inputs: PlanInputs, runtime: PlanRuntime, request: PlanRequest, directory: string) {
  await mkdir(directory, { recursive: true });
  const server = servePlan(inputs, runtime);
  try {
    const base = `http://${inputs.settings.listener.hostname}:${server.port}/api/2026-10-20`;
    return await requestPlannerHttp(base, inputs, request, directory);
  } finally { await server.stop(true); }
}
async function runWorkflow() {
  const { root, directory, inputs, runtime, request, identity, registrations, host, outputPath, date }
    = await preparePlannerWorkflow(process.cwd(), process.env);
  let result: Awaited<ReturnType<typeof invokePlannerHttp>> | undefined;
  try {
    await writeGitHubOutputs(outputPath, {
      run_id: identity.run_id, date, planning_complete: "false",
      current_run_files: JSON.stringify(host.host.status === "recorded"
        ? host.host.files.map(file => file.path) : []),
    });
    result = await invokePlannerHttp(inputs, runtime, request, directory);
    if (!result.summary.planning_complete || result.http_status !== 200) process.exitCode = 2;
  } finally {
    const completed = await collectWorkflowFiles({ root, directory, identity, registrations });
    await writeGitHubOutputs(outputPath, {
      ...result?.outputs, current_run_files: JSON.stringify(completed.paths),
    });
    if (completed.failures.length) throw new AggregateError(completed.failures, "Workflow metadata collection failed; completed diagnostics retained");
  }
}
if (import.meta.main) {
  try { await runWorkflow(); }
  catch (error) {
    const failure = describePlanError(error, process.cwd());
    console.error(JSON.stringify({ event: "planner_workflow_failed", code: failure.code }));
    process.exitCode = 2;
  }
}
