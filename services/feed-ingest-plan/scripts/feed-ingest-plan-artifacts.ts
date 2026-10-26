/** Which exact run receipts can be retained without copying private stage or article populations? */
import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { z } from "zod";
import { WriterIdentitySchema } from "../../../packages/common-contracts/src/index";
import { PlanResponseSchema } from "../src/api/plan-response.schema";
import { verifyPlanningCompletion } from "./feed-ingest-plan-verification";
import { writeGitHubOutputs } from "./feed-ingest-plan-outputs";

export async function prepareWorkflowArtifacts(input: {
  root: string; directory: string; runNumber: string; attempt: number; outputPath?: string;
}) {
  // Actions run numbers and attempt numbers form filenames, never fetched text.
  const run = z.string().regex(/^\d+$/).parse(input.runNumber);
  const attempt = WriterIdentitySchema.shape.attempt.parse(input.attempt);
  const outputs: Record<string, string> = {};
  async function publish(key: string, path: string) {
    outputs[key] = path;
    if (input.outputPath !== undefined) await writeGitHubOutputs(input.outputPath, { [key]: path });
  }
  async function retain(key: string, source: string, filename: string) {
    if (!await Bun.file(source).exists()) {
      console.error(JSON.stringify({ event: "planner_evidence_unavailable", file: filename }));
      return;
    }
    const path = `artifacts/${run}-${attempt}-${filename}`;
    await mkdir(dirname(join(input.directory, path)), { recursive: true });
    await copyFile(source, join(input.directory, path));
    await publish(key, path);
  }
  for (const [key, name] of [
    ["response", "response.json"], ["health", "health.json"], ["history", "history-staging-ms.json"],
    ["commit", "commit-result.json"], ["runtime_log", "runtime.log"], ["commit_log", "commit.log"],
    ["policy", "workflow-policy.json"], ["resources", "resources.json"], ["report", "report.md"],
  ] as const) await retain(key, join(input.directory, name), name);
  await retain("independent", join(input.root, "test-results", "host-probes", "resource-proof.json"), "controlled-host-proof.json");
  const responsePath = join(input.directory, "response.json");
  if (!await Bun.file(responsePath).exists()) return outputs;
  const response = PlanResponseSchema.parse(JSON.parse(await readFile(responsePath, "utf8")));
  const registration = (name: string) => ({ name, family: "feed-ingest-plan", prefix: ["feed-ingest-plan", name],
    grain: "raw-and-compact" as const, lifecycle_status: "active" as const });
  const verified = await verifyPlanningCompletion(join(input.directory, "state"), response, {
    discovered_articles: registration("discovered-articles"), selected_articles: registration("selected-articles"),
    feed_health_state: registration("feed-health-state"), plan_runs: registration("plan-runs"),
  }, input.root);
  const paths = Object.values(verified).flatMap(result => result?.files ?? []);
  const commitFile = Bun.file(join(input.directory, "commit-result.json"));
  const commit = await commitFile.exists() ? z.object({
    status: z.enum(["landed", "already-on-main", "no-changes", "failed"]),
    commit: z.string().regex(/^[a-f0-9]{40}$/).nullable(), files: z.int().nonnegative(),
  }).parse(await commitFile.json()) : null;
  const confirmed = commit !== null && commit.files === paths.length
    && (commit.status === "landed" || commit.status === "already-on-main") && commit.commit !== null;
  if (!confirmed && paths.length > 0) {
    const recovery = `artifacts/uncommitted-metadata-${run}-${attempt}`;
    for (const path of paths) {
      const destination = join(input.directory, recovery, path);
      await mkdir(dirname(destination), { recursive: true });
      await copyFile(join(input.directory, "state", path), destination);
    }
    await writeFile(join(input.directory, recovery, "current-run-files.json"), JSON.stringify(paths));
    await publish("metadata_recovery", recovery);
    console.error(JSON.stringify({ event: "planner_uncommitted_metadata_retained", files: paths.length,
      commit_status: commit?.status ?? "not_recorded" }));
  }
  if (response.selected_articles_artifact !== null) {
    await retain("selected", join(input.root, response.selected_articles_artifact), "selected-articles.json");
  }
  return outputs;
}

if (import.meta.main) {
  const { RUNNER_TEMP, GITHUB_OUTPUT, GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT } = process.env;
  if (!RUNNER_TEMP || !GITHUB_OUTPUT || !GITHUB_RUN_ID || !GITHUB_RUN_ATTEMPT) throw new Error("Artifact execution controls are missing");
  await prepareWorkflowArtifacts({
    root: process.cwd(), directory: join(RUNNER_TEMP, "feed-ingest-plan"),
    runNumber: GITHUB_RUN_ID, attempt: Number(GITHUB_RUN_ATTEMPT), outputPath: GITHUB_OUTPUT,
  });
}
