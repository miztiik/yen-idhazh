/** Accumulate this run's actual feed work by UTC work day without saving operation histories. */
import { FeedHealthStateRowSchema } from "@idhazh/common-contracts";
import type {
  CandidateRejectionRecord, DocumentWorkFact, FeedHealthStateRow,
  FeedOutcomePayload, PlannerRejectionCount, SourceSnapshot, FetchedDocument, SourceArticleOutcome,
} from "@idhazh/common-contracts";
import type { RunContext } from "./resolve-run-context";
import type { SourceHistoryEvidence } from "./read-ledger-history/read-feed-history";
import type { FeedEntry, HarvestArticleResult } from "./harvest-feeds/harvest-types";
import { deriveArticleIdentity, InvalidArticleUrlError } from "./harvest-feeds/article-identity";
import { UnsafeTargetError } from "./harvest-feeds/safe-target";
import { retryableStatus } from "./harvest-feeds/robots-policy";
import { inputEndpointKey } from "./read-ledger-history/health-summary";
import { attributeIngestOutcome } from "./attribute-ingest-outcomes";
import type { FetchResult } from "./harvest-feeds/robots-policy";
import { hasArticleCapture, resolveArticleSourceOutcome } from "./article-source-outcome";

export function createRunHealth(context: RunContext, sources: readonly SourceSnapshot[],
  history: ReadonlyMap<string, SourceHistoryEvidence>,
  admission: { min_words: number; blocked_http_statuses: readonly number[]; tidy_urls: boolean; clock?: () => Date },
  initialRows: readonly FeedHealthStateRow[] = []) {
  const rows = new Map<string, FeedHealthStateRow>();
  const exclusions = new Map<string, PlannerRejectionCount>();
  const pendingReads = new Map<string, FeedHealthStateRow>();
  const sourceById = new Map(sources.map(source => [source.feed_id, source]));
  const captures = new Map<string, {
    feed_id: string; captured_at: string; outcome: SourceArticleOutcome | null;
  }>();
  const articleResults = new Set<string>();
  function row(feed: string, instant: string) {
    const source = sourceById.get(feed);
    if (source === undefined) throw new Error("Observed work names an unconfigured feed");
    const date = instant.slice(0, 10);
    const key = `${date}:${feed}`;
    let value = rows.get(key);
    if (value === undefined) {
      const prior = history.get(feed);
      value = FeedHealthStateRowSchema.parse({
        date, run_id: context.run_id, attempt: context.writer.attempt, feed_id: feed,
        endpoint_key: inputEndpointKey(source.feed_url), checked_at: null, permission: "unknown",
        availability: prior?.lifecycle ?? "unknown", strikes: prior?.strikes ?? null,
        rested_runs: prior?.rested_runs ?? null, last_failure_code: null, status: null,
        reliability: prior?.reliability ?? null, feed_reads: 0, productive_reads: 0, failed_reads: 0,
        article_candidates: 0, articles_selected: 0, feed_requests: 0, article_requests: 0,
        robots_requests: 0, counts_complete: true, rejection_counts: [], items: null, outcome: null,
      });
      rows.set(key, value);
    }
    return value;
  }
  function group(grouped: PlannerRejectionCount, instant: string) {
    const key = JSON.stringify([grouped.feed_id, grouped.subject, grouped.stage, grouped.reason_code, grouped.attribution]);
    const previous = exclusions.get(key);
    if (previous === undefined) exclusions.set(key, grouped);
    else previous.count += grouped.count;
    const target = row(grouped.feed_id, instant);
    const { feed_id: _feed, ...reason } = grouped;
    const held = target.rejection_counts.find(value => value.subject === reason.subject
      && value.stage === reason.stage && value.reason_code === reason.reason_code && value.attribution === reason.attribution);
    if (held === undefined) target.rejection_counts.push(reason);
    else held.count += reason.count;
  }
  function reject(rejection: CandidateRejectionRecord, override?: PlannerRejectionCount["attribution"]) {
    const parserDetail = rejection.details.diagnostics?.detail;
    const typedParserFailure = parserDetail === "parser-timeout" || parserDetail === "parser-cancelled"
      || parserDetail === "parser-failed" ? parserDetail : null;
    const failureCode = rejection.details.diagnostics?.fetch_failure ?? rejection.details.diagnostics?.extraction_failure
      ?? typedParserFailure
      ?? (rejection.drop_reason === "FETCH_FAILED_HTTP" ? "http" : rejection.drop_reason === "FETCH_TIMEOUT" ? "timeout"
        : rejection.drop_reason === "FEED_PARSE_FAILED" ? "malformed-feed" : rejection.drop_reason === "EXTRACT_EMPTY" ? "empty-content" : null);
    const failure = failureCode !== null || ["FETCH_FAILED", "EXTRACT_FAILED", "FETCH_TIMEOUT"].includes(rejection.drop_reason);
    const attribution = failure
      ? attributeIngestOutcome({
        document_kind: rejection.subject, operation: rejection.drop_reason.startsWith("EXTRACT") || rejection.drop_reason === "FEED_PARSE_FAILED" ? "parse" : "fetch",
        outcome: "failed", failure_code: failureCode,
        http_status: rejection.details.http_status ?? null, request_phase: null,
      }) : null;
    const grouped: PlannerRejectionCount = {
      feed_id: rejection.feed_id, subject: rejection.subject, stage: rejection.stage,
      reason_code: rejection.drop_reason, attribution: override !== undefined ? override : attribution === "source" ? "feed"
        : attribution === "unresolved" ? "unknown" : attribution, count: 1,
    };
    group(grouped, rejection.rejected_at);
  }
  for (const original of initialRows) {
    const saved = FeedHealthStateRowSchema.parse(original);
    if (saved.run_id !== context.run_id || saved.attempt !== context.writer.attempt) throw new Error("Initial health belongs to another execution");
    saved.article_candidates = 0;
    saved.rejection_counts = saved.rejection_counts.filter(value => value.subject !== "article" || value.attribution !== "feed");
    rows.set(`${saved.date}:${saved.feed_id}`, saved);
    for (const rejection of saved.rejection_counts) {
      const value = { feed_id: saved.feed_id, ...rejection };
      const key = JSON.stringify([value.feed_id, value.subject, value.stage, value.reason_code, value.attribution]);
      const held = exclusions.get(key);
      if (held === undefined) exclusions.set(key, value);
      else held.count += value.count;
    }
  }
  function captureArticle(id: string, feedId: string, capturedAt: string, outcome: SourceArticleOutcome | null) {
    const previous = captures.get(id);
    if (previous !== undefined && (previous.feed_id !== feedId || previous.captured_at !== capturedAt)) {
      throw new Error("Original article capture changed its source or observation clock");
    }
    if (previous?.outcome != null) return;
    captures.set(id, { feed_id: feedId, captured_at: capturedAt, outcome });
  }
  function snapshots() {
    for (const capture of captures.values()) row(capture.feed_id, capture.outcome?.settled_at ?? capture.captured_at);
    const result = new Map([...rows].map(([key, value]) => [key, structuredClone(value)]));
    for (const capture of captures.values()) {
      const outcome = capture.outcome;
      const target = result.get(`${(outcome?.settled_at ?? capture.captured_at).slice(0, 10)}:${capture.feed_id}`)!;
      if (outcome === null) target.article_candidates = null;
      else if (outcome.disposition === "admitted") {
        if (target.article_candidates !== null) target.article_candidates++;
      } else {
        const stage = outcome.reason_code === "REJECTED_SCREENING_MIN_WORDS" || outcome.reason_code === "PAYWALL_OR_BLOCKED"
          ? "screen-article-candidates" : "harvest-feeds";
        const held = target.rejection_counts.find(value => value.subject === "article" && value.stage === stage
          && value.reason_code === outcome.reason_code && value.attribution === "feed");
        if (held === undefined) target.rejection_counts.push({
          subject: "article", stage, reason_code: outcome.reason_code!, attribution: "feed", count: 1,
        });
        else held.count++;
      }
    }
    return [...result.values()].map(value => FeedHealthStateRowSchema.parse({
      ...value, counts_complete: [
        value.feed_reads, value.productive_reads, value.failed_reads, value.article_candidates,
        value.articles_selected, value.feed_requests, value.article_requests, value.robots_requests,
      ].every(count => count !== null),
    }));
  }
  return {
    observe(fact: DocumentWorkFact) {
      if (fact.run_id !== context.run_id || fact.attempt !== context.writer.attempt) throw new Error("Work fact belongs to another run attempt");
      if (fact.feed_id === null || fact.operation !== "attempt") return;
      const target = row(fact.feed_id, fact.occurred_at);
      const field = fact.request_phase === "robots" ? "robots_requests"
        : fact.document_kind === "feed" ? "feed_requests" : "article_requests";
      if (fact.request_coverage !== "complete" || fact.dispatched_request_count === null) {
        target.counts_complete = false;
        target[field] = null;
      } else if (target[field] !== null) target[field] += fact.dispatched_request_count;
    },
    pendingFeed(feedId: string, fetched: FetchResult, checkedAt: string) {
      const target = row(feedId, checkedAt);
      pendingReads.set(feedId, target);
      target.checked_at = checkedAt;
      target.permission = fetched.robots ?? "unknown";
      target.status = fetched.http_status;
      target.feed_reads = fetched.failure === null ? null : fetched.failure === "robots-denied" || fetched.failure === "robots-unknown" ? 0 : 1;
      target.items = fetched.failure === null ? null : 0;
      target.outcome = fetched.failure === null ? "ok" : fetched.failure === "robots-denied" || fetched.failure === "robots-unknown"
        ? "robots_denied" : fetched.failure === "unsafe-target" ? "blocked"
        : fetched.failure === "http" && fetched.http_status !== null && !retryableStatus.has(fetched.http_status) ? "permanent" : "transient";
      target.productive_reads = fetched.failure === null ? null : 0;
      target.failed_reads = fetched.failure === null ? null : target.feed_reads;
      target.counts_complete = fetched.failure !== null
        && target.feed_requests !== null && target.article_requests !== null && target.robots_requests !== null;
    },
    unknownRequests(feedId: string, instant: string) {
      const target = row(feedId, instant);
      target.feed_requests = null;
      target.article_requests = null;
      target.robots_requests = null;
      target.counts_complete = false;
    },
    restoreRequests(artifact: FetchedDocument) {
      if (artifact.attempts.length === 0) {
        const target = row(artifact.feed_id, artifact.observation.occurred_at);
        target.feed_requests = null;
        target.article_requests = null;
        target.robots_requests = null;
        target.counts_complete = false;
      }
      for (const [index, attempt] of artifact.attempts.entries()) {
        const instant = artifact.attempt_observations[index]!.occurred_at;
        const target = row(artifact.feed_id, instant);
        if (attempt.phase === "validation") continue;
        const field = attempt.phase === "robots" ? "robots_requests" : artifact.fetch_item_type === "feed" ? "feed_requests" : "article_requests";
        if (attempt.http_status === null) {
          target[field] = null;
          target.counts_complete = false;
        } else if (target[field] !== null) target[field]++;
      }
    },
    feed(outcome: FeedOutcomePayload, entries: readonly FeedEntry[], checkedAt: string, fetched?: FetchResult) {
      const target = row(outcome.source.feed_id, checkedAt);
      const pending = pendingReads.get(outcome.source.feed_id);
      if (pending !== undefined && pending !== target) {
        pending.checked_at = null;
        pending.items = null;
        pending.outcome = null;
        pending.feed_reads = 0;
        pending.productive_reads = 0;
        pending.failed_reads = 0;
        pending.counts_complete = pending.feed_requests !== null && pending.article_requests !== null && pending.robots_requests !== null;
      }
      pendingReads.delete(outcome.source.feed_id);
      const failure = fetched?.failure ?? outcome.diagnostics?.fetch_failure ?? null;
      const status = fetched?.http_status ?? outcome.diagnostics?.http_status ?? null;
      const skipped = outcome.fetch_status === "not_requested";
      const robots = failure === "robots-denied" || failure === "robots-unknown";
      target.checked_at = checkedAt;
      target.permission = fetched?.robots ?? outcome.diagnostics?.robots ?? "unknown";
      target.status = status;
      target.items = new Set(entries.flatMap(entry => {
        if (entry.link === null) return [];
        try { return [deriveArticleIdentity(entry.link, admission).url_key]; }
        catch (error) {
          if (error instanceof InvalidArticleUrlError || error instanceof UnsafeTargetError) return [];
          throw error;
        }
      })).size;
      target.outcome = skipped ? "skipped" : robots ? "robots_denied" : failure === "unsafe-target" ? "blocked"
        : failure === "http" && status !== null ? retryableStatus.has(status) ? "transient" : "permanent"
        : outcome.fetch_status === "success" ? "ok" : "transient";
      target.feed_reads = skipped || robots ? 0 : 1;
      const productive = target.outcome === "ok" && target.items > 0;
      target.productive_reads = productive ? 1 : 0;
      target.failed_reads = !skipped && !robots && !productive ? 1 : 0;
      target.counts_complete = target.feed_requests !== null && target.article_requests !== null && target.robots_requests !== null;
      target.last_failure_code = outcome.rejection_reason;
      if (outcome.rejection_reason !== null) {
        const parserDetail = outcome.diagnostics?.detail;
        const typedParserFailure = parserDetail === "parser-timeout" || parserDetail === "parser-cancelled"
          || parserDetail === "parser-failed" ? parserDetail : null;
        const failureCode = typedParserFailure ?? (outcome.parse_status === "failure" ? "malformed-feed" : failure);
        const attribution = failureCode === null ? null : attributeIngestOutcome({
          document_kind: "feed", operation: outcome.parse_status === "failure" ? "parse" : "fetch",
          outcome: "failed", failure_code: failureCode, http_status: status, request_phase: null,
        });
        group({
          feed_id: outcome.source.feed_id, subject: "feed", stage: "harvest-feeds",
          reason_code: outcome.rejection_reason, count: 1,
          attribution: attribution === "source" ? "feed" : attribution === "unresolved" ? "unknown" : attribution,
        }, checkedAt);
      }
    },
    article(article: HarvestArticleResult, captureId = article.observation.candidate_id, settled?: SourceArticleOutcome | null) {
      if (articleResults.has(captureId)) return;
      articleResults.add(captureId);
      const outcome = settled === undefined ? resolveArticleSourceOutcome(article, admission.min_words,
        admission.blocked_http_statuses, (admission.clock?.() ?? new Date()).toISOString()) : settled;
      if (hasArticleCapture(article)) {
        const feedId = article.candidate?.feed_id ?? article.rejection?.feed_id;
        if (feedId === undefined) throw new Error("Captured article lacks its configured source");
        captureArticle(captureId, feedId, article.observation.observed_at, outcome);
      }
      if (article.rejection !== null && outcome?.disposition !== "source_refused") reject(article.rejection);
    },
    captureArticle,
    reject,
    rows: snapshots,
    exclusions: () => {
      const result = new Map([...exclusions].map(([key, value]) => [key, { ...value }]));
      for (const saved of snapshots()) for (const reason of saved.rejection_counts) {
        if (reason.subject !== "article" || reason.attribution !== "feed") continue;
        const value = { feed_id: saved.feed_id, ...reason };
        const key = JSON.stringify([value.feed_id, value.subject, value.stage, value.reason_code, value.attribution]);
        const held = result.get(key);
        if (held === undefined) result.set(key, value);
        else held.count += value.count;
      }
      return [...result.values()];
    },
  };
}
