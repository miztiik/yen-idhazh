/** Do verified native records explain exact article failures and paused feeds without changing their bytes? */
import { expect, test } from "bun:test";
import { copyFile, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseHTML } from "linkedom";
import {
  FeedHealthStateRowContract, FeedHealthStateRowSchema, RejectedArticleRowContract, RejectedArticleRowSchema,
} from "@idhazh/common-contracts";
import { readExecutionEvidence, renderWorkflowPlanMarkdown, writeWorkflowReport } from "../scripts/feed-ingest-plan-report";
import { readReportFailureEvidence } from "../scripts/feed-ingest-plan-report-evidence";
import { renderPlanMarkdown } from "../src/reporting";
import { plannerOutputRecording } from "./planner-output-recordings";
import { writeRows } from "./partition-fixtures";

function attention(markdown: string) {
  const { document } = parseHTML(Bun.markdown.html(markdown));
  return [...document.querySelectorAll("table")[1]!.querySelectorAll("tbody tr")]
    .map(row => [...row.querySelectorAll("td")].map(cell => cell.textContent!));
}

async function terminalRows(f: Awaited<ReturnType<typeof plannerOutputRecording>>) {
  const recorded = await Bun.file(new URL(
    "../../../tests/fixtures/feed-ingest-plan/article-terminal-failures.json", import.meta.url,
  )).json();
  const base = RejectedArticleRowSchema.array().parse(await Bun.file(new URL(
    "../../../tests/fixtures/feed-ingest-plan/entry-points/rejected-articles.rows.json", import.meta.url,
  )).json())[0]!;
  return ["forbidden", "robots-unavailable"].map((name, index) => RejectedArticleRowSchema.parse({
    ...base, run_id: f.response.run_id, attempt: f.response.attempt,
    candidate_id: index === 0 ? "a".repeat(64) : null, url_key: String(index + 1).repeat(64),
    stage: "harvest-feeds", reason_code: index === 0 ? "FETCH_FAILED_HTTP" : "FETCH_FAILED",
    freshness_cutoff_at: null,
    ...recorded.cases.find((entry: { name: string }) => entry.name === name).expected,
  }));
}

test("workflow report reads terminal article 403 once and keeps robots 503 separate from unknown article status", async () => {
  const f = await plannerOutputRecording();
  try {
    const articles = await terminalRows(f);
    const receipt = await writeRows(f.inputs.outputRoot, "rejected-articles", f.response.date,
      RejectedArticleRowContract, [articles[0]!, articles[0]!, articles[1]!]);
    const response = { ...f.response, files: { ...f.response.files, rejected_articles: receipt } };
    const cause = { subject: "article", stage: "harvest-feeds", attribution: "feed" };
    const health = { ...f.health, rows: [{ ...f.health.rows[0]!, rejection_counts: [
      { ...cause, reason_code: "FETCH_FAILED_HTTP", count: 2 },
      { ...cause, reason_code: "FETCH_FAILED", count: 1 },
    ] }] };
    await writeFile(join(f.directory, "response.json"), JSON.stringify(response));
    await writeFile(join(f.directory, "health.json"), JSON.stringify(health));
    const file = join(f.inputs.outputRoot, receipt.files[0]!.path);
    const before = await readFile(file);
    const evidence = await readExecutionEvidence(f.directory);
    const report = renderWorkflowPlanMarkdown(evidence);
    const rows = attention(report.markdown);
    const exact = rows.filter(row => row[2]!.includes("article HTTP 403"));
    expect(exact).toHaveLength(1);
    expect(exact[0]![3]).toContain("1 affected article;");
    const robots = rows.find(row => row[2]!.includes("robots HTTP 503"))!;
    expect(robots[2]).toContain("article response status unavailable");
    expect(robots[2]).not.toContain("article HTTP 503");
    expect(rows.filter(row => row[3]!.includes("recorded article failure"))).toHaveLength(1);
    expect(rows.find(row => row[3]!.includes("recorded article failure"))![3]).toContain("1 recorded article failure;");
    expect(report.markdown).not.toContain("paywall");
    expect(await readFile(file)).toEqual(before);
    const fullyCovered = renderWorkflowPlanMarkdown({ ...evidence, health: {
      ...health, rows: [{ ...health.rows[0]!, rejection_counts: health.rows[0]!.rejection_counts
        .map(failure => ({ ...failure, count: 1 })) }],
    } });
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
      paths.planning, paths.taxonomy, paths.sources, paths.extraction, paths.registrations]) {
      const destination = join(root, path);
      await mkdir(dirname(destination), { recursive: true });
      await copyFile(join(sourceRoot, path), destination);
    }
    const base = f.health.rows[0]!;
    const checkedAt = "2026-10-20T12:00:00Z";
    const saved = FeedHealthStateRowSchema.parse({
      ...base, date: "2026-10-20", run_id: "2026-10-20-699", attempt: 1,
      checked_at: checkedAt, check_request_id: "9e759c80-2f1d-4e2e-8cb5-516fc6ae8e11",
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
    const carried = { ...base, feed_reads: 0, checked_at: null, check_request_id: null, check_result: null,
      rejection_counts: [], status: null, last_failure_code: null };
    const { availability, strikes, failed_recovery_checks, availability_complete, availability_updated_at,
      first_confirmed_failure_at, rest_until, retired_at, retirement_reason, feed_id, endpoint_key } = saved;
    const health = { ...f.health, rows: [carried], availability: { eligible_feed_ids: [], feeds: [{
      feed_id, endpoint_key, availability, strikes, failed_recovery_checks, availability_complete,
      availability_updated_at, first_confirmed_failure_at, rest_until, retired_at, retirement_reason,
    }] } };
    await writeFile(join(f.directory, "response.json"), JSON.stringify(f.response));
    await writeFile(join(f.directory, "health.json"), JSON.stringify(health));
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
      const report = renderPlanMarkdown({ response: f.response, health,
        failures: { ...evidence.failures, earlier_checks: [check] } });
      const unknown = attention(report.markdown).find(row => row[2]!.includes("Coverage paused"))!;
      expect(unknown[2]).toContain("historical cause unavailable");
      expect(unknown[2]).not.toContain("403");
    }
    const current = renderPlanMarkdown({ response: f.response, failures: evidence.failures!,
      health: { ...health, rows: [base] } });
    expect(attention(current.markdown).find(row => row[2]!.includes("Coverage paused"))![3])
      .toContain("Paused after this run's feed work; not an additional failure");
    const unknownWork = renderPlanMarkdown({ response: f.response, failures: evidence.failures!,
      health: { ...health, rows: [{ ...carried, feed_reads: null, counts_complete: false }] } });
    expect(attention(unknownWork.markdown).find(row => row[2]!.includes("Coverage paused"))![3])
      .toContain("Current feed-check count unavailable");
    const robotsCheck = renderPlanMarkdown({ response: f.response, health,
      failures: { earlier_checks: [{ ...saved, check_result: "robots" }] } });
    const robotsPause = attention(robotsCheck.markdown).find(row => row[2]!.includes("Coverage paused"))!;
    expect(robotsPause[2]).toContain("Feed robots restriction");
    expect(robotsPause[2]).not.toContain("HTTP 403");
  } finally { await f.close(); }
});

test("foreign execution and conflicting terminal copies are refused rather than reported as exact evidence", async () => {
  const f = await plannerOutputRecording();
  try {
    const [article] = await terminalRows(f);
    expect(() => renderPlanMarkdown({ response: f.response, health: f.health,
      failures: { articles: [{ ...article!, attempt: f.response.attempt + 1 }] } })).toThrow("another execution");
    expect(() => renderPlanMarkdown({ response: f.response, health: f.health,
      failures: { articles: [article!, { ...article!, http_status: 429 }] } })).toThrow("Conflicting terminal");
    const written = await writeRows(f.inputs.outputRoot, "rejected-articles", f.response.date,
      RejectedArticleRowContract, [article!]);
    const path = join(f.inputs.outputRoot, written.files[0]!.path);
    await writeFile(path, "damaged native file");
    await expect(readReportFailureEvidence({ directory: f.directory,
      response: { ...f.response, files: { ...f.response.files, rejected_articles: written } } })).rejects.toThrow();
  } finally { await f.close(); }
});
