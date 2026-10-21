/** Writes typed Arrow tables to Parquet and reports the engine and memory used. */
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { Compression, Table as WasmTable, WriterPropertiesBuilder, default as initializeWasm, wasmMemory, writeParquet } from "parquet-wasm/esm";
import { tableToIPC } from "apache-arrow";
import type { Table } from "apache-arrow";
import { LEDGER_PARQUET_WRITER } from "./envelope-footer";

type PackageMetadata = { version: string };

let wasmInitialization: ReturnType<typeof initializeWasm> | undefined;
let writerVersionValue: Promise<string> | undefined;

export async function readParquetEngineVersion(): Promise<string> {
  writerVersionValue ??= (async () => {
    const wasmEntry = import.meta.resolve("parquet-wasm");
    const arrowEntry = import.meta.resolve("apache-arrow");
    const wasmPackageUrl = new URL("../package.json", wasmEntry);
    const arrowPackageUrl = new URL("./package.json", arrowEntry);
    const [wasmPackage, arrowPackage] = await Promise.all([
      readFile(fileURLToPath(wasmPackageUrl), "utf8").then((text) => JSON.parse(text) as PackageMetadata),
      readFile(fileURLToPath(arrowPackageUrl), "utf8").then((text) => JSON.parse(text) as PackageMetadata),
    ]);
    return `parquet-wasm-${wasmPackage.version}; apache-arrow-${arrowPackage.version}`;
  })();
  return writerVersionValue;
}

function toParquetCompression(compression: "snappy" | "zstd" | "none"): Compression {
  switch (compression) {
    case "snappy": return Compression.SNAPPY;
    case "zstd": return Compression.ZSTD;
    case "none": return Compression.UNCOMPRESSED;
  }
}

export type ParquetBytes = {
  data: Uint8Array;
  writerVersion: string;
  wasmMemoryBytes: number;
};

export async function serializeParquet(
  table: Table,
  metadata: Map<string, string>,
  compression: "snappy" | "zstd" | "none",
): Promise<ParquetBytes> {
  wasmInitialization ??= initializeWasm();
  await wasmInitialization;
  const properties = new WriterPropertiesBuilder()
    .setCompression(toParquetCompression(compression))
    .setKeyValueMetadata(metadata)
    .setCreatedBy(LEDGER_PARQUET_WRITER)
    .build();
  const wasmTable = WasmTable.fromIPCStream(tableToIPC(table, "stream"));
  const data = writeParquet(wasmTable, properties);
  return {
    data,
    writerVersion: await readParquetEngineVersion(),
    wasmMemoryBytes: wasmMemory().buffer.byteLength,
  };
}
