/** Run one workflow plan while retaining completed diagnostics and closing its listener. */
import { describePlanError } from "../src/api/plan-request";
import { writeGitHubOutputs } from "./feed-ingest-plan-outputs";
import { collectWorkflowFiles } from "./feed-ingest-plan-current-files";
import { invokePlannerHttp } from "./feed-ingest-plan-supervisor";
import { preparePlannerWorkflow } from "./feed-ingest-plan-workflow-inputs";

async function runWorkflow(signal: AbortSignal) {
  const { root, directory, inputs, startup, request, identity, registrations, host, outputPath, date }
    = await preparePlannerWorkflow(process.cwd(), process.env);
  let result: Awaited<ReturnType<typeof invokePlannerHttp>> | undefined;
  try {
    await writeGitHubOutputs(outputPath, {
      run_id: identity.run_id, date, planning_complete: "false",
      current_run_files: JSON.stringify(host.host.status === "recorded"
        ? host.host.files.map(file => file.path) : []),
    });
    result = await invokePlannerHttp(inputs, startup, request, directory, { signal });
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
  const cancellation = new AbortController();
  const stop = () => cancellation.abort(new Error("Planner workflow cancelled"));
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
  try { await runWorkflow(cancellation.signal); }
  catch (error) {
    const failure = describePlanError(error, process.cwd());
    console.error(JSON.stringify({ event: "planner_workflow_failed", code: failure.code }));
    process.exitCode = 2;
  }
  finally {
    process.off("SIGINT", stop);
    process.off("SIGTERM", stop);
  }
}
