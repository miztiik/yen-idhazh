/** Prepare bounded history, effective settings and execution evidence for one workflow invocation. */
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { randomUUID } from "node:crypto";
import { PositiveCountSchema } from "@idhazh/common-contracts";
import { loadPlanInputs } from "../src/load-plan-inputs";
import type { PlanRuntime } from "../src/run-feed-plan";
import { parseCliRequest } from "../src/api/plan-request";
import { ServiceSettingsSchema } from "../src/config/service-settings";
import { stagePlannerHistory } from "./feed-ingest-plan-history";
import { WorkflowPolicySchema } from "./feed-ingest-plan-policy-report";
import { captureWorkflowHostFingerprint } from "./feed-ingest-plan-host-fingerprint";
import { readMetadataRegistrations } from "./feed-ingest-plan-metadata";

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

export async function preparePlannerWorkflow(root: string, environment: Record<string, string | undefined>) {
  const request = readWorkflowRequest(environment);
  const { RUNNER_TEMP, GITHUB_OUTPUT, GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT } = environment;
  if (!RUNNER_TEMP || !GITHUB_OUTPUT || !GITHUB_RUN_ID || !GITHUB_RUN_ATTEMPT) throw new Error("Workflow execution controls are missing");
  const directory = join(RUNNER_TEMP, "feed-ingest-plan");
  const inputs = await loadPlanInputs(root);
  const attempt = PositiveCountSchema.parse(Number(GITHUB_RUN_ATTEMPT));
  const staged = await stagePlannerHistory(root, inputs, new Date().toISOString().replace(/\.\d{3}Z$/, "Z"));
  inputs.settings = ServiceSettingsSchema.parse({
    ...inputs.settings, enabled: true,
    inputs: { ...inputs.settings.inputs, feed_health_days: staged.feed_health_days, feed_health_input_gap: staged.feed_health_input_gap },
  });
  inputs.outputRoot = join(directory, "state");
  const git = Bun.spawn(["git", "rev-parse", "HEAD"], { cwd: root, stdout: "pipe", stderr: "pipe" });
  const [gitSha] = await Promise.all([new Response(git.stdout).text(), new Response(git.stderr).text()]);
  if (await git.exited !== 0) throw new Error("Code identity could not be read");
  const captured = new Date();
  const correlationId = randomUUID();
  const runtime: PlanRuntime = { git_sha: gitSha.trim(), run_number: GITHUB_RUN_ID, correlation_id: correlationId, attempt,
    clock: () => captured, selection_clock: () => new Date() };
  await mkdir(directory, { recursive: true });
  await writeFile(join(directory, "workflow-policy.json"), JSON.stringify(WorkflowPolicySchema.parse({
    config: inputs.harvest.config, request, history: inputs.clock_config.collect,
    parser_concurrency: inputs.settings.listener.parser_concurrency,
  })));
  console.error(JSON.stringify({ event: "planner_history_staged", notices: staged.notices }));
  const identity = { run_id: `${captured.toISOString().slice(0, 10)}-${GITHUB_RUN_ID}`,
    attempt, git_sha: runtime.git_sha };
  const registryPath = join(root, inputs.settings.inputs.registrations);
  const registrations = await readMetadataRegistrations(registryPath);
  const host = await captureWorkflowHostFingerprint({
    root, directory, stateRoot: inputs.outputRoot, registryPath, identity, registrations,
  });
  return { root, directory, inputs, runtime, request, identity, registrations, host,
    outputPath: GITHUB_OUTPUT, date: captured.toISOString().slice(0, 10) };
}
