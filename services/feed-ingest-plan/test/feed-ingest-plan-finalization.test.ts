/** Does consolidated finalization preserve real output across commit, report, collection and upload failures? */
import { expect, test } from "bun:test";
import { copyFile, mkdir, mkdtemp, readFile, readdir, rm, stat, symlink, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { finalizeRunOutput } from "../scripts/finalize-run-output";
import { finishRunOutput } from "../scripts/finish-run-output";
import { MetadataDeliveryResultSchema } from "../scripts/feed-ingest-plan-delivery-result";
import { publicationRecording, fixtureGit } from "./publication-recordings";
import { publishUploadInventory } from "../scripts/feed-ingest-plan-upload-inventory";
import type { FeedIngestEvent } from "@idhazh/common-contracts";

async function recording(failCollection = false) {
  const fixture = await publicationRecording(failCollection);
  try {
    await writeFile(join(fixture.repository, "config", "feed-ingest-plan.json"),
      JSON.stringify(fixture.inputs.harvest.config));
    await writeFile(join(fixture.repository, "config", "data-delivery.json"),
      JSON.stringify({ name: "Fixture", email: "fixture@example.test" }));
    return {
      ...fixture,
      finalize: {
        root: fixture.repository, directory: fixture.directory, currentRunFiles: JSON.stringify(fixture.paths),
        runNumber: "700", attempt: 1, cancelled: false,
        summaryPath: join(fixture.repository, "job-summary.md"), outputPath: join(fixture.directory, "step-outputs"),
      },
      finish: {
        root: fixture.repository, temporaryRoot: dirname(fixture.directory), runNumber: "700", attempt: 1,
        collectionOutcome: "success", planningComplete: "true", finalizationOutcome: "success",
        uploadOutcome: "success", artifactId: "123",
      },
    };
  } catch (error) {
    await fixture.close();
    throw error;
  }
}

async function runScript(name: "finalize-run-output.ts" | "finish-run-output.ts", root: string, controls: Record<string, string>) {
  const child = Bun.spawn([process.execPath, fileURLToPath(new URL(`../scripts/${name}`, import.meta.url))], {
    cwd: root, env: { ...Bun.env, ...controls }, stdout: "pipe", stderr: "pipe",
  });
  const [output, errors, code] = await Promise.all([
    new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited,
  ]);
  return { output, errors, code };
}

test("one Git delivery precedes the report and prepares only the selected handoff and receipts", async () => {
  const f = await recording();
  try {
    const indexBefore = await readFile(join(f.repository, ".git", "index"));
    const finalized = await runScript("finalize-run-output.ts", f.repository, {
      RUNNER_TEMP: dirname(f.directory), GITHUB_RUN_ID: "700", GITHUB_RUN_ATTEMPT: "1",
      GITHUB_OUTPUT: f.finalize.outputPath, GITHUB_STEP_SUMMARY: f.finalize.summaryPath,
      CURRENT_RUN_FILES: f.finalize.currentRunFiles, RUN_CANCELLED: "false",
    });
    expect(finalized.code, finalized.errors).toBe(0);
    const receipt = MetadataDeliveryResultSchema.parse(await Bun.file(join(f.directory, "delivery-result.json")).json());
    expect(receipt).toMatchObject({ status: "landed", files: f.paths.length, paths: f.paths });
    const committed = await fixtureGit(f.origin, [
      "--git-dir", f.origin, "diff-tree", "--no-commit-id", "--name-only", "-r", "main",
    ]);
    expect(committed.split("\n").sort()).toEqual(f.paths.map(path => `state/${path}`).sort());
    expect(await fixtureGit(f.repository, ["rev-parse", "HEAD"])).toBe(f.head);
    expect(await readFile(join(f.repository, ".git", "index"))).toEqual(indexBefore);
    const artifacts = join(f.directory, "artifacts");
    expect((await readdir(artifacts)).sort()).toEqual([
      "700-1-delivery-result.json", "700-1-report.md", "700-1-selected-articles.json",
    ]);
    const inventory: FeedIngestEvent[] = [];
    expect(await publishUploadInventory({ directory: artifacts, runNumber: "700",
      write: event => { inventory.push(event); } })).toBe(3);
    expect(inventory.flatMap(event => typeof event.details.file === "string" ? [event.details.file] : []).sort())
      .toEqual((await readdir(artifacts)).sort());
    const selected = await readFile(join(f.repository, f.summary.selected_articles_artifact!));
    expect(await readFile(join(artifacts, "700-1-selected-articles.json"))).toEqual(selected);
    const report = await readFile(join(artifacts, "700-1-report.md"), "utf8");
    expect(report).toBe(await readFile(f.finalize.summaryPath, "utf8"));
    expect(report).toContain(receipt.commit!);
    expect(report).toContain("Git delivery: **landed**");
    expect(report).not.toContain(JSON.parse(selected.toString()).articles[0].article_text);
    expect(await readFile(f.finalize.outputPath, "utf8")).toContain("artifact_directory<<");

    await expect(finishRunOutput({ ...f.finish, uploadOutcome: "failure" }))
      .rejects.toThrow("Run output is incomplete");
    expect((await stat(f.directory)).isDirectory()).toBe(true);
    await expect(finishRunOutput({ ...f.finish, artifactId: "" })).rejects.toThrow("Run output is incomplete");
    expect((await stat(f.directory)).isDirectory()).toBe(true);
    const finished = await runScript("finish-run-output.ts", f.repository, {
      RUNNER_TEMP: dirname(f.directory), GITHUB_RUN_ID: "700", GITHUB_RUN_ATTEMPT: "1",
      COLLECTION_OUTCOME: "success", PLANNING_COMPLETE: "true", FINALIZATION_OUTCOME: "success",
      UPLOAD_OUTCOME: "success", UPLOAD_ARTIFACT_ID: "123",
    });
    expect(finished.code, finished.errors).toBe(0);
    await expect(stat(f.directory)).rejects.toMatchObject({ code: "ENOENT" });
    expect(await readFile(f.finalize.summaryPath, "utf8")).toBe(report);
    expect(await readFile(join(f.repository, f.summary.selected_articles_artifact!))).toEqual(selected);
  } finally { await f.close(); }
});

test("a refused Git delivery still writes the report and prepares exact metadata recovery and article text", async () => {
  const f = await recording();
  try {
    await fixtureGit(f.repository, ["remote", "set-url", "origin", join(dirname(f.directory), "missing-origin.git")]);
    await expect(finalizeRunOutput(f.finalize)).rejects.toThrow("Run finalization failed");
    const receipt = MetadataDeliveryResultSchema.parse(await Bun.file(join(f.directory, "delivery-result.json")).json());
    expect(receipt.status).toBe("failed");
    const artifacts = join(f.directory, "artifacts");
    const recovery = join(artifacts, "uncommitted-metadata-700-1");
    expect(await Bun.file(join(recovery, "current-run-files.json")).json()).toEqual(f.paths);
    for (const path of f.paths) {
      expect(await readFile(join(recovery, path))).toEqual(await readFile(join(f.directory, "state", path)));
    }
    expect(await readFile(join(artifacts, "700-1-selected-articles.json")))
      .toEqual(await readFile(join(f.repository, f.summary.selected_articles_artifact!)));
    expect(await readFile(join(artifacts, "700-1-report.md"), "utf8")).toContain("Git delivery: **failed**");
    expect(await readFile(f.finalize.outputPath, "utf8")).toContain("artifact_directory<<");
    expect(await fixtureGit(f.origin, ["--git-dir", f.origin, "rev-parse", "main"])).toBe(f.head);
    await expect(finishRunOutput({ ...f.finish, finalizationOutcome: "failure" })).rejects.toThrow("Run output is incomplete");
    expect((await stat(f.directory)).isDirectory()).toBe(true);
  } finally { await f.close(); }
});

test("a job-summary write failure cannot prevent an already-rendered report or selected text from being uploaded", async () => {
  const f = await recording();
  try {
    await expect(finalizeRunOutput({ ...f.finalize, summaryPath: f.repository })).rejects.toThrow("Run finalization failed");
    expect(MetadataDeliveryResultSchema.parse(await Bun.file(join(f.directory, "delivery-result.json")).json()).status).toBe("landed");
    const artifacts = join(f.directory, "artifacts");
    expect(await Bun.file(join(artifacts, "700-1-report.md")).exists()).toBe(true);
    expect(await readFile(join(artifacts, "700-1-selected-articles.json")))
      .toEqual(await readFile(join(f.repository, f.summary.selected_articles_artifact!)));
    expect(await readFile(f.finalize.outputPath, "utf8")).toContain("artifact_directory<<");
  } finally { await f.close(); }
});

test("cancelled finalization preserves recovery and a report without creating a Git commit", async () => {
  const f = await recording();
  try {
    await finalizeRunOutput({ ...f.finalize, cancelled: true });
    expect(await fixtureGit(f.origin, ["--git-dir", f.origin, "rev-parse", "main"])).toBe(f.head);
    expect(await Bun.file(join(f.directory, "delivery-result.json")).exists()).toBe(false);
    expect(await readFile(join(f.directory, "artifacts", "700-1-report.md"), "utf8")).toContain("Git delivery was not confirmed");
    expect(await Bun.file(join(f.directory, "artifacts", "uncommitted-metadata-700-1", "current-run-files.json")).json())
      .toEqual(f.paths);
    const finished = await runScript("finish-run-output.ts", f.repository, {
      RUNNER_TEMP: dirname(f.directory), GITHUB_RUN_ID: "700", GITHUB_RUN_ATTEMPT: "1",
      COLLECTION_OUTCOME: "cancelled", PLANNING_COMPLETE: "false", FINALIZATION_OUTCOME: "success",
      UPLOAD_OUTCOME: "success", UPLOAD_ARTIFACT_ID: "123",
    });
    expect(finished.code).toBe(2);
    expect(finished.errors).not.toMatch(/[A-Za-z]:[\\/]/);
    expect((await stat(f.directory)).isDirectory()).toBe(true);
  } finally { await f.close(); }
});

test("completed diagnostics can land and be cleaned while a partial collection still fails the job", async () => {
  const f = await recording(true);
  try {
    expect(f.summary.planning_complete).toBe(false);
    await finalizeRunOutput(f.finalize);
    expect(MetadataDeliveryResultSchema.parse(await Bun.file(join(f.directory, "delivery-result.json")).json()).status).toBe("landed");
    expect(await Bun.file(join(f.directory, "artifacts", "700-1-selected-articles.json")).exists()).toBe(false);
    await expect(finishRunOutput({ ...f.finish, collectionOutcome: "failure", planningComplete: "false" }))
      .rejects.toThrow("Run output is incomplete");
    await expect(stat(f.directory)).rejects.toMatchObject({ code: "ENOENT" });
    expect(await fixtureGit(f.origin, ["--git-dir", f.origin, "rev-parse", "main"])).not.toBe(f.head);
  } finally { await f.close(); }
});

test("cleanup refuses a repository directory and a temporary-directory junction", async () => {
  const directory = await mkdtemp(join(tmpdir(), "workflow-cleanup-"));
  try {
    const repository = join(directory, "repository");
    const runner = join(directory, "runner");
    const outside = join(directory, "outside");
    await mkdir(join(repository, "feed-ingest-plan"), { recursive: true });
    await mkdir(runner);
    await mkdir(outside);
    await writeFile(join(repository, "feed-ingest-plan", "keep.txt"), "Repository work");
    await writeFile(join(outside, "keep.txt"), "Outside work");
    await symlink(outside, join(runner, "feed-ingest-plan"), "junction");
    for (const temporaryRoot of [repository, runner]) {
      await expect(finishRunOutput({
        root: repository, temporaryRoot, runNumber: "700", attempt: 1,
        collectionOutcome: "success", planningComplete: "true", finalizationOutcome: "success",
        uploadOutcome: "success", artifactId: "123",
      })).rejects.toThrow("Run output is incomplete");
    }
    expect(await readFile(join(repository, "feed-ingest-plan", "keep.txt"), "utf8")).toBe("Repository work");
    expect(await readFile(join(outside, "keep.txt"), "utf8")).toBe("Outside work");
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test("missing collection output still produces a report artifact without inventing a delivery receipt", async () => {
  const root = await mkdtemp(join(tmpdir(), "workflow-missing-result-"));
  try {
    await mkdir(join(root, "config"));
    await copyFile(new URL("../../../config/feed-ingest-plan.json", import.meta.url), join(root, "config", "feed-ingest-plan.json"));
    const directory = join(root, "runner", "feed-ingest-plan");
    const outputPath = join(root, "step-outputs");
    await expect(finalizeRunOutput({
      root, directory, runNumber: "700", attempt: 1, cancelled: false,
      summaryPath: join(root, "summary.md"), outputPath,
    })).rejects.toThrow("Run finalization failed");
    expect(await readFile(join(directory, "artifacts", "700-1-report.md"), "utf8")).toContain("Planning result unavailable");
    expect(await readFile(outputPath, "utf8")).toContain("artifact_directory<<");
    expect(await Bun.file(join(directory, "delivery-result.json")).exists()).toBe(false);
  } finally { await rm(root, { recursive: true, force: true }); }
});
