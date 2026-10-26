/** How is one real planner and host run prepared against an isolated bare Git origin? */
import { copyFile, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { recordedPlan } from "./plan-recordings";
import { recordedWorkflowHost } from "./host-recordings";
import { runFeedPlan, summarizePlan } from "../src/run-feed-plan";
import { createExecutionOutputs } from "../scripts/feed-ingest-plan-outputs";

export async function fixtureGit(directory: string, args: string[], environment: Record<string, string> = {}) {
  const env = { ...Bun.env, GIT_AUTHOR_NAME: "Fixture", GIT_AUTHOR_EMAIL: "fixture@example.test",
    GIT_COMMITTER_NAME: "Fixture", GIT_COMMITTER_EMAIL: "fixture@example.test", ...environment };
  const child = Bun.spawn(["git", ...args], { cwd: directory, env, stdout: "pipe", stderr: "pipe" });
  const [output, errors, code] = await Promise.all([
    new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited,
  ]);
  if (code !== 0) throw new Error(`Generated publication Git ${args[0]} failed: ${errors}`);
  return output.trim();
}

export async function publicationRecording(failPlanning = false) {
  const plan = await recordedPlan();
  try {
    const repository = join(plan.directory, "checkout");
    const origin = join(plan.directory, "origin.git");
    const directory = join(plan.directory, "feed-ingest-plan");
    await mkdir(join(repository, "config"), { recursive: true });
    await fixtureGit(plan.directory, ["init", "--bare", "--initial-branch=main", origin]);
    await fixtureGit(repository, ["init", "--initial-branch=main"]);
    await writeFile(join(repository, "README.md"), "Generated publication fixture.\n");
    for (const name of ["ledgers.json", "feed-ingest-plan-service.json"]) {
      await copyFile(new URL(`../../../config/${name}`, import.meta.url), join(repository, "config", name));
    }
    const retry = { deadline_seconds: { default: 90 }, base_step_seconds: 0.01, ceiling_seconds: 0.1, ceiling_after: 1 };
    await writeFile(join(repository, "config", "push-retry.json"), JSON.stringify(retry));
    await fixtureGit(repository, ["add", "--", "README.md", "config/ledgers.json",
      "config/feed-ingest-plan-service.json", "config/push-retry.json"]);
    await fixtureGit(repository, ["commit", "-m", "Create generated publication inputs"]);
    await fixtureGit(repository, ["remote", "add", "origin", origin]);
    await fixtureGit(repository, ["push", "origin", "HEAD:refs/heads/main"]);
    const head = await fixtureGit(repository, ["rev-parse", "HEAD"]);
    const identity = { run_id: "2026-10-21-700", attempt: 1, git_sha: head };
    const host = await recordedWorkflowHost(directory, identity);
    plan.inputs.root = repository;
    plan.inputs.outputRoot = join(directory, "state");
    plan.runtime.git_sha = head;
    if (failPlanning) {
      plan.inputs.settings.inputs.artifact_root = "blocked-artifacts";
      await writeFile(join(repository, "blocked-artifacts"), "Artifact persistence must fail");
    }
    const summary = summarizePlan(await runFeedPlan({}, plan.inputs, plan.runtime));
    await writeFile(join(directory, "response.json"), JSON.stringify(summary));
    const plannerPaths: string[] = JSON.parse(createExecutionOutputs(summary, plan.inputs.registrations).current_run_files!);
    const paths = [...host.response.files.map(file => file.path), ...plannerPaths];
    const commit = { repository, stateRoot: plan.inputs.outputRoot, paths, identity,
      registrations: host.registrations, message: "Record generated planner and host metadata", retry };
    return { ...plan, repository, origin, directory, head, host, summary, plannerPaths, paths, commit };
  } catch (error) { await plan.close(); throw error; }
}
