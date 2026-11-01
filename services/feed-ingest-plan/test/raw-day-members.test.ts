/** Preserve complete local membership, usable siblings and immutable native-file captures. */
import { expect, test } from "bun:test";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { PlanRunRowContract } from "@idhazh/common-contracts";
import { plannerRecordings } from "../../../packages/ledger-file-writer/test/planner-recordings";
import { registration, writeRows } from "./partition-fixtures";
import { createPlannerHistoryCache, readPlannerDay } from "../src/read-ledger-history/read-planner-history";
import { PlannerDayInputSchema } from "../src/config/service-settings";

const day = "2026-10-20";
const row = (attempt: number) => PlanRunRowContract.schema.parse(
  plannerRecordings(day, attempt).find(record => record.name === "plan-runs")!.row,
);

test("complete local day membership rejects an omitted sibling without losing valid native evidence", async () => {
  const root = await mkdtemp(join(tmpdir(), "planner-file-day-"));
  try {
    expect(PlannerDayInputSchema.safeParse({ day, raw_files: [] }).success).toBe(true);
    expect(PlannerDayInputSchema.safeParse({ day, raw_revision: "a".repeat(40) }).success).toBe(false);
    expect(PlannerDayInputSchema.safeParse({ day, raw_index: "old/index.json" }).success).toBe(false);
    const outputs = await Promise.all([1, 2].map(attempt =>
      writeRows(join(root, "state"), "plan-runs", day, PlanRunRowContract, [row(attempt)])));
    const paths = outputs.flatMap(output => output.files.map(file => `state/${file.path}`)).sort();
    await writeFile(join(dirname(join(root, paths[0]!)), "index.json"), "obsolete invalid JSON");
    const complete = await readPlannerDay(root, registration("plan-runs"), { day }, PlanRunRowContract);
    expect(complete).toMatchObject({ complete: true, represented: true, gaps: [] });
    expect(complete.rows.map(value => value.attempt).sort()).toEqual([1, 2]);
    const partial = await readPlannerDay(root, registration("plan-runs"), {
      day, raw_files: paths.slice(0, 1),
    }, PlanRunRowContract);
    expect(partial).toMatchObject({ complete: false, gaps: ["membership_refused"] });
    expect(partial.rows).toEqual(complete.rows);
    await expect(readPlannerDay(root, registration("plan-runs"), {
      day, raw_files: [paths[0]!, paths[0]!],
    }, PlanRunRowContract)).rejects.toThrow("repeats a file");
    await writeFile(join(root, "state", outputs[0]!.files[0]!.path), new Uint8Array([1, 2, 3]));
    const damaged = await readPlannerDay(root, registration("plan-runs"), { day }, PlanRunRowContract);
    expect(damaged.complete).toBe(false);
    expect(damaged.rows).toEqual([row(2)]);
    expect(damaged.gaps).toContain("native_refused");
    const absent = await readPlannerDay(root, registration("plan-runs"), { day: "2026-10-19" }, PlanRunRowContract);
    expect(absent).toMatchObject({ complete: true, represented: false, rows: [], gaps: [] });
    const empty = await readPlannerDay(root, registration("plan-runs"), {
      day: "2026-10-19", raw_files: [],
    }, PlanRunRowContract);
    expect(empty).toMatchObject({ complete: true, represented: false, rows: [], gaps: [] });
    const missing = await readPlannerDay(root, registration("plan-runs"), {
      day: "2026-10-19", raw_files: [paths[0]!.replace("/20/", "/19/")],
    }, PlanRunRowContract);
    expect(missing.complete).toBe(false);
    expect(missing.gaps).toContain("missing");
    await mkdir(join(root, "state", "raw", "feed-ingest-plan", "plan-runs", "2026", "10", "18"), { recursive: true });
    expect(await readPlannerDay(root, registration("plan-runs"), { day: "2026-10-18" }, PlanRunRowContract))
      .toMatchObject({ complete: true, represented: false, rows: [] });
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("a loaded day keeps its membership and validated bytes after edits, removal and new siblings", async () => {
  const root = await mkdtemp(join(tmpdir(), "planner-held-file-day-"));
  try {
    const written = await writeRows(join(root, "state"), "plan-runs", day, PlanRunRowContract, [row(1)]);
    const path = join(root, "state", written.files[0]!.path);
    const cache = createPlannerHistoryCache<ReturnType<typeof row>>();
    const original = await readPlannerDay(root, registration("plan-runs"), { day }, PlanRunRowContract, cache);
    const bytes = await readFile(path);
    await writeFile(path, new Uint8Array([1, 2, 3]));
    await writeRows(join(root, "state"), "plan-runs", day, PlanRunRowContract, [row(2)]);
    expect(await readPlannerDay(root, registration("plan-runs"), { day }, PlanRunRowContract, cache)).toEqual(original);
    await rm(path);
    expect(await readPlannerDay(root, registration("plan-runs"), { day }, PlanRunRowContract, cache)).toEqual(original);
    await writeFile(path, bytes);
    const fresh = await readPlannerDay(root, registration("plan-runs"), { day }, PlanRunRowContract);
    expect(fresh.rows.map(value => value.attempt).sort()).toEqual([1, 2]);
  } finally { await rm(root, { recursive: true, force: true }); }
});
