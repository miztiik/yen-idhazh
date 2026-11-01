/** Does consolidated finalization preserve real output across commit, report, collection and upload failures? */
import { expect, test } from "bun:test";
import { copyFile, mkdir, mkdtemp, readFile, readdir, rm, stat, symlink, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { finalizeRunOutput } from "../scripts/finalize-run-output";
import { finishRunOutput } from "../scripts/finish-run-output";
import { MetadataDeliveryResultSchema } from "../scripts/feed-ingest-plan-delivery-result";
import { publicationRecording } from "./publication-recordings";
import { fixtureGit } from "./fixture-git";
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
        runNumber: "700", attempt: 3, cancelled: false, runId: fixture.identity.run_id,
        gitSha: fixture.identity.git_sha,
        summaryPath: join(fixture.repository, "job-summary.md"), outputPath: join(fixture.directory, "step-outputs"),
      },
      finish: {
        root: fixture.repository, temporaryRoot: dirname(fixture.directory), runNumber: "700", attempt: 3,
        gitSha: fixture.identity.git_sha,
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
    const controls = {
      RUNNER_TEMP: dirname(f.directory), GITHUB_RUN_ID: "700", GITHUB_RUN_ATTEMPT: "3",
      GITHUB_SHA: f.identity.git_sha,
      CURRENT_RUN_FILES: f.finalize.currentRunFiles, RUN_CANCELLED: "false",
      GITHUB_STEP_SUMMARY: f.finalize.summaryPath, GITHUB_OUTPUT: f.finalize.outputPath,
      DUMP_RAW_DOCUMENT_CONTENTS: "false", RUN_ID: f.identity.run_id,
    };
    for (const operation of ["commit-ledgers", "write-report", "prepare-artifacts"]) {
      const finalized = await runScript("finalize-run-output.ts", f.repository, {
        ...controls, FINALIZATION_OPERATION: operation,
        REPORT_FILENAME: "feed-ingest-report-2026-10-21-700.md",
      });
      expect(finalized.code, finalized.errors).toBe(0);
      if (operation === "commit-ledgers") {
        expect(finalized.errors).toContain('"event":"safe_persist_http_completed"');
        expect(await Bun.file(join(f.directory, "feed-ingest-report-2026-10-21-700.md")).exists()).toBe(false);
      } else expect(finalized.errors).not.toContain('"event":"safe_persist_http_completed"');
      expect(finalized.errors).not.toContain('"event":"safe_persist_http_failed"');
      expect(finalized.errors).not.toMatch(/[A-Za-z]:[\\/]/);
      expect(finalized.errors).not.toContain("article_text");
    }
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
      "700-3-delivery-result.json", "700-3-selected-articles.json", "feed-ingest-report-2026-10-21-700.md",
    ]);
    const inventory: FeedIngestEvent[] = [];
    expect(await publishUploadInventory({ directory: artifacts, runNumber: "700",
      write: event => { inventory.push(event); } })).toBe(3);
    expect(inventory.flatMap(event => typeof event.details.file === "string" ? [event.details.file] : []).sort())
      .toEqual((await readdir(artifacts)).sort());
    const selected = await readFile(join(f.repository, f.summary.selected_articles_artifact!));
    expect(await readFile(join(artifacts, "700-3-selected-articles.json"))).toEqual(selected);
    const report = await readFile(join(artifacts, "feed-ingest-report-2026-10-21-700.md"), "utf8");
    expect(report).toBe(await readFile(f.finalize.summaryPath, "utf8"));
    expect(report).not.toContain("Metadata delivery");
    expect(report).not.toContain("Git delivery");
    expect(report).not.toContain(JSON.parse(selected.toString()).articles[0].article_text);
    expect(await readFile(f.finalize.outputPath, "utf8")).toContain("artifact_directory<<");

    await expect(finishRunOutput({ ...f.finish, commitOutcome: "failure" }))
      .rejects.toThrow("Run output is incomplete");
    await expect(finishRunOutput({ ...f.finish, reportOutcome: "failure" }))
      .rejects.toThrow("Run output is incomplete");
    await expect(finishRunOutput({ ...f.finish, uploadOutcome: "failure" }))
      .rejects.toThrow("Run output is incomplete");
    expect((await stat(f.directory)).isDirectory()).toBe(true);
    await expect(finishRunOutput({ ...f.finish, artifactId: "" })).rejects.toThrow("Run output is incomplete");
    expect((await stat(f.directory)).isDirectory()).toBe(true);
    await finishRunOutput({ ...f.finish, commitOutcome: "success", reportOutcome: "skipped", writeReport: false });
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
    const recovery = join(artifacts, "uncommitted-metadata-700-3");
    expect(await Bun.file(join(recovery, "current-run-files.json")).json()).toEqual(f.paths);
    for (const path of f.paths) {
      expect(await readFile(join(recovery, path))).toEqual(await readFile(join(f.directory, "state", path)));
    }
    expect(await readFile(join(artifacts, "700-3-selected-articles.json")))
      .toEqual(await readFile(join(f.repository, f.summary.selected_articles_artifact!)));
    expect(await readFile(join(artifacts, "feed-ingest-report-2026-10-21-700.md"), "utf8")).not.toContain("Git delivery");
    expect(await readFile(f.finalize.outputPath, "utf8")).toContain("artifact_directory<<");
    expect(await fixtureGit(f.origin, ["--git-dir", f.origin, "rev-parse", "main"])).toBe(f.head);
    await expect(finishRunOutput({ ...f.finish, finalizationOutcome: "failure" })).rejects.toThrow("Run output is incomplete");
    expect((await stat(f.directory)).isDirectory()).toBe(true);
  } finally { await f.close(); }
});

test("no-delivery CLI validates and packages real output without Git delivery or a fabricated receipt", async () => {
  const f = await recording();
  try {
    const controls = {
      RUNNER_TEMP: dirname(f.directory), GITHUB_RUN_ID: "700", GITHUB_RUN_ATTEMPT: "3",
      GITHUB_SHA: f.identity.git_sha, CURRENT_RUN_FILES: f.finalize.currentRunFiles,
      RUN_CANCELLED: "false", GITHUB_STEP_SUMMARY: f.finalize.summaryPath,
      GITHUB_OUTPUT: f.finalize.outputPath, RUN_ID: f.identity.run_id,
      DELIVER_METADATA: "false",
    };
    const finalized = await runScript("finalize-run-output.ts", f.repository, controls);
    expect(finalized.code, finalized.errors).toBe(0);
    expect(finalized.errors).toContain('"reason":"delivery_not_requested"');
    expect(finalized.errors).toContain('"event":"workflow_local_metadata_verified"');
    expect(finalized.errors).not.toContain("safe_persist_http_completed");
    expect(await fixtureGit(f.origin, ["--git-dir", f.origin, "rev-parse", "main"])).toBe(f.head);
    expect(await fixtureGit(f.repository, ["rev-parse", "HEAD"])).toBe(f.head);
    expect(await Bun.file(join(f.directory, "delivery-result.json")).exists()).toBe(false);
    const artifacts = join(f.directory, "artifacts");
    expect(await readFile(join(artifacts, "700-3-response.json")))
      .toEqual(await readFile(join(f.directory, "response.json")));
    expect(await readFile(join(artifacts, "700-3-host-fingerprint.json")))
      .toEqual(await readFile(join(f.directory, "host-fingerprint.json")));
    expect(await Bun.file(join(artifacts, "uncommitted-metadata-700-3", "current-run-files.json")).json())
      .toEqual(f.paths);
    const report = await readFile(join(artifacts, "feed-ingest-report-2026-10-21-700.md"), "utf8");
    expect(report).toContain("Metadata delivery was not requested");
    expect(await readFile(join(artifacts, "700-3-selected-articles.json")))
      .toEqual(await readFile(join(f.repository, f.summary.selected_articles_artifact!)));
    await expect(finishRunOutput({ ...f.finish, deliverMetadata: false, commitOutcome: "skipped" }))
      .rejects.toThrow("Run output is incomplete");
    await expect(finishRunOutput({ ...f.finish, deliverMetadata: false, uploadOutcome: "failure" }))
      .rejects.toThrow("Run output is incomplete");
    expect((await stat(f.directory)).isDirectory()).toBe(true);
    const finished = await runScript("finish-run-output.ts", f.repository, {
      ...controls, COLLECTION_OUTCOME: "success", PLANNING_COMPLETE: "true",
      FINALIZATION_OUTCOME: "success", COMMIT_OUTCOME: "success", REPORT_OUTCOME: "success",
      UPLOAD_OUTCOME: "success", UPLOAD_ARTIFACT_ID: "123",
    });
    expect(finished.code, finished.errors).toBe(0);
    expect(finished.errors).toContain('"commit":"not_requested"');
    await expect(stat(f.directory)).rejects.toMatchObject({ code: "ENOENT" });
  } finally { await f.close(); }
});

test("no-delivery refuses mismatched or damaged local metadata and retains failure recovery", async () => {
  const f = await recording();
  try {
    await expect(finalizeRunOutput({ ...f.finalize, deliverMetadata: false,
      currentRunFiles: "[]", operation: "commit-ledgers" })).rejects.toThrow("Run finalization failed");
    await writeFile(join(f.directory, "state", f.paths[0]!), "Invalid Parquet");
    await expect(finalizeRunOutput({ ...f.finalize, deliverMetadata: false }))
      .rejects.toThrow("Run finalization failed");
    expect(await fixtureGit(f.origin, ["--git-dir", f.origin, "rev-parse", "main"])).toBe(f.head);
    expect(await Bun.file(join(f.directory, "delivery-result.json")).exists()).toBe(false);
    await expect(finishRunOutput({ ...f.finish, deliverMetadata: false, finalizationOutcome: "failure" }))
      .rejects.toThrow("Run output is incomplete");
    expect((await stat(f.directory)).isDirectory()).toBe(true);
  } finally { await f.close(); }
});

test("a job-summary write failure cannot prevent an already-rendered report or selected text from being uploaded", async () => {
  const f = await recording();
  try {
    await expect(finalizeRunOutput({ ...f.finalize, summaryPath: f.repository })).rejects.toThrow("Run finalization failed");
    expect(MetadataDeliveryResultSchema.parse(await Bun.file(join(f.directory, "delivery-result.json")).json()).status).toBe("landed");
    const artifacts = join(f.directory, "artifacts");
    expect(await Bun.file(join(artifacts, "feed-ingest-report-2026-10-21-700.md")).exists()).toBe(true);
    expect(await readFile(join(artifacts, "700-3-selected-articles.json")))
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
    expect(await readFile(join(f.directory, "artifacts", "feed-ingest-report-2026-10-21-700.md"), "utf8")).not.toContain("Git delivery");
    expect(await Bun.file(join(f.directory, "artifacts", "uncommitted-metadata-700-3", "current-run-files.json")).json())
      .toEqual(f.paths);
    const finished = await runScript("finish-run-output.ts", f.repository, {
      RUNNER_TEMP: dirname(f.directory), GITHUB_RUN_ID: "700", GITHUB_RUN_ATTEMPT: "3",
      GITHUB_SHA: f.identity.git_sha,
      COLLECTION_OUTCOME: "cancelled", PLANNING_COMPLETE: "false", FINALIZATION_OUTCOME: "success",
      UPLOAD_OUTCOME: "success", UPLOAD_ARTIFACT_ID: "123",
    });
    expect(finished.code).toBe(2);
    expect(finished.errors).not.toMatch(/[A-Za-z]:[\\/]/);
    expect(finished.errors).not.toContain('"event":"workflow_cleanup_refused"');
    expect(finished.errors).not.toContain('"code":"ENOENT"');
    expect((await stat(f.directory)).isDirectory()).toBe(true);
  } finally { await f.close(); }
});

test("completed diagnostics can land and be cleaned while a partial collection still fails the job", async () => {
  const f = await recording(true);
  try {
    expect(f.summary.planning_complete).toBe(false);
    await finalizeRunOutput({ ...f.finalize, operation: "commit-ledgers" });
    await finalizeRunOutput({ ...f.finalize, operation: "prepare-artifacts" });
    expect(MetadataDeliveryResultSchema.parse(await Bun.file(join(f.directory, "delivery-result.json")).json()).status).toBe("landed");
    expect(await Bun.file(join(f.directory, "artifacts", "feed-ingest-report-2026-10-21-700.md")).exists()).toBe(false);
    expect(await Bun.file(join(f.directory, "artifacts", "700-3-selected-articles.json")).exists()).toBe(false);
    await expect(finishRunOutput({ ...f.finish, collectionOutcome: "failure", planningComplete: "false",
      commitOutcome: "success", reportOutcome: "skipped", writeReport: false }))
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
        gitSha: "a".repeat(40),
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
      root, directory, runNumber: "700", attempt: 1, cancelled: false, runId: "2026-10-21-700",
      gitSha: "a".repeat(40),
      summaryPath: join(root, "summary.md"), outputPath,
    })).rejects.toThrow("Run finalization failed");
    expect(await readFile(join(directory, "artifacts", "feed-ingest-report-2026-10-21-700.md"), "utf8")).toContain("Planning result unavailable");
    expect(await readFile(outputPath, "utf8")).toContain("artifact_directory<<");
    expect(await Bun.file(join(directory, "delivery-result.json")).exists()).toBe(false);
  } finally { await rm(root, { recursive: true, force: true }); }
});
