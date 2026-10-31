/** Build a health row for known unperformed work without inventing a check. */
import { FeedHealthStateRowSchema, FeedLifecycleFieldsSchema } from "@idhazh/common-contracts";
import type { FeedLifecycleFields, SourceSnapshot } from "@idhazh/common-contracts";
import type { SourceHistoryEvidence } from "./read-ledger-history/read-feed-history";
import type { RunContext } from "./resolve-run-context";
import { createUnknownFeedLifecycle } from "./availability/feed-lifecycle";
import { inputEndpointKey } from "./read-ledger-history/health-summary";

export function projectLifecycleFields(source?: SourceHistoryEvidence): FeedLifecycleFields {
  if (source === undefined) return createUnknownFeedLifecycle();
  const { lifecycle, endpoint_key: _endpoint, reliability: _reliability, article_pass_rate: _pass, ...fields } = source;
  return FeedLifecycleFieldsSchema.parse({ ...fields, availability: lifecycle });
}

export function createFeedHealthRow(
  context: RunContext, source: SourceSnapshot, prior: SourceHistoryEvidence | undefined, at: string,
) {
  return FeedHealthStateRowSchema.parse({
    date: at.slice(0, 10), run_id: context.run_id, attempt: context.writer.attempt,
    feed_id: source.feed_id, endpoint_key: inputEndpointKey(source.feed_url),
    checked_at: null, check_request_id: null, check_result: null, permission: "unknown",
    ...projectLifecycleFields(prior), last_failure_code: null, status: null, reliability: prior?.reliability ?? null,
    feed_reads: 0, productive_reads: 0, failed_reads: 0, article_candidates: 0, articles_selected: 0,
    feed_requests: 0, article_requests: 0, robots_requests: 0, counts_complete: true,
    rejection_counts: [], items: null, outcome: null,
  });
}
