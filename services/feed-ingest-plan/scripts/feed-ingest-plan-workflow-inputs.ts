/** Prepare bounded history, effective settings and execution evidence for one workflow invocation. */
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { CommitShaSchema, createRootContext, PositiveCountSchema } from "@idhazh/common-contracts";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { parseCliRequest } from "../src/api/plan-request";
import { parseGlobalAgeCeiling, resolveRunPolicy, RunPolicyOverridesSchema } from "../src/config/resolve-run-policy";
import type { PlanRequest } from "../src/api/plan-request";
import type { RunPolicyOverrides } from "../src/config/resolve-run-policy";
import { parseRawDocumentDumpControl, ServiceSettingsSchema } from "../src/config/service-settings";
import { WorkflowPolicySchema } from "./feed-ingest-plan-policy-report";
import { readMetadataRegistrations } from "./feed-ingest-plan-metadata";
import { createPlannerStartup } from "./feed-ingest-plan-supervisor";

export function readWorkflowRequest(environment: Record<string, string | undefined>): {
  request: PlanRequest; policy_overrides: RunPolicyOverrides;
} {
  const args = ["--cli"];
  for (const [name, flag] of [
    ["ARTICLE_LIMIT", "--article-limit"],
    ["SHARDS", "--shards"], ["PARTITION_STRATEGY", "--partition-strategy"],
  ] as const) {
    const value = environment[name];
    if (value !== undefined && value.trim() !== "") args.push(`${flag}=${value}`);
  }
  const overrides = RunPolicyOverridesSchema.parse({
    global_age_ceiling_hours: parseGlobalAgeCeiling(environment.GLOBAL_AGE_CEILING_HOURS),
  });
  return { request: parseCliRequest(args).request,
    policy_overrides: Object.fromEntries(Object.entries(overrides).filter(([, value]) => value !== undefined)) };
}

export async function preparePlannerWorkflow(root: string, environment: Record<string, string | undefined>) {
  const { request, policy_overrides: policyOverrides } = readWorkflowRequest(environment);
  const dumpRawDocuments = environment.DUMP_RAW_DOCUMENT_CONTENTS === undefined ? undefined
    : parseRawDocumentDumpControl(environment.DUMP_RAW_DOCUMENT_CONTENTS);
  const { RUNNER_TEMP, GITHUB_OUTPUT, GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT } = environment;
  if (!RUNNER_TEMP || !GITHUB_OUTPUT || !GITHUB_RUN_ID || !GITHUB_RUN_ATTEMPT) throw new Error("Workflow execution controls are missing");
  const gitSha = CommitShaSchema.parse(environment.GITHUB_SHA);
  const directory = join(RUNNER_TEMP, "feed-ingest-plan");
  const inputs = await loadPlanInputs(root);
  inputs.harvest = { ...inputs.harvest, config: resolveRunPolicy(inputs.harvest.config, policyOverrides) };
  const attempt = PositiveCountSchema.parse(Number(GITHUB_RUN_ATTEMPT));
  inputs.settings = ServiceSettingsSchema.parse({
    ...inputs.settings, enabled: true,
    ...(dumpRawDocuments === undefined ? {} : { dump_raw_document_contents: dumpRawDocuments }),
  });
  inputs.outputRoot = join(directory, "state");
  const captured = new Date();
  const context = createRootContext();
  await mkdir(directory, { recursive: true });
  await writeFile(join(directory, "workflow-policy.json"), JSON.stringify(WorkflowPolicySchema.parse({
    config: inputs.harvest.config, request: { ...request, ...policyOverrides }, history: inputs.clock_config.collect,
    parser_concurrency: inputs.settings.listener.parser_concurrency,
  })));
  const identity = { run_id: `${captured.toISOString().slice(0, 10)}-${GITHUB_RUN_ID}`,
    attempt, git_sha: gitSha };
  const registryPath = join(root, inputs.settings.inputs.registrations);
  const registrations = await readMetadataRegistrations(registryPath);
  const startup = createPlannerStartup(inputs, {
    ...context, git_sha: identity.git_sha, run_number: GITHUB_RUN_ID,
    attempt, captured_at: captured.toISOString(),
  });
  return { root, directory, inputs, startup, request, identity, registrations,
    outputPath: GITHUB_OUTPUT, date: captured.toISOString().slice(0, 10) };
}
