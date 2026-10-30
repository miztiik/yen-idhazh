/** Do report facts distinguish known counts, partial admissions and missing evidence? */
import { expect, test } from "bun:test";
import { FeedHealthStateRowSchema, PlanRunRowSchema } from "@idhazh/common-contracts";
import { parseHTML } from "linkedom";
import { renderRunFacts } from "../src/reporting/run-facts-markdown";
import { renderFeedRest } from "../src/reporting/feed-rest-markdown";

async function fixture() {
  const feed = FeedHealthStateRowSchema.parse(await Bun.file(
    new URL("../../../tests/fixtures/feed-ingest-plan/health-field-history.json", import.meta.url),
  ).json());
  const run = PlanRunRowSchema.parse({
    run_id: feed.run_id, date: feed.date, attempt: feed.attempt, started_at: feed.checked_at,
    duration_ms: 1234, status: "completed", failure_code: null, selected_count: 2,
    strategy: "round-robin", dispatch_count: 3, selected_articles_artifact: null,
    api_timings: [], lifecycle_window_days: 31, reliability_floor: 0.5,
    reliability_penalty_enabled: true, evaluated_at: feed.checked_at,
    request_report_closed_days: 7, reliability_window_days: 30, selection_started_at_utc: feed.checked_at,
  });
  return { feed, run };
}

function facts(markdown: string) {
  const { document } = parseHTML(Bun.markdown.html(markdown));
  return Object.fromEntries([...document.querySelectorAll("tbody tr")].map(row => {
    const cells = row.querySelectorAll("td");
    return [cells[1]!.textContent, cells[2]!.textContent];
  }));
}

test("keeps status, identity, attempt and literal assignment values in distinct fact rows", async () => {
  const { feed, run } = await fixture();
  const rows = [feed, { ...feed, date: "2026-10-24", checked_at: "2026-10-24T10:00:00Z" }];
  const before = structuredClone(rows);
  const report = renderRunFacts(run, rows);
  expect(facts(report.markdown)).toMatchObject({
    Status: "completed", Attempt: "1", "Feeds with saved run rows": "1", "Feeds checked": "1",
    "Admitted articles": "6", "Feeds with unavailable admission totals": "0",
    "Chosen articles": "2", "Article assignments": "3", "Assignment strategy": "round-robin",
    "Elapsed planning time (ms)": "1234", "Selection started": "true",
  });
  expect(facts(report.markdown).Run).toBe("2026-10-25-1234");
  expect(rows).toEqual(before);
});

test("keeps admission subtotal separate from unavailable totals and request completeness", async () => {
  const { feed, run } = await fixture();
  const rows = [feed, { ...feed, feed_id: "unresolved", article_candidates: null, counts_complete: false }];
  const report = renderRunFacts(run, rows);
  expect(facts(report.markdown)).toMatchObject({
    "Known admitted articles": "3", "Feeds with unavailable admission totals": "1",
  });
  expect(report.markdown).toContain("exact total unavailable");
  expect(report.markdown).toContain("unresolved");
  expect(report.notice).toContain("3 known admitted articles (1 feed total unavailable)");
  expect(report.notice).toContain("Request counts complete");
  expect(renderRunFacts(run, [{ ...rows[1]!, article_requests: null }]).notice)
    .toContain("Request counts incomplete");
});

test("distinguishes known empty, absent and entirely unknown counts", async () => {
  const { feed, run } = await fixture();
  expect(facts(renderRunFacts(run, []).markdown)).toMatchObject({
    "Admitted articles": "0", "Feeds checked": "0",
  });
  expect(facts(renderRunFacts(run, undefined).markdown)).toMatchObject({
    "Admitted articles": "Not recorded", "Feeds checked": "Not recorded",
  });
  const report = renderRunFacts(run, [{ ...feed, article_candidates: null, feed_reads: null }]);
  expect(facts(report.markdown)).toMatchObject({
    "Known admitted articles": "Not recorded", "Feeds checked": "0*",
  });
  expect(report.markdown).toContain("some check counts are unavailable");
  expect(report.notice).toContain("Admission subtotal unavailable");
  expect(report.notice).not.toContain("Not recorded known admitted articles");
});

test("keeps failed and unstarted selection facts distinct from configuration switches", async () => {
  const { run } = await fixture();
  const report = renderRunFacts({ ...run, status: "failed", failure_code: "PLANNER_EXECUTION_FAILED",
    selection_started_at_utc: null, duration_ms: null }, undefined);
  expect(facts(report.markdown)).toMatchObject({
    Status: "failed", "Failure code": "PLANNER_EXECUTION_FAILED",
    "Selection started": "false", "Elapsed planning time (ms)": "Not recorded",
  });
  expect(facts(report.markdown)).not.toHaveProperty("Selection began at (UTC)");
});

test("shows durable UTC recovery deadlines without inventing schedules from historical counters", async () => {
  const { feed } = await fixture();
  const html = Bun.markdown.html(renderFeedRest({
    revision: "recorded-revision", eligible_feed_ids: [], feeds: [{
      feed_id: "resting-feed", endpoint_key: feed.endpoint_key, status: "resting",
      consecutive_failed_checks: 5, failed_recovery_checks: 2,
      first_confirmed_failure_at: "2026-10-25T00:00:00Z",
      rest_until: "2026-10-30T12:00:00Z", retired_at: null, retirement_reason: null,
    }, {
      feed_id: "unknown-feed", endpoint_key: feed.endpoint_key, status: "unknown",
      consecutive_failed_checks: 0, failed_recovery_checks: 0,
      first_confirmed_failure_at: null, rest_until: null, retired_at: null, retirement_reason: null,
    }, {
      feed_id: "retired-feed", endpoint_key: feed.endpoint_key, status: "retired",
      consecutive_failed_checks: 12, failed_recovery_checks: 7,
      first_confirmed_failure_at: "2026-10-20T00:00:00Z", rest_until: null,
      retired_at: "2026-10-30T00:00:00Z", retirement_reason: "confirmed-recovery-failures",
    }],
  }));
  expect(html).toContain("<td>resting</td><td>5</td><td>2</td>");
  expect(html).toContain("2026-10-30T12:00:00Z");
  expect(html).toContain("2026-10-25T00:00:00Z");
  expect(html).toContain("Unknown availability preserves interrupted work");
  expect(html).toContain("Confirmed HTTP recovery failures met both limits");
  expect(html).not.toContain("skipped logical runs");
  expect(renderFeedRest()).toContain("Current feed availability was not recorded");
});
