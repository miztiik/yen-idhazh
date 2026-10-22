/** Which source diversity readings are supported by this run's recorded memberships? */
import {
  CONTRACT_VERSION, FEED_INGEST_AUDIT_VERSION, DiversityMetricRowSchema, FeedMetricsConfigSchema,
} from "@idhazh/common-contracts";
import type { DiversityMetricRow, FeedIngestCandidate } from "@idhazh/common-contracts";
import type { FeedPlanResult } from "../run-feed-plan";
import type { StageMembership } from "./stage-membership";

export function validateCounts(counts: readonly number[], field = "counts"): number {
  let total = 0;
  for (const [index, count] of counts.entries()) {
    if (!Number.isSafeInteger(count) || count < 0) throw new Error(`${field}.${index}: expected a nonnegative safe integer`);
    total += count;
    if (!Number.isSafeInteger(total)) throw new Error(`${field}: total exceeds the safe integer range`);
  }
  return total;
}

export function effectiveSources(counts: readonly number[]): number {
  const total = validateCounts(counts);
  if (total === 0) return 0;
  return Math.exp(-counts.reduce((sum, count) => {
    const share = count / total;
    return count === 0 ? sum : sum + share * Math.log(share);
  }, 0));
}

export function sourceGini(counts: readonly number[]): number | null {
  const total = validateCounts(counts);
  if (total === 0) return null;
  const sorted = counts.toSorted((a, b) => a - b);
  const difference = sorted.reduce((sum, value, index) => sum + (2 * index - sorted.length + 1) * value, 0);
  return difference / (sorted.length * total);
}

export function measuredRatio(numerator: number, denominator: number, field: string): number | null {
  validateCounts([numerator, denominator], field);
  if (numerator > denominator) throw new Error(`${field}.numerator: exceeds denominator`);
  return denominator === 0 ? null : numerator / denominator;
}

export function topSourceShare(counts: readonly number[], count: number) {
  if (!Number.isSafeInteger(count) || count < 1) throw new Error(`metrics.top_source_counts.${count}: top_k must be a positive safe integer`);
  const total = validateCounts(counts);
  const numerator = counts.toSorted((a, b) => b - a).slice(0, count).reduce((sum, value) => sum + value, 0);
  return { numerator, denominator: total, value: measuredRatio(numerator, total, "top_source_concentration") };
}

function sourceCounts(items: readonly FeedIngestCandidate[], active: readonly string[]): number[] {
  const counts = new Map(active.map(id => [id, 0]));
  for (const item of items) {
    if (!counts.has(item.source_id)) throw new Error(`candidate.${item.candidate_id}.source_id: not an active source in this run`);
    counts.set(item.source_id, counts.get(item.source_id)! + 1);
  }
  return [...counts.values()];
}

export function createMetricTemplate(
  context: { date: string; correlation_id: string; run_id: string; now: string },
  configSha256: string, sourceCount: number | null,
): DiversityMetricRow {
  return {
    version: FEED_INGEST_AUDIT_VERSION, date: context.date, correlation_id: context.correlation_id, run_id: context.run_id,
    metric: "effective_number_of_sources", basis: "selected", as_of: context.now,
    window_start: null, window_end: null, dimension: "source", stage: null, window_days: null,
    dimension_value: null, value: null, unit: "sources", before_value: null, after_value: null,
    numerator: null, denominator: null, item_count: null, source_count: sourceCount,
    history_coverage_days: null, history_required_days: null,
    algorithm_version: CONTRACT_VERSION, config_sha256: configSha256,
    availability: "unavailable", unavailable_reason: "empty_denominator", top_k: null,
  };
}

export function calculateDiversityMetrics(result: FeedPlanResult, membership: StageMembership): DiversityMetricRow[] {
  const config = FeedMetricsConfigSchema.parse(result.evidence.harvest.config.metrics);
  const active = membership.sources.filter(source => source.status === "active").map(source => source.source_id);
  const { context } = result;
  const base = createMetricTemplate(context, result.evidence.harvest.inputs.config_sha256, active.length);
  const rows: DiversityMetricRow[] = [];
  function record(values: Partial<DiversityMetricRow>) {
    const row = { ...base, ...values };
    if (row.value !== null) {
      row.availability = "available";
      row.unavailable_reason = null;
    }
    rows.push(DiversityMetricRowSchema.parse(row));
  }
  const eligibleSources = new Set(membership.eligible.map(item => item.source_id)).size;
  const selectedSources = new Set(membership.selected.map(item => item.source_id)).size;
  record({
    metric: "active_source_coverage", basis: "eligible", unit: "ratio", numerator: eligibleSources,
    denominator: active.length, value: measuredRatio(eligibleSources, active.length, "active_source_coverage"),
    item_count: membership.eligible.length,
  });
  record({
    metric: "selection_coverage", unit: "ratio", numerator: selectedSources, denominator: eligibleSources,
    value: measuredRatio(selectedSources, eligibleSources, "selection_coverage"), item_count: membership.selected.length,
  });
  const selectedCounts = sourceCounts(membership.selected, active);
  record({ value: effectiveSources(selectedCounts), item_count: membership.selected.length });
  record({ metric: "source_gini", unit: "ratio", value: sourceGini(selectedCounts), item_count: membership.selected.length });
  for (const count of new Set(config.top_source_counts)) {
    record({ metric: "top_source_concentration", unit: "ratio", top_k: count,
      ...topSourceShare(selectedCounts, count), item_count: membership.selected.length });
  }
  for (const [basis, items] of [["eligible", membership.eligible], ["selected", membership.selected]] as const) {
    const kinds = new Map<string, number>();
    for (const source of membership.sources) kinds.set(source.kind, 0);
    for (const item of items) kinds.set(item.source.kind, (kinds.get(item.source.kind) ?? 0) + 1);
    for (const [kind, count] of [...kinds].sort(([a], [b]) => a.localeCompare(b))) {
      record({ metric: "source_kind_distribution", basis, dimension: "source_kind", dimension_value: kind,
        unit: "count", value: count, item_count: items.length });
      record({ metric: "source_kind_distribution", basis, dimension: "source_kind", dimension_value: kind,
        unit: "ratio", value: measuredRatio(count, items.length, "source_kind_distribution"),
        numerator: count, denominator: items.length, item_count: items.length });
    }
  }
  const stages = [
    ["input", membership.harvested, membership.harvested],
    ["freshness", membership.harvested, membership.freshness],
    ["deduplication", membership.eligible, membership.representatives],
    ["normalization", membership.representatives, membership.normalized],
    ["selection", membership.normalized, membership.selected],
  ] as const;
  for (const [stage, before, after] of stages) {
    const beforeValue = effectiveSources(sourceCounts(before, active));
    const afterValue = effectiveSources(sourceCounts(after, active));
    record({ basis: "stage", stage, value: afterValue, item_count: after.length });
    if (stage !== "input") record({
      metric: "lost_diversity_by_stage", basis: "stage", stage, unit: "source_difference",
      before_value: beforeValue, after_value: afterValue, value: beforeValue - afterValue, item_count: after.length,
    });
  }
  // No planning observation can establish what was actually published.
  for (const basis of ["published", "leads"] as const) record({ basis, unavailable_reason: "missing_publication" });
  record({ metric: "source_gini", basis: "published", unit: "ratio", unavailable_reason: "missing_publication" });
  for (const kind of new Set(membership.sources.map(source => source.kind))) {
    for (const unit of ["count", "ratio"] as const) record({
      metric: "source_kind_distribution", basis: "published", dimension: "source_kind", dimension_value: kind,
      unit, unavailable_reason: "missing_publication",
    });
  }
  for (const count of new Set(config.top_source_counts)) {
    record({ metric: "top_source_concentration", basis: "published", unit: "ratio", top_k: count, unavailable_reason: "missing_publication" });
  }
  for (const window of new Set(config.overlap_windows_days)) {
    for (const dimension of ["source", "event_cluster"] as const) {
      for (const unit of ["count", "ratio"] as const) record({
        metric: "source_event_overlap", basis: "published", dimension, unit,
        window_days: window, unavailable_reason: "incomplete_history",
      });
    }
  }
  for (const metric of ["event_repetition_rate", "novel_source_contribution"] as const) record({
    metric, basis: "published", unit: "ratio", window_days: config.rolling_window_days,
    unavailable_reason: metric === "event_repetition_rate" ? "missing_event_evidence" : "incomplete_history",
  });
  record({ metric: "novel_source_contribution", basis: "published", unit: "count",
    window_days: config.rolling_window_days, unavailable_reason: "incomplete_history" });
  return rows;
}
