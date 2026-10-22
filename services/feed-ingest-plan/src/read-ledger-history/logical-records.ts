/** Which unique records belong to one attempt, regardless of file layout or order? */
import { createHash } from "node:crypto";
import {
  ArticleAssessmentContract, CandidateRejectionContract, CONTRACT_VERSION,
  DiversityMetricRowSchema, EditorialSelectionRowSchema, FEED_INGEST_AUDIT_VERSION,
  FeedIngestDispatchSchema, LogicalLedgerCommitmentSchema,
} from "@idhazh/common-contracts";
import type { LedgerCompletionEvidence } from "@idhazh/common-contracts";
import { describeObjectSchema, digestRows } from "@idhazh/ledger-file-writer";
import type { LedgerRowContract, StoredLedgerRow } from "@idhazh/ledger-file-writer";

type Ledger = LedgerCompletionEvidence["ledger"];
// These are the production settlement keys in backend/idhazh/ledger/keys.py.
export const PLANNING_RECORD_KEYS = {
  dispatches: ["content.date", "content.candidate_id"],
  "editorial-selections": ["date", "candidate_id"],
  rejections: ["date", "source_id", "subject", "candidate_id", "stage"],
  "article-assessments": ["date", "candidate_id", "stage"],
  "source-runs": ["date", "source_id", "observation_phase"],
  diversity: ["date", "metric", "basis", "unit", "dimension", "dimension_value", "stage",
    "window_days", "window_start", "window_end", "top_k"],
} as const;
const contracts: Record<Ledger, LedgerRowContract<object>> = {
  dispatches: { schema: FeedIngestDispatchSchema, schemaVersion: FEED_INGEST_AUDIT_VERSION },
  "editorial-selections": { schema: EditorialSelectionRowSchema, schemaVersion: CONTRACT_VERSION },
  rejections: CandidateRejectionContract,
  "article-assessments": ArticleAssessmentContract,
  diversity: { schema: DiversityMetricRowSchema, schemaVersion: FEED_INGEST_AUDIT_VERSION },
};
export type AttemptIdentity = Readonly<{ date: string; run_id: string; attempt: number; correlation_id: string }>;
function at(row: object, path: string): unknown {
  let value: unknown = row;
  for (const segment of path.split(".")) {
    if (typeof value !== "object" || value === null || !(segment in value)) throw new Error(`Missing logical record key ${path}`);
    value = (value as Record<string, unknown>)[segment];
  }
  return value;
}
export function commitLogicalRecords(
  ledger: Ledger, input: readonly StoredLedgerRow<object>[], attempt: AttemptIdentity,
  schemaVersion = contracts[ledger].schemaVersion,
) {
  const contract = contracts[ledger];
  const legacy = schemaVersion === contract.schemaVersion ? undefined : contract.legacyVersions?.[schemaVersion];
  if (schemaVersion !== contract.schemaVersion && legacy === undefined) {
    throw new Error(`${ledger}: unsupported logical record schema version ${schemaVersion}`);
  }
  const fields = describeObjectSchema(legacy?.schema ?? contract.schema).fields;
  const unique = new Map<string, { held: StoredLedgerRow<object>; digest: string }>();
  for (const held of input) {
    const identity = held.identity;
    if (identity.ledger !== ledger || identity.covers !== attempt.date
      || identity.run_id !== attempt.run_id || identity.attempt !== attempt.attempt) {
      throw new Error(`${ledger}: logical record belongs to another attempt`);
    }
    const row = contract.schema.parse(held.row);
    const correlation = at(row, ledger === "dispatches" ? "selection.correlation_id" : "correlation_id");
    const date = at(row, ledger === "dispatches" ? "selection.date" : "date");
    if (correlation !== attempt.correlation_id || date !== attempt.date) {
      throw new Error(`${ledger}: logical record belongs to another correlation or date`);
    }
    const key = JSON.stringify(PLANNING_RECORD_KEYS[ledger].map(path => at(row, path)));
    const encoded = legacy === undefined ? row : legacy.schema.parse(encodeHistoricalRecord(ledger, row, schemaVersion));
    const digest = digestRows([encoded as Record<string, unknown>], fields);
    const previous = unique.get(key);
    if (previous !== undefined && previous.digest !== digest) throw new Error(`${ledger}: conflicting duplicate logical record ${key}`);
    unique.set(key, previous ?? { held: { identity, row }, digest });
  }

  function encodeHistoricalRecord(ledger: Ledger, row: object, version: string): object {
    if (ledger === "rejections") {
      const current = CandidateRejectionContract.schema.parse(row);
      const { diagnostics, ...details } = current.details;
      if (diagnostics !== null) throw new Error("Historical rejection proof cannot omit measured diagnostics");
      return { ...current, version, details };
    }
    if (ledger === "article-assessments") {
      const { diagnostics, ...current } = ArticleAssessmentContract.schema.parse(row);
      if (diagnostics !== null) throw new Error("Historical assessment proof cannot omit measured diagnostics");
      if (version === CONTRACT_VERSION) {
        const { timing_at, timing_basis, ...original } = current;
        if (timing_basis === "first_seen") throw new Error("Historical assessment proof cannot represent first sight");
        return { ...original, version, effective_published_at: timing_at, publication_clock: timing_basis };
      }
      return { ...current, version };
    }
    throw new Error(`${ledger}: historical logical record encoding is not declared`);
  }
  const ordered = [...unique].sort(([left], [right]) => left < right ? -1 : left > right ? 1 : 0);
  // A protocol encoding: header then key/digest pairs, one JSON array per line.
  const hash = createHash("sha256").update(`${JSON.stringify([
    "2026-10-22", ledger, schemaVersion, attempt.date, attempt.run_id, attempt.attempt, attempt.correlation_id,
  ])}\n`);
  for (const [key, { digest }] of ordered) hash.update(`${JSON.stringify([key, digest])}\n`);
  return {
    commitment: LogicalLedgerCommitmentSchema.parse({
      version: "2026-10-22", row_schema_version: schemaVersion,
      row_count: ordered.length, content_sha256: hash.digest("hex"),
    }),
    rows: ordered.map(([, value]) => value.held),
  };
}
