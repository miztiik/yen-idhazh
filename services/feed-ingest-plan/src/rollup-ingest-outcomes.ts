/** What article opportunities and actual requests are supported by settled operation facts? */
import type { DocumentObservationRecord } from "@idhazh/common-contracts";
import { LedgerHistoryReadError } from "./read-ledger-history/ledger-history-error";

type Observation = DocumentObservationRecord;
export type IngestEvidenceTotals = Readonly<{
  observed_attempted_opportunities: number;
  observed_measured_opportunities: number;
  request_coverage: number | null;
  evidence_start: string | null;
  evidence_end: string | null;
  extracted_opportunities: number;
  source_failed_opportunities: number;
  pipeline_failed_opportunities: number;
  unresolved_opportunities: number;
  observed_target_requests: number;
  observed_source_wasted_requests: number;
  total_target_requests: number | null;
  source_wasted_requests: number | null;
  waste_ratio: number | null;
  availability: "available" | "partial" | "unavailable";
  cpu: null;
  private_memory: null;
}>;

export function articleOpportunityKey(row: Observation): string | null {
  return row.document_kind === "article" && row.observed_run_id !== null
    && row.source_id !== null && row.candidate_id !== null
    ? JSON.stringify([row.observed_run_id, row.source_id, row.candidate_id]) : null;
}

function totals(rows: readonly Observation[], historyComplete: boolean): IngestEvidenceTotals {
  const opportunities = new Map<string, Observation[]>();
  for (const row of rows) {
    const key = articleOpportunityKey(row);
    if (key === null || row.outcome === "not_attempted") continue;
    const held = opportunities.get(key) ?? [];
    held.push(row);
    opportunities.set(key, held);
  }
  let measured = 0, extracted = 0, sourceFailed = 0, pipelineFailed = 0, unresolved = 0;
  let requests = 0, waste = 0;
  for (const facts of opportunities.values()) {
    const byId = new Map(facts.map(row => [row.event_id, row]));
    const fetches = facts.filter(row => row.operation === "fetch");
    const attempts = facts.filter(row => row.operation === "attempt");
    const parses = facts.filter(row => row.operation === "parse");
    const ancestorFetch = (row: Observation): Observation | undefined => {
      const visited = new Set<string>();
      let current: Observation | undefined = row;
      while (current !== undefined) {
        if (visited.has(current.event_id)) throw new LedgerHistoryReadError("Cyclic document operation lineage");
        visited.add(current.event_id);
        if (current.operation === "fetch") return current;
        current = current.caused_by_event_id === null ? undefined : byId.get(current.caused_by_event_id);
      }
      return undefined;
    };
    const failed = facts.filter(row => row.operation !== "attempt" && row.outcome === "failed");
    const extractedHere = parses.some(row => row.outcome === "success");
    if (extractedHere) extracted++;
    if (failed.some(row => row.attribution === "source")) sourceFailed++;
    if (failed.some(row => row.attribution === "pipeline")) pipelineFailed++;
    if (failed.some(row => row.attribution === "unresolved") || !extractedHere && failed.length === 0) unresolved++;

    const wastedFetches = new Set<string>();
    for (const row of failed.filter(row => row.attribution === "source")) {
      const fetch = ancestorFetch(row);
      if (fetch !== undefined) wastedFetches.add(fetch.event_id);
    }
    const linked = new Map<string, Observation[]>();
    let complete = fetches.length > 0;
    for (const row of attempts) {
      const fetch = ancestorFetch(row);
      if (fetch === undefined) { complete = false; continue; }
      const held = linked.get(fetch.event_id) ?? [];
      held.push(row);
      linked.set(fetch.event_id, held);
    }
    for (const fetch of fetches) {
      const held = linked.get(fetch.event_id) ?? [];
      const sequences = held.map(row => row.request_sequence!).sort((a, b) => a - b);
      if (held.length === 0 || sequences.some((sequence, index) => sequence !== index)
        || held.some(row => row.request_coverage !== "complete")) complete = false;
    }
    for (const row of attempts) {
      if (row.request_phase !== "target") continue;
      const count = row.dispatched_request_count ?? 0;
      requests += count;
      const fetch = ancestorFetch(row);
      if (fetch !== undefined && wastedFetches.has(fetch.event_id)) waste += count;
    }
    if (complete) measured++;
  }
  const attempted = opportunities.size;
  const evidenceDates = [...opportunities.values()].flat().map(row => row.occurred_at).sort();
  const complete = historyComplete && attempted > 0 && measured === attempted;
  const knownWaste = complete && unresolved === 0;
  return {
    observed_attempted_opportunities: attempted, observed_measured_opportunities: measured,
    request_coverage: historyComplete && attempted > 0 ? measured / attempted : null,
    evidence_start: evidenceDates[0] ?? null, evidence_end: evidenceDates.at(-1) ?? null,
    extracted_opportunities: extracted, source_failed_opportunities: sourceFailed,
    pipeline_failed_opportunities: pipelineFailed, unresolved_opportunities: unresolved,
    observed_target_requests: requests, observed_source_wasted_requests: waste,
    total_target_requests: complete ? requests : null,
    source_wasted_requests: knownWaste ? waste : null,
    waste_ratio: knownWaste && requests > 0 ? waste / requests : null,
    availability: knownWaste ? "available" : attempted > 0 ? "partial" : "unavailable",
    cpu: null, private_memory: null,
  };
}

export function rollupIngestOutcomes(rows: readonly Observation[], historyComplete: boolean) {
  const sources = new Map<string, Observation[]>();
  const publishers = new Map<string, Observation[]>();
  for (const row of rows) {
    if (row.source_id !== null) {
      const held = sources.get(row.source_id) ?? [];
      held.push(row); sources.set(row.source_id, held);
    }
    if (row.publisher_id !== null) {
      const held = publishers.get(row.publisher_id) ?? [];
      held.push(row); publishers.set(row.publisher_id, held);
    }
  }
  const ordered = (groups: Map<string, Observation[]>) => [...groups].sort(([a], [b]) => a.localeCompare(b));
  return {
    sources: ordered(sources).map(([source_id, facts]) => ({ source_id, ...totals(facts, historyComplete) })),
    publishers: ordered(publishers).map(([publisher_id, facts]) => ({ publisher_id, ...totals(facts, historyComplete) })),
    unallocated: {
      observation_count: rows.filter(row => articleOpportunityKey(row) === null).length,
      observed_dispatched_requests: rows.filter(row => articleOpportunityKey(row) === null && row.operation === "attempt")
        .reduce((sum, row) => sum + (row.dispatched_request_count ?? 0), 0),
    },
  };
}
