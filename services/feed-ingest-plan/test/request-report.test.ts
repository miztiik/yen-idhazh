/** Do independent recorded counters retain honest coverage and report-only request ordering? */
import { expect, test } from "bun:test";
import { FeedHealthStateRowSchema, SourceSnapshotSchema } from "@idhazh/common-contracts";
import { projectFeedHealthFields } from "../src/read-ledger-history/read-feed-health-fields";
import { summarizeRequestReport } from "../src/read-ledger-history/request-summary";
import { inputEndpointKey } from "../src/read-ledger-history/health-summary";
import { renderRequestReport } from "../src/reporting/request-report-markdown";
import { renderPlanMarkdown } from "../src/reporting/plan-markdown";
import { runFeedPlan, summarizePlan } from "../src/run-feed-plan";
import { recordedPlan } from "./plan-recordings";
import { executeFeedHealthState } from "../src/api/feed-health-state-operation";
import { escapeMarkdown } from "../src/reporting/markdown-format";

async function fixture() {
  const source = SourceSnapshotSchema.parse({
    feed_id: "recorded-feed", feed_url: "https://news.example/feed.xml", title: "Recorded feed",
    tier: 2, status: "active", weight: 1, applied_tier_weight: 1,
  });
  const row = FeedHealthStateRowSchema.parse({
    ...await Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/health-field-history.json", import.meta.url)).json(),
    endpoint_key: inputEndpointKey(source.feed_url),
  });
  const days = [{ day: "2026-10-24", complete: true }, { day: row.date, complete: true }];
  function report(records: Record<string, unknown>[], options: {
    days?: typeof days; input_complete?: boolean; sources?: typeof source[];
  } = {}) {
    const projection = ["2026-10-24", row.date, "2026-10-26", "2026-10-23"].map(day =>
      projectFeedHealthFields(day, records.filter(record => record.date === day)).request_totals);
    return summarizeRequestReport({
      rows: projection.flatMap(use => use.rows), partial_rows: projection.flatMap(use => use.partial_rows),
      gaps: projection.flatMap(use => use.gaps), sources: [source], now: "2026-10-26T23:59:59Z",
      request_report_closed_days: 2, days, ...options,
    });
  }
  return { source, row, days, report };
}

test("sums each usable counter across full and partial records without double counting attempts", async () => {
  const { row, report } = await fixture();
  const { article_requests: _missing, ...partial } = row;
  const result = report([
    row, row, { ...row, attempt: 2, article_requests: null },
    { ...partial, attempt: 3 }, { ...row, attempt: 4, article_requests: -1 },
    { ...row, attempt: 5, endpoint_key: "2".repeat(64), article_requests: 100 },
    { ...row, date: "2026-10-26", run_id: "2026-10-26-1", article_requests: 200 },
    { ...row, date: "2026-10-23", run_id: "2026-10-23-1", article_requests: 400 },
  ]);
  expect(result.complete).toBe(false);
  expect(result.missing_days).toEqual([]);
  expect(result.feeds[0]).toMatchObject({
    feed_requests: 8, article_requests: 4, robots_requests: 0, counts_complete: false,
    coverage: {
      feed_requests: { status: "complete", known_records: 4, unknown_records: 0, complete_days: ["2026-10-24", row.date] },
      article_requests: { status: "partial", known_records: 1, unknown_records: 3, recorded_days: [row.date], complete_days: ["2026-10-24"] },
      robots_requests: { status: "complete", known_records: 4 },
    },
  });
  expect(() => report([row, { ...row, permission: "denied" }])).toThrow("Conflicting copies");
  const rendered = renderRequestReport(result);
  expect(rendered.markdown).toContain("| 4* | 8 | 0 | Partial |");
  expect(Bun.markdown.html(rendered.markdown)).toContain("<td>4*</td>");
  expect(rendered.notice).toContain("4* / 8 / 0");
  expect(rendered.markdown).toContain("3 records with missing or invalid counts");
});

test("reports missing files, unidentifiable records and staged input gaps without erasing known values", async () => {
  const { row, report, days } = await fixture();
  const missing = report([row], { days: [days[1]!] });
  expect(missing).toMatchObject({ complete: false, missing_days: ["2026-10-24"] });
  expect(missing.feeds[0]).toMatchObject({ feed_requests: 2, article_requests: 4, robots_requests: 0 });
  expect(missing.feeds[0]!.coverage.robots_requests).toMatchObject({
    status: "partial", known_records: 1, recorded_days: [row.date], complete_days: [row.date],
  });
  const unattributed = report([row, { ...row, attempt: "invalid" }]);
  expect(unattributed.unattributed_days).toEqual([row.date]);
  expect(unattributed.feeds[0]!.coverage.feed_requests).toMatchObject({
    status: "partial", known_records: 1, complete_days: ["2026-10-24"],
  });
  const staged = report([row], { input_complete: false });
  expect(staged).toMatchObject({ complete: false, input_complete: false });
  expect(staged.feeds[0]!.coverage.article_requests).toMatchObject({ status: "partial", complete_days: [] });
  const rendered = renderRequestReport(staged);
  expect(rendered.markdown).toContain("Staged history inputs: incomplete");
  expect(rendered.notice).toContain("4* / 2* / 0*");
});

test("distinguishes known zero from absent counts and leaves unrelated counters complete", async () => {
  const { row, report } = await fixture();
  const unknown = report([{ ...row, article_requests: null, feed_requests: 0 }]);
  expect(unknown.feeds[0]).toMatchObject({ feed_requests: 0, article_requests: null, robots_requests: 0 });
  expect(unknown.feeds[0]!.coverage.article_requests).toMatchObject({
    status: "none", known_records: 0, unknown_records: 1,
  });
  const empty = report([]);
  expect(empty).toMatchObject({ complete: true, feeds: [{ feed_requests: 0, article_requests: 0, robots_requests: 0 }] });
  const absent = report([], { days: [] });
  expect(absent.feeds[0]).toMatchObject({ feed_requests: null, article_requests: null, robots_requests: null });
  expect(renderRequestReport(absent).markdown).toContain("| Not recorded | Not recorded | Not recorded |");
  expect(renderRequestReport(unknown).markdown).toContain("| Not recorded | 0 | 0 |");
  const articleOnly = report([{ ...row, feed_requests: null, robots_requests: -1 }]);
  expect(articleOnly.feeds[0]).toMatchObject({
    feed_requests: null, article_requests: 4, robots_requests: null,
    coverage: { article_requests: { status: "complete" }, robots_requests: { status: "none", unknown_records: 1 } },
  });
  expect(renderRequestReport(articleOnly).markdown).toContain("| 4 | Not recorded | Not recorded |");
  expect(Bun.markdown.html(renderRequestReport(report([{ ...row, feed_requests: 0 }], { days: [] })).markdown))
    .toContain("<td>0*</td>");
  expect(renderRequestReport(undefined).notice).toContain("was not recorded");
});

test("sorts request rows by article requests, feed requests, then name with unknown values last", async () => {
  const { row, source, report } = await fixture();
  const cases = [
    { feed_id: "unknown", feed_requests: null, article_requests: 100 },
    { feed_id: "beta", feed_requests: 2, article_requests: 4 },
    { feed_id: "zero", feed_requests: 0, article_requests: 200 },
    { feed_id: "alpha", feed_requests: 2, article_requests: 4 },
    { feed_id: "missing-article", feed_requests: 2, article_requests: null },
    { feed_id: "most-articles", feed_requests: 2, article_requests: 5 },
    { feed_id: "most-feeds", feed_requests: 3, article_requests: 0 },
  ];
  const request_report = report(cases.map(value => ({ ...row, ...value })), {
    sources: cases.map(value => ({ ...source, feed_id: value.feed_id })),
  });
  const before = structuredClone(request_report);
  const fixturePlan = await recordedPlan();
  try {
    const response = summarizePlan(await runFeedPlan({}, fixturePlan.inputs, fixturePlan.runtime));
    const health = await executeFeedHealthState({ batch_id: response.batches.selection_batch_id, action: "summarize" },
      fixturePlan.inputs, fixturePlan.runtime);
    const original = renderPlanMarkdown({ response, health });
    const rendered = renderPlanMarkdown({ response, health: { ...health, request_report } });
    const lines = rendered.markdown.split("\n").filter(line => /^\| F\d+ \|/.test(line));
    expect(lines.map(line => line.split(" | ")[1])).toEqual([
      "zero", "unknown", "most-articles", "alpha", "beta", "most-feeds", "missing-article",
    ].map(escapeMarkdown));
    expect(rendered.markdown.split("<details>\n<summary>Request counts and coverage")[0])
      .toBe(original.markdown.split("<details>\n<summary>Request counts and coverage")[0]);
    expect(request_report).toEqual(before);
    const html = Bun.markdown.html(rendered.markdown);
    expect(html).toContain("<td>Partial</td>");
    expect(html).toContain("Partial totals include recorded counts only");
    expect(rendered.markdown).toContain("<summary>Request counts and coverage");
    expect(renderRequestReport(report([row])).markdown).not.toContain("Partial*");
  } finally { await fixturePlan.close(); }
});

test("sorts feed results by admitted and chosen articles, and exclusions by count then reason", async () => {
  const fixturePlan = await recordedPlan();
  try {
    const response = summarizePlan(await runFeedPlan({}, fixturePlan.inputs, fixturePlan.runtime));
    const health = await executeFeedHealthState({ batch_id: response.batches.selection_batch_id, action: "summarize" },
      fixturePlan.inputs, fixturePlan.runtime);
    const base = health.rows[0]!;
    const cause = base.rejection_counts[0]!;
    const rows = [
      { feed_id: "alpha", chosen: 5, admitted: 10, reason: "MISSING_REQUIRED_FIELDS", count: 5 },
      { feed_id: "beta", chosen: 5, admitted: 12, reason: "EXTRACT_EMPTY", count: 8 },
      { feed_id: "charlie", chosen: 7, admitted: 7, reason: "REJECTED_SCREENING_MIN_WORDS", count: 5 },
      { feed_id: "delta", chosen: 5, admitted: 12, reason: "EXTRACT_EMPTY", count: 5 },
    ];
    const rendered = renderPlanMarkdown({ response, health: { ...health, rows: [...rows.map(value => ({
      ...base, feed_id: value.feed_id, article_candidates: value.admitted, articles_selected: value.chosen,
      rejection_counts: [{ ...cause, reason_code: value.reason, count: value.count }],
    })), { ...base, feed_id: "epsilon", article_candidates: 12, articles_selected: 6, rejection_counts: [] },
    { ...base, feed_id: "unknown", article_candidates: null, counts_complete: false, articles_selected: 99, rejection_counts: [] }] } });
    const lines = rendered.markdown.split("\n");
    const feedRows = lines.filter(line => /^\| D\d+ \|/.test(line));
    expect(feedRows.map(line => line.split(" | ")[1])).toEqual(["epsilon", "beta", "delta", "alpha", "charlie", "unknown"]);
    const exclusionRows = lines.filter(line => /^\| G\d+ \|/.test(line));
    expect(exclusionRows.map(line => line.split(" | ")[4])).toEqual([
      "EXTRACT&#95;EMPTY", "EXTRACT&#95;EMPTY", "MISSING&#95;REQUIRED&#95;FIELDS", "REJECTED&#95;SCREENING&#95;MIN&#95;WORDS",
    ]);
    expect(rendered.notices[2]!.message).toContain(
      "EXTRACT_EMPTY: 13 decisions; MISSING_REQUIRED_FIELDS: 5 decisions; REJECTED_SCREENING_MIN_WORDS: 5 decisions",
    );
    expect(rendered.markdown).toContain("<summary>Per-feed article results</summary>");
    expect(rendered.markdown).toContain("<summary>Grouped exclusions</summary>");
  } finally { await fixturePlan.close(); }
});

test("joins latest recorded feed reliability without treating missing or incomplete scores as zero", async () => {
  const { row, source, report } = await fixture();
  const sources = ["recorded-feed", "missing-feed", "unmeasured-feed"].map(feed_id => ({ ...source, feed_id }));
  const requests = report(sources.map(value => ({ ...row, feed_id: value.feed_id })), { sources });
  const reliability = {
    productive: 1, attempted: 2, success_fraction: 0.5, production_factor: 0.5,
    from_day: "2026-10-01", through_day: "2026-10-25", complete: false,
  };
  const health = [
    { ...row, reliability },
    { ...row, date: "2026-10-24", reliability: { ...reliability, success_fraction: 1, complete: true } },
    { ...row, feed_id: "unmeasured-feed", reliability: null },
  ];
  const before = structuredClone({ requests, health });
  const rendered = renderRequestReport(requests, health).markdown;
  const lines = rendered.split("\n").filter(line => /^\| F\d+ \|/.test(line));
  expect(lines.find(line => line.includes(escapeMarkdown("recorded-feed"))))
    .toContain("| 0.5 | false | 2026-10-01 through 2026-10-25 |");
  for (const id of ["missing-feed", "unmeasured-feed"]) {
    expect(lines.find(line => line.includes(escapeMarkdown(id))))
      .toEndWith("| Not recorded | Not recorded | Not recorded |");
  }
  expect(rendered).toContain("<summary>Request counts and coverage</summary>");
  expect(rendered).toContain("| Expected closed UTC days | 2 |");
  expect(rendered).toContain("2026-10-24 through 2026-10-25");
  expect(rendered).toContain("separate from the closed request window");
  expect({ requests, health }).toEqual(before);
});
