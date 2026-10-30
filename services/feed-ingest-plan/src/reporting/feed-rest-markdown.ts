/** Which recorded feed states explain rest and retry without inventing a schedule? */
import { escapeMarkdown } from "./markdown-format";
import type { z } from "zod";
import type { FeedAvailabilitySnapshotSchema } from "../api/feed-health-state.schema";

export function renderFeedRest(availability?: z.infer<typeof FeedAvailabilitySnapshotSchema>) {
  const rows = [...(availability?.feeds ?? [])].sort((a, b) => a.feed_id.localeCompare(b.feed_id));
  return [
    "<details>", "<summary>Feed rest and retry</summary>", "",
    "## Table I - Feed rest and retry", "",
    "| Id | Feed | Availability | Consecutive failed checks | Qualifying recovery failures | First confirmed failure (UTC) | Next eligible check (UTC) | Retired (UTC) | Retirement reason |",
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ...rows.map((feed, index) =>
      `| I${index + 1} | ${escapeMarkdown(feed.feed_id)} | ${feed.status} | ${feed.consecutive_failed_checks} | ${feed.failed_recovery_checks} | ${feed.first_confirmed_failure_at ?? "None"} | ${feed.rest_until ?? "None"} | ${feed.retired_at ?? "None"} | ${feed.retirement_reason === null ? "None" : "Confirmed HTTP recovery failures met both limits"} |`),
    ...(rows.length ? [] : ["", availability === undefined
      ? "Current feed availability was not recorded. Historical health rows do not establish a UTC retry deadline."
      : "Current feed availability was recorded with no feed rows."]),
    "", "A check becomes eligible on the first invocation at or after its UTC deadline. An eligible check is not a scheduled request.",
    "Retirement requires both configured gates and a new confirmed failing recovery. A valid parsed feed, even empty, clears the failure episode.",
    ...(rows.some(feed => feed.status === "unknown") ? [
      "", "Unknown availability preserves interrupted work. An operator must resolve it before another check; it is not counted as a source failure.",
    ] : []),
    "", "</details>",
  ].join("\n");
}
