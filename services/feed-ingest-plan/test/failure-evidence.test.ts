/** Does the operator report separate recorded failures from policy exclusions and missing causes? */
import { expect, test } from "bun:test";
import { renderFailureEvidence } from "../src/reporting/failure-evidence-markdown";
import { renderPlanMarkdown } from "../src/reporting/plan-markdown";
import { executeFeedHealthState } from "../src/api/feed-health-state-operation";
import { runFeedPlan, summarizePlan } from "../src/run-feed-plan";
import { recordedPlan } from "./plan-recordings";

test("groups actual failure rows by subject, reason, status and attribution", async () => {
  const fixture = await recordedPlan();
  try {
    const response = summarizePlan(await runFeedPlan({}, fixture.inputs, fixture.runtime));
    const health = await executeFeedHealthState({ batch_id: response.batches.selection_batch_id, action: "summarize" },
      fixture.inputs, fixture.runtime);
    const base = health.rows[0]!;
    const rejection = (subject: "article" | "feed", reason_code: string, count: number,
      attribution: "feed" | "pipeline" | "unknown") => ({
      subject, reason_code, count, attribution, stage: "harvest-feeds",
    });
    const row = (feed_id: string, article_candidates: number | null,
      rejection_counts: typeof base.rejection_counts, fields: Partial<typeof base> = {}) => ({
      ...base, feed_id, article_candidates, counts_complete: article_candidates !== null,
      rejection_counts, ...fields,
    });
    const rows = [
      row("fastcompany-tech", 0, [rejection("article", "FETCH_FAILED_HTTP", 20, "feed")]),
      row("business-today-in", 0, [rejection("article", "EXTRACT_EMPTY", 7, "feed")]),
      row("marktechpost", 0, [rejection("article", "EXTRACT_EMPTY", 4, "feed")]),
      row("marginal-revolution", null, [rejection("article", "EXTRACT_FAILED", 1, "unknown")]),
      row("abc-au-world", null, [rejection("article", "FETCH_FAILED", 1, "pipeline")]),
      row("timeout-feed", 0, [rejection("article", "FETCH_TIMEOUT", 1, "feed")]),
      row("feed-a", 0, [rejection("feed", "FETCH_FAILED_HTTP", 1, "feed")],
        { status: 403, last_failure_code: "FETCH_FAILED_HTTP" }),
      row("feed-b", 0, [rejection("feed", "FETCH_FAILED_HTTP", 1, "feed")],
        { status: 403, last_failure_code: "FETCH_FAILED_HTTP" }),
      row("feed-c", 0, [rejection("feed", "FETCH_FAILED", 1, "pipeline")],
        { status: 200, last_failure_code: "FETCH_FAILED" }),
      row("feed-d", 0, [rejection("feed", "FEED_PARSE_FAILED", 1, "feed")],
        { status: 202, last_failure_code: "FEED_PARSE_FAILED" }),
      row("policy-only", 0, [rejection("article", "REJECTED_SCREENING_MIN_WORDS", 171, "feed")]),
    ];
    const before = structuredClone(rows);
    const failureSection = renderFailureEvidence(rows).markdown;
    expect(failureSection).toContain("| J1 | FETCH&#95;FAILED&#95;HTTP | Not recorded / feed | 20 failures | fastcompany&#45;tech | HTTP failure recorded; response status not recorded |");
    expect(failureSection).toContain("| J2 | EXTRACT&#95;EMPTY | Not recorded / feed | 11 failures | business&#45;today&#45;in, marktechpost | Confirmed empty extraction; content cause not recorded |");
    expect(failureSection).toContain("| J3 | EXTRACT&#95;FAILED | Not recorded / unknown | 1 failure | marginal&#45;revolution | Extraction failure recorded; detailed cause not recorded |");
    expect(failureSection).toContain("| J4 | FETCH&#95;FAILED | Not recorded / pipeline | 1 failure | abc&#45;au&#45;world | Inferred from pipeline attribution; underlying trigger not recorded |");
    expect(failureSection).toContain("| J5 | FETCH&#95;TIMEOUT | Not recorded / feed | 1 failure | timeout&#45;feed | Confirmed timeout; detailed cause not recorded |");
    expect(failureSection).toContain("| K1 | FETCH&#95;FAILED&#95;HTTP | 403 / feed | 2 failures | feed&#45;a, feed&#45;b | Confirmed HTTP 403; lower&#45;level cause not recorded |");
    expect(failureSection).toContain("Inferred from pipeline attribution");
    expect(failureSection).toContain("Admission totals are unavailable for 2 feeds named in Table A");
    expect(failureSection).not.toContain("REJECTED_SCREENING_MIN_WORDS");
    expect(failureSection).not.toContain("https://");
    expect(rows).toEqual(before);
    const html = Bun.markdown.html(failureSection);
    expect(html).toContain("<summary>Failure evidence</summary>");
    expect(html).toContain("<td>2 failures</td>");

    const integrated = renderPlanMarkdown({ response, health: { ...health, rows } });
    expect(integrated.markdown).toContain("## Table A - Run facts");
    expect(integrated.markdown).toContain("abc&#45;au&#45;world, marginal&#45;revolution");
    expect(integrated.markdown).toContain("## Table J - Article failures");
    expect(integrated.markdown).toContain("## Table K - Feed failures");
    expect(integrated.markdown).toContain("REJECTED&#95;SCREENING&#95;MIN&#95;WORDS");
    expect(integrated.notices.some(notice => notice.title === "Failure evidence")).toBe(true);
  } finally { await fixture.close(); }
});

test("keeps unavailable failures distinct from empty failure results", () => {
  const missing = renderFailureEvidence(undefined);
  expect(missing.markdown).toContain("Failure evidence");
  expect(missing.markdown).toContain("Failure evidence is unavailable.");
  expect(missing.markdown).toContain("Admission availability is not recorded");
  expect(missing.notice).toBe("Failure evidence was not recorded.");
});
