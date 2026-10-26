/** What row and columns do the persisted Parquet bytes actually contain? */
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { tableFromIPC } from "apache-arrow";
import type { Table } from "apache-arrow";
import initializeWasm, { readParquet } from "parquet-wasm/esm";

export async function readTable(root: string, path: string) {
  await initializeWasm();
  const bytes = new Uint8Array(await readFile(join(root, ...path.split("/"))));
  const table = tableFromIPC(readParquet(bytes).intoIPCStream());
  return { table, bytes };
}

export function storedRow(table: Table): Record<string, unknown> {
  const row = table.get(0);
  if (!row) throw new Error("expected one persisted host row");
  return Object.fromEntries(Object.entries(row.toJSON()).map(([name, value]) =>
    [name, typeof value === "bigint" ? Number(value) : value]));
}
