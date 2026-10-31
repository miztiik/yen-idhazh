import { createHash } from "node:crypto";
import { chmod, copyFile, mkdir, mkdtemp, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { expect, test } from "bun:test";
import {
  compare_and_swap_data,
  read_git_data,
  CompareAndSwapDataInputSchema,
  SafePersistDataError,
  SafePersistDataInputSchema,
  SafePersistDataResultSchema,
  safe_persist_data,
} from "../src/index";

function digest(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

function retry(deadline = 4) {
  return {
    deadline_seconds: { default: deadline },
    base_step_seconds: 0.01,
    ceiling_seconds: 0.02,
    ceiling_after: 2,
  };
}

function artifactInput(sourceRoot: string, directory: string, bytes: Uint8Array) {
  return {
    sourceRoot,
    files: [{ sourcePath: "completed/item.bin", targetPath: "items/item.bin", sha256: digest(bytes) }],
    permittedPaths: ["items"],
    destination: { kind: "artifact-directory" as const, directory },
  };
}

async function git(directory: string, args: string[], extra: Record<string, string> = {}): Promise<string> {
  const environment: Record<string, string | undefined> = { ...process.env, ...extra };
  delete environment.GIT_INDEX_FILE;
  delete environment.GIT_DIR;
  delete environment.GIT_WORK_TREE;
  environment.GIT_AUTHOR_NAME = "Fixture";
  environment.GIT_AUTHOR_EMAIL = "fixture@example.test";
  environment.GIT_COMMITTER_NAME = "Fixture";
  environment.GIT_COMMITTER_EMAIL = "fixture@example.test";
  const child = Bun.spawn(["git", ...args], { cwd: directory, env: environment, stdout: "pipe", stderr: "pipe" });
  const [output, errors, code] = await Promise.all([
    new Response(child.stdout).text(),
    new Response(child.stderr).text(),
    child.exited,
  ]);
  if (code !== 0) throw new Error(`Generated Git fixture refused ${args[0]}: ${errors}`);
  return output.trim();
}

async function gitBytes(directory: string, args: string[]): Promise<Uint8Array> {
  const environment: Record<string, string | undefined> = { ...process.env };
  delete environment.GIT_INDEX_FILE;
  delete environment.GIT_DIR;
  delete environment.GIT_WORK_TREE;
  const child = Bun.spawn(["git", ...args], { cwd: directory, env: environment, stdout: "pipe", stderr: "pipe" });
  const [output, errors, code] = await Promise.all([
    new Response(child.stdout).arrayBuffer(),
    new Response(child.stderr).text(),
    child.exited,
  ]);
  if (code !== 0) throw new Error(`Generated Git fixture refused ${args[0]}: ${errors}`);
  return new Uint8Array(output);
}

async function repositoryFixture() {
  const root = await mkdtemp(join(tmpdir(), "data-delivery-"));
  const origin = join(root, "origin.git");
  const repository = join(root, "checkout");
  const sourceRoot = join(root, "run");
  await mkdir(repository);
  await mkdir(sourceRoot);
  await git(root, ["init", "--bare", "--initial-branch=main", origin]);
  await git(repository, ["init", "--initial-branch=main"]);
  await writeFile(join(repository, "README.md"), "Base revision.\n");
  await git(repository, ["add", "--", "README.md"]);
  await git(repository, ["commit", "-m", "Create delivery fixture"]);
  await git(repository, ["remote", "add", "origin", origin]);
  await git(repository, ["push", "origin", "HEAD:refs/heads/main"]);
  const base = await git(repository, ["rev-parse", "HEAD"]);
  return {
    root,
    origin,
    repository,
    sourceRoot,
    base,
    close: () => rm(root, { recursive: true, force: true }),
  };
}

function gitInput(input: Awaited<ReturnType<typeof repositoryFixture>>, bytes: Uint8Array) {
  return {
    sourceRoot: input.sourceRoot,
    files: [{
      sourcePath: "completed/item.bin",
      targetPath: "state/raw/planner/2026/10/27/item.bin",
      sha256: digest(bytes),
    }],
    permittedPaths: ["state/raw/planner"],
    destination: { kind: "git" as const, repository: input.repository },
    committer: { name: "Test Data Delivery", email: "delivery@example.test" },
    message: "Record completed data",
    retry: retry(),
  };
}

async function createSource(root: string, bytes: Uint8Array): Promise<void> {
  await mkdir(join(root, "completed"), { recursive: true });
  await writeFile(join(root, "completed", "item.bin"), bytes);
}

test("the input contract refuses unsafe paths, broad permission and repeated targets", () => {
  const base = {
    sourceRoot: "C:\\run",
    files: [{ sourcePath: "completed/item.bin", targetPath: "items/item.bin", sha256: "a".repeat(64) }],
    permittedPaths: ["items"],
    destination: { kind: "artifact-directory", directory: "C:\\artifacts" },
  };
  expect(SafePersistDataInputSchema.safeParse({
    ...base,
    files: [{ ...base.files[0]!, sourcePath: "../item.bin" }],
  }).success).toBe(false);
  expect(SafePersistDataInputSchema.safeParse({
    ...base,
    files: [{ ...base.files[0]!, targetPath: "items/*.bin" }],
  }).success).toBe(false);
  expect(SafePersistDataInputSchema.safeParse({ ...base, permittedPaths: ["state"] }).success).toBe(false);
  expect(SafePersistDataInputSchema.safeParse({
    ...base,
    files: [base.files[0]!, { ...base.files[0]!, sourcePath: "completed/other.bin" }],
  }).success).toBe(false);
  expect(SafePersistDataInputSchema.safeParse({ ...base, permittedPaths: ["elsewhere"] }).success).toBe(false);
  const gitRequest = {
    ...base,
    destination: { kind: "git" as const, repository: "C:\\repo" },
    committer: { name: "Test Data Delivery", email: "delivery@example.test" },
    message: "Commit completed bytes",
    retry: retry(),
  };
  expect(SafePersistDataInputSchema.safeParse({
    ...gitRequest,
    committer: { ...gitRequest.committer, name: "two\nlines" },
  }).success).toBe(false);
  expect(SafePersistDataResultSchema.safeParse({
    destination: "artifact-directory",
    status: "written",
    files: 1,
    paths: [],
  }).success).toBe(false);
  expect(CompareAndSwapDataInputSchema.safeParse({
    sourceRoot: "C:\\run", destination: { kind: "git", repository: "C:\\repo" },
    expected_revision: "not-a-revision", max_bytes: 4096, files: [],
    permittedPaths: ["state/raw/planner/availability"],
    committer: { name: "Test", email: "test@example.test" }, message: "CAS",
  }).success).toBe(false);
});

test("Git CAS publishes a complete state snapshot only from its exact baseline", async () => {
  const fixture = await repositoryFixture();
  const statePath = "state/raw/planner/availability/state.json";
  const markerPath = "state/raw/planner/availability/enrollment.json";
  const stateBytes = new TextEncoder().encode('{"version":"2026-10-30","sequence":1}\n');
  const markerBytes = new TextEncoder().encode('{"initialized":true}\n');
  const changedBytes = new TextEncoder().encode('{"version":"2026-10-30","sequence":2}\n');
  await createSource(fixture.sourceRoot, stateBytes);
  await writeFile(join(fixture.sourceRoot, "completed", "marker.json"), markerBytes);
  const committer = { name: "Test Data Delivery", email: "delivery@example.test" };
  const permissions = ["state/raw/planner/availability"];
  try {
    const snapshot = await read_git_data({
      repository: fixture.repository,
      max_bytes: 4096,
      paths: [{ path: statePath }, { path: markerPath }],
    });
    expect(snapshot.revision).toBe(fixture.base);
    expect(snapshot.files).toEqual([
      { path: statePath, sha256: null, content: null, ever_published: false },
      { path: markerPath, sha256: null, content: null, ever_published: false },
    ]);
    const result = await compare_and_swap_data({
      sourceRoot: fixture.sourceRoot,
      destination: { kind: "git", repository: fixture.repository },
      expected_revision: snapshot.revision,
      max_bytes: 4096,
      files: [
        { sourcePath: "completed/item.bin", targetPath: statePath, sha256: digest(stateBytes) },
        { sourcePath: "completed/marker.json", targetPath: markerPath, sha256: digest(markerBytes) },
      ],
      permittedPaths: permissions,
      committer,
      message: "Initialize availability state",
    });
    expect(result).toMatchObject({ status: "published", expected_revision: fixture.base, paths: [statePath, markerPath] });
    const published = await read_git_data({
      repository: fixture.repository, max_bytes: 4096, paths: [{ path: statePath }, { path: markerPath }],
    });
    expect(published.revision).toMatch(/^[a-f0-9]{40,64}$/);
    expect(published.files.map(file => file.ever_published)).toEqual([true, true]);
    expect(Buffer.from(published.files[0]!.content!, "base64").toString()).toBe(new TextDecoder().decode(stateBytes));
    expect(Buffer.from(published.files[1]!.content!, "base64").toString()).toBe(new TextDecoder().decode(markerBytes));
    await expect(read_git_data({
      repository: fixture.repository, max_bytes: 1, paths: [{ path: statePath }],
    })).rejects.toMatchObject({ code: "integrity-refused" });

    await writeFile(join(fixture.sourceRoot, "completed", "item.bin"), changedBytes);
    const stale = await compare_and_swap_data({
      sourceRoot: fixture.sourceRoot,
      destination: { kind: "git", repository: fixture.repository },
      expected_revision: fixture.base,
      max_bytes: 4096,
      files: [{ sourcePath: "completed/item.bin", targetPath: statePath, sha256: digest(changedBytes) }],
      permittedPaths: permissions, committer, message: "Stale availability update",
    });

    expect(stale).toMatchObject({ status: "conflict", expected_revision: fixture.base, revision: published.revision });
    const after = await read_git_data({
      repository: fixture.repository, max_bytes: 4096, paths: [{ path: statePath }, { path: markerPath }],
    });
    expect(after.revision).toBe(published.revision);
    expect(after.files.map(file => file.ever_published)).toEqual([true, true]);
    expect(Buffer.from(after.files[0]!.content!, "base64").toString()).toBe(new TextDecoder().decode(stateBytes));
    expect(Buffer.from(after.files[1]!.content!, "base64").toString()).toBe(new TextDecoder().decode(markerBytes));

    await git(fixture.repository, ["fetch", "--quiet", "origin", "refs/heads/main"]);
    await git(fixture.repository, ["reset", "--hard", "FETCH_HEAD"]);
    await git(fixture.repository, ["rm", "--", statePath, markerPath]);
    await git(fixture.repository, ["commit", "-m", "Remove established availability files"]);
    await git(fixture.repository, ["push", "origin", "HEAD:refs/heads/main"]);
    const removed = await read_git_data({
      repository: fixture.repository, max_bytes: 4096, paths: [{ path: statePath }, { path: markerPath }],
    });
    expect(removed.files).toEqual([
      { path: statePath, sha256: null, content: null, ever_published: true },
      { path: markerPath, sha256: null, content: null, ever_published: true },
    ]);
  } finally {
    await fixture.close();
  }
}, 30000);

test("Git CAS confirms its own publication when a later state update has already landed", async () => {
  const fixture = await repositoryFixture();
  const statePath = "state/raw/planner/availability/state.json";
  const bytes = new TextEncoder().encode('{"sequence":1}\n');
  try {
    await createSource(fixture.sourceRoot, bytes);
    const hook = join(fixture.origin, "hooks", "post-receive");
    await writeFile(hook, [
      "#!/bin/sh", "set -eu",
      "read before after reference",
      'test "$reference" = refs/heads/main || exit 0',
      'index=$(mktemp)', 'rm "$index"', 'export GIT_INDEX_FILE="$index"',
      'trap \'rm -f "$GIT_INDEX_FILE"\' EXIT',
      'git read-tree "$after"',
      'blob=$(printf \'{"sequence":2}\\n\' | git hash-object -w --stdin)',
      `git update-index --add --cacheinfo 100644 "$blob" "${statePath}"`,
      'tree=$(git write-tree)',
      'next=$(printf "Record subsequent state\\n" | git -c user.name=Fixture -c user.email=fixture@example.test commit-tree "$tree" -p "$after")',
      'git update-ref "$reference" "$next" "$after"', "",
    ].join("\n"));
    await chmod(hook, 0o755);
    const result = await compare_and_swap_data({
      sourceRoot: fixture.sourceRoot, destination: { kind: "git", repository: fixture.repository },
      expected_revision: fixture.base, max_bytes: 4096,
      files: [{ sourcePath: "completed/item.bin", targetPath: statePath, sha256: digest(bytes) }],
      permittedPaths: ["state/raw/planner/availability"],
      committer: { name: "Fixture", email: "fixture@example.test" }, message: "Record first state",
    });
    expect(result.status).toBe("published");
    if (result.status !== "published") throw new Error("The generated origin must accept the first state");
    expect(result.revision).toBe(result.commit);
    const latest = await read_git_data({
      repository: fixture.repository, max_bytes: 4096, paths: [{ path: statePath }],
    });
    expect(latest.revision).not.toBe(result.commit);
    expect(Buffer.from(latest.files[0]!.content!, "base64").toString()).toBe('{"sequence":2}\n');
    expect(await git(fixture.repository, ["show", `${result.commit}:${statePath}`])).toBe('{"sequence":1}');
    expect(await git(fixture.repository, ["for-each-ref", "--format=%(refname)", "refs/data-delivery-fetch/"])).toBe("");
  } finally { await fixture.close(); }
}, 120000);

test("artifact delivery copies only named files, verifies hashes and refuses replacement", async () => {
  const root = await mkdtemp(join(tmpdir(), "data-artifacts-"));
  const sourceRoot = join(root, "source");
  const directory = join(root, "output");
  const bytes = new TextEncoder().encode("completed output");
  await createSource(sourceRoot, bytes);
  await writeFile(join(sourceRoot, "completed", "sibling.bin"), "not named");
  try {
    const request = artifactInput(sourceRoot, directory, bytes);
    const first = await safe_persist_data(request);
    expect(first).toMatchObject({
      destination: "artifact-directory",
      status: "written",
      files: 1,
      paths: ["items/item.bin"],
    });
    expect(Array.from(await readFile(join(directory, "items", "item.bin")))).toEqual(Array.from(bytes));
    expect(await Bun.file(join(directory, "completed", "sibling.bin")).exists()).toBe(false);
    expect((await safe_persist_data(request)).status).toBe("already-present");
    await writeFile(join(directory, "items", "item.bin"), "different bytes");
    await expect(safe_persist_data(request)).rejects.toMatchObject({
      code: "integrity-refused",
      paths: ["items/item.bin"],
    } satisfies Partial<SafePersistDataError>);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("artifact delivery refuses a symlink parent", async () => {
  const root = await mkdtemp(join(tmpdir(), "data-artifact-link-"));
  const sourceRoot = join(root, "source");
  const directory = join(root, "output");
  const outside = join(root, "outside");
  const bytes = new TextEncoder().encode("completed output");
  await createSource(sourceRoot, bytes);
  await mkdir(directory);
  await mkdir(outside);
  await symlink(outside, join(directory, "items"), "junction");
  try {
    await expect(safe_persist_data(artifactInput(sourceRoot, directory, bytes))).rejects.toMatchObject({
      code: "integrity-refused",
      paths: ["items/item.bin"],
    } satisfies Partial<SafePersistDataError>);
    expect(await Bun.file(join(outside, "item.bin")).exists()).toBe(false);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("Git delivery checks exact paths in a state tree with unrelated siblings", async () => {
  const fixture = await repositoryFixture();
  const bytes = new Uint8Array([9, 8, 7, 0, 255]);
  const unrelatedPath = join(fixture.repository, "state", "unrelated", "keep.txt");
  await createSource(fixture.sourceRoot, bytes);
  await mkdir(join(fixture.repository, "state", "unrelated"), { recursive: true });
  await writeFile(unrelatedPath, "Keep this unrelated state.\n");
  try {
    await git(fixture.repository, ["add", "--", "state/unrelated/keep.txt"]);
    await git(fixture.repository, ["commit", "-m", "Add unrelated state"]);
    await git(fixture.repository, ["push", "origin", "HEAD:refs/heads/main"]);
    const request = gitInput(fixture, bytes);
    const result = await safe_persist_data(request);
    expect(result).toMatchObject({
      destination: "git", status: "landed", files: 1, paths: [request.files[0]!.targetPath],
    });
    expect(Array.from(await gitBytes(fixture.origin, [
      "--git-dir", fixture.origin, "show", `main:${request.files[0]!.targetPath}`,
    ]))).toEqual(Array.from(bytes));
    expect(await git(fixture.origin, [
      "--git-dir", fixture.origin, "show", "main:state/unrelated/keep.txt",
    ])).toBe("Keep this unrelated state.");
    expect((await safe_persist_data(request)).status).toBe("already-on-main");
    const conflictingBytes = new Uint8Array([1, 2, 3]);
    await writeFile(join(fixture.sourceRoot, "completed", "item.bin"), conflictingBytes);
    request.files[0]!.sha256 = digest(conflictingBytes);
    await expect(safe_persist_data(request)).rejects.toMatchObject({
      code: "integrity-refused",
      paths: [request.files[0]!.targetPath],
    } satisfies Partial<SafePersistDataError>);
    expect(Array.from(await gitBytes(fixture.origin, [
      "--git-dir", fixture.origin, "show", `main:${request.files[0]!.targetPath}`,
    ]))).toEqual(Array.from(bytes));
  } finally {
    await fixture.close();
  }
}, 30000);

test("a rejected push retries on fresh main without losing a concurrent file or changing completed bytes", async () => {
  const fixture = await repositoryFixture();
  const bytes = new Uint8Array([4, 5, 6, 0, 255]);
  await createSource(fixture.sourceRoot, bytes);
  try {
    await git(fixture.repository, ["sparse-checkout", "set", "--no-cone", "/README.md"]);
    await writeFile(join(fixture.repository, "README.md"), "Staged caller change.\n");
    await git(fixture.repository, ["add", "--", "README.md"]);
    const index = join(fixture.repository, ".git", "index");
    const foreignIndex = join(fixture.root, "foreign-index");
    const sparsePatterns = join(fixture.repository, ".git", "info", "sparse-checkout");
    await copyFile(index, foreignIndex);
    const [indexBefore, foreignBefore, sparseBefore] = await Promise.all([
      readFile(index),
      readFile(foreignIndex),
      readFile(sparsePatterns),
    ]);
    const headBefore = await readFile(join(fixture.repository, ".git", "HEAD"));
    const concurrent = join(fixture.root, "concurrent");
    await git(fixture.root, ["clone", "--quiet", fixture.origin, concurrent]);
    await writeFile(join(concurrent, "concurrent.txt"), "Keep this concurrent change.\n");
    await git(concurrent, ["add", "--", "concurrent.txt"]);
    await git(concurrent, ["commit", "-m", "Add concurrent file"]);
    await git(concurrent, ["push", "origin", "HEAD:refs/heads/prepared"]);
    const moved = await git(concurrent, ["rev-parse", "HEAD"]);
    const hook = join(fixture.repository, ".git", "hooks", "pre-push");
    const marker = join(fixture.root, "hook-used");
    const asGitPath = (path: string) => path.replaceAll("\\", "/").replaceAll("'", "'\\''");
    await writeFile(hook, [
      "#!/bin/sh",
      "set -eu",
      'if test ! -f "$DELIVERY_TEST_MARKER"; then',
      '  git --git-dir="$DELIVERY_TEST_ORIGIN" update-ref refs/heads/main "$DELIVERY_TEST_TIP" "$DELIVERY_TEST_BASE"',
      '  touch "$DELIVERY_TEST_MARKER"',
      "fi",
      "",
    ].join("\n"), { mode: 0o755 });
    const request = gitInput(fixture, bytes);
    request.retry = retry(30);
    const originalBytes = await readFile(join(fixture.sourceRoot, "completed", "item.bin"));
    const previousEnvironment = {
      gitIndex: process.env.GIT_INDEX_FILE,
      authorName: process.env.GIT_AUTHOR_NAME,
      authorEmail: process.env.GIT_AUTHOR_EMAIL,
      committerName: process.env.GIT_COMMITTER_NAME,
      committerEmail: process.env.GIT_COMMITTER_EMAIL,
      marker: process.env.DELIVERY_TEST_MARKER,
      origin: process.env.DELIVERY_TEST_ORIGIN,
      tip: process.env.DELIVERY_TEST_TIP,
      base: process.env.DELIVERY_TEST_BASE,
    };
    process.env.GIT_INDEX_FILE = foreignIndex;
    process.env.GIT_AUTHOR_NAME = "Inherited author";
    process.env.GIT_AUTHOR_EMAIL = "inherited@example.test";
    process.env.GIT_COMMITTER_NAME = "Inherited committer";
    process.env.GIT_COMMITTER_EMAIL = "inherited@example.test";
    process.env.DELIVERY_TEST_MARKER = asGitPath(marker);
    process.env.DELIVERY_TEST_ORIGIN = asGitPath(fixture.origin);
    process.env.DELIVERY_TEST_TIP = moved;
    process.env.DELIVERY_TEST_BASE = fixture.base;
    let result: Awaited<ReturnType<typeof safe_persist_data>>;
    try {
      result = await safe_persist_data(request);
    } finally {
      if (previousEnvironment.gitIndex === undefined) delete process.env.GIT_INDEX_FILE;
      else process.env.GIT_INDEX_FILE = previousEnvironment.gitIndex;
      if (previousEnvironment.authorName === undefined) delete process.env.GIT_AUTHOR_NAME;
      else process.env.GIT_AUTHOR_NAME = previousEnvironment.authorName;
      if (previousEnvironment.authorEmail === undefined) delete process.env.GIT_AUTHOR_EMAIL;
      else process.env.GIT_AUTHOR_EMAIL = previousEnvironment.authorEmail;
      if (previousEnvironment.committerName === undefined) delete process.env.GIT_COMMITTER_NAME;
      else process.env.GIT_COMMITTER_NAME = previousEnvironment.committerName;
      if (previousEnvironment.committerEmail === undefined) delete process.env.GIT_COMMITTER_EMAIL;
      else process.env.GIT_COMMITTER_EMAIL = previousEnvironment.committerEmail;
      if (previousEnvironment.marker === undefined) delete process.env.DELIVERY_TEST_MARKER;
      else process.env.DELIVERY_TEST_MARKER = previousEnvironment.marker;
      if (previousEnvironment.origin === undefined) delete process.env.DELIVERY_TEST_ORIGIN;
      else process.env.DELIVERY_TEST_ORIGIN = previousEnvironment.origin;
      if (previousEnvironment.tip === undefined) delete process.env.DELIVERY_TEST_TIP;
      else process.env.DELIVERY_TEST_TIP = previousEnvironment.tip;
      if (previousEnvironment.base === undefined) delete process.env.DELIVERY_TEST_BASE;
      else process.env.DELIVERY_TEST_BASE = previousEnvironment.base;
    }
    expect(result).toMatchObject({ destination: "git", status: "landed" });
    expect(await Bun.file(marker).exists()).toBe(true);
    if (result.destination !== "git" || result.commit === null) throw new Error("Git retry must return its published revision");
    expect(await git(fixture.origin, [
      "--git-dir", fixture.origin, "show", "-s", "--format=%an%x00%ae%x00%cn%x00%ce", result.commit,
    ])).toBe("Test Data Delivery\0delivery@example.test\0Test Data Delivery\0delivery@example.test");
    expect((await readFile(marker)).byteLength).toBe(0);
    expect(await readFile(index)).toEqual(indexBefore);
    expect(await readFile(foreignIndex)).toEqual(foreignBefore);
    expect(await readFile(sparsePatterns)).toEqual(sparseBefore);
    expect(await readFile(join(fixture.repository, ".git", "HEAD"))).toEqual(headBefore);
    expect(await git(fixture.origin, ["--git-dir", fixture.origin, "show", "main:concurrent.txt"]))
      .toBe("Keep this concurrent change.");
    expect(Array.from(await gitBytes(fixture.origin, ["--git-dir", fixture.origin, "show", `main:${result.paths[0]}`])))
      .toEqual(Array.from(originalBytes));
    expect(await readFile(join(fixture.sourceRoot, "completed", "item.bin"))).toEqual(originalBytes);
    const conflictingBytes = new TextEncoder().encode("different completed bytes");
    await writeFile(join(fixture.sourceRoot, "completed", "item.bin"), conflictingBytes);
    request.files[0]!.sha256 = digest(conflictingBytes);
    await expect(safe_persist_data(request)).rejects.toMatchObject({
      code: "integrity-refused",
      paths: [request.files[0]!.targetPath],
    } satisfies Partial<SafePersistDataError>);
    expect(Array.from(await gitBytes(fixture.origin, ["--git-dir", fixture.origin, "show", `main:${result.paths[0]}`])))
      .toEqual(Array.from(originalBytes));
  } finally {
    await fixture.close();
  }
}, 30000);
