/** Compacts one bounded planner period from exact files present at one Git revision. */
import { createHash } from "node:crypto";
import { lstat, readFile, realpath } from "node:fs/promises";
import { relative, resolve } from "node:path";
import { z } from "zod";
import {
  PlannerMaintenanceRequestSchema, PlannerMaintenanceResultSchema,
} from "@idhazh/common-contracts";
import type {
  PlannerMaintenanceRequest, PlannerMaintenanceResult,
} from "@idhazh/common-contracts";
import { PLANNER_CONTRACTS } from "./registration";
import { readPlannerParquet } from "./read-planner-file";
import { persistLedger } from "./persist-ledger";
import type { LedgerPeriod, LedgerRegistration, LedgerRowContract } from "./ledger-types";

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

type GitMember = { blob: string; bytes: number };

async function git(root: string, args: string[], input?: string): Promise<string> {
  const child = Bun.spawn(["git", ...args], {
    cwd: root,
    env: { ...process.env, GIT_LITERAL_PATHSPECS: "1" },
    stdin: input === undefined ? "ignore" : "pipe",
    stdout: "pipe",
    stderr: "pipe",
  });
  if (input !== undefined) {
    if (child.stdin === undefined) throw new Error("Planner maintenance Git did not open stdin");
    child.stdin.write(input);
    child.stdin.end();
  }
  const [stdout, stderr, status] = await Promise.all([
    new Response(child.stdout).text(),
    new Response(child.stderr).text(),
    child.exited,
  ]);
  if (status !== 0) throw new Error(`Planner maintenance Git ${args[0]} failed: ${stderr.trim()}`);
  return stdout.trim();
}

async function currentRevision(root: string): Promise<string> {
  const revision = await git(root, ["rev-parse", "--verify", "HEAD^{commit}"]);
  if (!/^[0-9a-f]{40}$/.test(revision)) throw new Error("Planner maintenance received an invalid Git revision");
  return revision;
}

function rootRelative(root: string, path: string): string {
  const result = relative(root, path);
  if (!result || result === ".." || result.startsWith(`..\\`) || result.startsWith("../")) {
    throw new MaintenanceRefusal("malformed-member", path.replaceAll("\\", "/"));
  }
  return result.replaceAll("\\", "/");
}

async function captureMembers(
  root: string,
  request: PlannerMaintenanceRequest,
  days: readonly string[],
  targetPath: string,
): Promise<{ compact: Map<string, { period: "daily" | "monthly" | "yearly"; covers: string }>; raw: Map<string, string[]>; members: Map<string, GitMember> }> {
  const compact = new Map<string, { period: "daily" | "monthly" | "yearly"; covers: string }>();
  const raw = new Map<string, string[]>();
  const pathspecs = new Set<string>();
  for (const day of days) {
    const rawDirectory = rawDayDirectory(request.registry_entry, day);
    raw.set(day, []);
    pathspecs.add(rawDirectory);
    for (const period of ["yearly", "monthly", "daily"] as const) {
      const covers = period === "yearly" ? day.slice(0, 4)
        : period === "monthly" ? day.slice(0, 7) : day;
      for (const format of ["parquet", "json"] as const) {
        const path = compactPeriodPath(request.registry_entry, period, covers, format);
        compact.set(path, { period, covers });
        pathspecs.add(path);
      }
    }
  }
  const named = [...pathspecs];
  const lines: string[] = [];
  for (let index = 0; index < named.length; index += 96) {
    const output = await git(root, [
      "ls-tree", "-r", "-l", request.revision, "--", ...named.slice(index, index + 96),
    ]);
    if (output !== "") lines.push(...output.split("\n").filter(Boolean));
  }
  const members = new Map<string, GitMember>();
  const rawFolders = [...raw.keys()].map(day => [day, rawDayDirectory(request.registry_entry, day)] as const);
  for (const line of lines) {
    const separator = line.indexOf("\t");
    const metadata = line.slice(0, separator);
    const path = line.slice(separator + 1);
    const rawDay = rawFolders.find(([, directory]) => path.startsWith(`${directory}/`))?.[0];
    if (rawDay !== undefined && path === `${rawDayDirectory(request.registry_entry, rawDay)}/index.json`) continue;
    const match = /^(\d{6}) blob ([0-9a-f]{40})\s+(\d+)$/.exec(metadata);
    if (match === null || match[1] !== "100644") {
      throw new MaintenanceRefusal("malformed-member", path);
    }
    if (rawDay !== undefined) {
      const name = path.slice(path.lastIndexOf("/") + 1);
      if (!/^[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.parquet$/.test(name)) {
        throw new MaintenanceRefusal("unsupported-member", path);
      }
      raw.get(rawDay)!.push(path);
    } else if (!compact.has(path)) {
      throw new MaintenanceRefusal("unsupported-member", path);
    }
    members.set(path, { blob: match[2]!, bytes: Number(match[3]) });
  }
  const targetStatus = await git(root, [
    "status", "--porcelain=v1", "--untracked-files=all", "--", targetPath,
  ]);
  if (targetStatus !== "") throw new MaintenanceRefusal("target-conflict", targetPath);
  for (let index = 0; index < named.length; index += 96) {
    const status = await git(root, [
      "status", "--porcelain=v1", "--untracked-files=all", "--", ...named.slice(index, index + 96),
    ]);
    if (status !== "") throw new MaintenanceRefusal("changed-member");
  }
  return { compact, raw, members };
}

async function verifyMember(
  root: string, path: string, member: GitMember, target = false,
): Promise<{ bytes: Uint8Array; file_sha256: string }> {
  const file = resolve(root, ...path.split("/"));
  const localPath = rootRelative(root, file);
  const [rootPath, actualPath] = await Promise.all([realpath(root), realpath(file).catch(error => {
    if (isMissing(error)) throw new MaintenanceRefusal("missing-local-member", path);
    throw error;
  })]);
  if (actualPath !== resolve(rootPath, ...localPath.split("/"))) {
    throw new MaintenanceRefusal("malformed-member", path);
  }
  const bytes = await readFile(file).catch(error => {
    if (isMissing(error)) throw new MaintenanceRefusal("missing-local-member", path);
    throw error;
  });
  const blob = createHash("sha1").update(`blob ${bytes.byteLength}\0`).update(bytes).digest("hex");
  if (bytes.byteLength !== member.bytes || blob !== member.blob) {
    throw new MaintenanceRefusal(target ? "target-conflict" : "changed-member", path);
  }
  return {
    bytes,
    file_sha256: createHash("sha256").update(bytes).digest("hex"),
  };
}

function rawDayDirectory(registration: LedgerRegistration, day: string): string {
  return `state/raw/${registration.prefix.join("/")}/${day.replaceAll("-", "/")}`;
}

function compactPeriodPath(
  registration: LedgerRegistration,
  period: "daily" | "monthly" | "yearly",
  covers: string,
  format: "parquet" | "json" = "parquet",
): string {
  const pieces = covers.split("-");
  const extension = `.${format}`;
  const suffix = period === "yearly" ? `${covers}/${covers}${extension}`
    : period === "monthly" ? `${pieces[0]}/${pieces[1]}${extension}`
      : `${pieces[0]}/${pieces[1]}/${pieces[2]}${extension}`;
  return `state/compact/${registration.prefix.join("/")}/${period}/${suffix}`;
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

function result(
  request: PlannerMaintenanceRequest,
  value: Record<string, unknown>,
): PlannerMaintenanceResult {
  return PlannerMaintenanceResultSchema.parse({
    version: request.version,
    revision: request.revision,
    ledger: request.ledger,
    period: request.period,
    covers: request.covers,
    ...value,
  });
}

export async function maintainPlannerPeriod(root: string, rawRequest: unknown): Promise<PlannerMaintenanceResult> {
  const request = PlannerMaintenanceRequestSchema.parse(rawRequest);
  switch (request.ledger) {
    case "discovered-articles": return maintainPeriod(root, request, PLANNER_CONTRACTS["discovered-articles"]);
    case "selected-articles": return maintainPeriod(root, request, PLANNER_CONTRACTS["selected-articles"]);
    case "rejected-articles": return maintainPeriod(root, request, PLANNER_CONTRACTS["rejected-articles"]);
    case "feed-health-state": return maintainPeriod(root, request, PLANNER_CONTRACTS["feed-health-state"]);
    case "plan-runs": return maintainPeriod(root, request, PLANNER_CONTRACTS["plan-runs"]);
  }
}

async function maintainPeriod<T extends object>(
  root: string, request: PlannerMaintenanceRequest, rowContract: LedgerRowContract<T>,
): Promise<PlannerMaintenanceResult> {
  if (await currentRevision(root) !== request.revision) {
    return result(request, { status: "refused", reason: "revision-changed", path: null });
  }
  const registration = request.registry_entry;
  const settings = request.ledger_settings;
  const period: Extract<LedgerPeriod, { tier: "compact" }> = {
    tier: "compact", period: request.period, covers: request.covers, builtFrom: 0,
  };
  const targetPath = compactPeriodPath(registration, request.period, request.covers);
  const days = daysOf(request);
  const sources = new Map<string, SourceFile>();
  const rows: T[] = [];
  let carriedOver = false;
  try {
    const captured = await captureMembers(root, request, days, targetPath);
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
    for (const day of days) {
      for (const candidate of ["yearly", "monthly", "daily"] as const) {
        const covers = candidate === "yearly" ? day.slice(0, 4)
          : candidate === "monthly" ? day.slice(0, 7) : day;
        const path = compactPeriodPath(registration, candidate, covers);
        const jsonPath = compactPeriodPath(registration, candidate, covers, "json");
        if (captured.members.has(jsonPath)) {
          throw new MaintenanceRefusal("unsupported-member", jsonPath);
        }
        const member = captured.members.get(path);
        if (member === undefined) continue;
        const verified = await verifyMember(root, path, member, path === targetPath);
        const file = await readPlannerParquet(resolve(root, ...path.split("/")), request.ledger, rowContract);
        if (file.bytes !== verified.bytes.byteLength || file.file_sha256 !== verified.file_sha256
          || file.envelope.tier !== "compact" || file.envelope.period !== candidate
          || file.envelope.covers !== covers || file.rows.length === 0
          || file.rows.some(row => !rowIsWithin(row, candidate, covers))) {
          throw new MaintenanceRefusal("malformed-member", path);
        }
        sources.set(path, checkedSource(path, file));
        if (compactRank(candidate) > compactRank(request.period)) {
          return result(request, { status: "unchanged", reason: "higher-precedence-compact" });
        }
        rows.push(...file.rows.filter(row => rowIsWithin(row, "daily", day)));
        break;
      }
      for (const path of rawPathsByDay.get(day) ?? []) {
        if (!selectedRawPaths.has(path)) continue;
        const member = captured.members.get(path);
        if (member === undefined) throw new MaintenanceRefusal("changed-member", path);
        const verified = await verifyMember(root, path, member);
        const file = await readPlannerParquet(resolve(root, ...path.split("/")), request.ledger, rowContract);
        if (file.bytes !== verified.bytes.byteLength || file.file_sha256 !== verified.file_sha256
          || file.envelope.tier !== "raw" || file.envelope.covers !== day
          || file.rows.some(row => !rowIsWithin(row, "daily", day))) {
          throw new MaintenanceRefusal("malformed-member", path);
        }
        sources.set(path, checkedSource(path, file));
        rows.push(...file.rows);
      }
    }
  } catch (error) {
    if (error instanceof MaintenanceRefusal) {
      return result(request, { status: "refused", reason: error.reason, path: error.path });
    }
    if (error instanceof z.ZodError || error instanceof Error && error.name === "PlannerLedgerFileError") {
      return result(request, { status: "refused", reason: "malformed-member", path: null });
    }
    if (isMissing(error)) return result(request, { status: "refused", reason: "missing-local-member", path: null });
    throw error;
  }
  if (await currentRevision(root) !== request.revision) {
    return result(request, { status: "refused", reason: "revision-changed", path: null });
  }
  const targetSha = sources.get(targetPath)?.file_sha256 ?? null;
  if (rows.length === 0) return result(request, { status: "empty" });
  let settled: T[];
  try {
    const records = (await import("./row-identity")).settlePlannerRows(rows.map(rowRecord), request.ledger);
    settled = records.map(record => rowContract.schema.parse(record));
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("conflicting duplicate")) {
      return result(request, { status: "refused", reason: "malformed-member", path: null });
    }
    throw error;
  }
  if (targetSha !== null && [...sources.keys()].every(path => path === targetPath)) {
    return result(request, { status: "unchanged", reason: "already-current" });
  }
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
    if (persisted.status === "empty") return result(request, { status: "empty" });
    throw new Error("Planner compact writer returned no file for a nonempty period");
  }
  const output = persisted.files[0]!;
  const relativeTarget = output.path;
  if (relativeTarget !== targetPath.replace(/^state\//, "")) {
    throw new Error("Planner compact writer returned an unexpected target path");
  }
  const targetBytes = await readFile(resolve(outputRoot, ...relativeTarget.split("/")));
  const targetFileSha = createHash("sha256").update(targetBytes).digest("hex");
  if (await currentRevision(root) !== request.revision) {
    return result(request, { status: "refused", reason: "revision-changed", path: null });
  }
  const deletePaths = [...sources.keys()].filter(path => path !== targetPath);
  return result(request, {
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
