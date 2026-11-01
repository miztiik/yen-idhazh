/** Verify the filesystem authority for exact planner days and named compact files. */
import { expect, test } from "bun:test";
import { mkdtemp, mkdir, rm, symlink, unlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { PlanRunRowContract } from "@idhazh/common-contracts";
import { readPlannerDayFiles, readPlannerCompactFile, rawDayDirectory, persistLedger } from "../src/index";
import { plannerRecordings } from "./planner-recordings";
import type { LedgerRegistration } from "../src/index";

const registration: LedgerRegistration = { name: "plan-runs", family: "feed-ingest-plan",
  grain: "raw-and-compact", lifecycle_status: "active", prefix: ["feed-ingest-plan", "plan-runs"] };
const day = "2026-10-20";

test("one exact UTC day lists every regular UUID file and ignores only a regular old raw index", async () => {
  const root = await mkdtemp(join(tmpdir(), "writer-planner-day-"));
  try {
    expect(await readPlannerDayFiles(root, registration, day)).toEqual({ present: false, members: [], refused: [] });
    const written = await persistLedger({
      ledger: registration.name, registryEntry: registration, outputRoot: join(root, "state"),
      rowContract: PlanRunRowContract, rows: [PlanRunRowContract.schema.parse(
        plannerRecordings(day).find(record => record.name === "plan-runs")!.row)],
      ledgerSettings: { format: "parquet", compression_raw: "snappy", compression_compact: "zstd" },
      period: { tier: "raw", covers: day },
    });
    const directory = rawDayDirectory(registration, day);
    await writeFile(join(root, directory, "index.json"), "not parsed");
    expect(await readPlannerDayFiles(root, registration, day)).toEqual({
      present: true, members: written.files.map(file => `state/${file.path}`), refused: [],
    });
    await writeFile(join(root, directory, "unsupported.json"), "{}");
    await mkdir(join(root, directory, "nested"));
    const partial = await readPlannerDayFiles(root, registration, day);
    expect(partial.members).toEqual(written.files.map(file => `state/${file.path}`));
    expect(partial.refused.map(value => value.reason).sort()).toEqual(["nonregular-member", "unsupported-member"]);
    await expect(readPlannerDayFiles(root, registration, "2026-02-30")).rejects.toThrow("UTC day");
    await expect(readPlannerDayFiles(root, { ...registration, prefix: [".."] }, day)).rejects.toThrow("prefix");
    expect(await readPlannerCompactFile(root, registration, "daily", day)).toBeUndefined();
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("a named directory or compact file cannot cross a linked ancestor or become a nonregular file", async () => {
  const root = await mkdtemp(join(tmpdir(), "writer-planner-path-"));
  try {
    const directory = join(root, rawDayDirectory(registration, day));
    await mkdir(dirname(directory), { recursive: true });
    await writeFile(directory, "not a directory");
    await expect(readPlannerDayFiles(root, registration, day)).rejects.toThrow("regular");
    await rm(directory);
    const target = join(root, "generated-target");
    await mkdir(target);
    await symlink(target, directory, "junction");
    await expect(readPlannerDayFiles(root, registration, day)).rejects.toThrow("regular");
    await unlink(directory);
    const compact = join(root, "state", "compact", ...registration.prefix, "daily", "2026", "10", "20.parquet");
    await mkdir(compact, { recursive: true });
    await expect(readPlannerCompactFile(root, registration, "daily", day)).rejects.toThrow("regular");
  } finally { await rm(root, { recursive: true, force: true }); }
});
