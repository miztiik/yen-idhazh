/** Compacts one bounded planner period from validated local files. */
import { createHash } from "node:crypto";
import { lstat, readFile, realpath } from "node:fs/promises";
import { resolve } from "node:path";
import { z } from "zod";
import {
  PlannerMaintenanceRequestSchema, PlannerMaintenanceResultSchema,
} from "@idhazh/common-contracts";
import type {
  PlannerMaintenanceRequest, PlannerMaintenanceResult, PlannerMaintenanceFailure,
} from "@idhazh/common-contracts";
import { PLANNER_CONTRACTS } from "./registration";
import { readPlannerParquet } from "./read-planner-file";
import { persistLedger } from "./persist-ledger";
import { compactPeriodFile, readPlannerDayFiles, regularPlannerPath } from "./read-planner-day-files";
import type { LedgerPeriod, LedgerRowContract } from "./ledger-types";
import { PlannerMaintenanceFailureError } from "./planner-maintenance-failure";

type SourceFile = Extract<PlannerMaintenanceResult, { status: "written" }>["input_files"][number];
type RefusalReason = Extract<PlannerMaintenanceResult, { status: "refused" }>["reason"];

class MaintenanceRefusal extends Error {
  constructor(readonly reason: RefusalReason, readonly path: string | null = null) {
    super(reason);
  }
}

function isMissing(error: unknown): boolean {
  return error instanceof Error && "code" in error && error.code === "ENOENT";
}

async function captureMembers(
  root: string,
  request: PlannerMaintenanceRequest,
  days: readonly string[],
): Promise<{ raw: Map<string, string[]>; compact: Set<string> }> {
  const raw = new Map<string, string[]>();
  const compact = new Set<string>();
  const named = new Set<string>();
  for (const day of days) {
    const files = await readPlannerDayFiles(root, request.registry_entry, day);
    const refused = files.refused[0];
    if (refused !== undefined) {
      throw new MaintenanceRefusal(refused.reason === "nonregular-member"
        ? "malformed-member" : "unsupported-member");
    }
    raw.set(day, files.members);
    for (const period of ["yearly", "monthly", "daily"] as const) {
      const covers = period === "yearly" ? day.slice(0, 4)
        : period === "monthly" ? day.slice(0, 7) : day;
      const parquet = compactPeriodFile(request.registry_entry, period, covers);
      for (const path of [parquet, parquet.replace(/\.parquet$/, ".json")]) {
        if (named.has(path)) continue;
        named.add(path);
        try {
          await regularPlannerPath(root, path);
          compact.add(path);
        } catch (error) {
          if (isMissing(error)) continue;
          if (error instanceof Error && error.name === "PlannerLedgerFileError") {
            throw new MaintenanceRefusal("malformed-member", path);
          }
          throw error;
        }
      }
    }
  }
  return { raw, compact };
}

async function verifyMember(
  root: string, path: string, expected?: SourceFile, target = false,
): Promise<{ bytes: Uint8Array; file_sha256: string }> {
  const file = await regularPlannerPath(root, path).catch(error => {
    if (isMissing(error)) throw new MaintenanceRefusal("missing-local-member", path);
    if (error instanceof Error && error.name === "PlannerLedgerFileError") {
      throw new MaintenanceRefusal("malformed-member", path);
    }
    throw error;
  });
  const bytes = await readFile(file).catch(error => {
    if (isMissing(error)) throw new MaintenanceRefusal("missing-local-member", path);
    throw error;
  });
  const file_sha256 = createHash("sha256").update(bytes).digest("hex");
  if (expected !== undefined && (bytes.byteLength !== expected.bytes || file_sha256 !== expected.file_sha256)) {
    throw new MaintenanceRefusal(target ? "target-conflict" : "changed-member", path);
  }
  return { bytes, file_sha256 };
}

async function verifySources(root: string, sources: Map<string, SourceFile>, targetPath: string) {
  for (const source of sources.values()) {
    await verifyMember(root, source.path, source, source.path === targetPath);
  }
  if (!sources.has(targetPath)) {
    try {
      await regularPlannerPath(root, targetPath);
    } catch (error) {
      if (isMissing(error)) return;
      throw error;
    }
    throw new MaintenanceRefusal("target-conflict", targetPath);
  }
}

function daysOf(request: PlannerMaintenanceRequest): string[] {
  if (request.period === "daily") return [request.covers];
  const start = request.period === "yearly" ? `${request.covers}-01-01` : `${request.covers}-01`;
  const from = new Date(`${start}T00:00:00.000Z`);
  const end = request.period === "yearly"
    ? new Date(Date.UTC(from.getUTCFullYear() + 1, 0, 1))
    : new Date(Date.UTC(from.getUTCFullYear(), from.getUTCMonth() + 1, 1));
  const days: string[] = [];
  for (let cursor = from; cursor < end; cursor = new Date(cursor.getTime() + 86_400_000)) {
    days.push(cursor.toISOString().slice(0, 10));
  }
  return days;
}

function compactRank(period: "daily" | "monthly" | "yearly"): number {
  return period === "yearly" ? 3 : period === "monthly" ? 2 : 1;
}

function rowIsWithin(row: object, period: "daily" | "monthly" | "yearly", covers: string): boolean {
  if (!("date" in row) || typeof row.date !== "string") return false;
  return period === "daily" ? row.date === covers : row.date.startsWith(`${covers}-`);
}

function rowRecord(row: object): Record<string, unknown> {
  if (typeof row !== "object" || row === null || Array.isArray(row)) {
    throw new MaintenanceRefusal("malformed-member");
  }
  return Object.fromEntries(Object.entries(row));
}

function checkedSource(
  path: string,
  file: Awaited<ReturnType<typeof readPlannerParquet>>,
): SourceFile {
  return {
    path,
    tier: file.envelope.tier,
    period: file.envelope.period,
    covers: file.envelope.covers,
    bytes: file.bytes,
    file_sha256: file.file_sha256,
  };
}

export async function readMaintenanceSource<T extends object>(
  root: string, path: string, ledger: PlannerMaintenanceRequest["ledger"], contract: LedgerRowContract<T>,
  sources: Map<string, SourceFile>, targetPath: string,
) {
  const expected = sources.get(path);
  const verified = await verifyMember(root, path, expected, path === targetPath);
  const file = await readPlannerParquet(resolve(root, ...path.split("/")), ledger, contract);
  if (file.bytes !== verified.bytes.byteLength || file.file_sha256 !== verified.file_sha256) {
    throw new MaintenanceRefusal(path === targetPath ? "target-conflict" : "changed-member", path);
  }
  if (expected === undefined) sources.set(path, checkedSource(path, file));
  return file;
}

function result(
  request: PlannerMaintenanceRequest,
  value: Record<string, unknown>,
): PlannerMaintenanceResult {
  return PlannerMaintenanceResultSchema.parse({
    version: request.version,
    ledger: request.ledger,
    period: request.period,
    covers: request.covers,
    ...value,
  });
}

export async function maintainPlannerPeriod(root: string, rawRequest: unknown): Promise<PlannerMaintenanceResult> {
  let stage: PlannerMaintenanceFailure["stage"] = "validate-request";
  const setStage = (value: PlannerMaintenanceFailure["stage"]) => { stage = value; };
  try {
    const request = PlannerMaintenanceRequestSchema.parse(rawRequest);
    switch (request.ledger) {
      case "discovered-articles": return await maintainPeriod(root, request, PLANNER_CONTRACTS["discovered-articles"], setStage);
      case "selected-articles": return await maintainPeriod(root, request, PLANNER_CONTRACTS["selected-articles"], setStage);
      case "rejected-articles": return await maintainPeriod(root, request, PLANNER_CONTRACTS["rejected-articles"], setStage);
      case "feed-health-state": return await maintainPeriod(root, request, PLANNER_CONTRACTS["feed-health-state"], setStage);
      case "plan-runs": return await maintainPeriod(root, request, PLANNER_CONTRACTS["plan-runs"], setStage);
    }
  } catch (error) {
    throw new PlannerMaintenanceFailureError(stage, error,
      error instanceof MaintenanceRefusal && (error.reason === "missing-local-member"
        || error.reason === "malformed-member") ? error.reason : undefined);
  }
}

async function maintainPeriod<T extends object>(
  root: string, request: PlannerMaintenanceRequest, rowContract: LedgerRowContract<T>,
  setStage: (stage: PlannerMaintenanceFailure["stage"]) => void,
): Promise<PlannerMaintenanceResult> {
  const registration = request.registry_entry;
  const settings = request.ledger_settings;
  const period: Extract<LedgerPeriod, { tier: "compact" }> = {
    tier: "compact", period: request.period, covers: request.covers, builtFrom: 0,
  };
  const targetPath = compactPeriodFile(registration, request.period, request.covers);
  const days = daysOf(request);
  const sources = new Map<string, SourceFile>();
  const rows: T[] = [];
  let carriedOver = false;
  const receipt = (value: Record<string, unknown>) => {
    setStage("validate-result");
    return result(request, value);
  };
  try {
    setStage("capture-members");
    const captured = await captureMembers(root, request, days);
    const rawPathsByDay = new Map(
      days.map(day => [day, [...(captured.raw.get(day) ?? [])].sort()] as const),
    );
    const rawPaths = [...rawPathsByDay.values()].flat().sort((left, right) => {
      const leftName = left.slice(left.lastIndexOf("/") + 1);
      const rightName = right.slice(right.lastIndexOf("/") + 1);
      return leftName < rightName ? -1 : leftName > rightName ? 1
        : left < right ? -1 : left > right ? 1 : 0;
    });
    const selectedRawPaths = new Set(rawPaths.slice(0, request.max_raw_files_per_period));
    carriedOver = [...rawPathsByDay.values()].reduce(
      (count, paths) => count + paths.length, 0,
    ) > selectedRawPaths.size;
    setStage("read-sources");
    for (const day of days) {
      for (const candidate of ["yearly", "monthly", "daily"] as const) {
        const covers = candidate === "yearly" ? day.slice(0, 4)
          : candidate === "monthly" ? day.slice(0, 7) : day;
        const path = compactPeriodFile(registration, candidate, covers);
        const jsonPath = path.replace(/\.parquet$/, ".json");
        if (captured.compact.has(jsonPath)) {
          throw new MaintenanceRefusal("unsupported-member", jsonPath);
        }
        if (!captured.compact.has(path)) continue;
        const file = await readMaintenanceSource(root, path, request.ledger, rowContract, sources, targetPath);
        if (file.envelope.tier !== "compact" || file.envelope.period !== candidate
          || file.envelope.covers !== covers || file.rows.length === 0
          || file.rows.some(row => !rowIsWithin(row, candidate, covers))) {
          throw new MaintenanceRefusal("malformed-member", path);
        }
        if (compactRank(candidate) > compactRank(request.period)) {
          return receipt({ status: "unchanged", reason: "higher-precedence-compact" });
        }
        rows.push(...file.rows.filter(row => rowIsWithin(row, "daily", day)));
        break;
      }
      for (const path of rawPathsByDay.get(day) ?? []) {
        if (!selectedRawPaths.has(path)) continue;
        const file = await readMaintenanceSource(root, path, request.ledger, rowContract, sources, targetPath);
        if (file.envelope.tier !== "raw" || file.envelope.covers !== day
          || file.rows.some(row => !rowIsWithin(row, "daily", day))) {
          throw new MaintenanceRefusal("malformed-member", path);
        }
        rows.push(...file.rows);
      }
    }
    setStage("verify-sources");
    await verifySources(root, sources, targetPath);
  } catch (error) {
    if (error instanceof MaintenanceRefusal) {
      return receipt({ status: "refused", reason: error.reason, path: error.path });
    }
    if (error instanceof z.ZodError || error instanceof Error && error.name === "PlannerLedgerFileError") {
      return receipt({ status: "refused", reason: "malformed-member", path: null });
    }
    if (isMissing(error)) return receipt({ status: "refused", reason: "missing-local-member", path: null });
    throw error;
  }
  const targetSha = sources.get(targetPath)?.file_sha256 ?? null;
  if (rows.length === 0) return receipt({ status: "empty" });
  let settled: T[];
  try {
    setStage("settle-rows");
    const records = (await import("./row-identity")).settlePlannerRows(rows.map(rowRecord), request.ledger);
    settled = records.map(record => rowContract.schema.parse(record));
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("conflicting duplicate")) {
      return receipt({ status: "refused", reason: "malformed-member", path: null });
    }
    throw error;
  }
  if (targetSha !== null && [...sources.keys()].every(path => path === targetPath)) {
    return receipt({ status: "unchanged", reason: "already-current" });
  }
  setStage("validate-staging");
  const stagingRoot = resolve(root, request.staging_root);
  const stage = await lstat(stagingRoot).catch(error => {
    if (isMissing(error)) throw new MaintenanceRefusal("missing-local-member", request.staging_root);
    throw error;
  });
  if (!stage.isDirectory() || stage.isSymbolicLink()) {
    throw new MaintenanceRefusal("malformed-member", request.staging_root);
  }
  const [rootPath, actualStage] = await Promise.all([realpath(root), realpath(stagingRoot)]);
  if (actualStage !== resolve(rootPath, request.staging_root)) {
    throw new MaintenanceRefusal("malformed-member", request.staging_root);
  }
  const outputRoot = resolve(stagingRoot, "state");
  setStage("write-compact");
  const persisted = await persistLedger({
    ledger: request.ledger,
    rowContract,
    outputRoot,
    registryEntry: registration,
    ledgerSettings: settings,
    period,
    rows: settled,
  });
  if (persisted.status !== "written" || persisted.files.length !== 1) {
    if (persisted.status === "empty") return receipt({ status: "empty" });
    throw new Error("Planner compact writer returned no file for a nonempty period");
  }
  setStage("verify-output");
  const output = persisted.files[0]!;
  const relativeTarget = output.path;
  if (relativeTarget !== targetPath.replace(/^state\//, "")) {
    throw new Error("Planner compact writer returned an unexpected target path");
  }
  const targetBytes = await readFile(resolve(outputRoot, ...relativeTarget.split("/")));
  const targetFileSha = createHash("sha256").update(targetBytes).digest("hex");
  try {
    setStage("verify-sources-after-write");
    await verifySources(root, sources, targetPath);
  } catch (error) {
    if (error instanceof MaintenanceRefusal) {
      return receipt({ status: "refused", reason: error.reason, path: error.path });
    }
    throw error;
  }
  const deletePaths = [...sources.keys()].filter(path => path !== targetPath);
  return receipt({
    status: "written",
    target_path: targetPath,
    output_path: `${request.staging_root}/state/${relativeTarget}`,
    expected_target_sha256: targetSha,
    target_file_sha256: targetFileSha,
    content_sha256: output.content_sha256,
    target_bytes: targetBytes.byteLength,
    row_count: settled.length,
    carried_over: carriedOver,
    input_files: [...sources.values()],
    delete_paths: deletePaths,
  });
}
