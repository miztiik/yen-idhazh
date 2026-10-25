/** Which unique operation facts remain after replay and revision replacement? */
import { DocumentObservationRecordSchema } from "@idhazh/common-contracts";
import type { DocumentObservationRecord } from "@idhazh/common-contracts";
import { LedgerHistoryReadError } from "./read-ledger-history/ledger-history-error";

export type ObservationNotice = Readonly<{
  event_id: string; target_event_id: string | null;
  reason: "correction_target_unavailable" | "correction_outside_window";
}>;

export function settleIngestObservations(
  input: readonly DocumentObservationRecord[], start: string, end: string,
) {
  const events = new Map<string, DocumentObservationRecord>();
  for (const raw of input) {
    const row = DocumentObservationRecordSchema.parse(raw);
    const prior = events.get(row.event_id);
    if (prior !== undefined && JSON.stringify(prior) !== JSON.stringify(row)) {
      throw new LedgerHistoryReadError(`Conflicting replay of document event ${row.event_id}`);
    }
    events.set(row.event_id, row);
  }
  const notices: ObservationNotice[] = [];
  const replacements = new Map<string, Map<number, DocumentObservationRecord>>();
  const revisionsSeen = new Map<string, Set<number>>();
  const rootOf = (row: DocumentObservationRecord): DocumentObservationRecord | undefined => {
    const visited = new Set<string>();
    let target = row;
    while (target.corrects_event_id !== null) {
      if (visited.has(target.event_id)) throw new LedgerHistoryReadError("Cyclic document correction");
      visited.add(target.event_id);
      const prior = events.get(target.corrects_event_id);
      if (prior === undefined) return undefined;
      target = prior;
    }
    return target;
  };
  for (const row of events.values()) {
    if (row.corrects_event_id === null) continue;
    const target = rootOf(row);
    const revisionKey = target?.event_id ?? row.corrects_event_id;
    const seen = revisionsSeen.get(revisionKey) ?? new Set<number>();
    if (seen.has(row.correction_revision!)) throw new LedgerHistoryReadError(`Tied document correction revision for ${revisionKey}`);
    seen.add(row.correction_revision!);
    revisionsSeen.set(revisionKey, seen);
    if (target === undefined) {
      notices.push({ event_id: row.event_id, target_event_id: row.corrects_event_id, reason: "correction_target_unavailable" });
      continue;
    }
    const day = target.occurred_at.slice(0, 10);
    if (day < start || day > end) {
      notices.push({ event_id: row.event_id, target_event_id: target.event_id, reason: "correction_outside_window" });
      continue;
    }
    for (const field of [
      "observed_run_id", "source_id", "publisher_id", "candidate_id", "article_id",
      "document_kind", "operation", "caused_by_event_id", "request_phase", "request_sequence",
    ] as const) {
      if (row[field] !== target[field]) throw new LedgerHistoryReadError(`Document correction changes ${field}`);
    }
    let revisions = replacements.get(target.event_id);
    if (revisions === undefined) replacements.set(target.event_id, revisions = new Map());
    const revision = row.correction_revision!;
    revisions.set(revision, row);
  }
  const rows = [...events.values()].filter(row => row.corrects_event_id === null
    && row.occurred_at.slice(0, 10) >= start && row.occurred_at.slice(0, 10) <= end)
    .map(original => {
      const revisions = replacements.get(original.event_id);
      if (revisions === undefined) return original;
      const replacement = revisions.get(Math.max(...revisions.keys()))!;
      // Correction time is receipt time, not a new article or request occurrence.
      return { ...replacement, event_id: original.event_id, occurred_at: original.occurred_at,
        corrects_event_id: null, correction_revision: null };
    });
  return { rows, notices };
}
