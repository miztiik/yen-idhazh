/** Does the workflow expose only decisions while preserving exact, partial and artifact evidence? */
import { expect, test } from "bun:test";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseHTML } from "linkedom";
import { renderWorkflowPlanMarkdown, writeWorkflowReport } from "../scripts/feed-ingest-plan-report";
import { renderPlanMarkdown } from "../src/reporting";
import { readPlannerOutputRecording } from "./planner-output-recordings";

async function evidence() {
  const { response, health } = await readPlannerOutputRecording();
  const config = await Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json();
  const settings = await Bun.file(new URL("../../../config/idhazh.json", import.meta.url)).json();
  const host = await Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/host-report.json", import.meta.url)).json();
  return { response, health, host, policy: {
    config, request: { article_limit: 17 }, history: settings.collect, parser_concurrency: 2,
  } };
}

test("only outcome and attention remain outside five closed folds with unique table row identities", async () => {
  const input = await evidence();
  const before = structuredClone(input);
  const report = renderWorkflowPlanMarkdown(input);
  const { document } = parseHTML(Bun.markdown.html(report.markdown));
  const folds = [...document.querySelectorAll("details")];
  expect(folds.map(fold => fold.querySelector("summary")!.textContent)).toEqual([
    "Per-feed article results", "Request counts and coverage", "Why articles were not selected",
    "Effective settings", "Execution measurements",
  ]);
  expect(folds.every(fold => !fold.hasAttribute("open"))).toBe(true);
  expect([...document.querySelectorAll("h2")].filter(heading => !heading.closest("details")).map(heading => heading.textContent))
    .toEqual(["Table A - Run outcome", "Table B - Needs attention"]);
  const ids = [...document.querySelectorAll("tbody tr")].map(row => row.querySelector("td")!.textContent);
  expect(new Set(ids).size).toBe(ids.length);
  expect(folds.at(-1)!.querySelectorAll("table")).toHaveLength(1);
  expect(document.querySelectorAll("table")[0]!.textContent).toContain("1 / 17");
  expect(folds[3]!.textContent).toContain("workflow override");
  expect(report.notices).toEqual([]);
  expect(input).toEqual(before);
});

test("UTC day rows aggregate once per feed while one missing constituent keeps its exact total unknown", async () => {
  const { response, health } = await readPlannerOutputRecording();
  const base = health.rows[0]!;
  const day = (feed_id: string, selected: number | null, candidates: number | null, date: string) => ({
    ...base, feed_id, articles_selected: selected, article_candidates: candidates,
    counts_complete: false, date, checked_at: `${date}T12:00:00Z`, rejection_counts: [],
  });
  const rows = [
    day("combined", 2, 3, "2026-10-21"), day("combined", 3, null, "2026-10-22"),
    day("known", 5, 6, "2026-10-21"), day("missing-selection", null, 100, "2026-10-21"),
  ];
  const report = renderPlanMarkdown({ response, health: { ...health, rows } });
  const { document } = parseHTML(Bun.markdown.html(report.markdown));
  const cells = [...document.querySelector("details")!.querySelectorAll("tbody tr")]
    .map(row => [...row.querySelectorAll("td")].map(cell => cell.textContent));
  expect(cells.map(row => row.slice(1, 4))).toEqual([
    ["known", "5", "6"], ["combined", "5", "Not recorded"], ["missing-selection", "Not recorded", "100"],
  ]);
  expect(document.querySelectorAll("table")[0]!.textContent).toContain("109 known; exact total unavailable for 1 feed");
});

test("artifact retains per-feed diagnostics without restoring them in the job summary", async () => {
  const input = await evidence();
  const directory = await mkdtemp(join(tmpdir(), "planner-report-"));
  try {
    for (const [name, value] of [["response", input.response], ["health", input.health],
      ["workflow-policy", input.policy], ["host-fingerprint", input.host]] as const) {
      await writeFile(join(directory, `${name}.json`), JSON.stringify(value));
    }
    const summaryPath = join(directory, "summary.md");
    const result = await writeWorkflowReport({
      root: fileURLToPath(new URL("../../../", import.meta.url)),
      directory, summaryPath, runNumber: "700", runId: input.response.run_id,
    });
    if (result.status !== "written") throw new Error("Recorded report must be enabled");
    const summary = await readFile(summaryPath, "utf8");
    const artifact = await readFile(join(directory, result.filename), "utf8");
    expect(summary).toBe(result.markdown);
    expect(summary).not.toContain("Table I");
    expect(artifact).toStartWith(summary);
    expect(artifact).toContain("Per-feed exclusion diagnostics");
    expect(artifact).toContain("MISSING&#95;REQUIRED&#95;FIELDS");
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
