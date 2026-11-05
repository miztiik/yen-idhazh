/** Do verified native records explain exact article failures and paused feeds without changing their bytes? */
import { expect, test } from "bun:test";
import { copyFile, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseHTML } from "linkedom";
import {
  ArticleFailureDiagnosticDataSchema, ArticleFailureDiagnosticSchema, createCandidateId, createCloudEvent,
  createRootContext, FEED_INGEST_EVENT_VERSION, FeedHealthStateRowContract, FeedHealthStateRowSchema,
  HarvestDiagnosticsSchema, RejectedArticleRowContract, RejectedArticleRowSchema, writeTraceContext,
} from "@idhazh/common-contracts";
import { PLANNER_EVENT_SOURCE } from "../src/declare-event-source";
import type { RejectedArticleRow } from "@idhazh/common-contracts";
import { readExecutionEvidence, renderWorkflowPlanMarkdown, writeWorkflowReport } from "../scripts/feed-ingest-plan-report";
import { readReportFailureEvidence } from "../scripts/feed-ingest-plan-report-evidence";
import { renderPlanMarkdown } from "../src/reporting";
import { plannerOutputRecording } from "./planner-output-recordings";
import { writeRows } from "./partition-fixtures";
import { operationLink } from "../src/api/operation-context";
import { readArticleFailureDiagnostics } from "../scripts/read-article-failure-diagnostics";
import {
  readMachineServerEvidence as readServerEvidence, MachineServerEvidenceSchema as ServerEvidenceSchema,
} from "@idhazh/host-probes/machine-evidence";
import { serverLogFilename } from "@idhazh/serve-pipeline-apis/evidence";
import { describePlanError } from "../src/api/plan-failure";

function attention(markdown: string) {
  const { document } = parseHTML(Bun.markdown.html(markdown));
  const table = [...document.querySelectorAll("table")].find(node =>
    [...node.querySelectorAll("th")].some(header => header.textContent === "Feed or scope"))!;
  return [...table.querySelectorAll("tbody tr")]
    .map(row => [...row.querySelectorAll("td")].map(cell => cell.textContent!));
}

async function terminalRows(f: Awaited<ReturnType<typeof plannerOutputRecording>>) {
  const recorded = await Bun.file(new URL(
    "../../../tests/fixtures/feed-ingest-plan/article-terminal-failures.json", import.meta.url,
  )).json();
  const base = RejectedArticleRowSchema.array().parse(await Bun.file(new URL(
    "../../../tests/fixtures/feed-ingest-plan/entry-points/rejected-articles.rows.json", import.meta.url,
  )).json())[0]!;
  return ["forbidden", "dns"].map((name, index) => RejectedArticleRowSchema.parse({
    ...base, run_id: f.response.run_id, attempt: f.response.attempt,
    candidate_id: createCandidateId(), url_key: String(index + 1).repeat(64),
    stage: "harvest-feeds", reason_code: index === 0 ? "FETCH_FAILED_HTTP" : "FETCH_FAILED",
    freshness_cutoff_at: null,
    ...recorded.cases.find((entry: { name: string }) => entry.name === name).expected,
  }));
}

async function terminalDiagnostic(f: Awaited<ReturnType<typeof plannerOutputRecording>>, article: RejectedArticleRow) {
  return ArticleFailureDiagnosticSchema.parse(createCloudEvent({
    source: PLANNER_EVENT_SOURCE, type: "planner.progress", context: { ...createRootContext(), traceId: f.response.traceId },
    data: {
      version: FEED_INGEST_EVENT_VERSION, run_id: article.run_id, operation: "fetch", phase: "failed",
      details: {
        attempt: article.attempt, feed_id: article.feed_id, candidate_id: article.candidate_id,
        url_key: article.url_key, stage: "harvest-feeds", reason_code: article.reason_code,
        diagnostics: HarvestDiagnosticsSchema.parse({
          http_status: article.http_status, fetch_failure: article.fetch_failure, error_code: article.error_code,
          pacing_time_ms: article.pacing_time_ms, pacing_settings: article.pacing_settings,
          stopped_stage: "fetch", detail: article.fetch_failure,
        }),
      },
    }, parseData: value => ArticleFailureDiagnosticDataSchema.parse(value),
  }));
}

async function writeDiagnosticMirror(f: Awaited<ReturnType<typeof plannerOutputRecording>>, records: readonly unknown[],
  available = true) {
  const run = { run_id: f.response.run_id.slice(11), attempt: f.response.attempt, started_at: f.response.started_at };
  const server = ServerEvidenceSchema.parse({
    version: "2026-11-04", server_name: "hono-server", group: "planning", ...run,
    pid: null, startup: "not_started", startup_ms: null, shutdown: "not_started", exit_code: null,
    log_filename: serverLogFilename(run), log_available: available, error_code: null, cleanup_error_code: null,
  });
  await writeFile(join(f.directory, "hono-server-planning.json"), JSON.stringify(server));
  await writeFile(join(f.directory, server.log_filename), records.map(record => JSON.stringify(record)).join("\n") + "\n");
  return server;
}

test("workflow report reads terminal article 403 once and keeps DNS failure separate from unavailable status", async () => {
  const f = await plannerOutputRecording();
  try {
    const articles = await terminalRows(f);
    const receipt = await writeRows(f.inputs.outputRoot, "rejected-articles", f.response.date,
      RejectedArticleRowContract, [articles[0]!, articles[0]!, articles[1]!]);
    const cause = { subject: "article", stage: "harvest-feeds", attribution: "feed" };
    const health = { ...f.health, rows: [{ ...f.health.rows[0]!, rejection_counts: [
      { ...cause, reason_code: "FETCH_FAILED_HTTP", count: 2 },
      { ...cause, reason_code: "FETCH_FAILED", count: 1 },
    ] }] };
    const response = { ...f.response, health, files: { ...f.response.files, rejected_articles: receipt } };
    await writeFile(join(f.directory, "response.json"), JSON.stringify(response));
    const file = join(f.inputs.outputRoot, receipt.files[0]!.path);
    const before = await readFile(file);
    const evidence = await readExecutionEvidence(f.directory);
    const report = renderWorkflowPlanMarkdown(evidence);
    const rows = attention(report.markdown);
    const exact = rows.filter(row => row[2]!.includes("article HTTP 403"));
    expect(exact).toHaveLength(1);
    expect(exact[0]![3]).toContain("1 affected article;");
    const unavailable = rows.find(row => row[2]!.includes("transport code: ENOTFOUND"))!;
    expect(unavailable[2]).toContain("article response status unavailable");
    expect(unavailable[2]).not.toContain("article HTTP");
    expect(report.markdown.toLowerCase()).not.toContain("robots");
    expect(rows.filter(row => row[3]!.includes("recorded article failure"))).toHaveLength(1);
    expect(rows.find(row => row[3]!.includes("recorded article failure"))![3]).toContain("1 recorded article failure;");
    expect(report.markdown).not.toContain("paywall");
    expect(await readFile(file)).toEqual(before);
    const fullyCovered = renderWorkflowPlanMarkdown({ ...evidence, response: { ...response, health: {
      ...health, rows: [{ ...health.rows[0]!, rejection_counts: health.rows[0]!.rejection_counts
        .map(failure => ({ ...failure, count: 1 })) }],
    } } });
    expect(attention(fullyCovered.markdown).some(row => row[3]!.includes("recorded article failure"))).toBe(false);
    const missing = await readReportFailureEvidence({ directory: f.directory,
      response: { ...response, files: { ...response.files, rejected_articles: undefined } } });
    expect(missing.articles).toBeUndefined();
    await rm(file);
    const absent = await readExecutionEvidence(f.directory);
    expect(absent.failures?.articles).toBeUndefined();
    const absentRows = attention(renderWorkflowPlanMarkdown(absent).markdown);
    expect(absentRows.some(row => row[2]!.includes("Terminal article evidence file missing"))).toBe(true);
    expect(absentRows.some(row => row[2]!.includes("article HTTP 403"))).toBe(false);
  } finally { await f.close(); }
});

test("report uses a staged earlier check at the saved pause instant, never a new failure or another endpoint", async () => {
  const f = await plannerOutputRecording();
  try {
    const root = join(f.directory, "staged");
    const sourceRoot = fileURLToPath(new URL("../../../", import.meta.url));
    const paths = f.inputs.settings.inputs;
    for (const path of ["config/feed-ingest-plan-service.json",
      paths.planning, paths.sources, paths.extraction, paths.registrations]) {
      const destination = join(root, path);
      await mkdir(dirname(destination), { recursive: true });
      await copyFile(join(sourceRoot, path), destination);
    }
    const base = f.health.rows[0]!;
    const checkedAt = "2026-10-20T12:00:00Z";
    const saved = FeedHealthStateRowSchema.parse({
      ...base, date: "2026-10-20", run_id: "2026-10-20-699", attempt: 1,
      checked_at: checkedAt, links: [operationLink(createRootContext())],
      check_result: "other-http-failure", status: 403, last_failure_code: "FETCH_FAILED_HTTP",
      availability: "resting", availability_updated_at: checkedAt, rest_until: "2026-10-23T12:00:00Z",
    });
    const written = await writeRows(join(root, "state"), "feed-health-state", saved.date,
      FeedHealthStateRowContract, [saved]);
    await writeFile(join(root, "config", "feed-ingest-plan-service.json"), JSON.stringify({
      ...f.inputs.settings, inputs: { ...paths, feed_health_days: [
        { day: saved.date, raw_files: written.files.map(file => `state/${file.path}`) },
      ] },
    }));
    const carried = { ...base, feed_reads: 0, checked_at: null, links: [], check_result: null,
      rejection_counts: [], status: null, last_failure_code: null };
    const { availability, strikes, failed_recovery_checks, availability_complete, availability_updated_at,
      first_confirmed_failure_at, rest_until, retired_at, retirement_reason, feed_id, endpoint_key } = saved;
    const health = { ...f.health, rows: [carried], availability: { eligible_feed_ids: [], feeds: [{
      feed_id, endpoint_key, availability, strikes, failed_recovery_checks, availability_complete,
      availability_updated_at, first_confirmed_failure_at, rest_until, retired_at, retirement_reason,
    }] } };
    const response = { ...f.response, health };
    await writeFile(join(f.directory, "response.json"), JSON.stringify(response));
    await rm(join(f.directory, "health.json"), { force: true });
    const file = join(root, "state", written.files[0]!.path);
    const before = await readFile(file);
    const summaryPath = join(f.directory, "summary.md");
    const result = await writeWorkflowReport({ root, directory: f.directory, summaryPath,
      runNumber: "700", runId: f.response.run_id });
    if (result.status !== "written") throw new Error("Fixture report must be enabled");
    const paused = attention(result.markdown).find(row => row[2]!.includes("Coverage paused"))!;
    expect(paused[2]).toContain("saved earlier check: Feed HTTP failure (feed HTTP 403)");
    expect(paused[3]).toContain("not a new HTTP failure");
    expect(paused[4]).toBe(`Saved earlier check at ${checkedAt} UTC`);
    expect(paused[5]).toBe("2026-10-23T12:00:00Z");
    expect(attention(result.markdown).some(row => row[3]!.includes("recorded feed failures"))).toBe(false);
    expect(await readFile(file)).toEqual(before);
    const evidence = await readExecutionEvidence(f.directory, root);
    for (const check of [
      { ...saved, endpoint_key: "b".repeat(64) },
      { ...saved, checked_at: "2026-10-20T11:00:00Z" },
      { ...saved, run_id: f.response.run_id, attempt: f.response.attempt },
    ]) {
      const report = renderPlanMarkdown({ response,
        failures: { ...evidence.failures, earlier_checks: [check] } });
      const unknown = attention(report.markdown).find(row => row[2]!.includes("Coverage paused"))!;
      expect(unknown[2]).toContain("historical cause unavailable");
      expect(unknown[2]).not.toContain("403");
    }
    const current = renderPlanMarkdown({ response: { ...response, health: { ...health, rows: [base] } },
      failures: evidence.failures! });
    expect(attention(current.markdown).find(row => row[2]!.includes("Coverage paused"))![3])
      .toContain("Paused after this run's feed work; not an additional failure");
    const unknownWork = renderPlanMarkdown({ response: { ...response,
      health: { ...health, rows: [{ ...carried, feed_reads: null, counts_complete: false }] } },
      failures: evidence.failures! });
    expect(attention(unknownWork.markdown).find(row => row[2]!.includes("Coverage paused"))![3])
      .toContain("Current feed-check count unavailable");
    const timeoutCheck = renderPlanMarkdown({ response,
      failures: { earlier_checks: [{ ...saved, check_result: "timeout" }] } });
    const timeoutPause = attention(timeoutCheck.markdown).find(row => row[2]!.includes("Coverage paused"))!;
    expect(timeoutPause[2]).toContain("Feed request timed out");
    expect(timeoutPause[2]).not.toContain("HTTP 403");
  } finally { await f.close(); }
});

test("foreign execution and conflicting terminal copies are refused rather than reported as exact evidence", async () => {
  const f = await plannerOutputRecording();
  try {
    const [article] = await terminalRows(f);
    expect(() => renderPlanMarkdown({ response: f.response,
      failures: { articles: [{ ...article!, attempt: f.response.attempt + 1 }] } })).toThrow("another execution");
    expect(() => renderPlanMarkdown({ response: f.response,
      failures: { articles: [article!, { ...article!, http_status: 429 }] } })).toThrow("Conflicting terminal");
    const written = await writeRows(f.inputs.outputRoot, "rejected-articles", f.response.date,
      RejectedArticleRowContract, [article!]);
    const path = join(f.inputs.outputRoot, written.files[0]!.path);
    await writeFile(path, "damaged native file");
    await expect(readReportFailureEvidence({ directory: f.directory,
      response: { ...f.response, files: { ...f.response.files, rejected_articles: written } } })).rejects.toThrow();
  } finally { await f.close(); }
});

test("the named-mirror reader deduplicates records, excludes unrelated work and keeps valid partial evidence with explicit gaps", async () => {
  const f = await plannerOutputRecording();
  try {
    const event = await terminalDiagnostic(f, (await terminalRows(f))[0]!);
    const expected = { run_id: f.response.run_id, attempt: f.response.attempt, traceId: f.response.traceId };
    const read = async (identity = expected) => readArticleFailureDiagnostics({
      directory: f.directory, servers: await readServerEvidence(f.directory), expected: identity,
    });
    const server = await writeDiagnosticMirror(f, [event, event]);
    expect((await read()).article_diagnostics).toEqual([event]);
    expect((await read()).gaps).toEqual([]);
    await writeDiagnosticMirror(f, [event,
      { ...event, data: { ...event.data, run_id: "2026-10-21-999" } },
      { ...event, data: { ...event.data, details: { ...event.data.details, attempt: expected.attempt + 1 } } },
      { ...event, ...writeTraceContext(createRootContext()) },
    ]);
    const filtered = await read();
    expect(filtered.article_diagnostics).toEqual([event]);
    expect(filtered.gaps.map(row => row[1])).toContain("Unrelated article diagnostic excluded");
    for (const conflict of [
      { ...event, id: createCandidateId() },
      { ...event, data: { ...event.data, details: { ...event.data.details, candidate_id: createCandidateId() } } },
    ]) {
      await writeDiagnosticMirror(f, [event, conflict]);
      await expect(read()).rejects.toThrow("Conflicting terminal article diagnostics");
    }
    await writeDiagnosticMirror(f, [event], false);
    await writeFile(join(f.directory, server.log_filename), [
      JSON.stringify(event),
      JSON.stringify({ ...event, data: { ...event.data, details: { ...event.data.details, attempt: 0,
        diagnostics: { title: "PRIVATE_TITLE", error_code: "PRIVATE_EXCEPTION includes arbitrary exception text" } } } }),
      JSON.stringify({ data: { code: "CHILD_DIAGNOSTIC_INVALID" } }), '{"data":',
    ].join("\n"));
    const partial = await read();
    expect(partial.article_diagnostics).toEqual([event]);
    expect(partial.gaps.map(row => row[1])).toEqual(expect.arrayContaining([
      "Article diagnostic mirror is partial or unavailable", "Article diagnostic log is incomplete",
      "Malformed terminal article diagnostic", "A child diagnostic was rejected",
      "Article diagnostic log contains an unreadable line",
    ]));
    expect(JSON.stringify(partial)).not.toContain("PRIVATE_");
    const noIdentity = await readArticleFailureDiagnostics({
      directory: f.directory, servers: await readServerEvidence(f.directory), expected: {},
    });
    expect(noIdentity.article_diagnostics).toEqual([]);
    expect(noIdentity.gaps.map(row => row[1])).toContain("Article diagnostic identity unavailable");
    const noExecution = await readArticleFailureDiagnostics({
      directory: f.directory, servers: await readServerEvidence(f.directory),
      expected: { run_id: expected.run_id, attempt: expected.attempt },
    });
    expect(noExecution.article_diagnostics).toEqual([event]);
    expect(noExecution.gaps.map(row => row[1])).toContain("Article diagnostic execution identity unavailable");
    await expect(read({ ...expected, attempt: expected.attempt + 1 })).rejects.toThrow("another run or attempt");
    await expect(readReportFailureEvidence({ directory: f.directory, response: f.response,
      execution: { attempt: expected.attempt + 1 } })).rejects.toThrow("another execution");
    await rm(join(f.directory, server.log_filename));
    expect((await read()).gaps.map(row => row[1])).toContain("Article diagnostic log missing");
    await rm(join(f.directory, "hono-server-planning.json"));
    const missing = await read();
    expect(missing.article_diagnostics).toEqual([]);
    expect(missing.gaps.map(row => row[1])).toContain("Article diagnostic mirror unavailable");
  } finally { await f.close(); }
});

test("complete, partial, error and absent response reports keep diagnostics without inventing planning or health success", async () => {
  const f = await plannerOutputRecording();
  try {
    const event = await terminalDiagnostic(f, (await terminalRows(f))[0]!);
    await writeDiagnosticMirror(f, [event]);
    const execution = { run_id: f.response.run_id, attempt: f.response.attempt, traceId: f.response.traceId };
    const health = structuredClone(f.health);
    const error = describePlanError(new Error("PRIVATE_EXCEPTION includes source content"), undefined, {
      operation: "plan", execution: { ...execution, spanId: createRootContext().spanId, git_sha: "a".repeat(40) },
    });
    const responses = [f.response, { ...f.response, status: "partial", failure_code: "PERSIST_FAILED",
      planning_complete: false, selected_articles_artifact: null }, error, undefined];
    for (const response of responses) {
      const path = join(f.directory, "response.json");
      if (response === undefined) await rm(path, { force: true });
      else await writeFile(path, JSON.stringify(response));
      const evidence = await readExecutionEvidence(f.directory, undefined, { execution });
      expect(evidence.failures?.article_diagnostics).toEqual([event]);
      const report = renderWorkflowPlanMarkdown(evidence);
      expect(attention(report.markdown).some(row => row[2]!.includes("article HTTP 403"))).toBe(true);
      expect(report.markdown).not.toContain("PRIVATE_");
      if (response === undefined || !("planning_complete" in response)) {
        expect(report.markdown).toContain("**Planning result unavailable.**");
        expect(report.markdown).toContain("Feed work evidence unavailable");
        expect(report.markdown).toContain("Feed availability evidence unavailable");
      } else if (!response.planning_complete) {
        expect(report.markdown).toContain("completion not established");
      }
    }
    await mkdir(join(f.directory, "config"));
    await writeFile(join(f.directory, "config", "feed-ingest-plan.json"), JSON.stringify(f.inputs.harvest.config));
    await writeFile(join(f.directory, "config", "feed-ingest-plan-service.json"), JSON.stringify(f.inputs.settings));
    const report = await writeWorkflowReport({ root: f.directory, directory: f.directory,
      summaryPath: join(f.directory, "summary.md"), runId: execution.run_id,
      runNumber: execution.run_id.slice(11), attempt: execution.attempt });
    if (report.status !== "written") throw new Error("Recorded workflow reporting must be enabled");
    expect(report.markdown).toContain("**Planning result unavailable.**");
    expect(report.markdown).toContain("Terminal article diagnostic details");
    expect(report.markdown).toContain("Article diagnostic execution identity unavailable");
    expect(f.health).toEqual(health);
  } finally { await f.close(); }
});
