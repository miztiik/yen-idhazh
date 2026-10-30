/** Builds one typed Parquet file, its stored-row digest, and its envelope metadata. */
import { buildArrowTable } from "./parquet/arrow-builder";
import type { ArrowColumn } from "./parquet/arrow-builder";
import { buildEnvelopeMetadata, buildPlannerEnvelopeMetadata } from "./parquet/envelope-footer";
import { digestRows } from "./parquet/row-digest";
import { readParquetEngineVersion, serializeParquet } from "./parquet/wasm-serializer";
import type { LedgerPeriod, PersistedLedgerFile, ValidatedLedgerWrite } from "./ledger-types";
import { createFileId, createPlannerFileId, createRejectedRawFileId } from "./uuid/file-id";
import { createUnitId } from "./uuid/unit-id";

export async function renderLedgerFile<T extends object>(
  rows: readonly Record<string, unknown>[],
  columns: readonly ArrowColumn[],
  context: ValidatedLedgerWrite<T>,
  covers: string,
  tier: "raw" | "compact",
): Promise<{ file: Omit<PersistedLedgerFile, "path">; data: Uint8Array }> {
  const writerContext = context.writerContext;
  const unit = writerContext === null ? null : createUnitId({
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
  const digest = digestRows(rows, columns);
  const id = context.ledger === "rejected-articles" && tier === "raw"
    ? createRejectedRawFileId(context.input.rowContract.schemaVersion, covers, digest)
    : context.planner ? createPlannerFileId(writtenAtMs)
      : createFileId({ unit: unit!, attempt: writerContext!.attempt, writtenAtMs });
  const compactPeriod: Extract<LedgerPeriod, { tier: "compact" }> | null =
    context.input.period.tier === "compact" ? context.input.period : null;
  const compression = tier === "raw"
    ? context.input.ledgerSettings.compression_raw
    : context.input.ledgerSettings.compression_compact;
  const writerVersion = await readParquetEngineVersion();
  const common = {
    rowSchemaVersion: context.input.rowContract.schemaVersion,
    tier,
    ledger: context.ledger,
    covers,
    period: compactPeriod?.period ?? null,
    fileId: id,
    contentSha256: digest,
    writerVersion,
    compression,
  };
  const metadata = context.planner ? buildPlannerEnvelopeMetadata({
    ...common,
    updatedAt: context.ledger === "feed-health-state"
      ? context.input.updatedAt ?? new Date(writtenAtMs).toISOString() : null,
  }) : buildEnvelopeMetadata({
    ...common, writtenAtMs, identity: writerContext!, unitId: unit!,
    builtFrom: compactPeriod?.builtFrom ?? null,
  });
  const table = buildArrowTable(columns, rows);
  const serialized = await serializeParquet(table, metadata, compression);
  return {
    file: {
      file_id: id,
      ...(unit === null ? {} : { unit_id: unit }),
      covers,
      content_sha256: digest,
      row_count: rows.length,
    },
    data: serialized.data,
  };
}
