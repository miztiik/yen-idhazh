/** Does planner maintenance replace only validated files from one captured revision? */
import { execFileSync } from "node:child_process";
import { expect, setDefaultTimeout, test } from "bun:test";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { delimiter, dirname, join, resolve } from "node:path";
import { tmpdir } from "node:os";
import {
  PLANNER_FILE_VALIDATION_VERSION,
  PLANNER_MAINTENANCE_VERSION, PlannerMaintenanceRequestSchema,
} from "@idhazh/common-contracts";
import { maintainPlannerPeriod, persistLedger, readPlannerParquet } from "../src";
import { validatePlannerFiles } from "../src/validate-planner-files";
import { plannerRecordings } from "./planner-recordings";

setDefaultTimeout(60_000);

const registration = {
  name: "discovered-articles",
  family: "feed-ingest-plan",
  grain: "raw-and-compact" as const,
  lifecycle_status: "active" as const,
  prefix: ["feed-ingest-plan", "discovered-articles"],
};
const ledgerSettings = {
  format: "parquet" as const,
  compression_raw: "snappy" as const,
  compression_compact: "zstd" as const,
};

function git(root: string, ...args: string[]): string {
  return execFileSync("git", args, { cwd: root, encoding: "utf8" }).trim();
}

async function fixtureRoot(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "planner-maintenance-"));
  git(root, "init", "--quiet");
  git(root, "config", "user.name", "Fixture");
  git(root, "config", "user.email", "fixture@example.invalid");
  return root;
}

async function addRawDay(root: string, day: string): Promise<string> {
  const recording = plannerRecordings(day)[0]!;
  const persisted = await persistLedger({
    ledger: "discovered-articles",
    rowContract: recording.contract,
    outputRoot: join(root, "state"),
    registryEntry: registration,
    ledgerSettings,
    period: { tier: "raw", covers: day },
    rows: [recording.row],
  });
  expect(persisted.status).toBe("written");
  const path = `state/${persisted.files[0]!.path}`;
  return path;
}

async function request(
  root: string,
  revision: string,
  period: "daily" | "monthly" | "yearly",
  covers: string,
  maxRawFiles = 100,
) {
  const stagingRoot = `.planner-maintenance-${randomUUID().replaceAll("-", "")}`;
  await mkdir(join(root, stagingRoot));
  return PlannerMaintenanceRequestSchema.parse({
    version: PLANNER_MAINTENANCE_VERSION,
    revision,
    staging_root: stagingRoot,
    ledger: "discovered-articles",
    period,
    covers,
    max_raw_files_per_period: maxRawFiles,
    registry_entry: registration,
    ledger_settings: ledgerSettings,
  });
}

test("monthly maintenance settles captured raw files and deletes only its validated inputs", async () => {
  const root = await fixtureRoot();
  try {
    const raw = [
      await addRawDay(root, "2026-10-20"),
      await addRawDay(root, "2026-10-21"),
    ];
    git(root, "add", "state");
    git(root, "commit", "--quiet", "-m", "record raw planner fixtures");
    const revision = git(root, "rev-parse", "HEAD");
    const result = await maintainPlannerPeriod(
      root, await request(root, revision, "monthly", "2026-10"),
    );
    expect(result.status).toBe("written");
    if (result.status !== "written") return;
    expect(result.input_files.map(file => file.path).sort()).toEqual(raw.sort());
    expect(result.delete_paths.sort()).toEqual(raw.sort());
    expect(result.expected_target_sha256).toBeNull();
    expect(result.row_count).toBe(1);
    const staged = join(root, ...result.output_path.split("/"));
    const output = await readPlannerParquet(staged, "discovered-articles", plannerRecordings()[0]!.contract);
    expect(output.rows).toHaveLength(1);
    expect(output.rows[0]).toHaveProperty("date", "2026-10-20");

    const target = join(root, ...result.target_path.split("/"));
    await mkdir(dirname(target), { recursive: true });
    await writeFile(target, await readFile(staged));
    for (const path of raw) await rm(join(root, ...path.split("/")));
    await rm(join(root, result.output_path.split("/")[0]!), { recursive: true });
    git(root, "add", "state");
    git(root, "commit", "--quiet", "-m", "replace captured raw planner files");
    const currentRevision = git(root, "rev-parse", "HEAD");
    const repeated = await maintainPlannerPeriod(
      root, await request(root, currentRevision, "monthly", "2026-10"),
    );
    expect(repeated.status).toBe("unchanged");
    if (repeated.status === "unchanged") expect(repeated.reason).toBe("already-current");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("a changed Git member is refused without falling through to a complete result", async () => {
  const root = await fixtureRoot();
  try {
    const raw = await addRawDay(root, "2026-10-20");
    git(root, "add", "state");
    git(root, "commit", "--quiet", "-m", "record raw planner fixture");
    const revision = git(root, "rev-parse", "HEAD");
    await writeFile(join(root, ...raw.split("/")), "changed");
    const result = await maintainPlannerPeriod(
      root, await request(root, revision, "monthly", "2026-10"),
    );
    expect(result.status).toBe("refused");
    if (result.status === "refused") {
      expect(result.reason).toBe("changed-member");
      expect(result.path).toBeNull();
    }
    expect(await Bun.file(join(root, ...raw.split("/"))).text()).toBe("changed");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("yearly maintenance keeps uncaptured raw files for the next bounded pass", async () => {
  const root = await fixtureRoot();
  try {
    const raw = [
      await addRawDay(root, "2024-02-28"),
      await addRawDay(root, "2024-02-29"),
    ];
    git(root, "add", "state");
    git(root, "commit", "--quiet", "-m", "record yearly planner fixtures");
    const revision = git(root, "rev-parse", "HEAD");
    const result = await maintainPlannerPeriod(
      root, await request(root, revision, "yearly", "2024", 1),
    );
    expect(result.status).toBe("written");
    if (result.status !== "written") return;
    expect(result.input_files.map(file => file.path)).toEqual([raw[0]!]);
    expect(result.delete_paths).toEqual([raw[0]!]);
    expect(result.carried_over).toBe(true);
    expect(await Bun.file(join(root, ...raw[1]!.split("/"))).exists()).toBe(true);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("daily maintenance refuses a legacy JSON compact member", async () => {
  const root = await fixtureRoot();
  try {
    const legacy = "state/compact/feed-ingest-plan/discovered-articles/daily/2026/10/20.json";
    await mkdir(dirname(join(root, legacy)), { recursive: true });
    await writeFile(join(root, legacy), "{}");
    git(root, "add", "state");
    git(root, "commit", "--quiet", "-m", "record legacy compact fixture");
    const revision = git(root, "rev-parse", "HEAD");
    const result = await maintainPlannerPeriod(
      root, await request(root, revision, "daily", "2026-10-20"),
    );
    expect(result.status).toBe("refused");
    if (result.status === "refused") {
      expect(result.reason).toBe("unsupported-member");
      expect(result.path).toBe(legacy);
    }
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("the Python scheduler receives verified compact bytes from the real adapter", async () => {
  const root = await fixtureRoot();
  try {
    const raw = await addRawDay(root, "2026-10-20");
    git(root, "add", "state");
    git(root, "commit", "--quiet", "-m", "record raw planner fixture");
    const projectRoot = resolve(import.meta.dir, "../../..");
    const python = process.env.IDHAZH_PYTHON ?? "python";
    const script = [
      "import contextlib, io, json, sys",
      "from pathlib import Path",
      "from idhazh.contracts.ledger_name import LedgerName",
      "from idhazh.ledger.published_columns import check",
      "from idhazh.ledger.planner_maintenance import maintain_period",
      "root = Path(sys.argv[1]).resolve()",
      "result = maintain_period(root, LedgerName('discovered-articles'), 'monthly', '2026-10', max_raw_files_per_period=100)",
      "result.target_path.parent.mkdir(parents=True, exist_ok=True)",
      "result.target_path.write_bytes(result.data)",
      "output = io.StringIO()",
      "with contextlib.redirect_stdout(output): code = check(root, [LedgerName('discovered-articles')])",
      "print(json.dumps({'status': result.status, 'target': result.target_path.relative_to(root).as_posix(), 'deletes': [path.relative_to(root).as_posix() for path in result.delete_paths], 'bytes': len(result.data), 'check_code': code, 'check_output': output.getvalue()}))",
    ].join("\n");
    const response = execFileSync(python, ["-c", script, root], {
      cwd: projectRoot,
      encoding: "utf8",
      env: {
        ...process.env,
        PYTHONPATH: [
          resolve(projectRoot, "backend"),
          process.env.PYTHONPATH,
        ].filter(Boolean).join(delimiter),
      },
    });
    expect(JSON.parse(response)).toEqual({
      status: "written",
      target: "state/compact/feed-ingest-plan/discovered-articles/monthly/2026/10.parquet",
      deletes: [raw],
      bytes: expect.any(Number),
      check_code: 0,
      check_output: "published-columns discovered-articles: checked 2 file(s), current 2, history none\n",
    });
    expect(
      (await Array.fromAsync(new Bun.Glob(".planner-maintenance-*").scan({ cwd: root }))).length,
    ).toBe(0);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("published planner files use the TypeScript contract and reject malformed rows", async () => {
  const root = await fixtureRoot();
  try {
    const raw = await addRawDay(root, "2026-10-20");
    const request = {
      version: PLANNER_FILE_VALIDATION_VERSION,
      files: [{ ledger: "discovered-articles", path: raw }],
    };
    const valid = await validatePlannerFiles(root, request);
    expect(valid.files).toEqual([{
      ledger: "discovered-articles",
      path: raw,
      status: "valid",
      row_count: 1,
      reason: null,
    }]);

    await writeFile(join(root, ...raw.split("/")), "not a Parquet file");
    const invalid = await validatePlannerFiles(root, request);
    expect(invalid.files).toEqual([{
      ledger: "discovered-articles",
      path: raw,
      status: "invalid",
      row_count: null,
      reason: "invalid",
    }]);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
