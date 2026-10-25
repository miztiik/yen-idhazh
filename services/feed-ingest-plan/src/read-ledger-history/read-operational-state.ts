/** Which saved registered state is safe to use for one planner selection? */
import { createHash } from "node:crypto";
import {
  FeedIngestOperationalStateRowSchema, OperationalStateReadSchema, SourceOperationalEvidenceSchema,
} from "@idhazh/common-contracts";
import type {
  FeedIngestConfig, FeedIngestOperationalStateRow, OperationalStateRead, SourceOperationalEvidence,
} from "@idhazh/common-contracts";
import type { LedgerRegistration } from "@idhazh/ledger-file-writer";
import type { SeenDayInput } from "../config/service-settings";
import { defaultDayInput, readNamedDays } from "./named-days";
import type { LedgerHistoryReadSource } from "./named-days";
import { OperationalStateContract } from "../metrics/audit-contracts";
import { shiftUtcDay } from "../metrics/history-window";
import { closedObservationDays } from "./read-ingest-evidence";
import { estimateSourceFeedback } from "../estimate-operational-feedback";
import type { MeasuredSourceEvidence } from "../estimate-operational-feedback";
import { classifyPublicationHistoryError } from "./classify-publication-history-error";
import { writeJsonLine } from "../logging/structured-logger";

export function operationalPolicyVersion(policy: FeedIngestConfig["feedback"]): string {
  return createHash("sha256").update(JSON.stringify({
    window_days: policy.window_days,
    minimum_measured_opportunities: policy.minimum_measured_opportunities,
    minimum_measured_coverage: policy.minimum_measured_coverage,
    component_weights: policy.component_weights,
  })).digest("hex");
}

function candidateDays(now: string, days: readonly SeenDayInput[], windowDays: number, prefix: readonly string[]) {
  const today = now.slice(0, 10);
  const named = new Map(days.map(day => [day.day, day]));
  for (let offset = 0; offset <= windowDays; offset++) {
    const day = shiftUtcDay(today, -offset);
    if (!named.has(day)) named.set(day, defaultDayInput(prefix, day));
  }
  return [...named.values()].sort((left, right) => left.day.localeCompare(right.day));
}

function validateSnapshot(
  rows: readonly FeedIngestOperationalStateRow[], policy?: FeedIngestConfig["feedback"],
): boolean {
  if (rows.length === 0) return false;
  const first = rows[0]!;
  const sources = new Set<string>();
  for (const row of rows) {
    if (row.state_revision !== first.state_revision || row.parent_revision !== first.parent_revision
      || row.date !== first.date || row.written_at_utc !== first.written_at_utc
      || row.evidence_cutoff_utc !== first.evidence_cutoff_utc || row.window_days !== first.window_days
      || row.window_start !== first.window_start || row.window_end !== first.window_end
      || row.code_revision !== first.code_revision || row.policy_version !== first.policy_version
      || sources.has(row.source_id)) return false;
    sources.add(row.source_id);
    const cutoffDay = row.evidence_cutoff_utc.slice(0, 10);
    const expectedEnd = shiftUtcDay(cutoffDay, -1);
    const expectedStart = shiftUtcDay(expectedEnd, 1 - row.window_days);
    if (row.state_revision !== (row.parent_revision ?? 0) + 1
      || row.date !== cutoffDay || row.written_at_utc !== row.evidence_cutoff_utc
      || expectedEnd !== row.window_end || expectedStart !== row.window_start
      || row.window_end >= cutoffDay
      || (row.evidence_start_utc !== null && row.evidence_start_utc.slice(0, 10) < row.window_start)
      || (row.evidence_end_utc !== null && row.evidence_end_utc.slice(0, 10) > row.window_end)) return false;
    if (row.observed_attempted_opportunities === 0) {
      if (row.measured_coverage !== null) return false;
    } else if (row.measured_coverage !== row.observed_measured_opportunities / row.observed_attempted_opportunities) {
      return false;
    }
    if (row.qualification_status === "qualified"
      && (row.measured_target_requests === null || row.measured_source_wasted_requests === null
        || row.request_waste_ratio !== row.measured_source_wasted_requests / row.measured_target_requests)) {
      return false;
    }
    if (policy !== undefined) {
      const source: MeasuredSourceEvidence = {
        source_id: row.source_id,
        observed_attempted_opportunities: row.observed_attempted_opportunities,
        observed_measured_opportunities: row.observed_measured_opportunities,
        measured_coverage: row.measured_coverage,
        measured_target_requests: row.measured_target_requests,
        measured_source_wasted_requests: row.measured_source_wasted_requests,
      };
      const expected = estimateSourceFeedback(source, policy);
      if (expected.qualification_status !== row.qualification_status
        || expected.request_waste_ratio !== row.request_waste_ratio
        || (expected.qualification_status === "qualified"
          ? expected.request_component_penalty : null) !== row.operational_penalty) return false;
    }
  }
  return true;
}

function operationalEvidence(
  row: FeedIngestOperationalStateRow, stateStatus: "current" | "stale_fallback",
): SourceOperationalEvidence {
  return SourceOperationalEvidenceSchema.parse({
    status: row.qualification_status, state_status: stateStatus,
    state_revision: row.state_revision, window_days: row.window_days,
    window_start: row.window_start, window_end: row.window_end,
    total_requests: row.measured_target_requests,
    wasted_requests: row.measured_source_wasted_requests,
    observed_attempted_opportunities: row.observed_attempted_opportunities,
    observed_measured_opportunities: row.observed_measured_opportunities,
    coverage: row.measured_coverage, operational_penalty: row.operational_penalty,
  });
}

export async function readOperationalState(input: Readonly<{
  root: string; now: string; policy: FeedIngestConfig["feedback"];
  registration: LedgerRegistration; days: readonly SeenDayInput[];
  read_source?: LedgerHistoryReadSource<FeedIngestOperationalStateRow>;
}>) {
  if (input.registration.name !== "operational-state" || input.registration.family !== "feed-ingest-plan") {
    throw new Error("Operational state requires the registered operational-state ledger");
  }
  const named = candidateDays(input.now, input.days, input.policy.window_days, input.registration.prefix);
  const cache = new Map<string, Promise<import("./read-parquet").ReadLedgerFile<FeedIngestOperationalStateRow>>>();
  const rows = new Map<string, FeedIngestOperationalStateRow>();
  const errors: { day: string; diagnostic: string }[] = [];
  const dayStatuses: { day: string; status: string }[] = [];
  let invalidSnapshot = false;
  for (const day of named) {
    try {
      const held = await readNamedDays(input.root, input.registration, [day], OperationalStateContract, cache,
        input.read_source);
      dayStatuses.push(...held.map(item => ({ day: item.day, status: item.status })));
      for (const file of held.flatMap(item => item.files)) {
        for (const stored of file.rows) {
          const row = FeedIngestOperationalStateRowSchema.parse(stored.row);
          const key = `${row.state_revision}:${row.source_id}`;
          if (rows.has(key)) invalidSnapshot = true;
          else rows.set(key, row);
        }
      }
    } catch (error) {
      const diagnostic = classifyPublicationHistoryError(error);
      errors.push({
        day: day.day,
        diagnostic: diagnostic ?? (error instanceof Error ? error.message : "unknown_reader_error"),
      });
    }
  }
  const all = [...rows.values()];
  const latestRevision = all.reduce((latest, row) => Math.max(latest, row.state_revision), 0) || null;
  const revisionGroups = new Map<number, FeedIngestOperationalStateRow[]>();
  for (const row of all) {
    const group = revisionGroups.get(row.state_revision) ?? [];
    group.push(row);
    revisionGroups.set(row.state_revision, group);
  }
  for (const group of revisionGroups.values()) {
    if (!validateSnapshot(group)) invalidSnapshot = true;
    else if (group.every(row => row.policy_version === operationalPolicyVersion(input.policy))
      && !validateSnapshot(group, input.policy)) invalidSnapshot = true;
  }
  const policyVersion = operationalPolicyVersion(input.policy);
  const compatible = [...revisionGroups.entries()]
    .filter(([, group]) => validateSnapshot(group, input.policy) && group.every(row =>
      row.window_days === input.policy.window_days && row.policy_version === policyVersion))
    .sort(([left], [right]) => right - left)[0]?.[1] ?? [];
  const latest = compatible[0];
  const writable = errors.length === 0 && !invalidSnapshot;
  if (latest === undefined) {
    const reason = errors.length > 0 ? "unreadable"
      : all.length > 0 || invalidSnapshot ? "incompatible"
        : dayStatuses.some(day => day.status === "empty") ? "known_empty"
          : dayStatuses.length > 0 && dayStatuses.every(day => day.status === "missing") ? "missing"
            : "unknown";
    const state: OperationalStateRead = OperationalStateReadSchema.parse({
      status: "unavailable", state_revision: null, window_days: input.policy.window_days,
      window_start: null, window_end: null,
    });
    writeJsonLine({
      timestamp: input.now, level: "WARN", event: "operational_state_unavailable",
      reason: `restrictions_unverified:${reason}`,
    });
    return {
      state, reason, by_source: new Map<string, SourceOperationalEvidence>(),
      latest_revision: latestRevision, writable, errors,
    };
  }
  const expectedWindow = closedObservationDays(input.now, input.policy.window_days);
  const isCurrentWindow = latest.window_start === expectedWindow[0]
    && latest.window_end === expectedWindow.at(-1);
  const stale = errors.length > 0 || latestRevision !== latest.state_revision || !isCurrentWindow;
  const reason = stale ? errors.length > 0 ? "unreadable"
    : latestRevision !== latest.state_revision ? "incompatible" : "window_behind" : null;
  const state = OperationalStateReadSchema.parse({
    status: stale ? "stale_fallback" : "current", state_revision: latest.state_revision,
    window_days: latest.window_days, window_start: latest.window_start, window_end: latest.window_end,
  });
  if (stale) {
    writeJsonLine({
      timestamp: input.now, level: "WARN", event: "operational_state_stale_fallback",
      reason,
      state_revision: latest.state_revision, window_start: latest.window_start, window_end: latest.window_end,
      errors,
    });
  }
  return {
    state, reason, by_source: new Map(compatible.map(row =>
      [row.source_id, operationalEvidence(row, state.status as "current" | "stale_fallback")])),
    latest_revision: latestRevision, writable, errors,
  };
}
