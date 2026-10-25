/** Read each named native observation file produced by one recorded invocation. */
import { expect } from "bun:test";
import { join } from "node:path";
import type { PersistedLedgerFile } from "@idhazh/ledger-file-writer";
import { DocumentObservationContract } from "../src/metrics/audit-contracts";
import { readLedgerParquet } from "../src/read-ledger-history/read-parquet";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { fileURLToPath } from "node:url";
import { createIngestObservations } from "../src/ingest-observations";
import type { HarvestContext } from "../src/harvest-feeds/harvest-types";

export async function recordHarvestObservations(outputRoot: string, context: HarvestContext) {
  const inputs = await loadPlanInputs(fileURLToPath(new URL("../../../", import.meta.url)));
  const observations = createIngestObservations({
    writer: context.writer, outputRoot, registration: inputs.registrations.document_observations,
    settings: inputs.ledgerSettings,
  });
  context.observations = observations;
  context.observation_clock = context.clock ?? (() => new Date());
  return observations;
}

export async function readObservationFiles(root: string, files: readonly PersistedLedgerFile[]) {
  const saved = await Promise.all(files.map(async file => {
    const actual = await readLedgerParquet(join(root, ...file.path.split("/")), "document-observations", DocumentObservationContract);
    expect(actual.envelope).toMatchObject({
      tier: "raw", content_sha256: file.content_sha256, file_id: file.file_id, unit_id: file.unit_id,
      row_schema_version: DocumentObservationContract.schemaVersion,
    });
    expect(actual.rows).toHaveLength(file.row_count);
    expect(actual.rows.every(({ row }) => row.occurred_at.slice(0, 10) === actual.envelope.covers)).toBe(true);
    return actual.rows;
  }));
  return saved.flat();
}
