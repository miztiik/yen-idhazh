/** Do actual HTTP results, native files and selected artifacts survive the isolated handoff? */
import { expect, test } from "bun:test";
import { mkdir, mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createHash } from "node:crypto";
import { RawDayIndexSchema, SelectedArticlesArtifactSchema } from "../../../packages/common-contracts/src/index";
import { runFeedPlan, summarizePlan } from "../../../services/feed-ingest-plan/src/run-feed-plan";
import { recordedPlan } from "../../../services/feed-ingest-plan/test/plan-recordings";
import { source } from "../../../services/feed-ingest-plan/test/harvest-recordings";
import { main } from "../../../services/feed-ingest-plan/src/index";
import { executeFeedHealthState } from "../../../services/feed-ingest-plan/src/api/feed-health-state-operation";
import { invokePlannerHttp } from "../feed-ingest-plan-http-proof";
import { commitPlannerFiles } from "../feed-ingest-plan-commit";
import { verifyParquetFiles, verifyPlanningCompletion, verifyRecordedCompatibility } from "../feed-ingest-plan-verification";
import { createExecutionOutputs, writeGitHubOutputs } from "../feed-ingest-plan-outputs";
import { formatExecutionReport, readExecutionReport, writePlannerReport } from "../feed-ingest-plan-report";

async function git(directory: string, args: string[]) {
  const child = Bun.spawn(["git", ...args], { cwd: directory, stdout: "pipe", stderr: "pipe", env: {
    ...Bun.env, GIT_AUTHOR_NAME: "Fixture", GIT_AUTHOR_EMAIL: "fixture@example.test",
    GIT_COMMITTER_NAME: "Fixture", GIT_COMMITTER_EMAIL: "fixture@example.test",
  } });
  const [output, errors] = await Promise.all([new Response(child.stdout).text(), new Response(child.stderr).text()]);
  if (await child.exited !== 0) throw new Error(`Generated Git fixture refused ${args[0]}: ${errors}`);
  return output.trim();
}

test("actual HTTP output retains selected text separately from its strict metadata manifest", async () => {
  const fixture = await recordedPlan();
  try {
    fixture.inputs.settings.listener.port = 0;
    const directory = join(fixture.directory, "evidence");
    const result = await invokePlannerHttp(fixture.inputs, fixture.runtime, { article_limit: 1 }, directory);
    expect(result.http_status).toBe(200);
    expect(result.summary.planning_complete).toBe(true);
    const paths: string[] = JSON.parse(result.outputs.current_run_files!);
    expect(paths).toEqual(Object.values(result.summary.files).flatMap(result => result?.files.map(file => file.path) ?? []));
    expect(paths.every(path => path.endsWith(".parquet"))).toBe(true);
    expect(result.outputs).not.toHaveProperty("audited_complete");
    const artifact = SelectedArticlesArtifactSchema.parse(JSON.parse(await readFile(
      join(fixture.directory, result.outputs.selected_articles_artifact!), "utf8")));
    expect(artifact.articles[0]!.article_text.length).toBeGreaterThan(0);
    for (const evidence of [JSON.stringify(result.summary), JSON.stringify(result.outputs), JSON.stringify(result.health)]) {
      expect(evidence).not.toContain("article_text");
      expect(evidence).not.toContain(artifact.articles[0]!.article_text);
    }
    expect(JSON.parse(await readFile(join(directory, "response.json"), "utf8"))).toEqual(result.summary);
  } finally { await fixture.close(); }
});

test("exact metadata appends through a generated bare origin with complete raw indexes and safe replay", async () => {
  const fixture = await recordedPlan();
  try {
    const summary = summarizePlan(await runFeedPlan({}, fixture.inputs, fixture.runtime));
    const paths: string[] = JSON.parse(createExecutionOutputs(summary, fixture.inputs.registrations).current_run_files!);
    const repository = join(fixture.directory, "checkout");
    const origin = join(fixture.directory, "origin.git");
    await mkdir(repository);
    await git(fixture.directory, ["init", "--bare", "--initial-branch=main", origin]);
    await git(repository, ["init", "--initial-branch=main"]);
    await writeFile(join(repository, "README.md"), "Generated bounded fixture.\n");
    await git(repository, ["add", "--", "README.md"]);
    await git(repository, ["commit", "-m", "Create generated fixture"]);
    await git(repository, ["remote", "add", "origin", origin]);
    await git(repository, ["push", "origin", "HEAD:refs/heads/main"]);
    const head = await git(repository, ["rev-parse", "HEAD"]);
    const input = { repository, stateRoot: fixture.inputs.outputRoot, paths,
      message: "Record generated planner facts",
      retry: { deadline_seconds: { default: 20 }, base_step_seconds: 0.01, ceiling_seconds: 0.1, ceiling_after: 1 } };
    const committed = await commitPlannerFiles(input);
    expect(committed.status).toBe("landed");
    expect(await git(repository, ["rev-parse", "HEAD"])).toBe(head);
    expect(await git(repository, ["status", "--porcelain"])).toBe("");
    const indexes = [...new Set(paths.map(path => `state/${path.slice(0, path.lastIndexOf("/"))}/index.json`))];
    // This tree was just built by this case; it cannot grow with repository history.
    const members = (await git(fixture.directory, ["--git-dir", origin, "ls-tree", "-r", "--name-only", "main"])).split("\n");
    expect(members.sort()).toEqual(["README.md", ...paths.map(path => `state/${path}`), ...indexes].sort());
    for (const path of indexes) {
      const index = RawDayIndexSchema.parse(JSON.parse(await git(fixture.directory, ["--git-dir", origin, "show", `main:${path}`])));
      expect(index.files).toEqual(paths.filter(file => `state/${file}`.startsWith(path.slice(0, -10))).map(file => file.split("/").at(-1)!));
      expect(index.content_sha256).toBe(createHash("sha256").update(index.files.join("\n")).digest("hex"));
      if (index.bytes === null) throw new Error("The generated raw index must record actual byte counts");
      expect(index.bytes.every(value => value > 0)).toBe(true);
    }
    expect((await commitPlannerFiles(input)).status).toBe("already-on-main");
    await expect(commitPlannerFiles({ ...input, paths: ["raw/feed-ingest-plan/dispatches/2026/10/21/anything.parquet"] })).rejects.toThrow("current planner");
  } finally { await fixture.close(); }
});

test("one real result and every native file stay unchanged through both report modes", async () => {
  const fixture = await recordedPlan();
  try {
    const result = await runFeedPlan({}, fixture.inputs, fixture.runtime);
    const response = summarizePlan(result);
    const health = await executeFeedHealthState({ batch_id: response.batches.selection_batch_id, action: "summarize" },
      fixture.inputs, fixture.runtime);
    const outputs = createExecutionOutputs(response, fixture.inputs.registrations);
    const paths: string[] = JSON.parse(outputs.current_run_files!);
    const bytes = await Promise.all(paths.map(path => readFile(join(fixture.inputs.outputRoot, path))));
    const evidence = { response, health, historyStagingMs: 3 };
    const summary = join(fixture.directory, "summary.md");
    const annotations: string[] = [];
    await writePlannerReport({ config: { ...fixture.inputs.harvest.config, workflow_reporting: {
      ...fixture.inputs.harvest.config.workflow_reporting, enabled: false,
    } }, summary_path: summary, annotate: line => annotations.push(line) });
    await expect(stat(summary)).rejects.toMatchObject({ code: "ENOENT" });
    await writePlannerReport({ config: fixture.inputs.harvest.config, evidence, summary_path: summary,
      annotate: line => annotations.push(line) });
    expect(await readFile(summary, "utf8")).toBe(formatExecutionReport(evidence));
    expect(annotations).toEqual([]);
    const directory = join(fixture.directory, "evidence");
    await mkdir(directory);
    await writeFile(join(directory, "response.json"), JSON.stringify(response));
    await writeFile(join(directory, "health.json"), JSON.stringify(health));
    await writeFile(join(directory, "history-staging-ms.json"), "3");
    expect(await readExecutionReport(directory)).toBe(formatExecutionReport(evidence));
    for (const [index, path] of paths.entries()) expect(await readFile(join(fixture.inputs.outputRoot, path))).toEqual(bytes[index]!);
    await verifyPlanningCompletion(fixture.inputs.outputRoot, response, fixture.inputs.registrations, fixture.directory);
  } finally { await fixture.close(); }
});

test("uses actual selected identities and rejects inconsistent counts, assignments and foreign paths", async () => {
  const fixture = await recordedPlan();
  try {
    const response = summarizePlan(await runFeedPlan({ article_limit: 1, shards: 2 }, fixture.inputs, fixture.runtime));
    const outputs = createExecutionOutputs(response, fixture.inputs.registrations);
    expect(outputs.dispatch_count).toBe("2");
    expect(JSON.parse(outputs.matrix!)).toEqual({ include: [{ worker_assignment: 0 }, { worker_assignment: 1 }] });
    expect(() => createExecutionOutputs({ ...response, selected_count: 2 }, fixture.inputs.registrations)).toThrow();
    expect(() => createExecutionOutputs({ ...response, assignments: response.assignments.map(article =>
      ({ ...article, worker_assignment: 2 })) }, fixture.inputs.registrations)).toThrow();
    await expect(verifyPlanningCompletion(fixture.inputs.outputRoot, { ...response, duration_ms: response.duration_ms! + 1 },
      fixture.inputs.registrations, fixture.directory)).rejects.toThrow("native run outcome");
    const selected = response.files.selected_articles!;
    if (selected.status !== "written") throw new Error("The recorded selection must have actual metadata");
    expect(() => createExecutionOutputs({ ...response, files: { ...response.files, selected_articles: {
      ...selected, files: selected.files.map(file => ({ ...file, path: "../private\ninjected=true" })),
    } } }, fixture.inputs.registrations)).toThrow();
  } finally { await fixture.close(); }
});

test("refuses mismatched counts, damaged bytes and missing actual files", async () => {
  const fixture = await recordedPlan();
  try {
    const result = await runFeedPlan({}, fixture.inputs, fixture.runtime);
    const selected = result.files.selected_articles!;
    if (selected.status !== "written") throw new Error("The recorded selection must have actual metadata");
    const registration = fixture.inputs.registrations.selected_articles;
    expect((await verifyParquetFiles(fixture.inputs.outputRoot, "selected-articles", selected, registration)).row_count).toBe(result.row.selected_count);
    await expect(verifyParquetFiles(fixture.inputs.outputRoot, "selected-articles", {
      ...selected, files: selected.files.map(file => ({ ...file, row_count: file.row_count + 1 })),
    }, registration)).rejects.toThrow("readback");
    const path = join(fixture.inputs.outputRoot, selected.files[0]!.path);
    const bytes = await readFile(path);
    await writeFile(path, bytes.subarray(0, 12));
    await expect(verifyParquetFiles(fixture.inputs.outputRoot, "selected-articles", selected, registration)).rejects.toThrow();
    await rm(path);
    await expect(verifyParquetFiles(fixture.inputs.outputRoot, "selected-articles", selected, registration)).rejects.toMatchObject({ code: "ENOENT" });
  } finally { await fixture.close(); }
});

test("zero selections have an explicit empty ledger and an actual empty artifact", async () => {
  const fixture = await recordedPlan([source({ url: "https://news.example/empty.xml" })]);
  try {
    const response = await main(["--cli", "--partition-strategy=none"], { inputs: fixture.inputs, runtime: fixture.runtime, output: () => {} });
    if (!("files" in response)) throw new Error("Expected the awaited CLI result");
    expect(response.planning_complete).toBe(true);
    expect(response.selected_count).toBe(0);
    expect(response.files.selected_articles).toEqual({ status: "empty", files: [] });
    expect(response.files.plan_runs!.status).toBe("written");
    const verified = await verifyPlanningCompletion(fixture.inputs.outputRoot, response, fixture.inputs.registrations, fixture.directory);
    expect(verified["selected-articles"]!.row_count).toBe(0);
    const artifact = SelectedArticlesArtifactSchema.parse(JSON.parse(await readFile(join(fixture.directory, response.selected_articles_artifact!), "utf8")));
    expect(artifact.articles).toEqual([]);
    await expect(verifyParquetFiles(fixture.inputs.outputRoot, "selected-articles",
      { status: "written", files: [] }, fixture.inputs.registrations.selected_articles)).rejects.toThrow();
  } finally { await fixture.close(); }
});

test("writes GitHub output records with noncolliding delimiters and refuses key injection", async () => {
  const root = await mkdtemp(join(tmpdir(), "feed-outputs-"));
  try {
    const path = join(root, "outputs");
    await writeGitHubOutputs(path, { status: "partial", matrix: "first\r\ninjected=true\nEOF" });
    const text = await readFile(path, "utf8");
    const lines = text.split("\n");
    const headers = lines.filter(line => /^[a-z_]+<<output_[a-f0-9]+$/.test(line));
    expect(headers).toHaveLength(2);
    for (const header of headers) expect(lines.filter(line => line === header.split("<<")[1])).toHaveLength(1);
    expect(text).not.toContain("\r");
    await expect(writeGitHubOutputs(path, { "bad\nkey": "value" })).rejects.toThrow("key");
    expect(await readFile(path, "utf8")).toBe(text);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("checks current planner formats and unchanged generic identity and canonical-byte vectors", async () => {
  const verified = await verifyRecordedCompatibility();
  expect(verified).toMatchObject({ status: "verified", planner_row_count: 4 });
  expect(verified.legacy_seen_row_count).toBeGreaterThan(0);
});
