/** Which recorded planning attempt has reproducible original raw-file completion proof? */
import { isDeepStrictEqual } from "node:util";
import { CompletionLedgerSchema, SourceRunRecordSchema } from "@idhazh/common-contracts";
import type { SourceRunRecord } from "@idhazh/common-contracts";
import type { StoredLedgerRow } from "@idhazh/ledger-file-writer";
import type { LedgerDay } from "./read-period";

type CompletionLedger = typeof CompletionLedgerSchema.options[number];
export type AttemptHistory = Readonly<{
  sources: LedgerDay<SourceRunRecord>;
  ledgers: Readonly<Record<CompletionLedger, LedgerDay<object>>>;
}>;
export type ProvenAttempt = Readonly<{
  status: "complete"; date: string; run_id: string; attempt: number; correlation_id: string;
  sources: readonly SourceRunRecord[];
  rows: Readonly<Record<CompletionLedger, readonly StoredLedgerRow<object>[]>>;
}>;
export type AttemptFinding = Readonly<{
  run_id: string; attempt: number; status: "incomplete" | "unverifiable"; reason: string;
}>;
export type AttemptResolution = Readonly<{
  selected: ProvenAttempt | null; findings: readonly AttemptFinding[];
}>;

export function selectCompleteAttempt(history: AttemptHistory, runId?: string): AttemptResolution {
  const groups = new Map<string, StoredLedgerRow<SourceRunRecord>[]>();
  for (const held of history.sources.rows) {
    const row = SourceRunRecordSchema.parse(held.row);
    const observationDay = row.observed_at.slice(0, 10);
    if (row.date !== row.run_id.slice(0, 10)
      || held.identity.covers !== (row.observation_phase === "plan_complete" ? row.date : observationDay)
      || held.identity.ledger !== "source-runs" || held.identity.run_id !== row.run_id
      || held.identity.attempt !== row.attempt) throw new Error("Source completion row differs from its original identity");
    if (row.observation_phase !== "plan_complete" || (runId !== undefined && row.run_id !== runId)) continue;
    const key = `${row.run_id}/${row.attempt}`;
    const group = groups.get(key) ?? [];
    group.push({ identity: held.identity, row });
    groups.set(key, group);
  }
  const findings: AttemptFinding[] = [];
  let selected: ProvenAttempt | null = null;
  const runClocks = new Map<string, string>();
  for (const group of groups.values()) for (const { row } of group) {
    if (row.observed_at > (runClocks.get(row.run_id) ?? "")) runClocks.set(row.run_id, row.observed_at);
  }
  const ordered = [...groups.values()].sort((left, right) =>
    left[0]!.row.run_id === right[0]!.row.run_id
      ? right[0]!.row.attempt - left[0]!.row.attempt
      : runClocks.get(right[0]!.row.run_id)!.localeCompare(runClocks.get(left[0]!.row.run_id)!)
        || right[0]!.row.run_id.localeCompare(left[0]!.row.run_id),
  );
  for (const group of ordered) {
    const first = group[0]!.row;
    let reason: string | null = null;
    let status: AttemptFinding["status"] = "incomplete";
    if (history.sources.status === "lost" || history.sources.status === "missing") reason = "Source-run evidence is unavailable";
    const sources = new Map<string, SourceRunRecord>();
    for (const { row } of group) {
      const previous = sources.get(row.source_id);
      if (previous !== undefined && !isDeepStrictEqual(previous, row)) reason = "Source completion records disagree";
      sources.set(row.source_id, row);
      if (row.correlation_id !== first.correlation_id || row.expected_source_count !== first.expected_source_count
        || !isDeepStrictEqual(row.completion_evidence, first.completion_evidence)) reason = "Attempt completion evidence differs between sources";
    }
    if (sources.size !== first.expected_source_count || first.expected_source_count === 0) reason = "Expected source outcomes are incomplete";
    const rows: Record<CompletionLedger, StoredLedgerRow<object>[]> = {
      "editorial-selections": [], dispatches: [], rejections: [], "article-assessments": [], diversity: [],
    };
    for (const evidence of first.completion_evidence!) {
      const day = history.ledgers[evidence.ledger];
      if (day.ledger !== evidence.ledger || day.day !== first.date) throw new Error("Completion ledger belongs to another day");
      if (day.status === "missing" || day.status === "lost") {
        reason ??= `${evidence.ledger}: required history is ${day.status}`;
        continue;
      }
      for (const commitment of evidence.files) {
        const file = day.files.find(file => file.envelope.tier === "raw" && file.envelope.file_id === commitment.file_id);
        if (file === undefined) {
          if (day.tier !== "raw") {
            reason ??= `${evidence.ledger}: original raw-file membership and order are unavailable after packing`;
            status = "unverifiable";
          } else reason ??= `${evidence.ledger}: original completion file is missing`;
          continue;
        }
        if (file.envelope.content_sha256 !== commitment.content_sha256 || file.rows.length !== commitment.row_count) {
          reason ??= `${evidence.ledger}: recorded file commitment differs from verified original rows`;
          continue;
        }
        if (file.rows.some(held => {
          const row = held.row as Record<string, unknown>;
          const selection = row.selection;
          const correlation = typeof selection === "object" && selection !== null && "correlation_id" in selection
            ? selection.correlation_id : row.correlation_id;
          return held.identity.run_id !== first.run_id || held.identity.attempt !== first.attempt
            || held.identity.covers !== first.date || correlation !== first.correlation_id;
        })) {
          reason ??= `${evidence.ledger}: committed file contains another attempt or correlation`;
          continue;
        }
        rows[evidence.ledger].push(...file.rows);
      }
      if (rows[evidence.ledger].length !== evidence.row_count) {
        reason ??= `${evidence.ledger}: verified row count does not match completion evidence`;
      }
    }
    const selectedCount = [...sources.values()].reduce((count, row) => count + (row.selected_count ?? 0), 0);
    if ([...sources.values()].some(row => row.selected_count === null)
      || selectedCount !== rows["editorial-selections"].length || selectedCount !== rows.dispatches.length) {
      reason ??= "Selected source counts do not reconcile with selections and dispatches";
    }
    if (reason !== null) {
      findings.push({ run_id: first.run_id, attempt: first.attempt, status, reason });
      continue;
    }
    selected ??= {
      status: "complete", date: first.date, run_id: first.run_id, attempt: first.attempt,
      correlation_id: first.correlation_id, sources: [...sources.values()], rows,
    };
  }
  return { selected, findings };
}
