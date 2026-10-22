/** What did each configured source actually contribute before publication exists? */
import { DropReasonCountSchema, FEED_INGEST_AUDIT_VERSION, FiniteSchema, PositiveCountSchema, SourceRunRecordSchema } from "@idhazh/common-contracts";
import type { DropReasonCount, SourceRunRecord, LedgerCompletionEvidence } from "@idhazh/common-contracts";
import type { FeedPlanResult } from "../run-feed-plan";
import type { StageMembership } from "./stage-membership";
import { requireSame } from "./stage-membership";

export type SourceRunSummary = Omit<SourceRunRecord,
  "version" | "observation_phase" | "expected_source_count" | "completion_evidence">;

export function deriveSourceRunSummaries(result: FeedPlanResult, membership: StageMembership): SourceRunSummary[] {
  const { context, evidence } = result;
  return membership.sources.map(source => {
    const id = source.source_id;
    const outcome = evidence.harvest.feed_outcomes.find(row => row.source.source_id === id);
    if (outcome === undefined) throw new Error(`source.${id}.feed_outcome: missing observation`);
    const count = (items: StageMembership["eligible"]) => items.filter(candidate => candidate.source_id === id).length;
    const drops = membership.rejections.filter(row => row.source_id === id);
    const dropCounts = new Map<string, DropReasonCount>();
    for (const row of drops) {
      const key = `${row.subject}:${row.stage}:${row.drop_reason}`;
      const previous = dropCounts.get(key);
      dropCounts.set(key, DropReasonCountSchema.parse({
        subject: row.subject, stage: row.stage, reason: row.drop_reason, count: (previous?.count ?? 0) + 1,
      }));
    }

    const failures = drops.filter(row => row.subject === "feed" && row.drop_reason !== "SOURCE_INACTIVE" && row.drop_reason !== "FEED_EMPTY");
    const lastFailure = failures.toSorted((a, b) => b.rejected_at.localeCompare(a.rejected_at))[0];
    const operational = evidence.curation.input.filter(article => article.candidate.source_id === id)
      .map(article => article.evidence.operational);
    const history = operational[0] ?? null;
    for (const measured of operational) requireSame(measured, history, `source.${id}.operational_history`);
    if (history !== null) {
      FiniteSchema.min(0).max(1).parse(history.success_fraction);
      PositiveCountSchema.parse(history.attempted);
      PositiveCountSchema.parse(history.window_days);
    }
    return {
      date: context.date, correlation_id: context.correlation_id,
      run_id: context.run_id, attempt: context.writer.attempt,
      source_id: id, source, status: source.status,
      fetch_status: outcome.fetch_status, parse_status: outcome.parse_status,
      parsed_count: outcome.parsed_count, harvested_count: outcome.harvested_count,
      fresh_count: count(membership.freshness),
      duplicate_count: evidence.curation.carriers.suppressed.filter(row => row.article.candidate.source_id === id).length,
      eligible_count: count(membership.eligible), normalized_count: count(membership.normalized),
      selected_count: count(membership.selected), published_count: null, lead_count: null,
      drop_reasons: [...dropCounts.values()],
      fetch_duration_ms: outcome.fetch_duration_ms, parse_duration_ms: outcome.parse_duration_ms,
      last_failure_at: lastFailure?.rejected_at ?? null, last_failure_reason: lastFailure?.drop_reason ?? null,
      history_success_fraction: history?.success_fraction ?? null,
      history_success_attempts: history?.attempted ?? null, history_window_days: history?.window_days ?? null,
      observed_at: context.now,
    };
  });
}

export function completePlanningSources(
  summaries: readonly SourceRunSummary[], evidence: readonly LedgerCompletionEvidence[],
): SourceRunRecord[] {
  if (summaries.length === 0 || new Set(summaries.map(row => row.source_id)).size !== summaries.length) {
    throw new Error("Planning completion requires one recorded outcome per configured source");
  }
  return summaries.map(row => SourceRunRecordSchema.parse({
    ...row, version: FEED_INGEST_AUDIT_VERSION, observation_phase: "plan_complete", expected_source_count: summaries.length,
    completion_evidence: evidence,
  }));
}
