/** Prepare captured native planner output and host evidence against an isolated Git origin. */
import { copyFile, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { recordedPlan } from "./plan-recordings";
import { metadataRegistrations } from "./host-recordings";
import { writeRecordedHostOutput } from "./host-output-recordings";
import { createExecutionOutputs } from "../scripts/feed-ingest-plan-outputs";
import { fixtureGit } from "./fixture-git";
import { writePlannerOutputRecording } from "./planner-output-recordings";
import { ServiceSettingsSchema } from "../src/config/service-settings";

export async function publicationGitRecording() {
  const plan = await recordedPlan();
  try {
    const repository = join(plan.directory, "checkout");
    const origin = join(plan.directory, "origin.git");
    const directory = join(plan.directory, "feed-ingest-plan");
    await mkdir(join(repository, "config"), { recursive: true });
    await fixtureGit(plan.directory, ["init", "--bare", "--initial-branch=main", origin]);
    await fixtureGit(repository, ["init", "--initial-branch=main"]);
    for (const name of ["ledgers.json", "feed-ingest-plan-service.json", "data-delivery.json"]) {
      await copyFile(new URL(`../../../config/${name}`, import.meta.url), join(repository, "config", name));
    }
    const settingsPath = join(repository, "config", "feed-ingest-plan-service.json");
    const settings = ServiceSettingsSchema.parse(await Bun.file(settingsPath).json());
    const reservation = Bun.serve({ hostname: "127.0.0.1", port: 0, fetch: () => new Response() });
    settings.listener.port = reservation.port!;
    await reservation.stop(true);
    plan.inputs.settings.listener.port = settings.listener.port;
    await writeFile(settingsPath, JSON.stringify(settings));
    const retry = await Bun.file(new URL("../../../config/push-retry.json", import.meta.url)).json();
    await writeFile(join(repository, "config", "push-retry.json"), JSON.stringify(retry));
    await fixtureGit(repository, ["add", "--", "config/ledgers.json",
      "config/feed-ingest-plan-service.json", "config/push-retry.json", "config/data-delivery.json"]);
    await fixtureGit(repository, ["commit", "-m", "Create generated publication inputs"]);
    await fixtureGit(repository, ["remote", "add", "origin", origin]);
    await fixtureGit(repository, ["push", "origin", "HEAD:refs/heads/main"]);
    const head = await fixtureGit(repository, ["rev-parse", "HEAD"]);
    const identity = { run_id: "2026-10-21-700", attempt: 3, git_sha: head };
    const registrations = await metadataRegistrations();
    await mkdir(directory, { recursive: true });
    plan.inputs.root = repository;
    plan.inputs.outputRoot = join(directory, "state");
    plan.runtime.git_sha = head;
    const paths: string[] = [];
    const commit = { repository, stateRoot: plan.inputs.outputRoot, paths, identity,
      registrations, message: "Record generated planner and host metadata", retry };
    return { ...plan, repository, origin, directory, head, identity, registrations, commit };
  } catch (error) { await plan.close(); throw error; }
}

export async function publicationRecording(failPlanning = false) {
  const fixture = await publicationGitRecording();
  try {
    const { directory, identity, origin, head } = fixture;
    const host = await writeRecordedHostOutput(directory, identity, fixture.inputs.ledgerSettings);
    const recorded = await writePlannerOutputRecording(fixture.inputs, failPlanning);
    const summary = recorded.response;
    const beforeDelivery = await fixtureGit(origin, ["--git-dir", origin, "rev-parse", "main"]);
    if (beforeDelivery !== head) throw new Error("Planner stages made a Git commit before final delivery");
    await writeFile(join(directory, "response.json"), JSON.stringify(summary));
    const plannerPaths: string[] = JSON.parse(createExecutionOutputs(summary, fixture.inputs.registrations).current_run_files!);
    const paths = [...host.response.files.map(file => file.path), ...plannerPaths];
    const commit = { ...fixture.commit, paths };
    return { ...fixture, host, summary, plannerPaths, paths, commit };
  } catch (error) { await fixture.close(); throw error; }
}
