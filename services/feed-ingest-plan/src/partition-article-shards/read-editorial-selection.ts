/** Which validated current or proven historical selections retain their original article content? */
import { isDeepStrictEqual } from "node:util";
import { join } from "node:path";
import { EditorialSelectionContract, EditorialSelectionRowSchema } from "@idhazh/common-contracts";
import type { FeedIngestCandidate, WriterIdentity } from "@idhazh/common-contracts";
import type { PersistLedgerResult } from "@idhazh/ledger-file-writer";
import type { CurationResult } from "../curate-article-portfolio/editorial-selection";
import { readLedgerParquet } from "../read-ledger-history/read-parquet";
import type { ProvenAttempt } from "../read-ledger-history/complete-attempt";
import { preparePartitionInput } from "./partition-input";
import { DispatchContract } from "../metrics/audit-contracts";

export async function readCurrentSelections(input: Readonly<{
  curation: Pick<CurationResult, "rows" | "selected">;
  persisted: PersistLedgerResult;
  candidates: readonly FeedIngestCandidate[];
  writer: WriterIdentity;
  outputRoot: string;
  context: Readonly<{ date: string; run_id: string; correlation_id: string }>;
}>) {
  if (input.persisted.status === "skipped") throw new Error("Current editorial ledger was not written");
  if (input.writer.shard !== 0 || input.writer.run_id !== input.context.run_id) throw new Error("Current selections require their unsharded planning writer");
  const rows = [];
  for (const committed of input.persisted.files) {
    const file = await readLedgerParquet(join(input.outputRoot, committed.path), "editorial-selections", EditorialSelectionContract);
    if (file.envelope.tier !== "raw" || file.envelope.covers !== input.context.date
      || committed.covers !== file.envelope.covers || !isDeepStrictEqual(file.envelope.identity, input.writer)
      || file.envelope.identity.shard !== 0 || file.envelope.file_id !== committed.file_id
      || file.envelope.unit_id !== committed.unit_id || file.envelope.content_sha256 !== committed.content_sha256
      || file.rows.length !== committed.row_count) throw new Error("Selection write result differs from the actual current file");
    rows.push(...file.rows.map(held => held.row));
  }
  const ranked = [...rows].sort((a, b) => a.editorial_rank - b.editorial_rank);
  const expected = [...input.curation.rows].sort((a, b) => a.editorial_rank - b.editorial_rank);
  if (!isDeepStrictEqual(ranked, expected)) throw new Error("Persisted selections differ from actual curation rows");
  const original = new Map(input.candidates.map(candidate => [candidate.candidate_id, candidate]));
  const selected = input.curation.selected.map(article => article.candidate);
  if (selected.length !== ranked.length || selected.some(candidate =>
    !isDeepStrictEqual(original.get(candidate.candidate_id), candidate))) {
    throw new Error("Curation did not retain the selected original harvested content");
  }
  return preparePartitionInput(ranked, selected, input.context);
}

export function readHistoricalSelections(attempt: ProvenAttempt) {
  const selections = attempt.rows["editorial-selections"].map(held => EditorialSelectionRowSchema.parse(held.row));
  const dispatches = attempt.rows.dispatches.map(held => DispatchContract.schema.parse(held.row));
  if (selections.length !== dispatches.length) throw new Error("Historical selections and dispatches differ in count");
  const byId = new Map(dispatches.map(dispatch => [dispatch.selection.candidate_id, dispatch]));
  if (byId.size !== dispatches.length || selections.some(selection =>
    !isDeepStrictEqual(byId.get(selection.candidate_id)?.selection, selection))) {
    throw new Error("Historical dispatches do not preserve exact selected identities and ranks");
  }
  return preparePartitionInput(selections, dispatches.map(dispatch => dispatch.content), attempt);
}
