/** Renew the bounded selected-row and Arrow recordings from real native writer bytes. */
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { DataType, Field, tableFromIPC } from "apache-arrow";
import { readParquet } from "parquet-wasm/esm";
import { persistLedger, readPlannerParquet } from "../src";
import { plannerRecordings } from "./planner-recordings";

function encodeRecording(value: unknown): string {
  return `${JSON.stringify(value, null, 2).replace(/[\u007f-\uffff]/g,
    character => `\\u${character.charCodeAt(0).toString(16).padStart(4, "0")}`)}\n`;
}

function describeFields(fields: readonly Field[], prefix = ""): [string, string, boolean][] {
  return fields.flatMap(field => {
    const name = `${prefix}${field.name}`;
    const type = DataType.isStruct(field.type) ? "Struct" : DataType.isList(field.type) ? "List" : field.type.toString();
    const row: [string, string, boolean] = [name, type, field.nullable];
    if (DataType.isStruct(field.type)) return [row, ...describeFields(field.type.children, `${name}.`)];
    if (DataType.isList(field.type)) {
      const item = field.type.children[0]!;
      return [row, ...describeFields([new Field(`${name}[]`, item.type, item.nullable)])];
    }
    return [row];
  });
}

export async function recordSelectedFixtures(): Promise<void> {
  const repositoryRoot = fileURLToPath(new URL("../../../", import.meta.url));
  const root = await mkdtemp(join(repositoryRoot, ".selected-fixture-recording-"));
  try {
    const recording = plannerRecordings().find(row => row.name === "selected-articles")!;
    const written = await persistLedger({
      ledger: recording.name, outputRoot: root, rowContract: recording.contract, rows: [recording.row],
      registryEntry: {
        name: recording.name, family: "feed-ingest-plan", prefix: ["feed-ingest-plan", recording.name],
        grain: "raw-and-compact", lifecycle_status: "active",
      },
      ledgerSettings: { format: "parquet", compression_raw: "snappy", compression_compact: "zstd" },
      period: { tier: "raw", covers: String(recording.row.date) },
    });
    if (written.status !== "written") throw new Error("selected fixture was not written");
    const path = join(root, written.files[0]!.path);
    const actual = await readPlannerParquet(path, recording.name, recording.contract);
    const table = tableFromIPC(readParquet(await readFile(path)).intoIPCStream());
    const fixtures = join(repositoryRoot, "tests", "fixtures", "ledger-file-writer");
    await writeFile(join(fixtures, "feed-ingest-dispatch-row.json"), encodeRecording(actual.rows[0]));
    await writeFile(join(fixtures, "dispatch-arrow-schema.json"), encodeRecording({
      version: actual.envelope.row_schema_version, columns: describeFields(table.schema.fields),
    }));
  } finally { await rm(root, { recursive: true, force: true }); }
}

if (import.meta.main) await recordSelectedFixtures();
