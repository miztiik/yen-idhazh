import { createHash, randomUUID } from "node:crypto";
import { chmod, lstat, link, mkdir, mkdtemp, readFile, realpath, rm, unlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { isAbsolute, join, relative, sep } from "node:path";
import { SafePersistDataInputSchema, SafePersistDataResultSchema } from "./safe-persist-data-contract";
import type { SafePersistDataCommitter, SafePersistDataInput, SafePersistDataResult } from "./safe-persist-data-contract";

type DeliveryErrorCode = "integrity-refused" | "delivery-failed";

export class SafePersistDataError extends Error {
  constructor(
    message: string,
    readonly code: DeliveryErrorCode,
    readonly paths: readonly string[] = [],
  ) {
    super(message);
    this.name = "SafePersistDataError";
  }
}

type CheckedFile = {
  sourcePath: string;
  targetPath: string;
  sha256: string;
  bytes: Uint8Array;
};

type TreeEntry = {
  mode: string;
  type: string;
  oid: string;
};

type GitResult = {
  stdout: Uint8Array;
  stderr: string;
  code: number;
};

type GitOptions = {
  index?: string;
  input?: Uint8Array;
  timeout?: number;
  literalPaths?: boolean;
  identity?: SafePersistDataCommitter;
};

const MAIN_REF = "refs/heads/main";
const PLAIN_FILE_MODE = "100644";
const VERIFICATION_MILLISECONDS = 30_000;
const GIT_ENVIRONMENT_KEYS = [
  "GIT_DIR",
  "GIT_WORK_TREE",
  "GIT_COMMON_DIR",
  "GIT_INDEX_FILE",
  "GIT_INDEX_VERSION",
  "GIT_OBJECT_DIRECTORY",
  "GIT_ALTERNATE_OBJECT_DIRECTORIES",
  "GIT_PREFIX",
] as const;

function sha256(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

function isWithin(root: string, target: string): boolean {
  const path = relative(root, target);
  return path === "" || (path !== ".." && !path.startsWith(`..${sep}`) && !isAbsolute(path));
}

function absoluteRoot(value: string, name: string): void {
  if (!isAbsolute(value)) {
    throw new SafePersistDataError(`${name} must be an absolute path`, "integrity-refused");
  }
}

async function checkedSource(root: string, file: CheckedFile): Promise<Uint8Array> {
  let current = root;
  const parts = file.sourcePath.split("/");
  for (const [index, part] of parts.entries()) {
    current = join(current, part);
    const info = await lstat(current);
    if (info.isSymbolicLink() || !(index === parts.length - 1 ? info.isFile() : info.isDirectory())) {
      throw new SafePersistDataError("Completed output contains a symlink or non-file parent", "integrity-refused", [file.sourcePath]);
    }
    if (index === parts.length - 1 && process.platform !== "win32" && (info.mode & 0o111) !== 0) {
      throw new SafePersistDataError("Completed output is executable", "integrity-refused", [file.sourcePath]);
    }
  }
  const actual = await realpath(current);
  if (!isWithin(root, actual)) {
    throw new SafePersistDataError("Completed output escapes its source root", "integrity-refused", [file.sourcePath]);
  }
  const bytes = await readFile(current);
  if (sha256(bytes) !== file.sha256) {
    throw new SafePersistDataError("Completed output bytes do not match the declared SHA256", "integrity-refused", [file.sourcePath]);
  }
  return bytes;
}

function gitEnvironment(index?: string, literalPaths = true, identity?: SafePersistDataCommitter): Record<string, string | undefined> {
  const environment: Record<string, string | undefined> = { ...process.env, GIT_LITERAL_PATHSPECS: "1" };
  for (const key of GIT_ENVIRONMENT_KEYS) delete environment[key];
  if (!literalPaths) delete environment.GIT_LITERAL_PATHSPECS;
  if (index !== undefined) environment.GIT_INDEX_FILE = index;
  if (identity !== undefined) {
    environment.GIT_AUTHOR_NAME = identity.name;
    environment.GIT_AUTHOR_EMAIL = identity.email;
    environment.GIT_COMMITTER_NAME = identity.name;
    environment.GIT_COMMITTER_EMAIL = identity.email;
  }
  return environment;
}

async function runGit(
  repository: string,
  args: string[],
  options: GitOptions = {},
): Promise<GitResult> {
  const child = Bun.spawn(["git", ...args], {
    cwd: repository,
    env: gitEnvironment(options.index, options.literalPaths ?? true, options.identity),
    stdout: "pipe",
    stderr: "pipe",
    stdin: options.input === undefined ? "ignore" : "pipe",
    ...(options.timeout === undefined ? {} : { timeout: options.timeout }),
  });
  if (options.input !== undefined) {
    if (child.stdin === null || child.stdin === undefined) {
      throw new SafePersistDataError("Git input pipe is unavailable", "delivery-failed");
    }
    child.stdin.write(options.input);
    child.stdin.end();
  }
  const [stdout, stderr, code] = await Promise.all([
    new Response(child.stdout).arrayBuffer(),
    new Response(child.stderr).text(),
    child.exited,
  ]);
  return { stdout: new Uint8Array(stdout), stderr, code };
}

async function requiredGit(
  repository: string,
  args: string[],
  options: GitOptions = {},
): Promise<string> {
  const result = await runGit(repository, args, options);
  if (result.code !== 0) {
    const detail = args[0] === "fetch" || args[0] === "push" ? "" : `: ${result.stderr.trim()}`;
    throw new SafePersistDataError(`Git ${args[0] ?? "operation"} failed${detail}`, "delivery-failed");
  }
  return new TextDecoder().decode(result.stdout).trim();
}

async function requiredGitOutput(
  repository: string,
  args: string[],
  options: GitOptions = {},
): Promise<string> {
  const result = await runGit(repository, args, options);
  if (result.code !== 0) {
    const detail = args[0] === "fetch" || args[0] === "push" ? "" : `: ${result.stderr.trim()}`;
    throw new SafePersistDataError(`Git ${args[0] ?? "operation"} failed${detail}`, "delivery-failed");
  }
  return new TextDecoder().decode(result.stdout);
}

async function fetchMain(repository: string, timeout: number): Promise<string> {
  await requiredGit(repository, ["fetch", "--quiet", "--no-tags", "origin", MAIN_REF], { timeout });
  return requiredGit(repository, ["rev-parse", "--verify", "FETCH_HEAD"], { timeout });
}

async function treeEntries(
  repository: string,
  tree: string,
  paths: string[],
  timeout: number,
): Promise<Map<string, TreeEntry>> {
  const requested = [...new Set(paths)];
  if (requested.length === 0) return new Map();
  const input = new TextEncoder().encode(requested.map(path => `${tree}:${path}\n`).join(""));
  const listed = await requiredGitOutput(repository, ["cat-file", "--batch-check=%(objectname) %(objecttype)"], {
    input, timeout,
  });
  const rows = listed.split(/\r?\n/);
  if (rows.at(-1) === "") rows.pop();
  if (rows.length !== requested.length) {
    throw new SafePersistDataError("Git returned incomplete named tree metadata", "delivery-failed");
  }
  const entries = new Map<string, TreeEntry>();
  const blobs: { path: string; oid: string }[] = [];
  for (const [index, path] of requested.entries()) {
    const row = rows[index]!;
    if (row === `${tree}:${path} missing`) continue;
    const [oid, type, extra] = row.split(" ");
    if (oid === undefined || type === undefined || extra !== undefined || !/^[a-f0-9]{40,64}$/.test(oid)
      || !["blob", "tree", "commit"].includes(type)) {
      throw new SafePersistDataError("Git returned invalid named tree metadata", "delivery-failed", [path]);
    }
    entries.set(path, {
      mode: type === "tree" ? "040000" : type === "commit" ? "160000" : PLAIN_FILE_MODE,
      type, oid,
    });
    if (type === "blob") blobs.push({ path, oid });
  }
  if (blobs.length === 0) return entries;
  const blobPaths = blobs.map(({ path }) => path);
  const blobPathSet = new Set(blobPaths);
  const blobListing = await requiredGitOutput(repository, ["ls-tree", "-z", tree, "--", ...blobPaths], { timeout });
  const modes = new Map<string, TreeEntry>();
  for (const row of blobListing.split("\0").filter(Boolean)) {
    const separator = row.indexOf("\t");
    if (separator < 0) {
      throw new SafePersistDataError("Git returned an invalid tree entry", "delivery-failed");
    }
    const path = row.slice(separator + 1);
    const [mode, type, oid] = row.slice(0, separator).split(" ");
    if (!blobPathSet.has(path) || mode === undefined || type !== "blob" || oid === undefined) {
      throw new SafePersistDataError("Git returned an unexpected tree entry", "delivery-failed", [path]);
    }
    modes.set(path, { mode, type, oid });
  }
  for (const { path, oid } of blobs) {
    const entry = modes.get(path);
    if (entry === undefined || entry.oid !== oid) {
      throw new SafePersistDataError("Git returned incomplete named blob metadata", "delivery-failed", [path]);
    }
    entries.set(path, entry);
  }
  return entries;
}

async function buildGitBlobs(
  repository: string,
  files: CheckedFile[],
  sourceRoot: string,
  timeout: number,
): Promise<Map<string, string>> {
  const blobs = new Map<string, string>();
  for (const file of files) {
    const bytes = await checkedSource(sourceRoot, file);
    const blob = await requiredGit(
      repository,
      ["hash-object", "--no-filters", "-w", "--stdin"],
      { input: bytes, timeout },
    );
    blobs.set(file.targetPath, blob);
  }
  return blobs;
}

async function missingGitFiles(
  repository: string,
  tree: string,
  files: CheckedFile[],
  blobs: Map<string, string>,
  timeout: number,
): Promise<CheckedFile[]> {
  const names = files.flatMap(file => {
    const parts = file.targetPath.split("/");
    return [
      ...parts.slice(0, -1).map((_part, index) => parts.slice(0, index + 1).join("/")),
      file.targetPath,
    ];
  });
  const entries = await treeEntries(repository, tree, names, timeout);
  const missing: CheckedFile[] = [];
  for (const file of files) {
    const parts = file.targetPath.split("/");
    for (let count = 1; count < parts.length; count++) {
      const parent = parts.slice(0, count).join("/");
      const parentEntry = entries.get(parent);
      if (parentEntry !== undefined && (parentEntry.type !== "tree" || parentEntry.mode !== "040000")) {
        throw new SafePersistDataError("Completed output parent is not a directory", "integrity-refused", [file.targetPath]);
      }
    }
    const existing = entries.get(file.targetPath);
    if (existing === undefined) {
      missing.push(file);
      continue;
    }
    if (existing.mode !== PLAIN_FILE_MODE || existing.type !== "blob") {
      throw new SafePersistDataError("Completed output target is not a plain data file", "integrity-refused", [file.targetPath]);
    }
    if (existing.oid !== blobs.get(file.targetPath)) {
      throw new SafePersistDataError("Immutable output collision", "integrity-refused", [file.targetPath]);
    }
  }
  return missing;
}

async function refuseNewIgnoredFiles(
  repository: string,
  files: CheckedFile[],
  timeout: number,
): Promise<void> {
  if (files.length === 0) return;
  const checked = await runGit(repository, ["check-ignore", "--no-index", "-z", "--stdin"], {
    input: new TextEncoder().encode(files.map(file => `${file.targetPath}\0`).join("")),
    timeout,
    literalPaths: false,
  });
  if (checked.code !== 0 && checked.code !== 1) {
    throw new SafePersistDataError(
      `Git could not check named output ignore rules (exit ${checked.code}): ${checked.stderr.trim()}`,
      "delivery-failed",
    );
  }
  const ignored = new Set(new TextDecoder().decode(checked.stdout).split("\0").filter(Boolean));
  for (const file of files) {
    if (ignored.has(file.targetPath)) {
      throw new SafePersistDataError("New ignored output is refused", "integrity-refused", [file.targetPath]);
    }
  }
}

async function createCandidate(
  repository: string,
  base: string,
  files: CheckedFile[],
  blobs: Map<string, string>,
  message: string,
  committer: SafePersistDataCommitter,
  timeout: number,
): Promise<string> {
  const directory = await mkdtemp(join(tmpdir(), "safe-persist-data-"));
  const index = join(directory, "index");
  try {
    await requiredGit(repository, ["-c", "core.sparseCheckout=false", "-c", "index.sparse=false", "read-tree", base], {
      index,
      timeout,
    });
    const entries = files
      .filter(file => blobs.has(file.targetPath))
      .map(file => `${PLAIN_FILE_MODE} ${blobs.get(file.targetPath)}\t${file.targetPath}\0`)
      .join("");
    await requiredGit(repository, ["-c", "core.sparseCheckout=false", "-c", "index.sparse=false", "update-index", "-z", "--index-info"], {
      index,
      input: new TextEncoder().encode(entries),
      timeout,
    });
    const tree = await requiredGit(repository, ["-c", "core.sparseCheckout=false", "-c", "index.sparse=false", "write-tree"], {
      index,
      timeout,
    });
    return requiredGit(repository, [
      "commit-tree", tree, "-p", base, "-m", message,
    ], { timeout, identity: committer });
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}

async function deliverToGit(input: Extract<SafePersistDataInput, { destination: { kind: "git" } }>): Promise<SafePersistDataResult> {
  if (input.files.length === 0) {
    return { destination: "git", status: "no-changes", commit: null, files: 0, paths: [] };
  }
  absoluteRoot(input.sourceRoot, "sourceRoot");
  absoluteRoot(input.destination.repository, "repository");
  const sourceRoot = await realpath(input.sourceRoot);
  const repository = await realpath(input.destination.repository);
  const worktree = await requiredGit(repository, ["rev-parse", "--show-toplevel"]);
  if (await realpath(worktree) !== repository) {
    throw new SafePersistDataError("Git destination must name the worktree root", "integrity-refused");
  }

  const files: CheckedFile[] = input.files.map(file => ({ ...file, bytes: new Uint8Array() }));
  const deadlineSeconds = input.retry.deadline_seconds.default;
  if (deadlineSeconds === undefined) {
    throw new SafePersistDataError("Push retry requires deadline_seconds.default", "integrity-refused");
  }
  const deadline = performance.now() + deadlineSeconds * 1000;
  let candidate: string | undefined;
  let pushCount = 0;
  while (performance.now() < deadline) {
    const timeout = Math.max(1, Math.ceil(deadline - performance.now()));
    const base = await fetchMain(repository, timeout);
    const blobs = await buildGitBlobs(repository, files, sourceRoot, timeout);
    const missing = await missingGitFiles(repository, base, files, blobs, timeout);
    if (missing.length === 0) {
      return {
        destination: "git",
        status: candidate === undefined ? "already-on-main" : "landed",
        commit: base,
        files: files.length,
        paths: files.map(file => file.targetPath),
      };
    }

    await refuseNewIgnoredFiles(repository, missing, timeout);
    candidate = await createCandidate(repository, base, missing, blobs, input.message, input.committer, timeout);
    const pushed = await runGit(repository, ["push", "--no-thin", "origin", `${candidate}:${MAIN_REF}`], { timeout });
    pushCount++;
    const observed = await fetchMain(repository, VERIFICATION_MILLISECONDS);
    if ((await missingGitFiles(repository, observed, files, blobs, VERIFICATION_MILLISECONDS)).length === 0) {
      return {
        destination: "git",
        status: "landed",
        commit: observed,
        files: files.length,
        paths: files.map(file => file.targetPath),
      };
    }
    if (pushed.code === 0) {
      throw new SafePersistDataError("Git accepted the candidate but completed files are not visible", "delivery-failed");
    }
    const remaining = deadline - performance.now();
    if (remaining <= 0) break;
    const backoff = Math.min(
      input.retry.base_step_seconds * 2 ** Math.min(pushCount - 1, input.retry.ceiling_after),
      input.retry.ceiling_seconds,
    ) * 1000;
    await new Promise(resolveDelay => setTimeout(resolveDelay, Math.min(backoff, remaining)));
  }
  throw new SafePersistDataError("Git delivery retry deadline exhausted; completed files are retained", "delivery-failed");
}

async function ensureArtifactParents(root: string, path: string): Promise<string> {
  let current = root;
  const parts = path.split("/");
  for (const part of parts.slice(0, -1)) {
    current = join(current, part);
    try {
      const info = await lstat(current);
      if (info.isSymbolicLink() || !info.isDirectory()) {
        throw new SafePersistDataError("Artifact target contains a symlink or non-directory parent", "integrity-refused", [path]);
      }
    } catch (error) {
      if (error instanceof SafePersistDataError || (error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
      await mkdir(current);
    }
  }
  return join(current, parts.at(-1)!);
}

async function artifactTargetStatus(root: string, file: CheckedFile): Promise<"missing" | "present"> {
  let parent = root;
  const parts = file.targetPath.split("/");
  for (const part of parts.slice(0, -1)) {
    parent = join(parent, part);
    try {
      const info = await lstat(parent);
      if (info.isSymbolicLink() || !info.isDirectory()) {
        throw new SafePersistDataError("Artifact target contains a symlink or non-directory parent", "integrity-refused", [file.targetPath]);
      }
    } catch (error) {
      if (error instanceof SafePersistDataError || (error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
      return "missing";
    }
  }
  const target = join(parent, parts.at(-1)!);
  try {
    const info = await lstat(target);
    if (info.isSymbolicLink() || !info.isFile() || (process.platform !== "win32" && (info.mode & 0o111) !== 0)) {
      throw new SafePersistDataError("Artifact target is not a plain data file", "integrity-refused", [file.targetPath]);
    }
    const existing = await readFile(target);
    if (sha256(existing) !== file.sha256) {
      throw new SafePersistDataError("Immutable artifact collision", "integrity-refused", [file.targetPath]);
    }
    return "present";
  } catch (error) {
    if (error instanceof SafePersistDataError || (error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    return "missing";
  }
}

async function writeArtifact(root: string, file: CheckedFile): Promise<boolean> {
  const target = await ensureArtifactParents(root, file.targetPath);
  const parent = join(target, "..");
  const temporary = join(parent, `.safe-persist-${randomUUID()}.tmp`);
  try {
    await writeFile(temporary, file.bytes, { flag: "wx", mode: 0o600 });
    if (process.platform !== "win32") await chmod(temporary, 0o644);
    try {
      await link(temporary, target);
      return true;
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
      const status = await artifactTargetStatus(root, file);
      if (status === "present") return false;
      throw new SafePersistDataError("Artifact target changed during delivery", "integrity-refused", [file.targetPath]);
    }
  } finally {
    await unlink(temporary).catch(error => {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    });
  }
}

async function deliverToArtifactDirectory(
  input: Extract<SafePersistDataInput, { destination: { kind: "artifact-directory" } }>,
): Promise<SafePersistDataResult> {
  if (input.files.length === 0) {
    return { destination: "artifact-directory", status: "no-changes", files: 0, paths: [] };
  }
  absoluteRoot(input.sourceRoot, "sourceRoot");
  absoluteRoot(input.destination.directory, "artifact directory");
  await mkdir(input.destination.directory, { recursive: true });
  const sourceRoot = await realpath(input.sourceRoot);
  const root = await realpath(input.destination.directory);
  const files: CheckedFile[] = input.files.map(file => ({ ...file, bytes: new Uint8Array() }));
  for (const file of files) file.bytes = await checkedSource(sourceRoot, file);
  const statuses = await Promise.all(files.map(file => artifactTargetStatus(root, file)));
  if (statuses.every(status => status === "present")) {
    return {
      destination: "artifact-directory",
      status: "already-present",
      files: files.length,
      paths: files.map(file => file.targetPath),
    };
  }
  let wrote = false;
  for (const [index, file] of files.entries()) {
    if (statuses[index] === "present") continue;
    wrote = (await writeArtifact(root, file)) || wrote;
  }
  return {
    destination: "artifact-directory",
    status: wrote ? "written" : "already-present",
    files: files.length,
    paths: files.map(file => file.targetPath),
  };
}

export function safe_persist_data(input: SafePersistDataInput): Promise<SafePersistDataResult>;
export async function safe_persist_data(input: SafePersistDataInput): Promise<SafePersistDataResult> {
  const parsed = SafePersistDataInputSchema.parse(input);
  let result: SafePersistDataResult;
  if ("retry" in parsed) {
    result = await deliverToGit(parsed);
  } else {
    result = await deliverToArtifactDirectory(parsed);
  }
  return SafePersistDataResultSchema.parse(result);
}
