/** Did every typed screening rejection reach the registered shared Parquet writer? */
import { CandidateRejectionRecordSchema, CandidateRejectionContract } from "@idhazh/common-contracts";
import type { CandidateRejectionRecord } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, LedgerSettings, PersistLedgerResult } from "@idhazh/ledger-file-writer";
import type { WriterIdentity } from "@idhazh/common-contracts";

export type RejectionLedgerContext = {
  outputRoot: string;
  writerContext: WriterIdentity;
  registryEntry: LedgerRegistration;
  ledgerSettings: LedgerSettings;
};

export async function sealRejections(
  rows: readonly CandidateRejectionRecord[],
  date: string,
  context: RejectionLedgerContext,
): Promise<Exclude<PersistLedgerResult, { status: "skipped" }>> {
  const validated = CandidateRejectionRecordSchema.array().parse(rows);
  if (validated.some(row => row.date !== date || row.stage !== "screen-article-candidates")) {
    throw new Error("rejections: rows must match the screening stage and UTC coverage date");
  }
  const result = await persistLedger({
    ...context,
    ledger: "ingest-rejections",
    period: { tier: "raw", covers: date },
    rowContract: CandidateRejectionContract,
    rows: validated,
  });
  if (result.status === "skipped") {
    throw new Error(`rejections.registryEntry.lifecycle_status: ${result.warning.lifecycle_status}; sealing did not complete`);
  }
  return result;
}
