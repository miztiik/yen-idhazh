/** Build real Parquet variants from one named recorded health row. */
import { readFile, writeFile } from "node:fs/promises";
import { z } from "zod";
import {
  FeedHealthStateRowContract, FeedHealthStateRowSchema,
} from "@idhazh/common-contracts";
import { describeObjectSchema, digestRows } from "@idhazh/ledger-file-writer";
import initializeParquet, { readMetadata } from "parquet-wasm/esm";
import { buildArrowTable } from "../../../packages/ledger-file-writer/src/parquet/arrow-builder";
import { serializeParquet } from "../../../packages/ledger-file-writer/src/parquet/wasm-serializer";
import { writeRows } from "./partition-fixtures";

export async function healthFieldFixture(root: string) {
  const row = FeedHealthStateRowSchema.parse(await Bun.file(
    new URL("../../../tests/fixtures/feed-ingest-plan/health-field-history.json", import.meta.url),
  ).json());
  const written = await writeRows(root, "feed-health-state", row.date, FeedHealthStateRowContract, [row]);
  return { row, written };
}

export async function rewriteHealthFields(
  path: string, rows: readonly Record<string, unknown>[], schema: z.ZodType,
  options: { stamp?: string; preserve_digest?: boolean; metadata?: Readonly<Record<string, string>> } = {},
) {
  await initializeParquet();
  const metadata = readMetadata(await readFile(path));
  const footer = metadata.fileMetadata();
  const pairs = new Map(footer.keyValueMetadata());
  footer.free();
  metadata.free();
  const columns = describeObjectSchema(schema).fields;
  const table = buildArrowTable(columns, rows);
  if (!options.preserve_digest) pairs.set("content_sha256", digestRows(rows, columns));
  if (options.stamp !== undefined) pairs.set("schema_version", options.stamp);
  for (const [key, value] of Object.entries(options.metadata ?? {})) pairs.set(key, value);
  await writeFile(path, (await serializeParquet(table, pairs, "snappy")).data);
}
