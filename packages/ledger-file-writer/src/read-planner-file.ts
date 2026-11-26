/** What one planner Parquet file proves before a consumer validates its fields. */
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import {
  PlannerFileEnvelopeSchema, PlannerStoredFileEnvelopeSchema, PLANNER_FOOTER_METADATA_KEYS, PLANNER_OPTIONAL_FOOTER_METADATA_KEYS,
  PLANNER_ENVELOPE_VERSION, PLANNER_ROW_SCHEMA_VERSIONS, SchemaVersionSchema,
} from "@idhazh/common-contracts";
import type { PlannerStoredFileEnvelope } from "@idhazh/common-contracts";
import { describeObjectSchema } from "./row-schema";
import { checkParquetFields, readParquetFooter, readVerifiedParquetRows } from "./parquet/read-verified-table";
import { initializeParquetWasm } from "./parquet/wasm-serializer";
import type { LedgerRowContract } from "./ledger-types";

export class PlannerLedgerFileError extends Error {
  override readonly name: string = "PlannerLedgerFileError";
}
export class PlannerUnsupportedFormatError extends PlannerLedgerFileError {
  override readonly name = "PlannerUnsupportedFormatError";
  constructor(ledger: PlannerStoredFileEnvelope["ledger"], readonly envelopeVersion: string, readonly rowSchemaVersion: string) {
    super(`${ledger} requires envelope ${PLANNER_ENVELOPE_VERSION} and row ${PLANNER_ROW_SCHEMA_VERSIONS[ledger]}; found envelope ${envelopeVersion} and row ${rowSchemaVersion}`);
  }
}

const plannerFailure = (message: string, cause?: unknown) => new PlannerLedgerFileError(`Planner ${message}`, { cause });

async function loadStoredPlannerParquet(path: string, ledger: PlannerStoredFileEnvelope["ledger"]) {
  await initializeParquetWasm();
  const bytes = await readFile(path);
  const values = readParquetFooter(bytes, PLANNER_FOOTER_METADATA_KEYS, PLANNER_OPTIONAL_FOOTER_METADATA_KEYS, plannerFailure);
  const footerLedger = values.get("ledger");
  const rowSchemaVersion = values.get("schema_version");
  const envelopeVersion = values.get("envelope_version");
  if (footerLedger === ledger && SchemaVersionSchema.safeParse(envelopeVersion).success
    && SchemaVersionSchema.safeParse(rowSchemaVersion).success
    && envelopeVersion !== PLANNER_ENVELOPE_VERSION) {
    throw new PlannerUnsupportedFormatError(ledger, envelopeVersion!, rowSchemaVersion!);
  }
  const envelope = PlannerStoredFileEnvelopeSchema.parse({
    version: envelopeVersion, row_schema_version: rowSchemaVersion,
    tier: values.get("tier"), ledger: footerLedger, covers: values.get("covers"),
    period: values.get("period") ?? null, file_id: values.get("file_id"),
    content_sha256: values.get("content_sha256"), writer: values.get("writer"),
    writer_version: values.get("writer_version"), compression: values.get("compression"),
    updated_at: values.get("updated_at") ?? null,
  });
  if (envelope.ledger !== ledger) {
    throw new PlannerLedgerFileError("Planner file does not match its registered ledger");
  }
  if (envelope.tier === "raw" && basename(path) !== `${envelope.file_id}.parquet`) {
    throw new PlannerLedgerFileError("Planner raw filename differs from its file identity");
  }
  return {
    envelope, ...readVerifiedParquetRows(bytes, envelope.content_sha256, plannerFailure), bytes: bytes.byteLength,
    file_sha256: createHash("sha256").update(bytes).digest("hex"),
  };
}

export async function readStoredPlannerParquet(path: string, ledger: PlannerStoredFileEnvelope["ledger"]) {
  const { fields, ...stored } = await loadStoredPlannerParquet(path, ledger);
  return stored;
}

export async function readPlannerParquet<T extends object>(
  path: string, ledger: PlannerStoredFileEnvelope["ledger"], contract: LedgerRowContract<T>,
) {
  const { fields, ...stored } = await loadStoredPlannerParquet(path, ledger);
  if (stored.envelope.row_schema_version !== PLANNER_ROW_SCHEMA_VERSIONS[ledger]) {
    throw new PlannerUnsupportedFormatError(ledger, stored.envelope.version, stored.envelope.row_schema_version);
  }
  if (stored.envelope.row_schema_version !== contract.schemaVersion) {
    throw new PlannerLedgerFileError(
      `Planner ${ledger} requires its current row schema ${contract.schemaVersion}`,
    );
  }
  const envelope = PlannerFileEnvelopeSchema.parse(stored.envelope);
  checkParquetFields(fields, describeObjectSchema(contract.schema).fields, plannerFailure);
  return { ...stored, envelope, rows: stored.rows.map(row => contract.schema.parse(row)) };
}
