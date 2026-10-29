/** Report request spend over closed UTC days without supplying planning evidence. */
import { PlannerRequestReportSchema } from "@idhazh/common-contracts";
import type { FeedHealthRequestFields, PlannerRequestReport, SourceSnapshot } from "@idhazh/common-contracts";
import type { HealthCapture } from "./read-health-capture";
import { inputEndpointKey } from "./health-summary";

const dayMilliseconds = 86_400_000;
export function closedRequestDays(now: string, count: number): string[] {
  const midnight = Date.parse(`${now.slice(0, 10)}T00:00:00Z`);
  return Array.from({ length: count }, (_, index) =>
    new Date(midnight - (count - index) * dayMilliseconds).toISOString().slice(0, 10));
}

export function summarizeRequestReport(input: {
  rows: readonly FeedHealthRequestFields[];
  partial_rows?: HealthCapture["uses"]["request_totals"]["partial_rows"];
  gaps?: HealthCapture["uses"]["request_totals"]["gaps"];
  input_complete?: boolean;
  days: readonly { day: string; complete: boolean }[];
  sources: readonly SourceSnapshot[]; now: string; request_report_closed_days: number;
}): PlannerRequestReport {
  const requestDays = closedRequestDays(input.now, input.request_report_closed_days);
  const missing_days = requestDays.filter(day => input.days.find(value => value.day === day)?.complete !== true);
  const unattributed_days = requestDays.filter(day => input.gaps?.some(gap => gap.day === day && gap.identity === null));
  const input_complete = input.input_complete ?? true;
  const feeds = input.sources.map(source => {
    const endpoint = inputEndpointKey(source.feed_url);
    const work = [...input.rows, ...input.partial_rows ?? []].filter(row => row.feed_id === source.feed_id
      && row.endpoint_key === endpoint && row.date !== undefined && requestDays.includes(row.date));
    function summarize(field: "feed_requests" | "article_requests" | "robots_requests") {
      const known = work.filter(row => typeof row[field] === "number");
      const unknown = work.filter(row => row[field] == null);
      const complete_days = requestDays.filter(day => input_complete && !missing_days.includes(day)
        && !unattributed_days.includes(day) && !unknown.some(row => row.date === day)
        && !input.gaps?.some(gap => gap.day === day && gap.field === field
          && gap.identity?.feed_id === source.feed_id && gap.identity.endpoint_key === endpoint));
      const complete = complete_days.length === requestDays.length;
      return {
        total: !complete && known.length === 0 ? null : known.reduce((sum, row) => sum + row[field]!, 0),
        coverage: {
          status: complete ? "complete" as const : known.length > 0 ? "partial" as const : "none" as const,
          known_records: known.length, unknown_records: unknown.length,
          recorded_days: requestDays.filter(day => known.some(row => row.date === day)), complete_days,
        },
      };
    }
    const feed = summarize("feed_requests");
    const article = summarize("article_requests");
    const robots = summarize("robots_requests");
    return {
      feed_id: source.feed_id, feed_requests: feed.total, article_requests: article.total, robots_requests: robots.total,
      counts_complete: [feed, article, robots].every(counter => counter.coverage.status === "complete"),
      coverage: { feed_requests: feed.coverage, article_requests: article.coverage, robots_requests: robots.coverage },
    };
  });
  return PlannerRequestReportSchema.parse({
    from_day: requestDays[0]!, through_day: requestDays.at(-1)!, missing_days, unattributed_days, input_complete,
    complete: input_complete && missing_days.length === 0 && unattributed_days.length === 0
      && feeds.every(feed => feed.counts_complete), feeds,
  });
}
