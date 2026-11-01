/** Does real loopback delivery reuse verified metadata, the existing Git engine and owned-child cleanup? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { PLANNER_API_PREFIX } from "@idhazh/common-contracts";
import { SafePersistDataCommitterSchema } from "@idhazh/data-delivery";
import { createSafePersistApp } from "../scripts/safe-persist-http-api";
import { deliverWorkflowMetadataHttp } from "../scripts/safe-persist-http-client";
import { finalizeRunOutput } from "../scripts/finalize-run-output";
import {
  MetadataDeliveryResultSchema, SafePersistHttpReadySchema, SafePersistHttpStartupFailureSchema,
  SafePersistHttpStartupSchema,
} from "../scripts/feed-ingest-plan-delivery-result";
import { ServiceSettingsSchema } from "../src/config/service-settings";
import { publicationGitRecording, publicationRecording } from "./publication-recordings";
import { fixtureGit } from "./fixture-git";
import { writeRecordedHostOutput } from "./host-output-recordings";

type Recording = Awaited<ReturnType<typeof publicationGitRecording>>;
const serverEntry = fileURLToPath(new URL("../scripts/safe-persist-http-server.ts", import.meta.url));
const requestFor = (f: Recording, paths = f.commit.paths) => ({ runNumber: "700", attempt: 3, paths });
const inputFor = (f: Recording) => ({
  root: f.repository, directory: f.directory, currentRunFiles: JSON.stringify(f.commit.paths), runNumber: "700", attempt: 3,
  gitSha: f.identity.git_sha,
});

async function hostRecording() {
  const f = await publicationGitRecording();
  try {
    const host = await writeRecordedHostOutput(f.directory, f.identity, f.inputs.ledgerSettings);
    const paths = host.response.files.map(file => file.path);
    return { ...f, host, paths, commit: { ...f.commit, paths } };
  } catch (error) { await f.close(); throw error; }
}

async function openApi(f: Recording) {
  const settings = ServiceSettingsSchema.parse(await Bun.file(join(f.repository, "config", "feed-ingest-plan-service.json")).json());
  const identity = SafePersistHttpReadySchema.parse({
    event: "safe_persist_ready", nonce: randomUUID(), pid: process.pid, port: settings.listener.port,
  });
  const app = createSafePersistApp({
    root: f.repository, directory: f.directory, maxBodyBytes: settings.listener.max_body_bytes,
    gitSha: f.identity.git_sha,
    identity, signal: new AbortController().signal,
  });
  const server = Bun.serve({
    hostname: "127.0.0.1", port: settings.listener.port,
    fetch: (request, listener) => app.fetch(request, { beginDelivery: () => listener.timeout(request, 0) }),
  });
  return {
    server, base: `http://127.0.0.1:${server.port}${PLANNER_API_PREFIX}`,
    post: (request: unknown) => fetch(`http://127.0.0.1:${server.port}${PLANNER_API_PREFIX}/safe-persist-data`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(request), timeout: false,
    }),
  };
}

async function assertReleased(port: number) {
  const probe = Bun.serve({ hostname: "127.0.0.1", port, fetch: () => new Response() });
  await probe.stop(true);
}

async function waitForHealth(port: number, signal: AbortSignal) {
  while (true) {
    signal.throwIfAborted();
    try {
      const response = await fetch(`http://127.0.0.1:${port}${PLANNER_API_PREFIX}/health`, { signal });
      if (response.status !== 200) throw new Error("Expected safe-persist child health");
      return SafePersistHttpReadySchema.parse((await response.json()).identity);
    } catch (error) {
      if (!(error instanceof Error) || !("code" in error) || !["ECONNREFUSED", "ConnectionRefused"].includes(String(error.code))) throw error;
      await Bun.sleep(10);
    }
  }
}

async function waitForExit(pid: number, signal: AbortSignal) {
  while (true) {
    try { process.kill(pid, 0); }
    catch (error) {
      if (!(error instanceof Error) || !("code" in error) || error.code !== "ESRCH") throw error;
      return;
    }
    signal.throwIfAborted();
    await Bun.sleep(10);
  }
}

test("HTTP delivery lands exact remote bytes and repeats without changing completed collection or the caller checkout", async () => {
  const f = await publicationRecording();
  const api = await openApi(f);
  try {
    const index = await readFile(join(f.repository, ".git", "index"));
    const responseBefore = await readFile(join(f.directory, "response.json"));
    const selectedBefore = await readFile(join(f.repository, f.summary.selected_articles_artifact!));
    const response = await api.post(requestFor(f));
    expect(response.status).toBe(200);
    const result = MetadataDeliveryResultSchema.parse(await response.json());
    expect(result).toMatchObject({ status: "landed", files: f.paths.length, paths: f.paths });
    expect(await fixtureGit(f.origin, ["--git-dir", f.origin, "rev-parse", "main"])).toBe(result.commit!);
    expect((await fixtureGit(f.origin, ["--git-dir", f.origin,
      "diff-tree", "--no-commit-id", "--name-only", "-r", "main"])).split("\n").sort())
      .toEqual(f.paths.map(path => `state/${path}`).sort());
    expect(await fixtureGit(f.origin, ["--git-dir", f.origin,
      "rev-parse", ...f.paths.map(path => `main:state/${path}`)]))
      .toBe(await fixtureGit(f.repository, ["hash-object", "--no-filters",
        ...f.paths.map(path => join(f.directory, "state", path))]));
    const committer = SafePersistDataCommitterSchema.parse(await Bun.file(join(f.repository, "config", "data-delivery.json")).json());
    expect(await fixtureGit(f.origin, ["--git-dir", f.origin, "log", "-1", "--format=%cn <%ce>"]))
      .toBe(`${committer.name} <${committer.email}>`);
    const repeated = await api.post(requestFor(f));
    expect(repeated.status).toBe(200);
    expect(MetadataDeliveryResultSchema.parse(await repeated.json())).toEqual({
      ...result, status: "already-on-main",
    });
    expect(await fixtureGit(f.origin, ["--git-dir", f.origin, "rev-parse", "main"])).toBe(result.commit!);
    expect(await fixtureGit(f.repository, ["rev-parse", "HEAD"])).toBe(f.head);
    expect(await readFile(join(f.repository, ".git", "index"))).toEqual(index);
    expect(await readFile(join(f.directory, "response.json"))).toEqual(responseBefore);
    expect(await readFile(join(f.repository, f.summary.selected_articles_artifact!))).toEqual(selectedBefore);
    expect((await fetch(`${api.base}/plan`, { method: "POST", body: "{}" })).status).toBe(404);
  } finally { await api.server.stop(true); await f.close(); }
});

test("HTTP rejects malformed controls and retains the adapter's existing identity and completed-path checks", async () => {
  const f = await publicationRecording();
  const api = await openApi(f);
  try {
    for (const controls of [
      { repository: "outside" }, { sourceRoot: "outside" }, { directory: "outside" },
      { permittedPaths: ["state"] }, { destination: { kind: "git", repository: "outside" } },
      { committer: { name: "Fixture", email: "fixture@example.test" } }, { retry: {} }, { message: "Other commit" },
      { article_text: "Not a delivery control" },
    ]) expect((await api.post({ ...requestFor(f), ...controls })).status).toBe(400);
    expect((await fetch(`${api.base}/safe-persist-data`, {
      method: "POST", headers: { "content-type": "application/json" }, body: "{",
    })).status).toBe(400);
    expect(await Bun.file(join(f.directory, "delivery-result.json")).exists()).toBe(false);
    for (const request of [
      { ...requestFor(f), runNumber: "701" }, { ...requestFor(f), attempt: 4 },
      { ...requestFor(f), paths: f.paths.slice(1) },
      { ...requestFor(f), paths: ["raw/unregistered/2026/10/21/file.parquet"] },
    ]) {
      expect((await api.post(request)).status).toBe(500);
      expect(MetadataDeliveryResultSchema.parse(await Bun.file(join(f.directory, "delivery-result.json")).json()).status).toBe("failed");
    }
    expect(await fixtureGit(f.origin, ["--git-dir", f.origin, "rev-parse", "main"])).toBe(f.head);
  } finally { await api.server.stop(true); await f.close(); }
});

test("the delivery child needs no planner process, response or collection input to deliver completed host metadata", async () => {
  const f = await hostRecording();
  try {
    const paths = f.paths;
    expect(await Bun.file(join(f.directory, "response.json")).exists()).toBe(false);
    expect(await Bun.file(join(f.repository, "config", "sources.json")).exists()).toBe(false);
    const result = await deliverWorkflowMetadataHttp({ ...inputFor(f), currentRunFiles: JSON.stringify(paths) });
    expect(result).toMatchObject({ status: "landed", paths, files: paths.length });
    expect((await fixtureGit(f.origin, ["--git-dir", f.origin,
      "diff-tree", "--no-commit-id", "--name-only", "-r", "main"])).split("\n"))
      .toEqual(paths.map(path => `state/${path}`));
    await assertReleased(f.inputs.settings.listener.port);
  } finally { await f.close(); }
});

test("an occupied port cannot reuse an earlier successful receipt or stop another listener", async () => {
  const f = await hostRecording();
  try {
    const delivered = await deliverWorkflowMetadataHttp(inputFor(f));
    let requests = 0;
    const occupied = Bun.serve({
      hostname: "127.0.0.1", port: f.inputs.settings.listener.port,
      fetch() { requests++; return new Response("Unrelated listener"); },
    });
    try {
      await expect(deliverWorkflowMetadataHttp(inputFor(f))).rejects.toThrow("could not bind");
      expect(requests).toBe(0);
      expect((await fetch(`http://127.0.0.1:${occupied.port}`)).status).toBe(200);
      expect(MetadataDeliveryResultSchema.parse(await Bun.file(join(f.directory, "delivery-result.json")).json()))
        .toEqual({ status: "failed", commit: null, files: f.paths.length, paths: f.paths });
    } finally { await occupied.stop(true); }
    expect(await fixtureGit(f.origin, ["--git-dir", f.origin, "rev-parse", "main"])).toBe(delivered.commit!);
    await assertReleased(f.inputs.settings.listener.port);
  } finally { await f.close(); }
});

test("expired delivery readiness reaps the child without starting Git delivery", async () => {
  const f = await publicationGitRecording();
  try {
    const path = join(f.repository, "config", "feed-ingest-plan-service.json");
    const settings = ServiceSettingsSchema.parse(await Bun.file(path).json());
    settings.supervision.readiness_timeout_ms = 1;
    await writeFile(path, JSON.stringify(settings));
    await expect(deliverWorkflowMetadataHttp(inputFor(f))).rejects.toThrow("SAFE_PERSIST_READY_TIMEOUT");
    expect(await fixtureGit(f.origin, ["--git-dir", f.origin, "rev-parse", "main"])).toBe(f.head);
    await assertReleased(f.inputs.settings.listener.port);
  } finally { await f.close(); }
});

test("cancelled HTTP startup creates no Git delivery and leaves no listener", async () => {
  const f = await publicationGitRecording();
  try {
    const cancellation = new AbortController();
    cancellation.abort(new Error("Recorded delivery cancellation"));
    await expect(deliverWorkflowMetadataHttp(inputFor(f), { signal: cancellation.signal }))
      .rejects.toThrow("Recorded delivery cancellation");
    expect(await fixtureGit(f.origin, ["--git-dir", f.origin, "rev-parse", "main"])).toBe(f.head);
    expect(MetadataDeliveryResultSchema.parse(await Bun.file(join(f.directory, "delivery-result.json")).json()).status).toBe("failed");
    await assertReleased(f.inputs.settings.listener.port);
  } finally { await f.close(); }
});

test("cancellation during a real refused Git push reaps the delivery child and preserves finalization recovery", async () => {
  const f = await publicationRecording();
  const cancellation = new AbortController();
  let pending: ReturnType<typeof finalizeRunOutput> | undefined;
  let gitPid: number | undefined;
  try {
    const settingsPath = join(f.repository, "config", "feed-ingest-plan-service.json");
    const settings = ServiceSettingsSchema.parse(await Bun.file(settingsPath).json());
    settings.supervision.shutdown_timeout_ms = 200;
    await writeFile(settingsPath, JSON.stringify(settings));
    await writeFile(join(f.repository, "config", "feed-ingest-plan.json"), JSON.stringify(f.inputs.harvest.config));
    const retryPath = join(f.repository, "config", "push-retry.json");
    const retry = await Bun.file(retryPath).json();
    retry.deadline_seconds.default = 10;
    await writeFile(retryPath, JSON.stringify(retry));
    const marker = join(f.repository, ".git", "delivery-hook-started");
    await writeFile(join(f.repository, ".git", "hooks", "pre-push"), [
      "#!/bin/sh", "set -eu", 'printf \'%s\' "$PPID" > .git/delivery-hook-started',
      "sleep 2", "exit 1", "",
    ].join("\n"), { mode: 0o755 });
    pending = finalizeRunOutput({
      ...inputFor(f), cancelled: false, signal: cancellation.signal,
      outputPath: join(f.directory, "outputs"), summaryPath: join(f.directory, "summary.md"),
    });
    void pending.catch(() => {});
    const deadline = AbortSignal.timeout(settings.supervision.readiness_timeout_ms);
    const ready = await waitForHealth(settings.listener.port, deadline);
    while (!await Bun.file(marker).exists()) {
      deadline.throwIfAborted();
      await Bun.sleep(10);
    }
    gitPid = Number(await Bun.file(marker).text());
    expect(Number.isSafeInteger(gitPid) && gitPid > 0).toBe(true);
    cancellation.abort(new Error("Recorded cancellation during delivery"));
    await expect(pending).rejects.toThrow("Run finalization failed");
    expect(() => process.kill(ready.pid, 0)).toThrow();
    await assertReleased(settings.listener.port);
    await waitForExit(gitPid, AbortSignal.timeout(5000));
    expect(await fixtureGit(f.origin, ["--git-dir", f.origin, "rev-parse", "main"])).toBe(f.head);
    expect(MetadataDeliveryResultSchema.parse(await Bun.file(join(f.directory, "delivery-result.json")).json()).status).toBe("failed");
    expect(await Bun.file(join(f.directory, "artifacts", "700-3-report.md")).exists()).toBe(true);
    expect(await Bun.file(join(f.directory, "artifacts", "uncommitted-metadata-700-3", "current-run-files.json")).json())
      .toEqual(f.paths);
    expect(await readFile(join(f.directory, "outputs"), "utf8")).toContain("artifact_directory<<");
  } finally {
    cancellation.abort();
    await pending?.catch(() => {});
    if (gitPid !== undefined) await waitForExit(gitPid, AbortSignal.timeout(5000));
    await f.close();
  }
});

test("the real delivery server exits on invalid startup and on its supervisor's pipe closure", async () => {
  const f = await publicationGitRecording();
  try {
    const settings = ServiceSettingsSchema.parse(await Bun.file(join(f.repository, "config", "feed-ingest-plan-service.json")).json());
    const startup = SafePersistHttpStartupSchema.parse({
      nonce: randomUUID(), settings, output_root: relative(f.repository, f.directory).replaceAll("\\", "/"),
      git_sha: f.identity.git_sha,
    });
    const invalid = Bun.spawn([process.execPath, serverEntry], {
      cwd: f.repository, stdin: "pipe", stdout: "pipe", stderr: "pipe",
    });
    invalid.stdin.write(`${JSON.stringify({ ...startup, extra: true })}\n`);
    await invalid.stdin.flush();
    const [output, , code] = await Promise.all([
      new Response(invalid.stdout).text(), new Response(invalid.stderr).text(), invalid.exited,
    ]);
    expect(code).toBe(2);
    expect(SafePersistHttpStartupFailureSchema.parse(JSON.parse(output)).code).toBe("SAFE_PERSIST_STARTUP_FAILED");
    expect(() => process.kill(invalid.pid, 0)).toThrow();
    await assertReleased(settings.listener.port);

    const child = Bun.spawn([process.execPath, serverEntry], {
      cwd: f.repository, stdin: "pipe", stdout: "pipe", stderr: "pipe",
    });
    const outputRead = new Response(child.stdout).text();
    const errorsRead = new Response(child.stderr).text();
    try {
      child.stdin.write(`${JSON.stringify(startup)}\n`);
      await child.stdin.flush();
      const ready = await waitForHealth(settings.listener.port, AbortSignal.timeout(settings.supervision.readiness_timeout_ms));
      expect(ready).toMatchObject({ nonce: startup.nonce, pid: child.pid });
      expect(ready.pid).not.toBe(process.pid);
      child.stdin.end();
      expect(await child.exited).toBe(0);
      expect(SafePersistHttpReadySchema.parse(JSON.parse(await outputRead))).toEqual(ready);
      expect(await errorsRead).toBe("");
      expect(() => process.kill(child.pid, 0)).toThrow();
      await assertReleased(settings.listener.port);
    } finally {
      if (child.exitCode === null) { child.kill("SIGKILL"); await child.exited; }
      await Promise.all([outputRead, errorsRead]);
    }
  } finally { await f.close(); }
});
