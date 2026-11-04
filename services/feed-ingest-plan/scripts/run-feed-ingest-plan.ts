/** Run one workflow plan while retaining completed diagnostics and closing its listener. */
import { describePlanError } from "../src/api/plan-request";
import { writeGitHubOutputs } from "./feed-ingest-plan-outputs";
import { collectWorkflowFiles } from "./feed-ingest-plan-current-files";
import { invokePlannerHttp } from "./feed-ingest-plan-supervisor";
import { preparePlannerWorkflow } from "./feed-ingest-plan-workflow-inputs";
import { join } from "node:path";
import { runtimeFailureExecution, withPlannerFailure } from "../src/api/plan-failure";
import { retainFailureThroughCleanup } from "../src/api/retain-failure-through-cleanup";
import { retainWorkflowFailure } from "./retain-workflow-failure";
import { captureWorkflowHostFingerprint } from "./feed-ingest-plan-host-fingerprint";

export async function runWorkflow(signal: AbortSignal, options: { serverEntry?: string } = {}) {
  const { root, directory, inputs, startup, request, identity, registrations, outputPath, date }
    = await preparePlannerWorkflow(process.cwd(), process.env);
  let result: Awaited<ReturnType<typeof invokePlannerHttp>> | undefined;
  const capture = { operation: "workflow" as const, execution: runtimeFailureExecution(startup.runtime),
    limits: inputs.settings.diagnostics.failure };
  let failure: ReturnType<typeof withPlannerFailure> | undefined;
  try {
    await writeGitHubOutputs(outputPath, {
      run_id: identity.run_id, date, planning_complete: "false",
      dump_raw_document_contents: String(inputs.settings.dump_raw_document_contents),
      current_run_files: "[]",
    });
    result = await invokePlannerHttp(inputs, startup, request, directory, {
      signal, ...options,
      beforePlan: async (origin, requestSignal) => {
        await captureWorkflowHostFingerprint({
          root, directory, stateRoot: inputs.outputRoot, identity, registrations,
          origin, signal: requestSignal,
        });
      },
    });
    if (!result.summary.planning_complete || result.summary.failure !== null || result.http_status !== 200) process.exitCode = 2;
  } catch (error) { failure = withPlannerFailure(error, capture); }
  const finish = async () => {
    const completed = await collectWorkflowFiles({ root, directory, identity, registrations });
    await writeGitHubOutputs(outputPath, {
      ...result?.outputs, current_run_files: JSON.stringify(completed.paths),
    });
    if (completed.failures.length) throw new AggregateError(completed.failures, "Workflow metadata collection failed; completed diagnostics retained");
  };
  if (failure !== undefined) failure = await retainFailureThroughCleanup(failure, capture, [
    { operation: "verify-output", execute: finish },
  ]);
  else {
    try { await finish(); }
    catch (error) { failure = withPlannerFailure(error, { ...capture, operation: "verify-output" }); }
  }
  if (failure !== undefined) {
    throw await retainFailureThroughCleanup(failure, capture, [{
      operation: "record-run", execute: () => retainWorkflowFailure({ directory, error: failure, capture }),
    }]);
  }
}
if (import.meta.main) {
  const cancellation = new AbortController();
  const stop = () => cancellation.abort(withPlannerFailure(new DOMException("Cancelled", "AbortError"), { operation: "workflow" }));
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
  try { await runWorkflow(cancellation.signal); }
  catch (error) {
    const failure = describePlanError(error, process.cwd());
    if (process.env.RUNNER_TEMP) {
      try {
        await retainWorkflowFailure({
          directory: join(process.env.RUNNER_TEMP, "feed-ingest-plan"), error,
          capture: { operation: "workflow" },
        });
      } catch (recordingError) {
        console.error(JSON.stringify({ event: "planner_workflow_failure_write_failed",
          ...describePlanError(new AggregateError([error, recordingError], "Workflow failure could not be retained")) }));
      }
    }
    console.error(JSON.stringify({ event: "planner_workflow_failed", code: failure.code, failure: failure.failure }));
    process.exitCode = 2;
  }
  finally {
    process.off("SIGINT", stop);
    process.off("SIGTERM", stop);
  }
}
