/** Builds the declared Parquet footer keys from a validated ledger envelope. */
import { FileEnvelopeSchema } from "@idhazh/common-contracts";
import type { WriterIdentity } from "@idhazh/common-contracts";

// This stable protocol name identifies files written by this package.
export const LEDGER_PARQUET_WRITER = "idhazh_typescript.ledger.parquet";

export type FooterInput = {
  rowSchemaVersion: string;
  tier: "raw" | "compact";
  ledger: string;
  covers: string;
  period: "daily" | "monthly" | "yearly" | null;
  writtenAtMs: number;
  identity: WriterIdentity;
  unitId: string;
  fileId: string;
  contentSha256: string;
  writerVersion: string;
  compression: "snappy" | "zstd" | "none";
  builtFrom: number | null;
};

export function buildEnvelopeMetadata(input: FooterInput): Map<string, string> {
  const envelope = FileEnvelopeSchema.parse({
    row_schema_version: input.rowSchemaVersion,
    tier: input.tier,
    ledger: input.ledger,
    covers: input.covers,
    period: input.period,
    written_at_ms: input.writtenAtMs,
    identity: input.identity,
    unit_id: input.unitId,
    file_id: input.fileId,
    content_sha256: input.contentSha256,
    writer: LEDGER_PARQUET_WRITER,
    writer_version: input.writerVersion,
    compression: input.compression,
    built_from: input.builtFrom,
  });

  const metadata = new Map<string, string>([
    ["envelope_version", envelope.version],
    ["schema_version", envelope.row_schema_version],
    ["tier", envelope.tier],
    ["ledger", envelope.ledger],
    ["covers", envelope.covers],
    ["period", envelope.period],
    ["written_at_ms", String(envelope.written_at_ms)],
    ["run_id", envelope.identity.run_id],
    ["attempt", String(envelope.identity.attempt).padStart(2, "0")],
    ["job", envelope.identity.job],
    ["pipeline_name", envelope.identity.pipeline_name],
    ["task_name", envelope.identity.task_name],
    ["shard", String(envelope.identity.shard).padStart(2, "0")],
    ["producer", envelope.identity.producer],
    ["unit_id", envelope.unit_id],
    ["file_id", envelope.file_id],
    ["content_sha256", envelope.content_sha256],
    ["git_sha", envelope.identity.git_sha],
    ["writer", envelope.writer],
    ["writer_version", envelope.writer_version],
    ["compression", envelope.compression],
    ["built_from", envelope.built_from === null ? null : String(envelope.built_from)],
  ].filter((entry): entry is [string, string] => entry[1] !== null));
  return metadata;
}
