/** Which per-run and rolling diversity readings follow from settled recorded populations? */
import { isDeepStrictEqual } from "node:util";
import { DiversityMetricRowSchema, FeedMetricsConfigSchema } from "@idhazh/common-contracts";
import type { DiversityMetricRow } from "@idhazh/common-contracts";
import { createMetricTemplate, effectiveSources, measuredRatio, sourceGini, topSourceShare } from "./diversity-metrics";
import { uniquePublishedArticles, uniqueRecorded } from "./fingerprint-dedup";
import {
  eventOverlap, eventRepetitionRate, novelSourceContribution, sourceOverlap,
} from "./history-window";
import type { HistoryReading, HistoryWindow } from "./history-window";
import type { RecordedEventEvidence } from "./publication-evidence";
import type { PlanningDay, PlanningStage, PopulationItem } from "./planning-populations";
import type { PublicationOutcomes } from "./publication-outcomes";

export type PublicationMetricInput = Readonly<{
  run_id: string; correlation_id: string; config_sha256: string;
  config: Parameters<typeof FeedMetricsConfigSchema.parse>[0];
  history: HistoryWindow; planning: readonly PlanningDay[];
  run_publication: PublicationOutcomes | undefined;
  event_evidence?: RecordedEventEvidence;
}>;
function countSources(items: readonly { source_id: string }[], active: ReadonlySet<string>): number[] {
  const counts = new Map([...active].map(source => [source, 0]));
  for (const item of items) counts.set(item.source_id, (counts.get(item.source_id) ?? 0) + 1);
  return [...counts.values()];
}
function distinctSelected(items: readonly PopulationItem[]): PopulationItem[] {
  const indexed = new Map<string, PopulationItem>();
  for (const item of items) {
    if (item.url_key === null) throw new Error("A selected historical article has no URL identity");
    if (!indexed.has(item.url_key)) indexed.set(item.url_key, item);
  }
  return [...indexed.values()];
}

export function calculatePublicationMetrics(input: PublicationMetricInput) {
  const config = FeedMetricsConfigSchema.parse(input.config);
  const window = input.history;
  if (input.run_publication !== undefined && input.run_publication.run_id !== input.run_id) throw new Error("Publication outcome belongs to another measured run");
  if (new Set(input.planning.map(day => day.day)).size !== input.planning.length
    || input.planning.some(day => !window.days.some(held => held.day === day.day))) throw new Error("Planning history must name distinct requested UTC days");
  const output: DiversityMetricRow[] = [];
  const unavailable: string[] = [];
  for (const rolling of [false, true]) {
    const dates = rolling ? window.measured.map(day => day.day) : [input.run_id.slice(0, 10)];
    const days = dates.map(date => window.days.find(day => day.day === date));
    if (days.some(day => day === undefined)) throw new Error("Measured run is outside the requested rolling window");
    const heldDays = days.filter(day => day !== undefined);
    const publicationComplete = heldDays.every(day => day.status === "rows" || day.status === "empty")
      && (rolling ? heldDays.every(day => day.day < window.as_of.slice(0, 10)) : input.run_publication?.availability === "available");
    const published = uniquePublishedArticles(heldDays.flatMap(day => day.articles)
      .filter(article => rolling || article.run_id === input.run_id));
    const plans = dates.map(date => input.planning.find(day => day.day === date));
    const runs = plans.flatMap(day => day?.runs ?? []).filter(run => rolling || run.run_id === input.run_id);
    const planningComplete = plans.every(day => day !== undefined && (day.status === "rows" || day.status === "empty"))
      && (rolling ? dates.every(date => date < window.as_of.slice(0, 10)) : runs.length === 1);
    const planningCoverage = plans.filter(day => day !== undefined && (day.status === "rows" || day.status === "empty")
      && (!rolling || day.day < window.as_of.slice(0, 10))).length;
    const active = new Set(runs.flatMap(run => run.sources.filter(source => source.status === "active").map(source => source.source_id)));
    const base = createMetricTemplate({
      date: window.as_of.slice(0, 10), now: window.as_of, run_id: input.run_id, correlation_id: input.correlation_id,
    }, input.config_sha256, planningComplete ? active.size : null);
    base.window_start = rolling ? window.start : null;
    base.window_end = rolling ? window.end : null;
    base.history_required_days = dates.length;
    base.history_coverage_days = heldDays.filter(day => (day.status === "rows" || day.status === "empty") && (!rolling || day.day < window.as_of.slice(0, 10))).length;
    const record = (values: Partial<DiversityMetricRow>, reason: DiversityMetricRow["unavailable_reason"] = null) => {
      const row = { ...base, ...values };
      const dependsOnPlanning = row.basis === "eligible" || row.basis === "selected"
        || (row.basis === "stage" && row.stage !== "lead_selection");
      if (dependsOnPlanning) row.history_coverage_days = planningCoverage;
      if ((row.metric === "source_gini" && row.basis === "published") || (row.basis === "stage" && row.stage === "publication")) {
        row.history_coverage_days = plans.filter(day => day !== undefined && (day.status === "rows" || day.status === "empty")
          && heldDays.some(held => held.day === day.day && (held.status === "rows" || held.status === "empty"))
          && (!rolling || day.day < window.as_of.slice(0, 10))).length;
      }
      row.unavailable_reason = reason ?? (row.value === null ? "empty_denominator" : null);
      row.availability = row.unavailable_reason === null ? "available" : "unavailable";
      if (row.availability === "unavailable") row.value = null;
      if (row.unavailable_reason !== null && row.unavailable_reason !== "empty_denominator") {
        row.numerator = null; row.denominator = null;
      }
      output.push(DiversityMetricRowSchema.parse(row));
    };
    const planningReason = planningComplete ? null : "incomplete_history";
    const publicationReason = publicationComplete ? null : rolling ? "incomplete_history" : "missing_publication";
    const eligible = uniqueRecorded(runs.flatMap(run => run.eligible), row => row.candidate_id, isDeepStrictEqual);
    const selected = distinctSelected(runs.flatMap(run => run.selected));
    const selectedPublication = published.every(article => runs.some(run => run.run_id === article.run_id
      && run.selected.some(selected => selected.url_key === article.url_key && selected.source_id === article.source_id)));
    const eligibleSources = new Set(eligible.map(item => item.source_id));
    const selectedSources = new Set(selected.map(item => item.source_id));
    record({ metric: "active_source_coverage", basis: "eligible", unit: "ratio",
      numerator: planningComplete ? eligibleSources.size : null, denominator: planningComplete ? active.size : null,
      value: planningComplete ? measuredRatio(eligibleSources.size, active.size, "active_source_coverage") : null,
      item_count: planningComplete ? eligible.length : null }, planningReason);
    record({ metric: "selection_coverage", unit: "ratio",
      numerator: planningComplete ? selectedSources.size : null, denominator: planningComplete ? eligibleSources.size : null,
      value: planningComplete ? measuredRatio(selectedSources.size, eligibleSources.size, "selection_coverage") : null,
      item_count: planningComplete ? selected.length : null }, planningReason);
    for (const [basis, items, reason] of [
      ["eligible", eligible, planningReason], ["selected", selected, planningReason],
      ["published", published, publicationReason], ["leads", published.filter(item => item.lead), publicationReason],
    ] as const) {
      const counts = countSources(items, active);
      record({ basis, value: reason === null ? effectiveSources(counts) : null, item_count: reason === null ? items.length : null }, reason);
      if (basis === "selected" || basis === "published") {
        const outsideSnapshot = planningComplete && items.some(item => !active.has(item.source_id));
        const giniReason = reason ?? planningReason ?? (outsideSnapshot || (basis === "published" && !selectedPublication) ? "incomplete_history" : null);
        if (outsideSnapshot) unavailable.push(`${rolling ? "rolling" : "run"}.${basis}.source_gini: published source is outside the measured active snapshots`);
        record({ metric: "source_gini", basis, unit: "ratio", value: giniReason === null ? sourceGini(counts) : null,
          item_count: giniReason === null ? items.length : null }, giniReason);
        for (const k of new Set(config.top_source_counts)) {
          if (k !== 1 && k !== 5 && k !== 10) throw new Error(`metrics.top_source_counts.${k}: unsupported top_k`);
          record({ metric: "top_source_concentration", basis, unit: "ratio", top_k: k,
            ...(reason === null ? topSourceShare(counts, k) : {}),
            item_count: reason === null ? items.length : null }, reason);
        }
      }
      if (basis !== "leads") {
        const kinds = new Map<string, number>(runs.flatMap(run => run.sources.map(source => [source.source.kind, 0] as const)));
        for (const item of items) kinds.set(item.source_kind ?? "unknown", (kinds.get(item.source_kind ?? "unknown") ?? 0) + 1);
        if (kinds.size === 0) kinds.set("unknown", 0);
        for (const [kind, count] of kinds) {
          record({ metric: "source_kind_distribution", basis, unit: "count", dimension: "source_kind", dimension_value: kind,
            value: reason === null ? count : null, item_count: reason === null ? items.length : null }, reason);
          record({ metric: "source_kind_distribution", basis, unit: "ratio", dimension: "source_kind", dimension_value: kind,
            value: reason === null ? measuredRatio(count, items.length, "source_kind_distribution") : null,
            numerator: reason === null ? count : null, denominator: reason === null ? items.length : null,
            item_count: reason === null ? items.length : null }, reason);
        }
      }
    }
    const stages = Object.fromEntries((["input", "freshness", "deduplication", "normalization", "selection"] as const)
      .map(stage => [stage, stage === "selection" ? selected : uniqueRecorded(runs.flatMap(run => run.stages[stage]), item => item.candidate_id, isDeepStrictEqual)]));
    const before: Readonly<Record<Exclude<PlanningStage, "input">, readonly { source_id: string }[]>> = {
      freshness: stages.input!, deduplication: eligible, normalization: stages.deduplication!, selection: stages.normalization!,
    };
    for (const [stage, items] of Object.entries(stages)) {
      const after = effectiveSources(countSources(items, active));
      record({ basis: "stage", stage: stage as PlanningStage, value: planningComplete ? after : null,
        item_count: planningComplete ? items.length : null }, planningReason);
      if (stage !== "input" && planningComplete) {
        const previous = effectiveSources(countSources(before[stage as Exclude<PlanningStage, "input">], active));
        record({ metric: "lost_diversity_by_stage", basis: "stage", stage: stage as PlanningStage, unit: "source_difference",
          value: previous - after, before_value: previous, after_value: after, item_count: items.length });
      }
      if (stage !== "input" && !planningComplete) unavailable.push(`${rolling ? "rolling" : "run"}.${stage}: no complete before/after membership`);
    }
    for (const [stage, previous, items, reason] of [
      ["publication", selected, published, publicationReason ?? planningReason ?? (selectedPublication ? null : "incomplete_history")],
      ["lead_selection", published, published.filter(article => article.lead), publicationReason],
    ] as const) {
      const after = effectiveSources(countSources(items, active));
      record({ basis: "stage", stage, value: reason === null ? after : null, item_count: reason === null ? items.length : null }, reason);
      if (reason !== null) unavailable.push(`${rolling ? "rolling" : "run"}.${stage}: no complete before/after membership`);
      else {
        const prior = effectiveSources(countSources(previous, active));
        record({ metric: "lost_diversity_by_stage", basis: "stage", stage, unit: "source_difference",
          value: prior - after, before_value: prior, after_value: after, item_count: items.length });
      }
    }
    const historical = (metric: DiversityMetricRow["metric"], dimension: "source" | "event_cluster", span: number, reading: HistoryReading, units: readonly ("ratio" | "count")[]) => {
      for (const unit of units) record({ metric, basis: "published", dimension, window_days: span, unit,
        value: unit === "count" ? reading.numerator : reading.value,
        numerator: reading.numerator, denominator: reading.denominator,
        item_count: publicationComplete ? published.length : null,
        history_coverage_days: reading.coverage_days, history_required_days: reading.required_days,
      }, publicationReason ?? (unit === "count" && reading.unavailable_reason === "empty_denominator" ? null : reading.unavailable_reason));
    };
    for (const span of new Set(config.overlap_windows_days)) {
      historical("source_event_overlap", "source", span, sourceOverlap(window, published, span, dates), ["count", "ratio"]);
      historical("source_event_overlap", "event_cluster", span, eventOverlap(window, published, span, input.event_evidence, dates), ["count", "ratio"]);
    }
    historical("event_repetition_rate", "event_cluster", config.rolling_window_days,
      eventRepetitionRate(window, published, config.rolling_window_days, input.event_evidence, dates), ["ratio"]);
    historical("novel_source_contribution", "source", config.rolling_window_days,
      novelSourceContribution(window, published, config.rolling_window_days, dates), ["count", "ratio"]);
  }
  return { rows: output, unavailable };
}
