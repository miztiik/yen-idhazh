/** Which current failures, paused coverage and evidence gaps need operator attention? */
import { HarvestArticleFailureReasonSchema } from "@idhazh/common-contracts";
import type { FeedHealthStateRow, PlanRunRow, RejectedArticleRow, FeedHealthRestFields } from "@idhazh/common-contracts";
import type { z } from "zod";
import { isDeepStrictEqual } from "node:util";
import type { FeedAvailabilitySnapshotSchema } from "../api/feed-health-state.schema";
import { escapeMarkdown } from "./markdown-format";
import { describeReason } from "./selection-exclusions-markdown";

type AttentionRow = { scope: string; problem: string; impact: string; period: string; next: string };
export type ReportFailureEvidence = Readonly<{
  articles?: readonly RejectedArticleRow[];
  earlier_checks?: readonly FeedHealthRestFields[];
  gaps?: readonly [string, string, string][];
}>;

function describeArticleFailure(article: RejectedArticleRow) {
  const facts = [
    article.http_status === null ? "article response status unavailable" : `article HTTP ${article.http_status}`,
    ...(article.fetch_failure === null ? [] : [`fetch result: ${article.fetch_failure}`]),
    ...(article.error_code === null ? [] : [`transport code: ${article.error_code}`]),
    ...(article.robots === null ? [] : [`robots permission: ${article.robots}`]),
    ...(article.robots_http_status === null ? [] : [`robots HTTP ${article.robots_http_status}`]),
    ...(article.robots_failure === null ? [] : [`robots result: ${article.robots_failure}`]),
  ];
  return `${describeReason(article.reason_code)} (${facts.join("; ")})`;
}

function distinctArticleFailures(articles: readonly RejectedArticleRow[]) {
  const distinct = new Map<string, RejectedArticleRow>();
  for (const article of articles) {
    if (article.stage !== "harvest-feeds" || !HarvestArticleFailureReasonSchema.safeParse(article.reason_code).success) continue;
    const key = JSON.stringify([article.run_id, article.attempt,
      article.candidate_id ?? [article.feed_id, article.url_key]]);
    const previous = distinct.get(key);
    if (previous !== undefined && !isDeepStrictEqual(previous, article)) {
      throw new Error("Conflicting terminal article failure evidence");
    }
    distinct.set(key, article);
  }
  return [...distinct.values()];
}

function describeCheck(check: FeedHealthRestFields) {
  const names = {
    "valid-feed": "Valid feed response", "confirmed-http-failure": "Confirmed feed HTTP failure",
    "other-http-failure": "Feed HTTP failure", timeout: "Feed request timed out",
    robots: "Feed robots restriction", "transport-unknown": "Feed transport failure",
    "local-failure": "Local feed-check failure", interrupted: "Feed check interrupted",
  };
  const http = check.check_result === "confirmed-http-failure" || check.check_result === "other-http-failure";
  return `${names[check.check_result!]}${http && check.status !== null ? ` (feed HTTP ${check.status})` : ""}`;
}

export function renderFailureEvidence(
  feeds: readonly FeedHealthStateRow[] | undefined,
  availability?: z.infer<typeof FeedAvailabilitySnapshotSchema>,
  run?: PlanRunRow,
  gaps: readonly [string, string, string][] = [],
  evidence?: ReportFailureEvidence,
) {
  const rows: AttentionRow[] = [];
  const addGap = (scope: string, problem: string, impact: string) =>
    rows.push({ scope, problem, impact,
      period: scope === "Historical evidence" ? "Earlier evidence: closed UTC days" : "This run",
      next: "Not recorded" });
  for (const [scope, problem, impact] of gaps) addGap(scope, problem, impact);
  for (const [scope, problem, impact] of evidence?.gaps ?? []) addGap(scope, problem, impact);
  if (run?.failure_code) addGap("Run", run.failure_code, `Planning ${run.status}; completion not established`);
  if (feeds === undefined) addGap("Run", "Feed work evidence unavailable", "Checks, failures and article totals cannot be established");
  const failures = new Map<string, AttentionRow & { count: number; dates: Set<string> }>();
  const detailed = distinctArticleFailures(evidence?.articles ?? []);
  const remaining = new Map<string, number>();
  const reasonKey = (feed: string, stage: string, reason: string) => JSON.stringify([feed, stage, reason]);
  for (const article of detailed) {
    const key = reasonKey(article.feed_id, article.stage, article.reason_code);
    remaining.set(key, (remaining.get(key) ?? 0) + 1);
    const problem = describeArticleFailure(article);
    const groupKey = JSON.stringify([article.feed_id, problem]);
    const group = failures.get(groupKey) ?? {
      scope: article.feed_id, problem, impact: "", period: "", next: "Not recorded",
      count: 0, dates: new Set<string>(),
    };
    group.count++;
    group.dates.add(article.date);
    group.impact = `${group.count} affected ${group.count === 1 ? "article" : "articles"}; underlying cause unavailable`;
    failures.set(groupKey, group);
  }
  for (const feed of feeds ?? []) {
    for (const failure of feed.rejection_counts) {
      if (failure.attribution === null || (failure.subject === "article"
        && !HarvestArticleFailureReasonSchema.safeParse(failure.reason_code).success)) continue;
      const keyForReason = reasonKey(feed.feed_id, failure.stage, failure.reason_code);
      const covered = failure.subject === "article" ? Math.min(failure.count, remaining.get(keyForReason) ?? 0) : 0;
      if (covered) remaining.set(keyForReason, remaining.get(keyForReason)! - covered);
      const count = failure.count - covered;
      if (count === 0) continue;
      const status = failure.subject === "feed" && feed.checked_at !== null && feed.check_request_id !== null
        && (feed.check_result === "confirmed-http-failure" || feed.check_result === "other-http-failure")
        && failure.reason_code === feed.last_failure_code ? feed.status : null;
      const unknownArticleStatus = failure.subject === "article" && failure.reason_code === "FETCH_FAILED_HTTP";
      const problem = `${describeReason(failure.reason_code)}${status === null ? "" : ` (HTTP ${status})`}${unknownArticleStatus
        ? " (response status unavailable in report input)" : ""}`;
      const key = JSON.stringify([feed.feed_id, failure.subject, problem, failure.attribution]);
      const group = failures.get(key) ?? {
        scope: feed.feed_id, problem, impact: "", period: "", next: "Not recorded",
        count: 0, dates: new Set<string>(),
      };
      group.count += count;
      group.dates.add(feed.date);
      group.impact = `${group.count} recorded ${failure.subject} ${group.count === 1 ? "failure" : "failures"}; underlying cause unavailable`;
      failures.set(key, group);
    }
  }
  for (const group of failures.values()) {
    rows.push({ ...group, period: `This run: ${[...group.dates].sort().join(", ")} UTC` });
  }
  if (availability === undefined) addGap("Run", "Feed availability evidence unavailable", "Paused coverage and next checks cannot be established");
  for (const feed of availability?.feeds ?? []) {
    if (feed.availability === "eligible" && feed.availability_complete) continue;
    const paused = feed.availability === "resting" || feed.availability === "retired";
    const checks = (evidence?.earlier_checks ?? []).filter(check =>
      check.feed_id === feed.feed_id && check.endpoint_key === feed.endpoint_key
      && check.checked_at !== null && check.check_request_id !== null && check.check_result !== null
      && feed.availability_updated_at !== null
      && Date.parse(check.checked_at) === Date.parse(feed.availability_updated_at)
      && (run === undefined || ((check.run_id !== run.run_id || check.attempt !== run.attempt)
        && Date.parse(check.checked_at) <= Date.parse(run.started_at))));
    const distinctChecks = new Map<string | null, FeedHealthRestFields>();
    for (const check of checks) {
      const previous = distinctChecks.get(check.check_request_id);
      if (previous !== undefined && !isDeepStrictEqual(previous, check)) {
        throw new Error("Conflicting saved feed-check evidence");
      }
      distinctChecks.set(check.check_request_id, check);
    }
    const earlier = distinctChecks.size === 1 ? [...distinctChecks.values()][0] : undefined;
    const currentRows = (feeds ?? []).filter(row => row.feed_id === feed.feed_id && row.endpoint_key === feed.endpoint_key);
    const current = currentRows.some(row => row.checked_at !== null || (row.feed_reads !== null && row.feed_reads > 0));
    const knownZero = currentRows.length > 0 && currentRows.every(row => row.feed_reads === 0 && row.checked_at === null);
    rows.push({
      scope: feed.feed_id,
      problem: paused ? `Coverage paused: ${feed.availability}; ${earlier === undefined
        ? "historical cause unavailable" : `saved earlier check: ${describeCheck(earlier)}`}`
        : "Availability evidence incomplete",
      impact: paused ? (current ? "Paused after this run's feed work; not an additional failure"
        : knownZero ? "No new feed check while paused; not a new HTTP failure"
        : "Current feed-check count unavailable; saved pause is not a new HTTP failure")
        : "Earlier history incomplete; supported deadlines retained",
      period: earlier !== undefined ? `Saved earlier check at ${earlier.checked_at} UTC`
        : feed.availability_updated_at === null ? "Earlier evidence: time unavailable"
        : `Saved state at ${feed.availability_updated_at} UTC`,
      next: feed.rest_until ?? (feed.availability === "retired" ? "None: retired" : "Not recorded"),
    });
  }
  const missing = [...new Set(feeds?.filter(feed => feed.article_candidates === null).map(feed => feed.feed_id))].sort();
  if (missing.length) addGap(missing.join(", "), "Technical admission totals unavailable", "Known subtotal is not an exact run total");
  rows.sort((a, b) => a.scope.localeCompare(b.scope) || a.problem.localeCompare(b.problem));
  return {
    markdown: [
      "## Table B - Needs attention", "",
      ...(rows.length ? [
        "| Id | Feed or scope | Problem | Observed impact | Evidence period | Next eligible check (UTC) |",
        "| --- | --- | --- | --- | --- | --- |",
        ...rows.map((item, index) => `| B${index + 1} | ${[item.scope, item.problem, item.impact, item.period, item.next].map(escapeMarkdown).join(" | ")} |`),
        "", "An eligible check is not a scheduled request. A saved HTTP status is a response, not an underlying cause. Robots responses describe automated-access rules, not the article. Terminal article failures are counted once, not once per retry.",
      ] : ["No recorded problems in the supplied run and availability evidence."]),
    ].join("\n"),
    notice: `${rows.length} attention items in saved evidence.`,
  };
}
