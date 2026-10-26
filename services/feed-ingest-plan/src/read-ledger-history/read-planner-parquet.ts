/** Verify one current planner file without inventing generic row or writer identities. */
import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import { tableFromIPC } from "apache-arrow";
import initializeParquet, { readMetadata, readParquet } from "parquet-wasm/esm";
import {
  PlannerFileEnvelopeSchema, PLANNER_FOOTER_METADATA_KEYS, PLANNER_OPTIONAL_FOOTER_METADATA_KEYS,
} from "@idhazh/common-contracts";
import type { PlannerFileEnvelope } from "@idhazh/common-contracts";
import { describeObjectSchema, digestRows } from "@idhazh/ledger-file-writer";
import type { LedgerRowContract } from "@idhazh/ledger-file-writer";
import { checkFields, normalize } from "./read-parquet";
import { LedgerHistoryReadError } from "./ledger-history-error";

let initialization: ReturnType<typeof initializeParquet> | undefined;
export async function readPlannerParquet<T extends object>(
  path: string, ledger: PlannerFileEnvelope["ledger"], contract: LedgerRowContract<T>,
) {
  initialization ??= initializeParquet();
  await initialization;
  const bytes = await readFile(path);
  const metadata = readMetadata(bytes);
  const footer = metadata.fileMetadata();
  let envelope: PlannerFileEnvelope;
  try {
    const values = footer.keyValueMetadata();
    // Arrow embeds the physical schema under this standardized container key.
    const permitted = new Set<string>([...PLANNER_FOOTER_METADATA_KEYS, "ARROW:schema"]);
    if ([...values].some(([key, value]) => typeof key !== "string" || typeof value !== "string" || !permitted.has(key))) {
      throw new LedgerHistoryReadError("Planner footer contains an undeclared key or value");
    }
    for (const key of PLANNER_FOOTER_METADATA_KEYS) {
      if (!(PLANNER_OPTIONAL_FOOTER_METADATA_KEYS as readonly string[]).includes(key) && !values.has(key)) {
        throw new LedgerHistoryReadError(`Planner footer is missing ${key}`);
      }
    }
    envelope = PlannerFileEnvelopeSchema.parse({
      version: values.get("envelope_version"), row_schema_version: values.get("schema_version"),
      tier: values.get("tier"), ledger: values.get("ledger"), covers: values.get("covers"),
      period: values.get("period") ?? null, file_id: values.get("file_id"),
      content_sha256: values.get("content_sha256"), writer: values.get("writer"),
      writer_version: values.get("writer_version"), compression: values.get("compression"), updated_at: values.get("updated_at") ?? null,
    });
  } finally { footer.free(); metadata.free(); }
  if (envelope.ledger !== ledger || envelope.row_schema_version !== contract.schemaVersion) {
    throw new LedgerHistoryReadError("Planner file does not match its current ledger contract");
  }
  if (envelope.tier === "raw" && basename(path) !== `${envelope.file_id}.parquet`) {
    throw new LedgerHistoryReadError("Planner raw filename differs from its file identity");
  }
  const table = tableFromIPC(readParquet(bytes).intoIPCStream());
  const columns = describeObjectSchema(contract.schema).fields;
  checkFields(table.schema.fields, columns);
  const records = table.toArray().map(value => {
    const row = normalize(value);
    if (typeof row !== "object" || row === null || Array.isArray(row)) throw new LedgerHistoryReadError("Planner row must be an object");
    return row as Record<string, unknown>;
  });
  if (digestRows(records, columns) !== envelope.content_sha256) throw new LedgerHistoryReadError("Planner row digest differs from its footer");
  const rows = records.map(record => contract.schema.parse(record));
  for (const row of rows) {
    if (!("date" in row) || typeof row.date !== "string" || !(row.date === envelope.covers
      || (envelope.tier === "compact" && row.date.startsWith(`${envelope.covers}-`)))) {
      throw new LedgerHistoryReadError("Planner row lies outside its file's UTC coverage");
    }
  }
  return { envelope, rows, bytes: bytes.byteLength, file_sha256: Bun.CryptoHasher.hash("sha256", bytes, "hex") };
}
