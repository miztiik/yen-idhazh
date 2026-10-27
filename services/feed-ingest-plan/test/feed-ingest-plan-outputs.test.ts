/** Do actual HTTP results, native files and selected artifacts survive the isolated handoff? */
import { expect, test } from "bun:test";
import { copyFile, mkdir, mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { SelectedArticlesArtifactSchema } from "../../../packages/common-contracts/src/index";
import { runFeedPlan, summarizePlan } from "../src/run-feed-plan";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";
import { main } from "../src/index";
import { executeFeedHealthState } from "../src/api/feed-health-state-operation";
import { invokePlannerHttp } from "../scripts/feed-ingest-plan-http-proof";
import { commitPlannerFiles } from "../scripts/feed-ingest-plan-commit";
import { verifyParquetFiles, verifyPlanningCompletion } from "../scripts/feed-ingest-plan-verification";
import { createExecutionOutputs, writeGitHubOutputs } from "../scripts/feed-ingest-plan-outputs";
import { formatExecutionOutcome, formatExecutionReport, readExecutionReport, writePlannerReport } from "../scripts/feed-ingest-plan-report";
import { prepareWorkflowArtifacts } from "../scripts/feed-ingest-plan-artifacts";
import { observeWorkflowResources, WorkflowResourcesSchema } from "../scripts/feed-ingest-plan-workflow-resources";
import { escapeMarkdown } from "../scripts/feed-ingest-plan-report-format";
import { hostWriter } from "../scripts/feed-ingest-plan-metadata";
import { metadataRegistrations } from "./host-recordings";

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
    const publication = { identity: { run_id: "2026-10-21-700", attempt: 1, git_sha: fixture.runtime.git_sha },
      registrations: await metadataRegistrations() };
    fixture.inputs.settings.listener.port = 0;
    const directory = join(fixture.directory, "evidence");
    const resourceConfig = join(fixture.directory, "resource-config");
    await mkdir(join(resourceConfig, "config"), { recursive: true });
    const settings = await Bun.file(new URL("../../../config/idhazh.json", import.meta.url)).json();
    await writeFile(join(resourceConfig, "config", "idhazh.json"), JSON.stringify({ ...settings,
      observability: { ...settings.observability, host_fingerprint: false, host_fingerprint_placement_enabled: false } }));
    await writeFile(join(resourceConfig, "config", "host-probes.json"),
      await Bun.file(new URL("../../../config/host-probes.json", import.meta.url)).text());
    await mkdir(directory, { recursive: true });
    const closeResources = await observeWorkflowResources({
      root: resourceConfig, directory, stateRoot: join(directory, "state"), profileRequested: true, gitSha: fixture.runtime.git_sha, attempt: 1,
      identity: { pipeline_name: "feed-ingest-plan", task_name: "planner-http-request",
        run_id: "2026-10-21-700", correlation_id: fixture.runtime.correlation_id!, request_id: crypto.randomUUID() },
    });
    let result: Awaited<ReturnType<typeof invokePlannerHttp>>;
    let outcome: "success" | "error" = "error";
    try {
      result = await invokePlannerHttp(fixture.inputs, fixture.runtime, { article_limit: 1 }, directory);
      if (result.summary.planning_complete) outcome = "success";
    } finally { await closeResources.close(outcome); }
    const resources = WorkflowResourcesSchema.parse(await Bun.file(join(directory, "resources.json")).json());
    expect(resources.host.status).toBe("disabled");
    expect(resources.profile.status).toBe("recorded");
    if (resources.profile.status !== "recorded") throw new Error("The real optional planner profile must close");
    expect(resources.profile.value.identity.task_name).toBe("planner-http-request");
    expect(resources.profile.value.processes.server.closing.pid).toBeNull();
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
    await writeFile(join(directory, "runtime.log"), fixture.events.map(event => JSON.stringify(event)).join("\n"));
    const retained = await prepareWorkflowArtifacts({ root: fixture.directory, directory, runNumber: "700", attempt: 1, ...publication });
    expect(retained.selected).toBe("artifacts/700-1-selected-articles.json");
    expect(SelectedArticlesArtifactSchema.parse(await Bun.file(join(directory, retained.selected!)).json())).toEqual(artifact);
    const recovery = join(directory, retained.metadata_recovery!);
    expect(await Bun.file(join(recovery, "current-run-files.json")).json()).toEqual(paths);
    for (const path of paths) expect(await readFile(join(recovery, path))).toEqual(await readFile(join(fixture.inputs.outputRoot, path)));
    const log = await Bun.file(join(directory, retained.runtime_log!)).text();
    expect(log).not.toContain(artifact.articles[0]!.article_text);
    expect(log).not.toContain("article_text");
    await writeFile(join(directory, "commit-result.json"), JSON.stringify({ status: "landed", commit: "a".repeat(40), files: paths.length, paths }));
    const confirmed = await prepareWorkflowArtifacts({ root: fixture.directory, directory, runNumber: "700", attempt: 2, ...publication });
    expect(confirmed.metadata_recovery).toBeUndefined();
    expect(confirmed.selected).toBe("artifacts/700-2-selected-articles.json");
    expect(confirmed.selected).not.toBe(retained.selected);
    await expect(prepareWorkflowArtifacts({ root: fixture.directory, directory, runNumber: "../injected", attempt: 1, ...publication })).rejects.toThrow();
    await writeFile(join(directory, "response.json"), "invalid JSON");
    const published = join(directory, "artifact-outputs");
    await expect(prepareWorkflowArtifacts({ root: fixture.directory, directory, runNumber: "700", attempt: 3,
      outputPath: published, ...publication })).rejects.toThrow();
    expect(await readFile(published, "utf8")).toContain("runtime_log<<");
  } finally { await fixture.close(); }
});

test("exact metadata appends through a generated bare origin without raw indexes and with safe replay", async () => {
  const fixture = await recordedPlan([source({ url: "https://news.example/empty.xml" })]);
  try {
    fixture.inputs.outputRoot = join(fixture.directory, "feed-ingest-plan", "state");
    const summary = summarizePlan(await runFeedPlan({}, fixture.inputs, fixture.runtime));
    await writeFile(join(fixture.directory, "feed-ingest-plan", "response.json"), JSON.stringify(summary));
    const paths: string[] = JSON.parse(createExecutionOutputs(summary, fixture.inputs.registrations).current_run_files!);
    const repository = join(fixture.directory, "checkout");
    const origin = join(fixture.directory, "origin.git");
    await mkdir(repository);
    await git(fixture.directory, ["init", "--bare", "--initial-branch=main", origin]);
    await git(repository, ["init", "--initial-branch=main"]);
    await writeFile(join(repository, "README.md"), "Generated bounded fixture.\n");
    const retry = await Bun.file(new URL("../../../config/push-retry.json", import.meta.url)).json();
    await mkdir(join(repository, "config"));
    await writeFile(join(repository, "config", "push-retry.json"), JSON.stringify(retry));
    for (const name of ["ledgers.json", "feed-ingest-plan-service.json"]) {
      await writeFile(join(repository, "config", name), await Bun.file(new URL(`../../../config/${name}`, import.meta.url)).text());
    }
    await git(repository, ["add", "--", "README.md", "config/push-retry.json", "config/ledgers.json", "config/feed-ingest-plan-service.json"]);
    await git(repository, ["commit", "-m", "Create generated fixture"]);
    await git(repository, ["remote", "add", "origin", origin]);
    await git(repository, ["push", "origin", "HEAD:refs/heads/main"]);
    const head = await git(repository, ["rev-parse", "HEAD"]);
    const publication = { identity: { run_id: summary.run_id, attempt: summary.attempt, git_sha: head },
      registrations: await metadataRegistrations() };
    if (summary.selected_articles_artifact !== null) {
      const artifact = join(repository, summary.selected_articles_artifact);
      await mkdir(dirname(artifact), { recursive: true });
      await copyFile(join(fixture.directory, summary.selected_articles_artifact), artifact);
    }
    await writeFile(join(fixture.directory, "feed-ingest-plan", "resources.json"), JSON.stringify(WorkflowResourcesSchema.parse({
      host_request: { date: summary.date, writer: hostWriter(publication.identity) }, profile_requested: false,
      host: { status: "disabled", reason: "observability.host_fingerprint=false" },
      profile: { status: "disabled", reason: "profile_machine_memory=false" },
    })));
    const statusBefore = await git(repository, ["status", "--porcelain"]);
    async function invokeCommit() {
      const child = Bun.spawn([process.execPath, fileURLToPath(new URL("../scripts/feed-ingest-plan-commit.ts", import.meta.url))], {
        cwd: repository, stdout: "pipe", stderr: "pipe", timeout: 120000,
        env: { ...Bun.env, RUNNER_TEMP: fixture.directory, CURRENT_RUN_FILES: JSON.stringify(paths),
          GITHUB_RUN_ID: "700", GITHUB_RUN_ATTEMPT: "1" },
      });
      const [output, errors] = await Promise.all([new Response(child.stdout).text(), new Response(child.stderr).text()]);
      expect({ code: await child.exited, errors }).toEqual({ code: 0, errors: "" });
      const result: { status: string; commit: string; files: number } = JSON.parse(output);
      expect(JSON.parse(await readFile(join(fixture.directory, "feed-ingest-plan", "commit-result.json"), "utf8"))).toEqual(result);
      return result;
    }
    const committed = await invokeCommit();
    expect(committed.status).toBe("landed");
    expect(committed.commit).toBe(await git(fixture.directory, ["--git-dir", origin, "rev-parse", "main"]));
    expect(await git(repository, ["rev-parse", "HEAD"])).toBe(head);
    expect(await git(repository, ["status", "--porcelain"])).toBe(statusBefore);
    const indexes = [...new Set(paths.map(path => `state/${path.slice(0, path.lastIndexOf("/"))}/index.json`))];
    // This tree was just built by this case; it cannot grow with repository history.
    const members = (await git(fixture.directory, ["--git-dir", origin, "ls-tree", "-r", "--name-only", "main"])).split("\n");
    expect(members.sort()).toEqual(["README.md", "config/push-retry.json", "config/ledgers.json", "config/feed-ingest-plan-service.json",
      ...paths.map(path => `state/${path}`)].sort());
    for (const path of indexes) {
      expect(await git(fixture.directory, ["--git-dir", origin, "ls-tree", "main", "--", path])).toBe("");
    }
    expect((await invokeCommit()).status).toBe("already-on-main");
    await expect(commitPlannerFiles({ repository, stateRoot: fixture.inputs.outputRoot, retry, message: "Refuse old format",
      paths: ["raw/feed-ingest-plan/dispatches/2026/10/21/anything.parquet"], ...publication })).rejects.toThrow("current planner");
    await writeFile(join(repository, "config", "push-retry.json"), "{}");
    const failed = Bun.spawn([process.execPath, fileURLToPath(new URL("../scripts/feed-ingest-plan-commit.ts", import.meta.url))], {
      cwd: repository, stdout: "pipe", stderr: "pipe",
      env: { ...Bun.env, RUNNER_TEMP: fixture.directory, CURRENT_RUN_FILES: JSON.stringify(paths),
        GITHUB_RUN_ID: "700", GITHUB_RUN_ATTEMPT: "1" },
    });
    const [failedOutput, failedErrors, exit] = await Promise.all([
      new Response(failed.stdout).text(), new Response(failed.stderr).text(), failed.exited,
    ]);
    expect(exit).toBe(2);
    expect(failedOutput).toBe("");
    expect(JSON.parse(failedErrors)).toMatchObject({ event: "planner_metadata_commit_failed", status: "failed",
      reason: "push retry requires deadline_seconds.default" });
    expect(await Bun.file(join(fixture.directory, "feed-ingest-plan", "commit-result.json")).json())
      .toEqual({ status: "failed", commit: null, files: paths.length, paths });
    const recovered = await prepareWorkflowArtifacts({ root: fixture.directory, directory: join(fixture.directory, "feed-ingest-plan"),
      runNumber: "700", attempt: 3, ...publication });
    expect(recovered.metadata_recovery).toBeDefined();
    for (const path of paths) expect(await readFile(join(fixture.inputs.outputRoot, path))).toBeInstanceOf(Buffer);
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
    const evidence = { response, health, historyStagingMs: 3, policy: {
      config: fixture.inputs.harvest.config, request: {}, history: fixture.inputs.clock_config.collect,
      parser_concurrency: fixture.inputs.settings.listener.parser_concurrency,
    } };
    const summary = join(fixture.directory, "summary.md");
    const annotations: string[] = [];
    await writePlannerReport({ config: { ...fixture.inputs.harvest.config, workflow_reporting: {
      ...fixture.inputs.harvest.config.workflow_reporting, enabled: false,
    } }, summary_path: summary, annotate: line => annotations.push(line) });
    await expect(stat(summary)).rejects.toMatchObject({ code: "ENOENT" });
    await writePlannerReport({ config: fixture.inputs.harvest.config, evidence, summary_path: summary,
      annotate: line => annotations.push(line) });
    expect(await readFile(summary, "utf8")).toBe(formatExecutionReport(evidence));
    expect(annotations).toEqual([...formatExecutionOutcome(evidence).annotations]);
    expect(annotations.map(line => line.slice(0, line.indexOf("::", 2)))).toEqual([
      "::notice title=Resources", "::notice title=This run's feed work", "::notice title=Closed-day request spend",
      "::notice title=Grouped exclusions", "::notice title=Policy used",
    ]);
    const rendered = Bun.markdown.html(await readFile(summary, "utf8"));
    expect(rendered).toContain("Feed health before requests");
    expect(rendered).toContain("Fresh feed health for selection");
    const legacyTiming = formatExecutionReport({ ...evidence, response: {
      ...response, api_timings: response.api_timings.map(timing => ({
        ...timing, operation: timing.operation.startsWith("feed-health-") ? "feed-health-summary" : timing.operation,
      })),
    } });
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
      const cell = formatExecutionReport(evidence).split("\n").find(line => line.startsWith(`| C${index + 1} |`));
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
      expect(formatExecutionReport(missing)).toContain(escapeMarkdown(description));
    }
    const changed = { ...evidence, health: { ...health, rows: [{ ...firstHealth, rejection_counts: [
      ...firstHealth.rejection_counts, { reason_code: reason, count: 1, subject: "article", stage: "harvest-feeds", attribution: null },
      { reason_code: "HOSTILE\r\n::error title=unsafe::% <script>", count: 1, subject: "article", stage: "harvest-feeds", attribution: null },
    ] }] } };
    const escaped = formatExecutionOutcome(changed);
    expect(escaped.summary).toContain("It does not mean a feed configuration field is missing.");
    expect(escaped.annotations[3]).toContain("which field failed");
    expect(escaped.annotations.every(line => !line.includes("\n") && !line.includes("\r"))).toBe(true);
    expect(escaped.annotations[3]).toContain("%0A");
    expect(Bun.markdown.html(escaped.summary)).not.toContain("<script>");
    const directory = join(fixture.directory, "evidence");
    await mkdir(directory);
    await writeFile(join(directory, "response.json"), JSON.stringify(response));
    await writeFile(join(directory, "health.json"), JSON.stringify(health));
    await writeFile(join(directory, "history-staging-ms.json"), "3");
    await writeFile(join(directory, "workflow-policy.json"), JSON.stringify(evidence.policy));
    expect(await readExecutionReport(directory)).toBe(formatExecutionReport(evidence));
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
