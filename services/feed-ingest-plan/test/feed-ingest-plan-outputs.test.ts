/** Do captured native files, selected text and output validation survive the isolated handoff? */
import { expect, test } from "bun:test";
import { mkdir, mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { SelectedArticleRowContract, SelectedArticlesArtifactSchema } from "@idhazh/common-contracts";
import { verifyParquetFiles, verifyPlanningCompletion } from "../scripts/feed-ingest-plan-verification";
import { createExecutionOutputs, writeGitHubOutputs } from "../scripts/feed-ingest-plan-outputs";
import { readExecutionReport, renderWorkflowPlanMarkdown, writePlannerReport } from "../scripts/feed-ingest-plan-report";
import { prepareWorkflowArtifacts } from "../scripts/feed-ingest-plan-artifacts";
import { formatWorkflowAnnotation } from "../scripts/feed-ingest-plan-report-format";
import { renderPlanMarkdown } from "@idhazh/feed-ingest-plan/markdown";
import { metadataRegistrations } from "./host-recordings";
import { plannerOutputRecording } from "./planner-output-recordings";
import { recordedPlan } from "./plan-recordings";
import { recordedPersistenceBatch } from "./persistence-recordings";
import { executePersistence } from "../src/api/persistence-operation";
import { writeRows } from "./partition-fixtures";

test("captured native output retains selected text separately from its strict metadata manifest", async () => {
  const fixture = await plannerOutputRecording();
  try {
    const { response: summary, outputs, health, artifact } = fixture;
    const directory = join(fixture.directory, "evidence");
    await mkdir(directory);
    await writeFile(join(directory, "response.json"), JSON.stringify(summary));
    const paths: string[] = JSON.parse(outputs.current_run_files!);
    expect(paths).toEqual(Object.values(summary.files).flatMap(result => result?.files.map(file => file.path) ?? []));
    expect(paths.every(path => path.endsWith(".parquet"))).toBe(true);
    expect(artifact.articles[0]!.article_text.length).toBeGreaterThan(0);
    for (const evidence of [JSON.stringify(summary), JSON.stringify(outputs), JSON.stringify(health)]) {
      expect(evidence).not.toContain("article_text");
      expect(evidence).not.toContain(artifact.articles[0]!.article_text);
    }
    await mkdir(join(directory, "state"), { recursive: true });
    for (const path of paths) {
      const target = join(directory, "state", path);
      await mkdir(join(target, ".."), { recursive: true });
      await writeFile(target, await readFile(join(fixture.inputs.outputRoot, path)));
    }
    const deliveryContext = {
      identity: { run_id: summary.run_id, attempt: summary.attempt, git_sha: "a".repeat(40) },
      registrations: await metadataRegistrations(),
    };
    const retained = await prepareWorkflowArtifacts({ root: fixture.directory, directory, runNumber: "700", attempt: 3, ...deliveryContext });
    expect(SelectedArticlesArtifactSchema.parse(await Bun.file(join(directory, retained.selected!)).json())).toEqual(artifact);
    const recovery = join(directory, retained.metadata_recovery!);
    expect(await Bun.file(join(recovery, "current-run-files.json")).json()).toEqual(paths);
    for (const path of paths) expect(await readFile(join(recovery, path))).toEqual(await readFile(join(fixture.inputs.outputRoot, path)));
    await writeFile(join(directory, "delivery-result.json"), JSON.stringify({
      status: "landed", commit: "a".repeat(40), files: paths.length, paths,
    }));
    const confirmed = await prepareWorkflowArtifacts({ root: fixture.directory, directory, runNumber: "700", attempt: 4, ...deliveryContext });
    expect(confirmed.metadata_recovery).toBeUndefined();
    expect(confirmed.selected).not.toBe(retained.selected);
    await expect(prepareWorkflowArtifacts({ root: fixture.directory, directory, runNumber: "../injected", attempt: 3, ...deliveryContext })).rejects.toThrow();
    await writeFile(join(directory, "response.json"), "invalid JSON");
    const published = join(directory, "artifact-outputs");
    await expect(prepareWorkflowArtifacts({ root: fixture.directory, directory, runNumber: "700", attempt: 5,
      outputPath: published, ...deliveryContext })).rejects.toThrow();
    expect(await readFile(published, "utf8")).toContain("delivery<<");
  } finally { await fixture.close(); }
});

test("both report modes leave the recorded result and every native file unchanged", async () => {
  const fixture = await plannerOutputRecording();
  try {
    const { response, health } = fixture;
    const before = structuredClone({ response, health });
    const paths: string[] = JSON.parse(fixture.outputs.current_run_files!);
    const bytes = await Promise.all(paths.map(path => readFile(join(fixture.inputs.outputRoot, path))));
    const evidence = { response, health, policy: {
      config: fixture.inputs.harvest.config, request: {}, history: fixture.inputs.clock_config.collect,
      parser_concurrency: fixture.inputs.settings.listener.parser_concurrency,
    } };
    expect(renderPlanMarkdown({ response, health }).markdown).toContain("# Feed planner run");
    const summary = join(fixture.directory, "summary.md");
    const annotations: string[] = [];
    await writePlannerReport({ config: { ...fixture.inputs.harvest.config, workflow_reporting: {
      ...fixture.inputs.harvest.config.workflow_reporting, enabled: false,
    } }, summary_path: summary, annotate: line => annotations.push(line) });
    await expect(stat(summary)).rejects.toMatchObject({ code: "ENOENT" });
    await writePlannerReport({ config: fixture.inputs.harvest.config, evidence, summary_path: summary,
      annotate: line => annotations.push(line) });
    const report = renderWorkflowPlanMarkdown(evidence);
    expect(await readFile(summary, "utf8")).toBe(report.markdown);
    expect(annotations).toEqual(report.notices.map(formatWorkflowAnnotation));
    const directory = fixture.directory;
    await writeFile(join(directory, "response.json"), JSON.stringify(response));
    await writeFile(join(directory, "health.json"), JSON.stringify(health));
    await writeFile(join(directory, "workflow-policy.json"), JSON.stringify(evidence.policy));
    expect(await readExecutionReport(directory)).toBe(report.markdown);
    expect({ response, health }).toEqual(before);
    for (const [index, path] of paths.entries()) expect(await readFile(join(fixture.inputs.outputRoot, path))).toEqual(bytes[index]!);
    await verifyPlanningCompletion(fixture.inputs.outputRoot, response, fixture.inputs.registrations, fixture.directory);
  } finally { await fixture.close(); }
});

test("recorded identities reject inconsistent counts, assignments and foreign paths", async () => {
  const fixture = await plannerOutputRecording();
  try {
    const response = fixture.response;
    const outputs = createExecutionOutputs(response, fixture.inputs.registrations);
    expect(JSON.parse(outputs.matrix!).include).toHaveLength(response.dispatch_count);
    expect(() => createExecutionOutputs({ ...response, selected_count: response.selected_count + 1 }, fixture.inputs.registrations)).toThrow();
    expect(() => createExecutionOutputs({ ...response, assignments: response.assignments.map(article =>
      ({ ...article, worker_assignment: response.dispatch_count })) }, fixture.inputs.registrations)).toThrow();
    await expect(verifyPlanningCompletion(fixture.inputs.outputRoot, { ...response, duration_ms: response.duration_ms! + 1 },
      fixture.inputs.registrations, fixture.directory)).rejects.toThrow("native run outcome");
    const selected = response.files.selected_articles!;
    expect(() => createExecutionOutputs({ ...response, files: { ...response.files, selected_articles: {
      ...selected, files: selected.files.map(file => ({ ...file, path: "../private\ninjected=true" })),
    } } }, fixture.inputs.registrations)).toThrow();
  } finally { await fixture.close(); }
});

test("native readback refuses mismatched counts, damaged bytes and missing files", async () => {
  const fixture = await recordedPlan();
  try {
    const rows = SelectedArticleRowContract.schema.array().parse(await Bun.file(new URL(
      "../../../tests/fixtures/feed-ingest-plan/entry-points/selected-articles.rows.json", import.meta.url)).json());
    const selected = await writeRows(fixture.inputs.outputRoot, "selected-articles", rows[0]!.date, SelectedArticleRowContract, rows);
    if (selected.status !== "written" || selected.files.length !== 1) throw new Error("This check requires one genuine selected native file");
    const registration = fixture.inputs.registrations.selected_articles;
    expect((await verifyParquetFiles(fixture.inputs.outputRoot, "selected-articles", selected, registration)).row_count)
      .toBe(rows.length);
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

test("empty persistence produces an explicit empty ledger and an actual empty artifact", async () => {
  const fixture = await recordedPlan();
  try {
    const batch = await recordedPersistenceBatch(fixture.inputs, fixture.runtime, { empty: true });
    const result = await executePersistence({ batch_id: batch.batch_id }, fixture.inputs, fixture.runtime);
    expect(result.selected_count).toBe(0);
    expect(result.files).toEqual({ status: "empty", files: [] });
    const artifact = SelectedArticlesArtifactSchema.parse(await Bun.file(join(fixture.directory, result.artifact)).json());
    expect(artifact.articles).toEqual([]);
    expect((await verifyParquetFiles(fixture.inputs.outputRoot, "selected-articles", result.files,
      fixture.inputs.registrations.selected_articles)).row_count).toBe(0);
    await expect(verifyParquetFiles(fixture.inputs.outputRoot, "selected-articles",
      { status: "written", files: [] }, fixture.inputs.registrations.selected_articles)).rejects.toThrow();
  } finally { await fixture.close(); }
});

test("writes output records with noncolliding delimiters and refuses key injection", async () => {
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
