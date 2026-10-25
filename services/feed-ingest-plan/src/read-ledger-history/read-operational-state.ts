/** Which saved registered state is safe to use for one planner selection? */
import { createHash } from "node:crypto";
import { posix, resolve } from "node:path";
import {
  FeedIngestOperationalStateRowSchema, OperationalStateReadSchema, SourceOperationalEvidenceSchema,
} from "@idhazh/common-contracts";
import type {
  FeedIngestConfig, FeedIngestOperationalStateRow, OperationalStateRead, SourceOperationalEvidence,
} from "@idhazh/common-contracts";
import type { LedgerRegistration } from "@idhazh/ledger-file-writer";
import type { LedgerHistoryReadSource } from "./named-days";
import { OperationalStateContract } from "../metrics/audit-contracts";
import { shiftUtcDay } from "../metrics/history-window";
import { closedObservationDays } from "./read-ingest-evidence";
import { estimateSourceFeedback } from "../estimate-operational-feedback";
import type { MeasuredSourceEvidence } from "../estimate-operational-feedback";
import { classifyPublicationHistoryError } from "./classify-publication-history-error";
import { LedgerHistoryReadError } from "./ledger-history-error";
import { readLedgerParquet } from "./read-parquet";
import type { ReadLedgerFile } from "./read-parquet";
import { writeJsonLine } from "../logging/structured-logger";

export const OPERATIONAL_STATE_SNAPSHOT_FILES = {
  latest: "snapshots/latest.parquet",
  previous_complete: "snapshots/previous-complete.parquet",
} as const;
type SnapshotSlot = keyof typeof OPERATIONAL_STATE_SNAPSHOT_FILES;
type SnapshotResult =
  | { status: "valid"; rows: FeedIngestOperationalStateRow[] }
  | { status: "missing" }
  | { status: "invalid"; diagnostic: string };

export function operationalPolicyVersion(policy: FeedIngestConfig["feedback"]): string {
  return createHash("sha256").update(JSON.stringify({
    window_days: policy.window_days,
    minimum_measured_opportunities: policy.minimum_measured_opportunities,
    minimum_measured_coverage: policy.minimum_measured_coverage,
    component_weights: policy.component_weights,
  })).digest("hex");
}

export function operationalStateSnapshotPath(registration: LedgerRegistration, slot: SnapshotSlot): string {
  return posix.join("compact", ...registration.prefix, OPERATIONAL_STATE_SNAPSHOT_FILES[slot]);
}

export function operationalStateSnapshotDigest(rows: readonly FeedIngestOperationalStateRow[]): string {
  const canonical = [...rows]
    .sort((left, right) => left.source_id.localeCompare(right.source_id))
    .map(row => {
      const { snapshot_sha256: _snapshotSha256, ...content } = row;
      return content;
    });
  return createHash("sha256").update(JSON.stringify(canonical), "utf8").digest("hex");
}

function validateSnapshot(
  rows: readonly FeedIngestOperationalStateRow[], policy?: FeedIngestConfig["feedback"],
): boolean {
  if (rows.length === 0) return false;
  const first = rows[0]!;
  const roster = first.snapshot_source_ids;
  if (roster === null || first.snapshot_sha256 === null || roster.length !== rows.length) return false;
  const sources = new Set<string>();
  for (const row of rows) {
    if (row.state_revision !== first.state_revision || row.parent_revision !== first.parent_revision
      || row.date !== first.date || row.written_at_utc !== first.written_at_utc
      || row.evidence_cutoff_utc !== first.evidence_cutoff_utc || row.window_days !== first.window_days
      || row.window_start !== first.window_start || row.window_end !== first.window_end
      || row.code_revision !== first.code_revision || row.policy_version !== first.policy_version
      || row.snapshot_sha256 !== first.snapshot_sha256
      || JSON.stringify(row.snapshot_source_ids) !== JSON.stringify(roster)
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
  const sourceIds = [...sources].sort();
  return JSON.stringify(sourceIds) === JSON.stringify(roster)
    && operationalStateSnapshotDigest(rows) === first.snapshot_sha256;
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

async function readSnapshot(input: Readonly<{
  root: string; registration: LedgerRegistration; slot: SnapshotSlot;
  read_source?: LedgerHistoryReadSource<FeedIngestOperationalStateRow>;
}>): Promise<SnapshotResult> {
  const path = resolve(input.root, operationalStateSnapshotPath(input.registration, input.slot));
  try {
    const loaded: ReadLedgerFile<FeedIngestOperationalStateRow> = input.read_source?.readFile === undefined
      ? await readLedgerParquet(path, "operational-state", OperationalStateContract)
      : await input.read_source.readFile(path);
    if (loaded.envelope.ledger !== "operational-state" || loaded.envelope.tier !== "compact"
      || loaded.envelope.period !== "daily" || loaded.rows.length === 0
      || loaded.envelope.covers !== loaded.rows[0]!.row.date) {
      throw new LedgerHistoryReadError("Operational-state snapshot envelope is incomplete or inconsistent");
    }
    const rows = loaded.rows.map(({ row }) => FeedIngestOperationalStateRowSchema.parse(row));
    if (rows.some(row => row.date !== loaded.envelope.covers) || !validateSnapshot(rows)) {
      throw new LedgerHistoryReadError("Operational-state snapshot roster or digest is incomplete");
    }
    return { status: "valid", rows };
  } catch (error) {
    const diagnostic = classifyPublicationHistoryError(error);
    if (diagnostic === null) throw error;
    return diagnostic === "ENOENT" ? { status: "missing" } : { status: "invalid", diagnostic };
  }
}

function compatibleSnapshot(
  snapshot: SnapshotResult, policy: FeedIngestConfig["feedback"],
): FeedIngestOperationalStateRow[] | undefined {
  if (snapshot.status !== "valid" || !validateSnapshot(snapshot.rows, policy)) return undefined;
  const first = snapshot.rows[0]!;
  return first.window_days === policy.window_days
    && first.policy_version === operationalPolicyVersion(policy) ? snapshot.rows : undefined;
}

export async function readOperationalState(input: Readonly<{
  root: string; snapshot_root?: string; now: string; policy: FeedIngestConfig["feedback"];
  registration: LedgerRegistration;
  read_source?: LedgerHistoryReadSource<FeedIngestOperationalStateRow>;
}>) {
  if (input.registration.name !== "operational-state" || input.registration.family !== "feed-ingest-plan") {
    throw new Error("Operational state requires the registered operational-state ledger");
  }
  const snapshotRoot = input.snapshot_root ?? input.root;
  let latestSnapshot = await readSnapshot({
    root: snapshotRoot, registration: input.registration, slot: "latest",
    ...(input.read_source === undefined ? {} : { read_source: input.read_source }),
  });
  const previousSnapshot = await readSnapshot({
    root: snapshotRoot, registration: input.registration, slot: "previous_complete",
    ...(input.read_source === undefined ? {} : { read_source: input.read_source }),
  });
  if (latestSnapshot.status === "valid" && previousSnapshot.status === "valid") {
    const latest = latestSnapshot.rows[0]!;
    const previous = previousSnapshot.rows[0]!;
    if (latest.state_revision <= previous.state_revision || latest.parent_revision !== previous.state_revision) {
      latestSnapshot = { status: "invalid", diagnostic: "snapshot revision does not follow previous complete state" };
    }
  }
  const latestRows = compatibleSnapshot(latestSnapshot, input.policy);
  const previousRows = compatibleSnapshot(previousSnapshot, input.policy);
  const latestRevision = latestSnapshot.status === "valid" ? latestSnapshot.rows[0]!.state_revision
    : previousSnapshot.status === "valid" ? previousSnapshot.rows[0]!.state_revision : null;
  const writable = latestSnapshot.status === "valid"
    || (latestSnapshot.status === "missing" && previousSnapshot.status === "missing");
  const expectedWindow = closedObservationDays(input.now, input.policy.window_days);
  const useLatest = latestRows !== undefined;
  const selectedRows = latestRows ?? previousRows;
  const selectedSlot = selectedRows === undefined ? null : useLatest ? "latest" : "previous_complete";
  const latestCurrent = latestRows !== undefined
    && latestRows[0]!.window_start === expectedWindow[0]
    && latestRows[0]!.window_end === expectedWindow.at(-1);
  const stale = selectedRows !== undefined && (selectedSlot !== "latest" || !latestCurrent);
  const unavailableReason = latestSnapshot.status === "invalid" || previousSnapshot.status === "invalid"
    ? "unreadable"
    : latestSnapshot.status === "missing" && previousSnapshot.status === "missing" ? "missing"
      : latestRows === undefined && previousRows === undefined ? "incompatible" : "unknown";
  const reason = selectedRows === undefined ? unavailableReason
    : !stale ? null
      : selectedSlot === "previous_complete" ? latestSnapshot.status === "missing" ? "latest_missing"
        : latestSnapshot.status === "invalid" ? "unreadable" : "incompatible"
        : "window_behind";
  const errors = [
    latestSnapshot.status === "invalid" ? { file: "latest", diagnostic: latestSnapshot.diagnostic } : null,
    previousSnapshot.status === "invalid" ? { file: "previous_complete", diagnostic: previousSnapshot.diagnostic } : null,
  ].filter((item): item is { file: string; diagnostic: string } => item !== null);
  if (selectedRows === undefined) {
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
      latest_revision: latestRevision, latest_snapshot_rows: latestSnapshot.status === "valid" ? latestSnapshot.rows : undefined,
      writable, errors,
    };
  }
  const latestSelected = selectedRows[0]!;
  const state = OperationalStateReadSchema.parse({
    status: stale ? "stale_fallback" : "current",
    state_revision: latestSelected.state_revision,
    window_days: latestSelected.window_days,
    window_start: latestSelected.window_start, window_end: latestSelected.window_end,
  });
  if (stale) {
    writeJsonLine({
      timestamp: input.now, level: "WARN", event: "operational_state_stale_fallback",
      reason, state_revision: latestSelected.state_revision,
      window_start: latestSelected.window_start, window_end: latestSelected.window_end, errors,
    });
  }
  return {
    state, reason,
    by_source: new Map(selectedRows.map(row =>
      [row.source_id, operationalEvidence(row, state.status as "current" | "stale_fallback")])),
    latest_revision: latestRevision, latest_snapshot_rows: latestSnapshot.status === "valid" ? latestSnapshot.rows : undefined,
    writable, errors,
  };
}
