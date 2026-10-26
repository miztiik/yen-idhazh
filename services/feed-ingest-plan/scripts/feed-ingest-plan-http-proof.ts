/** Call the real HTTP planner and retain only selected text and body-free evidence. */
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { randomUUID } from "node:crypto";
import { loadPlanInputs } from "../src/load-plan-inputs";
import type { PlanInputs } from "../src/load-plan-inputs";
import type { PlanRuntime } from "../src/run-feed-plan";
import { parseCliRequest, describePlanError } from "../src/api/plan-request";
import type { PlanRequest } from "../src/api/plan-request";
import { servePlan } from "../src/api/server";
import { ServiceSettingsSchema } from "../src/config/service-settings";
import { PlanResponseSchema } from "../src/api/plan-response.schema";
import { FeedHealthStateUpdateResponseSchema } from "../src/api/feed-health-state.schema";
import { stagePlannerHistory } from "./feed-ingest-plan-history";
import { createExecutionOutputs, writeGitHubOutputs } from "./feed-ingest-plan-outputs";
import { verifyPlanningCompletion } from "./feed-ingest-plan-verification";
import { WorkflowMachineMemorySchema } from "../../host-probes/scripts/feed-ingest-plan-profile-schema";
import { WorkflowPolicySchema } from "./feed-ingest-plan-policy-report";
import { observeWorkflowResources } from "./feed-ingest-plan-workflow-resources";

export async function invokePlannerHttp(inputs: PlanInputs, runtime: PlanRuntime, request: PlanRequest, directory: string) {
  await mkdir(directory, { recursive: true });
  const server = servePlan(inputs, runtime);
  try {
    const base = `http://${inputs.settings.listener.hostname}:${server.port}/api/2026-10-20`;
    const healthResponse = await fetch(`${base}/health`);
    const listener: unknown = await healthResponse.json();
    if (healthResponse.status !== 200 || typeof listener !== "object" || listener === null
      || !("planner_enabled" in listener) || listener.planner_enabled !== true) throw new Error("Planner listener is not enabled and responsive");
    const response = await fetch(`${base}/plan`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(request), timeout: false,
    });
    const summary = PlanResponseSchema.parse(await response.json());
    await writeFile(join(directory, "response.json"), JSON.stringify(summary));
    await verifyPlanningCompletion(inputs.outputRoot, summary, inputs.registrations, inputs.root);
    let health: ReturnType<typeof FeedHealthStateUpdateResponseSchema.parse> | undefined;
    const batch = summary.batches.selection_batch_id ?? summary.batches.parsed_batch_id;
    if (batch !== undefined) {
      const result = await fetch(`${base}/feed-health-state`, {
        method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ batch_id: batch, action: "summarize" }),
      });
      if (result.status !== 200) throw new Error("Recorded health summary could not be read");
      health = FeedHealthStateUpdateResponseSchema.parse(await result.json());
      await writeFile(join(directory, "health.json"), JSON.stringify(health));
    }
    return { summary, health, outputs: createExecutionOutputs(summary, inputs.registrations), http_status: response.status };
  } finally { await server.stop(true); }
}
export function readWorkflowRequest(environment: Record<string, string | undefined>) {
  const args = ["--cli"];
  for (const [name, flag] of [
    ["FRESHNESS_HOURS", "--freshness-hours"], ["ARTICLE_LIMIT", "--article-limit"],
    ["SHARDS", "--shards"], ["PARTITION_STRATEGY", "--partition-strategy"],
  ] as const) {
    const value = environment[name];
    if (value !== undefined && value.trim() !== "") args.push(`${flag}=${value}`);
  }
  return parseCliRequest(args).request;
}
async function runWorkflow() {
  const request = readWorkflowRequest(process.env);
  const root = process.cwd();
  const { RUNNER_TEMP, GITHUB_OUTPUT, GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT } = process.env;
  if (!RUNNER_TEMP || !GITHUB_OUTPUT || !GITHUB_RUN_ID || !GITHUB_RUN_ATTEMPT) throw new Error("Workflow execution controls are missing");
  const profileRequested = WorkflowMachineMemorySchema.parse(process.env.PROFILE_MACHINE_MEMORY);
  const directory = join(RUNNER_TEMP, "feed-ingest-plan");
  const inputs = await loadPlanInputs(root);
  const started = performance.now();
  const staged = await stagePlannerHistory(root, inputs, new Date().toISOString().replace(/\.\d{3}Z$/, "Z"));
  const historyMs = Math.round(performance.now() - started);
  inputs.settings = ServiceSettingsSchema.parse({
    ...inputs.settings, enabled: true,
    inputs: { ...inputs.settings.inputs, feed_health_days: staged.feed_health_days, feed_health_input_gap: staged.feed_health_input_gap },
    run: { ...inputs.settings.run, attempt: Number(GITHUB_RUN_ATTEMPT) },
  });
  inputs.outputRoot = join(directory, "state");
  const git = Bun.spawn(["git", "rev-parse", "HEAD"], { cwd: root, stdout: "pipe", stderr: "pipe" });
  const [gitSha] = await Promise.all([new Response(git.stdout).text(), new Response(git.stderr).text()]);
  if (await git.exited !== 0) throw new Error("Code identity could not be read");
  const captured = new Date();
  const correlationId = randomUUID();
  const runtime: PlanRuntime = { git_sha: gitSha.trim(), run_number: GITHUB_RUN_ID, correlation_id: correlationId,
    clock: () => captured, selection_clock: () => new Date() };
  await mkdir(directory, { recursive: true });
  await writeFile(join(directory, "history-staging-ms.json"), JSON.stringify(historyMs));
  await writeFile(join(directory, "workflow-policy.json"), JSON.stringify(WorkflowPolicySchema.parse({
    config: inputs.harvest.config, request, history: inputs.clock_config.collect,
    parser_concurrency: inputs.settings.listener.parser_concurrency,
  })));
  console.error(JSON.stringify({ event: "planner_history_staged", notices: staged.notices }));
  const closeResources = await observeWorkflowResources({
    root, directory, profileRequested, gitSha: runtime.git_sha, attempt: inputs.settings.run.attempt,
    identity: { pipeline_name: "feed-ingest-plan", task_name: "planner-http-request",
      run_id: `${captured.toISOString().slice(0, 10)}-${GITHUB_RUN_ID}`, correlation_id: correlationId, request_id: randomUUID() },
  });
  let outcome: "success" | "error" = "error";
  try {
    const result = await invokePlannerHttp(inputs, runtime, request, directory);
    await writeGitHubOutputs(GITHUB_OUTPUT, result.outputs);
    if (!result.summary.planning_complete || result.http_status !== 200) process.exitCode = 2;
    else outcome = "success";
  } finally { await closeResources(outcome); }
}
if (import.meta.main) {
  try { await runWorkflow(); }
  catch (error) {
    const failure = describePlanError(error, process.cwd());
    console.error(JSON.stringify({ event: "planner_workflow_failed", code: failure.code }));
    process.exitCode = 2;
  }
}
