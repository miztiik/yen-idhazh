/** Save completed document facts without making a failed save repeat the work. */
import { DocumentObservationRecordSchema } from "@idhazh/common-contracts";
import type { DocumentObservationRecord, WriterIdentity } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRegistration, LedgerSettings, PersistedLedgerFile, PersistLedgerResult } from "@idhazh/ledger-file-writer";
import { DocumentObservationContract } from "./metrics/audit-contracts";

export function createIngestObservations(input: {
  writer: WriterIdentity; outputRoot: string; registration: LedgerRegistration; settings: LedgerSettings;
  on_persisted?: (files: readonly PersistedLedgerFile[]) => void;
}) {
  if (input.registration.name !== "document-observations" || input.registration.family !== "feed-ingest-plan"
    || input.registration.lifecycle_status !== "active") {
    throw new Error("document-observations requires its active registered ledger");
  }
  const files: PersistedLedgerFile[] = [];
  const failures: Error[] = [];
  return {
    async save(raw: readonly DocumentObservationRecord[]) {
      const days = new Map<string, DocumentObservationRecord[]>();
      for (const candidate of raw) {
        const row = DocumentObservationRecordSchema.parse(candidate);
        const day = row.occurred_at.slice(0, 10);
        const rows = days.get(day) ?? [];
        rows.push(row);
        days.set(day, rows);
      }
      for (const [covers, rows] of days) {
        const unit = rows.at(-1)!;
        let written: PersistLedgerResult;
        try {
          written = await persistLedger({
            ledger: "document-observations", registryEntry: input.registration,
            outputRoot: input.outputRoot,
            writerContext: { ...input.writer, task_name: `document-${unit.operation}-${unit.event_id}` },
            ledgerSettings: input.settings,
            rowContract: DocumentObservationContract, period: { tier: "raw", covers }, rows,
          });
          if (written.status !== "written") throw new Error("document-observations save produced no file");
        } catch (cause) {
          const error = new Error("document-observations save failed; completed work and files are retained", { cause });
          failures.push(error);
          process.stderr.write(`${JSON.stringify({
            event: "document_observation_save_failed", event_ids: rows.map(row => row.event_id),
          })}\n`);
          continue;
        }
        files.push(...written.files);
        input.on_persisted?.(written.files);
      }
    },
    assertSaved() {
      if (failures.length) throw new AggregateError(failures, "document-observations save failed; completed work and files are retained");
    },
    result(): PersistLedgerResult {
      if (failures.length) throw new AggregateError(failures, "document-observations save failed; completed work and files are retained");
      return files.length ? { status: "written", files: [...files] } : { status: "empty", files: [] };
    },
  };
}
export type IngestObservations = ReturnType<typeof createIngestObservations>;
