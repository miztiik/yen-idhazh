/** Do real planner CLI failures disclose only declared diagnostic values? */
import { expect, test } from "bun:test";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { delimiter, join, resolve } from "node:path";
import { tmpdir } from "node:os";
import {
  PLANNER_MAINTENANCE_VERSION, PLANNER_MAINTENANCE_FAILURE_VERSION,
  PlannerMaintenanceFailureSchema, PlannerMaintenanceFailureStageSchema,
  PlannerMaintenanceFailureCodeSchema,
} from "@idhazh/common-contracts";
import { persistLedger } from "../src";
import { plannerRecordings } from "./planner-recordings";

const cli = resolve(import.meta.dir, "../src/planner-maintenance-cli.ts");
const settings = { format: "parquet" as const, compression_raw: "snappy" as const,
  compression_compact: "zstd" as const };

test("each planner ledger's recorded rows succeeds through the real CLI", async () => {
  const root = await mkdtemp(join(tmpdir(), "planner-diagnostics-"));
  try {
    for (const recording of plannerRecordings()) {
      const registry = { name: recording.name, family: "feed-ingest-plan",
        grain: "raw-and-compact" as const, lifecycle_status: "active" as const,
        prefix: ["feed-ingest-plan", recording.name] };
      const written = await persistLedger({
        ledger: recording.name, rowContract: recording.contract,
        outputRoot: join(root, "state"), registryEntry: registry, ledgerSettings: settings,
        period: { tier: "raw", covers: "2026-10-20" }, rows: [recording.row],
      });
      expect(written.status).toBe("written");
      const original = await readFile(join(root, "state", written.files[0]!.path));
      const stage = `.planner-maintenance-${randomUUID().replaceAll("-", "")}`;
      await mkdir(join(root, stage));
      const input = { version: PLANNER_MAINTENANCE_VERSION, staging_root: stage,
        ledger: recording.name, period: "daily", covers: "2026-10-20",
        max_raw_files_per_period: 100, registry_entry: registry, ledger_settings: settings };
      const success = Bun.spawnSync([process.execPath, "run", cli], {
        cwd: root, stdin: new TextEncoder().encode(JSON.stringify(input)),
      });
      expect(success.exitCode).toBe(0);
      expect(success.stderr.toString()).toBe("");
      expect(JSON.parse(success.stdout.toString()).status).toBe("written");
      await rm(join(root, stage), { recursive: true });
      const failure = Bun.spawnSync([process.execPath, "run", cli], {
        cwd: root, stdin: new TextEncoder().encode(JSON.stringify(input)),
      });
      expect(failure.exitCode).not.toBe(0);
      expect(failure.stdout.toString()).toBe("");
      expect(JSON.parse(failure.stderr.toString())).toEqual({
        version: PLANNER_MAINTENANCE_FAILURE_VERSION, status: "failed",
        stage: "validate-staging", code: "missing-local-member",
      });
      expect(PlannerMaintenanceFailureSchema.safeParse(JSON.parse(failure.stderr.toString())).success).toBe(true);
      expect(failure.stderr.toString()).not.toContain(stage);
      expect(failure.stderr.toString()).not.toContain(root);
      expect(await readFile(join(root, "state", written.files[0]!.path))).toEqual(original);
      if (recording.name === "selected-articles") {
        await mkdir(join(root, stage));
        await writeFile(join(root, stage, "state"), "private-article-data");
        const failedWrite = Bun.spawnSync([process.execPath, "run", cli], {
          cwd: root, stdin: new TextEncoder().encode(JSON.stringify(input)),
        });
        expect(failedWrite.exitCode).toBe(1);
        expect(failedWrite.stdout.toString()).toBe("");
        expect(JSON.parse(failedWrite.stderr.toString())).toEqual({
          version: PLANNER_MAINTENANCE_FAILURE_VERSION, status: "failed",
          stage: "write-compact", code: "unexpected-error",
        });
        expect(failedWrite.stderr.toString()).not.toContain("private");
        expect(await readFile(join(root, stage, "state"), "utf8")).toBe("private-article-data");
      }
    }
  } finally { await rm(root, { recursive: true, force: true }); }
}, 180_000);

test("the failure schema and Python reader share the exact version and vocabulary", () => {
  const child = Bun.spawnSync([process.env.IDHAZH_PYTHON ?? "python", "-c", [
    "import json",
    "from idhazh.ledger import planner_maintenance as adapter",
    "print(json.dumps([adapter._FAILURE_VERSION, sorted(adapter._FAILURE_STAGES), sorted(adapter._FAILURE_CODES)]))",
  ].join("\n")], {
    env: { ...process.env, PYTHONPATH: [
      resolve(import.meta.dir, "../../../backend"), process.env.PYTHONPATH,
    ].filter(Boolean).join(delimiter) },
  });
  expect(child.exitCode, child.stderr.toString()).toBe(0);
  expect(JSON.parse(child.stdout.toString())).toEqual([
    PLANNER_MAINTENANCE_FAILURE_VERSION,
    [...PlannerMaintenanceFailureStageSchema.options].sort(),
    [...PlannerMaintenanceFailureCodeSchema.options].sort(),
  ]);
  const failure = { version: PLANNER_MAINTENANCE_FAILURE_VERSION,
    status: "failed", stage: "settle-rows", code: "unexpected-error" };
  expect(PlannerMaintenanceFailureSchema.safeParse(failure).success).toBe(true);
  for (const input of [
    { ...failure, version: "2026-10-27" },
    { ...failure, stage: "../article.txt" },
    { ...failure, code: "private exception" },
    { ...failure, message: "private article text" },
    { ...failure, path: "state/raw/private.parquet" },
  ]) {
    expect(PlannerMaintenanceFailureSchema.safeParse(input).success).toBe(false);
  }
});

test("invalid JSON and request values produce one content-free stderr record", () => {
  for (const [input, stage, code] of [
    ['{"private-article-data":', "decode-request", "invalid-json"],
    [JSON.stringify({ staging_root: "C:\\private\\article.txt", article_text: "private-article-data" }),
      "validate-request", "invalid-contract"],
  ]) {
    const child = Bun.spawnSync([process.execPath, "run", cli], {
      stdin: new TextEncoder().encode(input),
    });
    expect(child.exitCode).toBe(1);
    expect(child.stdout.toString()).toBe("");
    expect(JSON.parse(child.stderr.toString())).toEqual({
      version: PLANNER_MAINTENANCE_FAILURE_VERSION, status: "failed", stage, code,
    });
    expect(child.stderr.toString()).not.toContain("private");
    expect(child.stderr.toString().trim().split("\n")).toHaveLength(1);
  }
});
