/** How do saved feed-health rows group fetch and extraction failures? */
import { HarvestArticleFailureReasonSchema } from "../../../../packages/common-contracts/src/index";
import type { FeedHealthStateRow } from "../../../../packages/common-contracts/src/index";
import { escapeMarkdown } from "./markdown-format";

type FailureGroup = Readonly<{
  reason: string;
  status: number | null;
  attribution: "feed" | "pipeline" | "unknown";
  count: number;
  feedIds: readonly string[];
}>;

export function renderFailureEvidence(feeds: readonly FeedHealthStateRow[] | undefined) {
  const articleFailures = groupFailures(feeds, "article");
  const feedFailures = groupFailures(feeds, "feed");
  const unavailableAdmissions = feeds?.filter(feed => feed.article_candidates === null).map(feed => feed.feed_id) ?? [];
  const admissionNote = feeds === undefined
    ? "Admission availability is not recorded because feed-health evidence is unavailable."
    : feeds.length === 0
      ? "No feed-health rows were recorded, so admission totals are unavailable."
      : unavailableAdmissions.length
        ? `Admission totals are unavailable for ${unavailableAdmissions.length} feeds named in Table A; failures do not make other feed totals unavailable.`
        : "Admission totals are available for all saved feed rows; a failure does not make an admission total unavailable.";
  const rows = [
    ["article", articleFailures, "J", "Article failures"],
    ["feed", feedFailures, "K", "Feed failures"],
  ] as const;
  const markdown = [
    "<details>", "<summary>Failure evidence</summary>", "",
    ...rows.flatMap(([, groups, table, title]) => [
      `## Table ${table} - ${title}`, "",
      "| Id | Failure reason | HTTP status / attribution | Failures | Feed IDs | Cause evidence |",
      "| --- | --- | --- | --- | --- | --- |",
      ...groups.map((group, index) =>
        `| ${table}${index + 1} | ${escapeMarkdown(group.reason)} | ${group.status ?? "Not recorded"} / ${group.attribution} | ${countLabel(group.count)} | ${group.feedIds.map(escapeMarkdown).join(", ")} | ${escapeMarkdown(describeEvidence(group))} |`),
      ...(groups.length ? [] : ["", feeds === undefined
        ? "Failure evidence is unavailable."
        : `No attributed ${title.toLowerCase()} were recorded.`]),
      "",
    ]),
    admissionNote,
    "",
    "A confirmed HTTP status is an observed response, not its underlying cause. Inferred means saved attribution points to the feed or pipeline; the trigger is not recorded. Missing means the report input has no detailed cause or status. Article HTTP statuses and feed or article URLs are not present in these report inputs.",
    "", "</details>",
  ].join("\n");
  const articleCount = articleFailures.reduce((sum, group) => sum + group.count, 0);
  const feedCount = feedFailures.reduce((sum, group) => sum + group.count, 0);
  return {
    markdown,
    notice: feeds === undefined ? "Failure evidence was not recorded."
      : `${articleCount} article failures in ${articleFailures.length} groups; `
        + `${feedCount} feed failures in ${feedFailures.length} groups; `
        + `${unavailableAdmissions.length} feeds have unavailable admission totals.`,
  };
}

function groupFailures(feeds: readonly FeedHealthStateRow[] | undefined, subject: "article" | "feed") {
  const groups = new Map<string, {
    reason: string; status: number | null; attribution: "feed" | "pipeline" | "unknown";
    count: number; feedIds: Set<string>;
  }>();
  for (const feed of feeds ?? []) {
    for (const failure of feed.rejection_counts) {
      if (failure.subject !== subject || failure.attribution === null) continue;
      if (subject === "article" && !HarvestArticleFailureReasonSchema.safeParse(failure.reason_code).success) continue;
      const status = subject === "feed" && failure.reason_code === feed.last_failure_code ? feed.status : null;
      const key = JSON.stringify([failure.reason_code, status, failure.attribution]);
      const group = groups.get(key) ?? {
        reason: failure.reason_code, status, attribution: failure.attribution, count: 0, feedIds: new Set<string>(),
      };
      group.count += failure.count;
      group.feedIds.add(feed.feed_id);
      groups.set(key, group);
    }
  }
  return [...groups.values()]
    .map(group => ({ ...group, feedIds: [...group.feedIds].sort() }))
    .sort((left, right) => right.count - left.count || left.reason.localeCompare(right.reason)
      || compareStatus(left.status, right.status) || left.attribution.localeCompare(right.attribution));
}

function describeEvidence(group: FailureGroup) {
  if (group.status !== null) return `Confirmed HTTP ${group.status}; lower-level cause not recorded`;
  if (group.reason === "FETCH_TIMEOUT") return "Confirmed timeout; detailed cause not recorded";
  if (group.reason === "EXTRACT_EMPTY") return "Confirmed empty extraction; content cause not recorded";
  if (group.reason === "EXTRACT_FAILED") return "Extraction failure recorded; detailed cause not recorded";
  if (group.reason === "FETCH_FAILED_HTTP") return "HTTP failure recorded; response status not recorded";
  if (group.attribution === "unknown") return "Cause unavailable; only the failure reason is recorded";
  return `Inferred from ${group.attribution} attribution; underlying trigger not recorded`;
}

function countLabel(count: number) {
  return `${count} ${count === 1 ? "failure" : "failures"}`;
}

function compareStatus(left: number | null, right: number | null) {
  if (left === null) return right === null ? 0 : 1;
  return right === null ? -1 : left - right;
}
