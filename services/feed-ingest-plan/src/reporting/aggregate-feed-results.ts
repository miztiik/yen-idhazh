/** How do one run's UTC day rows combine without turning unknown counts into zero? */
import type { FeedHealthStateRow } from "@idhazh/common-contracts";

export const runCounterFields = [
  "articles_selected", "article_candidates", "feed_reads",
  "article_requests", "feed_requests", "robots_requests",
] as const;
type CounterField = typeof runCounterFields[number];
export type FeedResult = { feed_id: string } & Record<CounterField, number | null>;

export function aggregateFeedResults(rows: readonly FeedHealthStateRow[]): FeedResult[] {
  const results = new Map<string, FeedResult>();
  for (const row of rows) {
    const previous = results.get(row.feed_id);
    const result: FeedResult = {
      feed_id: row.feed_id, articles_selected: row.articles_selected,
      article_candidates: row.article_candidates, feed_reads: row.feed_reads,
      article_requests: row.article_requests, feed_requests: row.feed_requests, robots_requests: row.robots_requests,
    };
    for (const field of runCounterFields) {
      result[field] = previous === undefined ? row[field]
        : previous[field] === null || row[field] === null ? null : previous[field]! + row[field]!;
    }
    results.set(row.feed_id, result);
  }
  return [...results.values()];
}

export function compareKnownDescending(left: number | null, right: number | null) {
  if (left === null) return right === null ? 0 : 1;
  return right === null ? -1 : right - left;
}

export function formatDuration(milliseconds: number | null) {
  if (milliseconds === null) return "Not recorded";
  if (milliseconds < 1000) return `${milliseconds} ms`;
  const seconds = milliseconds / 1000;
  if (seconds < 60) return `${Number(seconds.toFixed(2))} s`;
  return `${Math.floor(seconds / 60)} min ${Number((seconds % 60).toFixed(1))} s`;
}
