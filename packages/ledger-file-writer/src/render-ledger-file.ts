/** Builds one typed Parquet file, its stored-row digest, and its envelope metadata. */
import type { WriterIdentity } from "@idhazh/common-contracts";
import { buildArrowTable } from "./parquet/arrow-builder";
import type { ArrowColumn } from "./parquet/arrow-builder";
import { buildEnvelopeMetadata } from "./parquet/envelope-footer";
import { digestRows } from "./parquet/row-digest";
import { readParquetEngineVersion, serializeParquet } from "./parquet/wasm-serializer";
import type { LedgerPeriod, PersistedLedgerFile, ValidatedLedgerWrite } from "./ledger-types";
import { createFileId } from "./uuid/file-id";
import { createUnitId } from "./uuid/unit-id";

export async function renderLedgerFile<T extends object>(
  rows: readonly Record<string, unknown>[],
  columns: readonly ArrowColumn[],
  context: ValidatedLedgerWrite<T>,
  covers: string,
  tier: "raw" | "compact",
): Promise<{ file: Omit<PersistedLedgerFile, "path">; data: Uint8Array }> {
  const writerContext: WriterIdentity = context.writerContext;
  const unit = createUnitId({
    ledger: context.ledger,
    covers,
    runId: writerContext.run_id,
    job: writerContext.job,
    pipelineName: writerContext.pipeline_name,
    taskName: writerContext.task_name,
    shard: writerContext.shard,
    producer: writerContext.producer,
  });
  const writtenAtMs = Date.now();
  const id = createFileId({ unit, attempt: writerContext.attempt, writtenAtMs });
  const digest = digestRows(rows, columns);
  const compactPeriod: Extract<LedgerPeriod, { tier: "compact" }> | null =
    context.input.period.tier === "compact" ? context.input.period : null;
  const compression = tier === "raw"
    ? context.input.ledgerSettings.compression_raw
    : context.input.ledgerSettings.compression_compact;
  const writerVersion = await readParquetEngineVersion();
  const metadata = buildEnvelopeMetadata({
    rowSchemaVersion: context.input.rowContract.schemaVersion,
    tier,
    ledger: context.ledger,
    covers,
    period: compactPeriod?.period ?? null,
    writtenAtMs,
    identity: writerContext,
    unitId: unit,
    fileId: id,
    contentSha256: digest,
    writerVersion,
    compression,
    builtFrom: compactPeriod?.builtFrom ?? null,
  });
  const table = buildArrowTable(columns, rows);
  const serialized = await serializeParquet(table, metadata, compression);
  return {
    file: {
      file_id: id,
      unit_id: unit,
      covers,
      content_sha256: digest,
      row_count: rows.length,
    },
    data: serialized.data,
  };
}
