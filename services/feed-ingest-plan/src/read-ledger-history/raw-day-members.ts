/** Which immutable Parquet members belong to one registered UTC day at one Git revision? */
import { lstat, readFile, realpath } from "node:fs/promises";
import { createHash } from "node:crypto";
import { relative, resolve } from "node:path";
import {
  DateStampSchema, MonthStampSchema, PlannerLedgerNameSchema, YearStampSchema,
} from "@idhazh/common-contracts";
import type { LedgerRegistration } from "@idhazh/ledger-file-writer";
import { LedgerHistoryReadError } from "./ledger-history-error";

async function git(repository: string, args: string[]) {
  const child = Bun.spawn(["git", ...args], {
    cwd: repository, env: { ...process.env, GIT_LITERAL_PATHSPECS: "1" },
    stdout: "pipe", stderr: "pipe",
  });
  const [output, error, code] = await Promise.all([
    new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited,
  ]);
  if (code !== 0) throw new LedgerHistoryReadError(`Named history Git ${args[0]} failed`, { cause: new Error(error) });
  return output.trim();
}

export async function fixedHistoryRevision(repository: string) {
  const revision = await git(repository, ["rev-parse", "--verify", "HEAD^{commit}"]);
  if (!/^[0-9a-f]{40}$/.test(revision)) throw new LedgerHistoryReadError("Invalid history revision");
  return revision;
}

export function rawDayDirectory(registration: LedgerRegistration, day: string) {
  const ledger = PlannerLedgerNameSchema.parse(registration.name);
  if (registration.family !== "feed-ingest-plan"
    || registration.prefix.join("/") !== `feed-ingest-plan/${ledger}`) {
    throw new LedgerHistoryReadError("Planner raw day requires its registered root");
  }
  DateStampSchema.parse(day);
  if (new Date(`${day}T00:00:00Z`).toISOString().slice(0, 10) !== day) {
    throw new LedgerHistoryReadError("Invalid raw UTC day");
  }
  return `state/raw/${registration.prefix.join("/")}/${day.replaceAll("-", "/")}`;
}

export function compactPeriodFile(
  registration: LedgerRegistration, period: "daily" | "monthly" | "yearly", covers: string,
) {
  const ledger = PlannerLedgerNameSchema.parse(registration.name);
  if (registration.family !== "feed-ingest-plan"
    || registration.prefix.join("/") !== `feed-ingest-plan/${ledger}`) {
    throw new LedgerHistoryReadError("Planner compact period requires its registered root");
  }
  const stamp = period === "yearly" ? YearStampSchema : period === "monthly" ? MonthStampSchema : DateStampSchema;
  stamp.parse(covers);
  if (period === "daily" && new Date(`${covers}T00:00:00Z`).toISOString().slice(0, 10) !== covers) {
    throw new LedgerHistoryReadError("Invalid compact UTC day");
  }
  const pieces = covers.split("-");
  const file = period === "yearly" ? `${covers}/${covers}.parquet`
    : period === "monthly" ? `${pieces[0]}/${pieces[1]}.parquet`
      : `${pieces[0]}/${pieces[1]}/${pieces[2]}.parquet`;
  return `state/compact/${registration.prefix.join("/")}/${period}/${file}`;
}

export async function listExactRawDayMembers(
  repository: string, registration: LedgerRegistration, day: string, revision: string,
  treeCache = new Map<string, Promise<string>>(),
) {
  if (!/^[0-9a-f]{40}$/.test(revision)) throw new LedgerHistoryReadError("Invalid history revision");
  const directory = rawDayDirectory(registration, day);
  function tree(path: string) {
    const key = `${revision}:${path}`;
    let pending = treeCache.get(key);
    if (pending === undefined) { pending = git(repository, ["ls-tree", revision, "--", path]); treeCache.set(key, pending); }
    return pending;
  }
  const entry = await tree(directory);
  async function absent() {
    try { await lstat(resolve(repository, directory)); }
    catch (error) {
      if (error instanceof Error && "code" in error && error.code === "ENOENT") {
        return { present: false as const, members: [] as const };
      }
      throw error;
    }
    throw new LedgerHistoryReadError("Uncommitted raw day differs from the selected Git revision");
  }
  const entryPath = entry.slice(entry.indexOf("\t") + 1);
  const directoryEntry = /^040000 tree [0-9a-f]{40}\t/.test(entry);
  if (entry === "") return absent();
  if (entryPath !== directory && directoryEntry && directory.startsWith(`${entryPath}/`)) return absent();
  if (!directoryEntry || entryPath !== directory) {
    throw new LedgerHistoryReadError("Named raw day is not a directory");
  }
  const listing = await git(repository, ["ls-tree", "-l", `${revision}:${directory}`]);
  const members: { path: string; blob: string; bytes: number }[] = [];
  for (const line of listing.split("\n").filter(Boolean)) {
    const match = /^100644 blob ([0-9a-f]{40})\s+(\d+)\t(.+)$/.exec(line);
    if (match === null) throw new LedgerHistoryReadError("Named raw day contains a nonregular member");
    const name = match[3]!;
    if (name === "index.json") continue;
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.parquet$/.test(name)) {
      throw new LedgerHistoryReadError("Named raw day contains an invalid Parquet name");
    }
    members.push({ path: `${directory}/${name}`, blob: match[1]!, bytes: Number(match[2]) });
  }
  return { present: true, members };
}

export async function verifyRawDayMember(
  root: string, member: { path: string; blob: string; bytes: number },
) {
  const path = resolve(root, member.path);
  const local = relative(root, path);
  if (local.startsWith("..") || await realpath(path) !== resolve(await realpath(root), local)) {
    throw new LedgerHistoryReadError("Named history file crosses its trusted root or a linked directory");
  }
  const bytes = await readFile(path);
  // Git's 40-character object IDs use its SHA-1 blob format, not the content-digest setting.
  const digest = createHash("sha1").update(`blob ${bytes.byteLength}\0`).update(bytes).digest("hex");
  if (bytes.byteLength !== member.bytes || digest !== member.blob) {
    throw new LedgerHistoryReadError("Raw day bytes differ from the selected Git revision");
  }
  return { bytes, file_sha256: createHash("sha256").update(bytes).digest("hex") };
}

export async function readNamedGitMember(
  root: string, path: string, revision: string,
  treeCache = new Map<string, Promise<string>>(),
) {
  if (!/^[0-9a-f]{40}$/.test(revision)) throw new LedgerHistoryReadError("Invalid history revision");
  const pieces = path.split("/");
  if (pieces.some(piece => piece === "" || piece === "." || piece === ".." || piece.includes("\\"))) {
    throw new LedgerHistoryReadError("Named history path is not canonical");
  }
  function tree(named: string) {
    const key = `${revision}:${named}`;
    let pending = treeCache.get(key);
    if (pending === undefined) { pending = git(root, ["ls-tree", "-l", revision, "--", named]); treeCache.set(key, pending); }
    return pending;
  }
  async function absent() {
    try { await lstat(resolve(root, path)); }
    catch (error) {
      if (error instanceof Error && "code" in error && error.code === "ENOENT") return undefined;
      throw error;
    }
    throw new LedgerHistoryReadError("Uncommitted history member differs from the selected Git revision");
  }
  const entry = await tree(path);
  if (entry === "") return absent();
  const entryPath = entry.slice(entry.indexOf("\t") + 1);
  if (entryPath !== path && /^040000 tree [0-9a-f]{40}\s+-\t/.test(entry)
    && path.startsWith(`${entryPath}/`)) return absent();
  const match = /^100644 blob ([0-9a-f]{40})\s+(\d+)\t(.+)$/.exec(entry);
  if (match === null || match[3] !== path) throw new LedgerHistoryReadError("Named history member is not a regular file");
  return verifyRawDayMember(root, { path, blob: match[1]!, bytes: Number(match[2]) });
}

export async function readNamedGitFile(root: string, path: string, revision: string) {
  const held = await readNamedGitMember(root, path, revision);
  return held?.bytes.toString("utf8");
}
