/** Does request coverage refuse complete claims that its days and counters cannot support? */
import { expect, test } from "bun:test";
import { PlannerRequestReportSchema } from "../src/index";

function fixture() {
  const day = "2026-10-25";
  const coverage = { status: "complete" as const, known_records: 1, unknown_records: 0,
    recorded_days: [day], complete_days: [day] };
  return {
    from_day: day, through_day: day, complete: true,
    input_complete: true, missing_days: [], unattributed_days: [],
    feeds: [{ feed_id: "recorded-feed", feed_requests: 2, article_requests: 4, robots_requests: 0,
      counts_complete: true, coverage: { feed_requests: coverage, article_requests: coverage, robots_requests: coverage } }],
  };
}
test("accepts independent complete, partial and absent totals with explicit record coverage", () => {
  const value = fixture();
  expect(PlannerRequestReportSchema.parse(value)).toEqual(value);
  const feed = value.feeds[0]!;
  const partial = { ...value, complete: false, feeds: [{
    ...feed, counts_complete: false, article_requests: 4, robots_requests: null,
    coverage: { ...feed.coverage,
      article_requests: { ...feed.coverage.article_requests, status: "partial" as const, unknown_records: 2, complete_days: [] },
      robots_requests: { status: "none" as const, known_records: 0, unknown_records: 1, recorded_days: [], complete_days: [] },
    },
  }] };
  expect(PlannerRequestReportSchema.parse(partial)).toEqual(partial);
});
test("rejects false completeness, missing coverage and unknown values disguised as measured zero", () => {
  const value = fixture();
  const feed = value.feeds[0]!;
  for (const invalid of [
    { ...value, input_complete: false },
    { ...value, missing_days: [value.from_day] },
    { ...value, unattributed_days: [value.from_day] },
    { ...value, feeds: [feed, feed] },
    { ...value, feeds: [{ ...feed, coverage: undefined }] },
    { ...value, feeds: [{ ...feed, feed_requests: null }] },
    { ...value, feeds: [{ ...feed, coverage: { ...feed.coverage,
      feed_requests: { ...feed.coverage.feed_requests, unknown_records: 1 } } }] },
    { ...value, feeds: [{ ...feed, coverage: { ...feed.coverage,
      feed_requests: { ...feed.coverage.feed_requests, complete_days: ["2026-10-26"] } } }] },
    { ...value, feeds: [{ ...feed, coverage: { ...feed.coverage,
      feed_requests: { ...feed.coverage.feed_requests, complete_days: [value.from_day, value.from_day] } } }] },
    { ...value, feeds: [{ ...feed, coverage: { ...feed.coverage,
      feed_requests: { ...feed.coverage.feed_requests, known_records: 0, recorded_days: [] } } }] },
  ]) expect(PlannerRequestReportSchema.safeParse(invalid).success).toBe(false);
  const absent = { status: "none", known_records: 0, unknown_records: 1, recorded_days: [], complete_days: [] };
  expect(PlannerRequestReportSchema.safeParse({ ...value, complete: false, feeds: [{
    ...feed, counts_complete: false, feed_requests: 0, coverage: { ...feed.coverage, feed_requests: absent },
  }] }).success).toBe(false);
});
