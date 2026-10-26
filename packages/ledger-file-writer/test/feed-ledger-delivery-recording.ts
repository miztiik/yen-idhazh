/** Generate current native planner files for the bounded browser delivery fixture. */
import { mkdir, stat, unlink, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { COMPACT_INDEX_VERSION, CompactIndexSchema } from "@idhazh/common-contracts";
import { describeObjectSchema, persistLedger } from "../src/index";
import type { LedgerRegistration } from "../src/index";
import { plannerRecordings } from "./planner-recordings";

export async function buildFeedDeliveryRecording(state: string) {
  const columns: Record<string, string[]> = {};
  const ledgerSettings = { format: "parquet" as const, compression_raw: "snappy" as const, compression_compact: "zstd" as const };
  for (const fixture of plannerRecordings()) {
    const registration: LedgerRegistration = {
      name: fixture.name, family: "feed-ingest-plan", prefix: ["feed-ingest-plan", fixture.name],
      grain: "raw-and-compact", lifecycle_status: "active",
    };
    const entries = [];
    for (const day of fixture.name === "selected-articles" ? ["2026-10-19", "2026-10-20"] : ["2026-10-20"]) {
      const input = plannerRecordings(day).find(value => value.name === fixture.name)!;
      const raw = await persistLedger({
        ledger: fixture.name, rowContract: fixture.contract, rows: [input.row], registryEntry: registration,
        outputRoot: state, ledgerSettings, period: { tier: "raw", covers: day }, updatedAt: `${day}T12:00:00Z`,
      });
      const packed = await persistLedger({
        ledger: fixture.name, rowContract: fixture.contract, rows: [input.row], registryEntry: registration,
        outputRoot: state, ledgerSettings, period: { tier: "compact", period: "daily", covers: day, builtFrom: 1 },
        updatedAt: `${day}T12:00:00Z`,
      });
      entries.push({ covers: day, rows: 1, bytes: (await stat(join(state, packed.files[0]!.path))).size });
      for (const file of raw.files) await unlink(join(state, file.path));
    }
    for (const period of ["daily", "monthly", "yearly"] as const) {
      const path = join(state, "compact", ...registration.prefix, "index", `${period}.json`);
      await mkdir(dirname(path), { recursive: true });
      await writeFile(path, JSON.stringify(CompactIndexSchema.parse({
        version: COMPACT_INDEX_VERSION, ledger: fixture.name, period,
        entries: period === "daily" ? [...entries, { covers: "2026-10-21", rows: 0, bytes: 0, state: "empty" }] : [],
      })));
    }
    columns[fixture.name] = describeObjectSchema(fixture.contract.schema).fields.map(field => field.name);
  }
  const selected = plannerRecordings("2026-10-23").find(value => value.name === "selected-articles")!;
  const raw = await persistLedger({
    ledger: selected.name, rowContract: selected.contract, rows: [selected.row], outputRoot: state, ledgerSettings,
    registryEntry: { name: selected.name, family: "feed-ingest-plan", prefix: ["feed-ingest-plan", selected.name],
      grain: "raw-and-compact", lifecycle_status: "active" },
    period: { tier: "raw", covers: "2026-10-23" },
  });
  return { columns, rawFile: raw.files[0]!.path };
}
if (import.meta.main) {
  const state = process.argv[2];
  if (!state) throw new Error("The generated fixture needs its output directory");
  console.log(JSON.stringify(await buildFeedDeliveryRecording(state)));
}
