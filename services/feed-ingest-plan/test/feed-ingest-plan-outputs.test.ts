/** Do actual HTTP results, native files and selected artifacts survive the isolated handoff? */
import { expect, test } from "bun:test";
import { mkdir, mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";
import { SelectedArticlesArtifactSchema } from "../../../packages/common-contracts/src/index";
import { runFeedPlan, summarizePlan } from "../src/run-feed-plan";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";
import { main } from "../src/index";
import { executeFeedHealthState } from "../src/api/feed-health-state-operation";
import { invokePlannerHttp } from "../scripts/run-feed-ingest-plan";
import { verifyParquetFiles, verifyPlanningCompletion } from "../scripts/feed-ingest-plan-verification";
import { createExecutionOutputs, writeGitHubOutputs } from "../scripts/feed-ingest-plan-outputs";
import { readExecutionReport, renderWorkflowPlanMarkdown, writePlannerReport } from "../scripts/feed-ingest-plan-report";
import { prepareWorkflowArtifacts } from "../scripts/feed-ingest-plan-artifacts";
import { captureWorkflowHostFingerprint, WorkflowHostFingerprintSchema } from "../scripts/feed-ingest-plan-host-fingerprint";
import { formatWorkflowAnnotation } from "../scripts/feed-ingest-plan-report-format";
import { escapeMarkdown } from "../src/reporting/markdown-format";
import { renderPlanMarkdown } from "@idhazh/feed-ingest-plan/markdown";
import { metadataRegistrations } from "./host-recordings";

test("actual HTTP output retains selected text separately from its strict metadata manifest", async () => {
  const fixture = await recordedPlan();
  try {
    const deliveryContext = { identity: { run_id: "2026-10-21-700", attempt: 1, git_sha: fixture.runtime.git_sha },
      registrations: await metadataRegistrations() };
    fixture.inputs.settings.listener.port = 0;
    const directory = join(fixture.directory, "evidence");
    const resourceConfig = join(fixture.directory, "resource-config");
    await mkdir(join(resourceConfig, "config"), { recursive: true });
    const settings = await Bun.file(new URL("../../../config/idhazh.json", import.meta.url)).json();
    await writeFile(join(resourceConfig, "config", "idhazh.json"), JSON.stringify({ ...settings,
      observability: { ...settings.observability, host_fingerprint: false, host_fingerprint_placement_enabled: false } }));
    await mkdir(directory, { recursive: true });
    const host = await captureWorkflowHostFingerprint({
      root: resourceConfig, directory, stateRoot: join(directory, "state"),
      registryPath: join(resourceConfig, "config", "ledgers.json"),
      identity: { run_id: "2026-10-21-700", attempt: 1, git_sha: fixture.runtime.git_sha },
      registrations: await metadataRegistrations(),
    });
    const savedHost = WorkflowHostFingerprintSchema.parse(await Bun.file(join(directory, "host-fingerprint.json")).json());
    expect(host.host.status).toBe("disabled");
    expect(savedHost).toEqual(host);
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
    await mkdir(join(directory, "state"), { recursive: true });
    for (const path of paths) {
      await mkdir(dirname(join(directory, "state", path)), { recursive: true });
      await Bun.write(join(directory, "state", path), await readFile(join(fixture.inputs.outputRoot, path)));
    }
    const retained = await prepareWorkflowArtifacts({ root: fixture.directory, directory, runNumber: "700", attempt: 1, ...deliveryContext });
    expect(retained.selected).toBe("artifacts/700-1-selected-articles.json");
    expect(SelectedArticlesArtifactSchema.parse(await Bun.file(join(directory, retained.selected!)).json())).toEqual(artifact);
    const recovery = join(directory, retained.metadata_recovery!);
    expect(await Bun.file(join(recovery, "current-run-files.json")).json()).toEqual(paths);
    for (const path of paths) expect(await readFile(join(recovery, path))).toEqual(await readFile(join(fixture.inputs.outputRoot, path)));
    await writeFile(join(directory, "delivery-result.json"), JSON.stringify({ status: "landed", commit: "a".repeat(40), files: paths.length, paths }));
    const confirmed = await prepareWorkflowArtifacts({ root: fixture.directory, directory, runNumber: "700", attempt: 2, ...deliveryContext });
    expect(confirmed.metadata_recovery).toBeUndefined();
    expect(confirmed.selected).toBe("artifacts/700-2-selected-articles.json");
    expect(confirmed.selected).not.toBe(retained.selected);
    await expect(prepareWorkflowArtifacts({ root: fixture.directory, directory, runNumber: "../injected", attempt: 1, ...deliveryContext })).rejects.toThrow();
    await writeFile(join(directory, "response.json"), "invalid JSON");
    const published = join(directory, "artifact-outputs");
    await expect(prepareWorkflowArtifacts({ root: fixture.directory, directory, runNumber: "700", attempt: 3,
      outputPath: published, ...deliveryContext })).rejects.toThrow();
    expect(await readFile(published, "utf8")).toContain("delivery<<");
  } finally { await fixture.close(); }
});

test("one real result and every native file stay unchanged through both report modes", async () => {
  const fixture = await recordedPlan([
    source(),
    source({ id: "recorded-empty", url: "https://news.example/empty.xml" }),
    source({ id: "recorded-malformed", url: "https://news.example/malformed.xml" }),
  ]);
  try {
    const result = await runFeedPlan({}, fixture.inputs, fixture.runtime);
    const response = summarizePlan(result);
    const health = await executeFeedHealthState({ batch_id: response.batches.selection_batch_id, action: "summarize" },
      fixture.inputs, fixture.runtime);
    const healthBefore = JSON.stringify(health);
    const outputs = createExecutionOutputs(response, fixture.inputs.registrations);
    const paths: string[] = JSON.parse(outputs.current_run_files!);
    const bytes = await Promise.all(paths.map(path => readFile(join(fixture.inputs.outputRoot, path))));
    const evidence = { response, health, policy: {
      config: fixture.inputs.harvest.config, request: {}, history: fixture.inputs.clock_config.collect,
      parser_concurrency: fixture.inputs.settings.listener.parser_concurrency,
    } };
    const markdownApi = renderPlanMarkdown({ response, health });
    expect(markdownApi.markdown).toContain("# Feed planner run");
    expect(markdownApi.notices.some(notice => notice.title === "This run's feed work")).toBe(true);
    const summary = join(fixture.directory, "summary.md");
    const annotations: string[] = [];
    await writePlannerReport({ config: { ...fixture.inputs.harvest.config, workflow_reporting: {
      ...fixture.inputs.harvest.config.workflow_reporting, enabled: false,
    } }, summary_path: summary, annotate: line => annotations.push(line) });
    await expect(stat(summary)).rejects.toMatchObject({ code: "ENOENT" });
    await writePlannerReport({ config: fixture.inputs.harvest.config, evidence, summary_path: summary,
      annotate: line => annotations.push(line) });
    const workflowReport = renderWorkflowPlanMarkdown(evidence);
    expect(await readFile(summary, "utf8")).toBe(workflowReport.markdown);
    expect(annotations).toEqual(workflowReport.notices.map(formatWorkflowAnnotation));
    expect(annotations.map(line => line.slice(0, line.indexOf("::", 2)))).toEqual([
      "::notice title=Host fingerprint", "::notice title=This run's feed work", "::notice title=Closed-day request spend",
      "::notice title=Grouped exclusions", "::notice title=Policy used",
    ]);
    const rendered = Bun.markdown.html(await readFile(summary, "utf8"));
    expect(rendered).toContain("Feed health before requests");
    expect(rendered).toContain("Fresh feed health for selection");
    const legacyTiming = renderWorkflowPlanMarkdown({ ...evidence, response: {
      ...response, api_timings: response.api_timings.map(timing => ({
        ...timing, operation: timing.operation.startsWith("feed-health-") ? "feed-health-summary" : timing.operation,
      })),
    } }).markdown;
    expect(legacyTiming).toContain("Legacy feed-health capture (purpose not recorded)");
    expect(legacyTiming).not.toContain("| Feed health before requests |");
    expect(legacyTiming).not.toContain("| Fresh feed health for selection |");
    expect((rendered.match(/<table>/g) ?? [])).toHaveLength(7);
    expect(rendered).toContain("<th>Feed read result</th>");
    expect(rendered).not.toContain("<th>Outcome</th>");
    for (const [feedId, code, description] of [
      ["recorded-empty", "FEED_EMPTY", "No usable feed URLs"],
      ["recorded-malformed", "FEED_PARSE_FAILED", "Feed parsing failed"],
    ] as const) {
      const index = health.rows.findIndex(row => row.feed_id === feedId);
      expect(index).toBeGreaterThanOrEqual(0);
      expect(health.rows[index]).toMatchObject({
        status: 200, outcome: "ok", items: 0, failed_reads: 1, last_failure_code: code,
      });
      const cell = workflowReport.markdown.split("\n").find(line => line.startsWith(`| C${index + 1} |`));
      expect(cell).toContain(`| ${description} |`);
    }
    expect(rendered).toContain("Feed read succeeded");
    for (const table of rendered.matchAll(/<table>[\s\S]*?<\/table>/g)) {
      const header = table[0].match(/<thead>[\s\S]*?<\/thead>/)?.[0] ?? "";
      const columns = (header.match(/<th>/g) ?? []).length;
      expect(columns).toBeGreaterThan(0);
      for (const row of table[0].matchAll(/<tr>([\s\S]*?)<\/tr>/g)) {
        const cells = (row[1]!.match(/<(?:th|td)>/g) ?? []).length;
        expect(cells).toBe(columns);
      }
    }
    const reason = "MISSING_REQUIRED_FIELDS";
    const firstHealth = health.rows[0]!;
    for (const [outcome, description] of [
      ["ok", "Download succeeded; parsing not recorded"],
      [null, "Unavailable (download outcome not recorded)"],
    ] as const) {
      const missing = { ...evidence, health: { ...health, rows: [{ ...firstHealth,
        outcome, items: null, last_failure_code: null,
      }] } };
      expect(renderWorkflowPlanMarkdown(missing).markdown).toContain(escapeMarkdown(description));
    }
    const changed = { ...evidence, health: { ...health, rows: [{ ...firstHealth, rejection_counts: [
      ...firstHealth.rejection_counts, { reason_code: reason, count: 1, subject: "article", stage: "harvest-feeds", attribution: null },
      { reason_code: "HOSTILE\r\n::error title=unsafe::% <script>", count: 1, subject: "article", stage: "harvest-feeds", attribution: null },
    ] }] } };
    const escaped = renderWorkflowPlanMarkdown(changed);
    expect(escaped.markdown).toContain("It does not mean a feed configuration field is missing.");
    expect(escaped.notices[3]!.message).toContain("which field failed");
    const annotation = formatWorkflowAnnotation(escaped.notices[3]!);
    expect(annotation).not.toContain("\n");
    expect(annotation).not.toContain("\r");
    expect(annotation).toContain("%0A");
    expect(Bun.markdown.html(escaped.markdown)).not.toContain("<script>");
    const directory = join(fixture.directory, "evidence");
    await mkdir(directory);
    await writeFile(join(directory, "response.json"), JSON.stringify(response));
    await writeFile(join(directory, "health.json"), JSON.stringify(health));
    await writeFile(join(directory, "workflow-policy.json"), JSON.stringify(evidence.policy));
    expect(await readExecutionReport(directory)).toBe(workflowReport.markdown);
    expect(JSON.stringify(health)).toBe(healthBefore);
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
