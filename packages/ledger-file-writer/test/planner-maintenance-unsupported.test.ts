/** Does maintenance refuse old native formats without changing their saved files? */
import { expect, test } from "bun:test";
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { delimiter, join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { tableFromIPC } from "apache-arrow";
import initializeParquet, { readMetadata, readParquet } from "parquet-wasm/esm";
import { PLANNER_MAINTENANCE_VERSION } from "@idhazh/common-contracts";
import { maintainPlannerPeriod, persistLedger } from "../src";
import { serializeParquet } from "../src/parquet/wasm-serializer";
import { plannerRecordings } from "./planner-recordings";

test("old raw and compact formats return an explicit refusal through the native scheduler", async () => {
  const root = await mkdtemp(join(tmpdir(), "planner-unsupported-"));
  const day = "2026-10-20";
  const settings = { format: "parquet" as const, compression_raw: "snappy" as const,
    compression_compact: "zstd" as const };
  try {
    await initializeParquet();
    for (const recording of plannerRecordings(day)) {
      const registry = { name: recording.name, family: "feed-ingest-plan",
        grain: "raw-and-compact" as const, lifecycle_status: "active" as const,
        prefix: ["feed-ingest-plan", recording.name] };
      for (const tier of ["raw", "compact"] as const) {
        const context = {
          ledger: recording.name, rowContract: recording.contract,
          outputRoot: join(root, "state"), registryEntry: registry, ledgerSettings: settings,
          rows: [recording.row],
        };
        const written = tier === "raw"
          ? await persistLedger({ ...context, period: { tier, covers: day } })
          : await persistLedger({ ...context, period: { tier, period: "daily", covers: day, builtFrom: 1 } });
        expect(written.status).toBe("written");
        const path = `state/${written.files[0]!.path}`;
        const local = join(root, ...path.split("/"));
        const original = await readFile(local);
        const metadata = readMetadata(original);
        const footer = metadata.fileMetadata();
        const values = new Map(footer.keyValueMetadata());
        footer.free();
        metadata.free();
        const table = tableFromIPC(readParquet(original).intoIPCStream());
        const stage = `.planner-maintenance-${randomUUID().replaceAll("-", "")}`;
        await mkdir(join(root, stage));
        for (const keys of [
          ["envelope_version"], ["schema_version"], ["envelope_version", "schema_version"],
        ]) {
          const prior = new Map(values);
          for (const key of keys) prior.set(key, "2026-10-29");
          const bytes = (await serializeParquet(table, prior, tier === "raw" ? "snappy" : "zstd")).data;
          await writeFile(local, bytes);
          const result = await maintainPlannerPeriod(root, {
            version: PLANNER_MAINTENANCE_VERSION, staging_root: stage,
            ledger: recording.name, period: "daily", covers: day,
            max_raw_files_per_period: 100, registry_entry: registry, ledger_settings: settings,
          });
          expect(result).toEqual({
            version: PLANNER_MAINTENANCE_VERSION, ledger: recording.name,
            period: "daily", covers: day, status: "refused", reason: "unsupported-member", path,
          });
          expect<Uint8Array>(await readFile(local)).toEqual(bytes);
          expect(await readdir(join(root, stage))).toEqual([]);
        }
        const before = await readFile(local);
        const child = Bun.spawnSync([process.env.IDHAZH_PYTHON ?? "python", "-c", [
          "import sys",
          "from pathlib import Path",
          "from idhazh.contracts.ledger_name import LedgerName",
          "from idhazh.ledger.planner_maintenance import maintain_period, PlannerMaintenanceRefusalError",
          "try:",
          "    maintain_period(Path(sys.argv[1]), LedgerName(sys.argv[2]), 'daily', sys.argv[3], max_raw_files_per_period=100)",
          "except PlannerMaintenanceRefusalError as error:",
          "    assert error.reason == 'unsupported-member'",
          "else:",
          "    raise AssertionError('The scheduler must refuse the old format')",
        ].join("\n"), root, recording.name, day], {
          env: { ...process.env, PYTHONPATH: [
            resolve(import.meta.dir, "../../../backend"), process.env.PYTHONPATH,
          ].filter(Boolean).join(delimiter) },
        });
        expect(child.exitCode, child.stderr.toString()).toBe(0);
        expect(child.stdout.toString()).toBe("");
        expect(child.stderr.toString()).toBe("");
        expect(await readFile(local)).toEqual(before);
        expect((await readdir(root)).filter(name => name.startsWith(".planner-maintenance-"))).toEqual([stage]);
        await rm(join(root, stage), { recursive: true });
        await rm(local);
      }
    }
  } finally { await rm(root, { recursive: true, force: true }); }
}, 180_000);
