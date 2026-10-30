/** Report request spend over closed UTC days without supplying planning evidence. */
import type { FeedHealthRequestFields, SourceSnapshot } from "@idhazh/common-contracts";
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
  gaps?: HealthCapture["uses"]["request_totals"]["gaps"];
  days: readonly { day: string; complete: boolean }[];
  sources: readonly SourceSnapshot[]; now: string; request_report_closed_days: number;
}) {
  const requestDays = closedRequestDays(input.now, input.request_report_closed_days);
  const windowComplete = requestDays.every(day => input.days.find(value => value.day === day)?.complete === true);
  return {
    from_day: requestDays[0]!, through_day: requestDays.at(-1)!, complete: windowComplete,
    feeds: input.sources.map(source => {
      const endpoint = inputEndpointKey(source.feed_url);
      const work = input.rows.filter(row => row.feed_id === source.feed_id
        && row.endpoint_key === endpoint && requestDays.includes(row.date));
      const missing = input.gaps?.some(gap => requestDays.includes(gap.day)
        && (gap.identity === null || (gap.identity.feed_id === source.feed_id && gap.identity.endpoint_key === endpoint)));
      const known = windowComplete && !missing && work.every(row =>
        row.feed_requests !== null && row.article_requests !== null && row.robots_requests !== null);
      const sum = (field: "feed_requests" | "article_requests" | "robots_requests") =>
        !known ? null : work.reduce((total, row) => total + row[field]!, 0);
      return {
        feed_id: source.feed_id, feed_requests: sum("feed_requests"), article_requests: sum("article_requests"),
        robots_requests: sum("robots_requests"), counts_complete: known,
      };
    }),
  };
}
