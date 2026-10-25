/** Save one qualified-policy snapshot from complete, closed-day observations. */
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { isDeepStrictEqual } from "node:util";
import { FeedIngestOperationalStateRowSchema, RowIdentitySchema } from "@idhazh/common-contracts";
import type { FeedIngestOperationalStateRow } from "@idhazh/common-contracts";
import { checkTrustedParent, createUnitId, persistLedger, writeAtomically } from "@idhazh/ledger-file-writer";
import type { PersistLedgerResult } from "@idhazh/ledger-file-writer";
import { OperationalStateContract } from "./metrics/audit-contracts";
import { estimateOperationalFeedback } from "./estimate-operational-feedback";
import type { readIngestEvidence } from "./read-ledger-history/read-ingest-evidence";
import type { PlanInputs } from "./load-plan-inputs";
import type { FeedIngestConfig, WriterIdentity } from "@idhazh/common-contracts";
import type { readOperationalState } from "./read-ledger-history/read-operational-state";
import { operationalPolicyVersion } from "./read-ledger-history/read-operational-state";
import { readLedgerParquet } from "./read-ledger-history/read-parquet";
import {
  operationalStateSnapshotDigest, operationalStateSnapshotPath,
} from "./read-ledger-history/read-operational-state";
import { writeJsonLine } from "./logging/structured-logger";

type Evidence = Awaited<ReturnType<typeof readIngestEvidence>>;
type SavedState = Awaited<ReturnType<typeof readOperationalState>>;

export type OperationalStateWrite = Readonly<{
  status: "written" | "not_written";
  reason: "none" | "history_unavailable" | "known_empty" | "state_read_failed" | "save_failed";
  result: PersistLedgerResult;
}>;

export async function renderOperationalStateSnapshots(input: Readonly<{
  rows: readonly FeedIngestOperationalStateRow[];
  previous_rows?: readonly FeedIngestOperationalStateRow[];
  writer: WriterIdentity;
  inputs: PlanInputs;
}>): Promise<readonly Readonly<{ path: string; bytes: Uint8Array }>[]> {
  const snapshots = [
    ...(input.previous_rows === undefined ? [] : [{ slot: "previous_complete" as const, rows: input.previous_rows }]),
    { slot: "latest" as const, rows: input.rows },
  ];
  const output: { path: string; bytes: Uint8Array }[] = [];
  for (const snapshot of snapshots) {
    const temporaryRoot = await mkdtemp(join(tmpdir(), "planner-operational-state-snapshot-"));
    try {
      const date = snapshot.rows[0]?.date;
      if (date === undefined || snapshot.rows.some(row => row.date !== date)
        || operationalStateSnapshotDigest(snapshot.rows) !== snapshot.rows[0]!.snapshot_sha256) {
        throw new Error("Operational-state snapshot rows do not form a complete dated snapshot");
      }
      const taskName = `operational-state-${snapshot.slot.replaceAll("_", "-")}`;
      const writerContext = { ...input.writer, task_name: taskName };
      const unitId = createUnitId({
        ledger: "operational-state", covers: date, runId: writerContext.run_id, job: writerContext.job,
        pipelineName: writerContext.pipeline_name, taskName, shard: writerContext.shard,
        producer: writerContext.producer,
      });
      const rows = snapshot.rows.map(row => ({
        identity: RowIdentitySchema.parse({
          ledger: "operational-state", covers: date, run_id: writerContext.run_id,
          attempt: writerContext.attempt, job: writerContext.job,
          pipeline_name: writerContext.pipeline_name, task_name: taskName,
          shard: writerContext.shard, unit_id: unitId,
        }),
        row,
      }));
      const result = await persistLedger({
        ledger: "operational-state", registryEntry: input.inputs.registrations.operational_state,
        rowContract: OperationalStateContract, outputRoot: temporaryRoot, writerContext,
        ledgerSettings: input.inputs.ledgerSettings,
        period: { tier: "compact", period: "daily", covers: date, builtFrom: 1 }, rows,
      });
      if (result.status !== "written" || result.files.length !== 1) {
        throw new Error("Operational-state snapshot did not produce one native Parquet file");
      }
      const temporaryPath = resolve(temporaryRoot, ...result.files[0]!.path.split("/"));
      const readback = await readLedgerParquet(temporaryPath, "operational-state", OperationalStateContract);
      if (!isDeepStrictEqual(readback.rows.map(held => held.row), snapshot.rows)) {
        throw new Error("Operational-state snapshot differs from its native readback");
      }
      output.push({
        path: operationalStateSnapshotPath(input.inputs.registrations.operational_state, snapshot.slot),
        bytes: await readFile(temporaryPath),
      });
    } finally {
      await rm(temporaryRoot, { recursive: true, force: true });
    }
  }
  return output;
}

export function buildOperationalStateRows(input: Readonly<{
  evidence: Evidence; now: string; writer: WriterIdentity; policy: FeedIngestConfig["feedback"];
  parent_revision: number | null;
}>): FeedIngestOperationalStateRow[] {
  if (input.evidence.availability !== "available") return [];
  const estimate = estimateOperationalFeedback(input.evidence, input.policy);
  const stateRevision = (input.parent_revision ?? 0) + 1;
  if (!Number.isSafeInteger(stateRevision) || stateRevision <= 0) throw new Error("Operational state revision exceeds the safe integer range");
  const rows = estimate.sources.filter(source => source.observed_attempted_opportunities > 0)
    .map(source => FeedIngestOperationalStateRowSchema.parse({
      date: input.now.slice(0, 10), state_revision: stateRevision,
      parent_revision: input.parent_revision,
      written_at_utc: input.now, evidence_cutoff_utc: input.now,
      window_days: input.evidence.window.days, window_start: input.evidence.window.start,
      window_end: input.evidence.window.end, code_revision: input.writer.git_sha,
      policy_version: operationalPolicyVersion(input.policy), source_id: source.source_id,
      snapshot_source_ids: null, snapshot_sha256: null,
      evidence_start_utc: input.evidence.sources.find(item => item.source_id === source.source_id)!.evidence_start,
      evidence_end_utc: input.evidence.sources.find(item => item.source_id === source.source_id)!.evidence_end,
      measured_target_requests: source.measured_target_requests,
      measured_source_wasted_requests: source.measured_source_wasted_requests,
      observed_attempted_opportunities: source.observed_attempted_opportunities,
      observed_measured_opportunities: source.observed_measured_opportunities,
      measured_coverage: source.measured_coverage,
      qualification_status: source.qualification_status,
      request_waste_ratio: source.request_waste_ratio,
      operational_penalty: source.qualification_status === "qualified"
        ? source.request_component_penalty : null,
    })).sort((left, right) => left.source_id < right.source_id ? -1 : left.source_id > right.source_id ? 1 : 0);
  if (rows.length === 0) return [];
  const sourceIds = rows.map(row => row.source_id);
  const withRoster = rows.map(row => FeedIngestOperationalStateRowSchema.parse({
    ...row, snapshot_source_ids: sourceIds, snapshot_sha256: "0".repeat(64),
  }));
  const digest = operationalStateSnapshotDigest(withRoster);
  return withRoster.map(row => FeedIngestOperationalStateRowSchema.parse({
    ...row, snapshot_sha256: digest,
  }));
}

export async function writeOperationalState(input: Readonly<{
  evidence: Evidence; now: string; writer: WriterIdentity; policy: FeedIngestConfig["feedback"];
  inputs: PlanInputs; saved: SavedState;
}>): Promise<OperationalStateWrite> {
  const empty: PersistLedgerResult = { status: "empty", files: [] };
  const unavailable = (reason: OperationalStateWrite["reason"]): OperationalStateWrite => ({
    status: "not_written", reason, result: empty,
  });
  if (!input.saved.writable) {
    writeJsonLine({
      timestamp: input.now, level: "WARN", event: "operational_state_save_skipped",
      reason: "state_read_failed", diagnostics: input.saved.errors,
    });
    return unavailable("state_read_failed");
  }
  if (input.evidence.availability !== "available") {
    writeJsonLine({
      timestamp: input.now, level: "WARN", event: "operational_state_save_skipped",
      reason: "history_unavailable", gaps: input.evidence.gaps,
    });
    return unavailable("history_unavailable");
  }
  if (input.evidence.sources.every(source => source.observed_attempted_opportunities === 0)) {
    writeJsonLine({
      timestamp: input.now, level: "INFO", event: "operational_state_save_skipped",
      reason: "known_empty",
    });
    return unavailable("known_empty");
  }
  const rows = buildOperationalStateRows({
    evidence: input.evidence, now: input.now, writer: input.writer, policy: input.policy,
    parent_revision: input.saved.latest_revision,
  });
  if (rows.length === 0) return unavailable("known_empty");
  const stateRevision = rows[0]!.state_revision;
  let result: PersistLedgerResult;
  try {
    result = await persistLedger({
      ledger: "operational-state", registryEntry: input.inputs.registrations.operational_state,
      rowContract: OperationalStateContract, outputRoot: input.inputs.outputRoot,
      writerContext: { ...input.writer, task_name: "operational-state" },
      ledgerSettings: input.inputs.ledgerSettings,
      period: { tier: "raw", covers: input.now.slice(0, 10) }, rows,
    });
    if (result.status !== "written") throw new Error("operational-state write produced no native file");
    const actual: FeedIngestOperationalStateRow[] = [];
    for (const file of result.files) {
      const loaded = await readLedgerParquet(
        resolve(input.inputs.outputRoot, ...file.path.split("/")),
        "operational-state", OperationalStateContract,
      );
      actual.push(...loaded.rows.map(held => held.row));
    }
    if (!isDeepStrictEqual(actual, rows)) throw new Error("operational-state Parquet readback differs from its rows");
    const snapshots = await renderOperationalStateSnapshots({
      rows, ...(input.saved.latest_snapshot_rows === undefined ? {} : { previous_rows: input.saved.latest_snapshot_rows }),
      writer: input.writer, inputs: input.inputs,
    });
    for (const snapshot of snapshots) {
      const target = resolve(input.inputs.outputRoot, ...snapshot.path.split("/"));
      await checkTrustedParent(input.inputs.outputRoot, target);
      await writeAtomically(target, snapshot.bytes);
    }
  } catch (error) {
    writeJsonLine({
      timestamp: input.now, level: "WARN", event: "operational_state_save_failed",
      state_revision: stateRevision, diagnostic: error instanceof Error ? error.message : "unknown_error",
    });
    return unavailable("save_failed");
  }
  return { status: "written", reason: "none", result };
}
