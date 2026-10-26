/** Does the workflow use the local host API and refuse evidence that does not match its file? */
import { expect, test } from "bun:test";
import { copyFile, mkdir, readFile, stat, symlink, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { dirname, join } from "node:path";
import { fixture } from "../../host-fingerprints/test/fixture";
import { captureLocalFingerprint } from "../../host-fingerprints/src/api/local-fingerprint";
import { serveFingerprints } from "../../host-fingerprints/src/api/server";
import { observeWorkflowResources, WorkflowResourcesSchema } from "../scripts/feed-ingest-plan-workflow-resources";
import { collectWorkflowFiles } from "../scripts/feed-ingest-plan-current-files";
import { hostWriter } from "../scripts/feed-ingest-plan-metadata";
import { verifyHostFingerprint } from "../scripts/feed-ingest-plan-host-verification";
import { formatUnavailableExecutionReport } from "../scripts/feed-ingest-plan-report";
import { formatResourceSummary } from "../scripts/feed-ingest-plan-resource-summary";
import { prepareWorkflowArtifacts } from "../scripts/feed-ingest-plan-artifacts";
import { metadataRegistrations, recordedWorkflowHost } from "./host-recordings";

const identity = { run_id: "2026-10-21-700", attempt: 1, git_sha: "a".repeat(40) };

async function reservePort() {
  const socket = createServer();
  await new Promise<void>(resolve => socket.listen(0, "127.0.0.1", resolve));
  const address = socket.address();
  if (address === null || typeof address === "string") throw new Error("Expected a real loopback TCP port");
  await new Promise<void>((resolve, reject) => socket.close(error => error ? reject(error) : resolve()));
  return address.port;
}

test("real API receipts survive a missing planner result and keep byte-valued cache storage", async () => {
  const f = await fixture();
  try {
    const directory = join(f.directory, "evidence");
    const host = await recordedWorkflowHost(directory, identity);
    const paths = await verifyHostFingerprint(join(directory, "state"), host.response, host.registrations, identity);
    expect(paths).toEqual(host.response.files.map(file => file.path));
    const completed = await collectWorkflowFiles({ root: f.directory, directory, identity, registrations: host.registrations });
    expect(completed.failures).toEqual([]);
    expect(completed.response).toBeUndefined();
    expect(completed.paths).toEqual(paths);
    const before = await readFile(join(directory, "state", paths[0]!));
    const report = formatUnavailableExecutionReport({ resources: host.resources });
    expect(report.summary).toContain("Planning result unavailable");
    const resourceNotice = formatResourceSummary(host.resources, undefined, false).notice;
    expect(resourceNotice).toContain("L3 48.00 MiB");
    expect(resourceNotice).toContain("total RAM 16383.750 MiB");
    expect(host.response.row.l3_cache_bytes).toBe(50_331_648);
    expect(host.response.row.machine_memory_total_mib).toBe(16_383.75);
    expect(host.response.row).toMatchObject({ job_seconds: null, model_load_ms: null,
      server_prompt_tokens: null, server_prompt_seconds: null });
    expect(Bun.markdown.html(report.summary)).toContain("<table>");
    const retained = await prepareWorkflowArtifacts({ root: f.directory, directory,
      runNumber: "700", attempt: 1, identity, registrations: host.registrations });
    expect(await Bun.file(join(directory, retained.metadata_recovery!, "current-run-files.json")).json()).toEqual(paths);
    expect(await readFile(join(directory, retained.metadata_recovery!, paths[0]!))).toEqual(before);
    expect(await readFile(join(directory, "state", paths[0]!))).toEqual(before);
    expect(JSON.stringify(host.resources)).not.toContain("article_text");
    await expect(stat(join(directory, "state", dirname(paths[0]!), "index.json"))).rejects.toMatchObject({ code: "ENOENT" });
  } finally { await f.cleanup(); }
});

test("workflow collection retains HTTP files while optional live profiling still records independently", async () => {
  const f = await fixture();
  try {
    const directory = join(f.directory, "evidence");
    await mkdir(join(f.directory, "config"), { recursive: true });
    await mkdir(directory);
    const settings = await Bun.file(new URL("../../../config/idhazh.json", import.meta.url)).json();
    await writeFile(join(f.directory, "config", "idhazh.json"), JSON.stringify({ ...settings, observability: {
      ...settings.observability, host_telemetry_enabled: true, host_fingerprint: true,
      host_fingerprint_placement_enabled: false, host_fingerprint_bandwidth_jobs: [],
    } }));
    const config = { ...f.config, listen_port: await reservePort() };
    await writeFile(join(f.directory, "config", "host-fingerprints.json"), JSON.stringify(config));
    for (const name of ["ledgers.json", "host-probes.json"]) {
      await copyFile(new URL(`../../../config/${name}`, import.meta.url), join(f.directory, "config", name));
    }
    const session = await observeWorkflowResources({
      root: f.directory, directory, stateRoot: join(directory, "state"), profileRequested: true,
      gitSha: identity.git_sha, attempt: identity.attempt, identity: {
        run_id: identity.run_id, pipeline_name: "feed-ingest-plan", task_name: "planner-http-request",
        correlation_id: crypto.randomUUID(), request_id: crypto.randomUUID(),
      },
    });
    await session.close("error");
    const saved = WorkflowResourcesSchema.parse(await Bun.file(join(directory, "resources.json")).json());
    expect(saved.host.status).toBe("recorded");
    expect(saved.profile_requested).toBe(true);
    expect(saved.profile.status).toBe("recorded");
    if (saved.host.status !== "recorded" || saved.profile.status !== "recorded") throw new Error("Both independent observations must be recorded");
    expect(saved.profile.value.outcome).toBe("error");
    expect(saved.profile.value.identity.task_name).toBe("planner-http-request");
    expect(saved.host.row.task_name).toBe("isolated-plan");
    expect(saved.host.files).toHaveLength(1);
    const server = serveFingerprints(config, f.settings, { outputRoot: join(f.directory, "must-not-write") });
    await server.stop(true);
  } finally { await f.cleanup(); }
});

test("configured off does not start a listener, read missing host config, or create state", async () => {
  const f = await fixture();
  try {
    await mkdir(join(f.directory, "config"));
    const directory = join(f.directory, "evidence");
    await mkdir(directory);
    const settings = await Bun.file(new URL("../../../config/idhazh.json", import.meta.url)).json();
    for (const key of ["host_telemetry_enabled", "host_fingerprint"] as const) {
      await writeFile(join(f.directory, "config", "idhazh.json"), JSON.stringify({ ...settings,
        observability: { ...settings.observability, host_telemetry_enabled: true, host_fingerprint: true, [key]: false } }));
      const session = await observeWorkflowResources({
        root: f.directory, directory, stateRoot: join(directory, "state"), profileRequested: false,
        gitSha: identity.git_sha, attempt: identity.attempt, identity: {
          run_id: identity.run_id, pipeline_name: "feed-ingest-plan", task_name: "planner-http-request",
          correlation_id: crypto.randomUUID(), request_id: crypto.randomUUID(),
        },
      });
      await session.close("success");
      expect(session.evidence.host).toEqual({ status: "disabled", reason: `observability.${key}=false` });
      const completed = await collectWorkflowFiles({ root: f.directory, directory, identity, registrations: await metadataRegistrations() });
      expect(completed.paths).toEqual([]);
      expect(completed.failures).toEqual([]);
      await expect(stat(join(directory, "state"))).rejects.toMatchObject({ code: "ENOENT" });
    }
    f.settings.observability.host_fingerprint = false;
    const response = await captureLocalFingerprint({ date: "2026-10-21", writer: hostWriter(identity) },
      { ...f.config, listen_port: 0 }, f.settings, { outputRoot: join(directory, "disabled"), registryPath: "missing" });
    expect(response).toEqual({ status: "disabled", row: null, files: [], unavailable: {} });
    await expect(stat(join(directory, "disabled"))).rejects.toMatchObject({ code: "ENOENT" });
  } finally { await f.cleanup(); }
});

test("native file validation refuses foreign receipts, provenance, altered rows and junction escapes", async () => {
  const f = await fixture();
  try {
    const directory = join(f.directory, "evidence");
    const host = await recordedWorkflowHost(directory, identity);
    const state = join(directory, "state");
    const file = host.response.files[0]!;
    for (const altered of [
      { ...file, row_count: 2 }, { ...file, content_sha256: "0".repeat(64) },
      { ...file, unit_id: "00000000-0000-5000-8000-000000000000" },
      { ...file, covers: "2026-10-22" }, { ...file, path: `../${file.path}` },
    ]) await expect(verifyHostFingerprint(state, { ...host.response, files: [altered] },
      host.registrations, identity)).rejects.toThrow();
    await expect(verifyHostFingerprint(state, { ...host.response, row: { ...host.response.row,
      machine_memory_total_mib: host.response.row.machine_memory_total_mib! + 1 } }, host.registrations, identity)).rejects.toThrow("receipt or row");
    await expect(verifyHostFingerprint(state, host.response, host.registrations,
      { ...identity, attempt: 2 })).rejects.toThrow("execution identity");
    await expect(verifyHostFingerprint(state, host.response, host.registrations,
      { ...identity, git_sha: "b".repeat(40) })).rejects.toThrow("execution identity");
    await expect(verifyHostFingerprint(state, host.response, { ...host.registrations,
      "host-fingerprint": { ...host.registrations["host-fingerprint"], prefix: ["other-host"] } }, identity)).rejects.toThrow("exact current");
    const escaped = join(f.directory, "escaped");
    const day = dirname(file.path);
    await mkdir(dirname(join(escaped, day)), { recursive: true });
    await symlink(join(state, day), join(escaped, day), "junction");
    await expect(verifyHostFingerprint(escaped, host.response, host.registrations, identity)).rejects.toThrow("symlink");
  } finally { await f.cleanup(); }
});

test("HTTP write failures and nonlocal listeners cannot return a successful host observation", async () => {
  const f = await fixture();
  try {
    const state = join(f.directory, "blocked");
    await writeFile(state, "Preserve this file");
    await expect(captureLocalFingerprint({ date: "2026-10-21", writer: hostWriter(identity) },
      { ...f.config, listen_port: 0 }, f.settings, { outputRoot: state, inspection: f.inspection })).rejects.toThrow("500");
    expect(await readFile(state, "utf8")).toBe("Preserve this file");
    await expect(captureLocalFingerprint(f.apiInput, { ...f.config, listen_host: "192.0.2.1" }, f.settings,
      { outputRoot: state })).rejects.toThrow("loopback");
    const directory = join(f.directory, "evidence");
    const host = await recordedWorkflowHost(directory, identity);
    const unavailable = formatResourceSummary({ ...host.resources,
      host: { status: "failed", reason: "Host persistence failed" } }, undefined, false);
    expect(unavailable.notice).toContain("failed (Host persistence failed)");
    expect(unavailable.notice).not.toContain("0.00 MiB");
  } finally { await f.cleanup(); }
});

test("the local HTTP boundary preserves task-selected copy work and unavailable hardware", async () => {
  const f = await fixture();
  try {
    const request = { date: "2026-10-21", writer: hostWriter(identity) };
    const options = { outputRoot: join(f.directory, "copy"), inspection: f.inspection };
    await writeFile(join(f.root, "sys", "devices", "system", "cpu", "cpu0", "cache", "index2", "size"), "1K");
    f.settings.observability.host_fingerprint_bandwidth_floor_mib = 1;
    f.settings.observability.host_fingerprint_bandwidth_jobs = [];
    const off = await captureLocalFingerprint(request, { ...f.config, listen_port: 0 }, f.settings, options);
    if (off.status !== "written") throw new Error("The copy-off HTTP capture must persist");
    expect(off.row.memcpy_probe_mib).toBe(0);
    expect(off.unavailable.memcpy_gib_s).toBe("configured_off");
    f.settings.observability.host_fingerprint_bandwidth_jobs = ["isolated-plan"];
    const on = await captureLocalFingerprint(request, { ...f.config, listen_port: 0 }, f.settings, options);
    if (on.status !== "written") throw new Error("The selected copy HTTP capture must persist");
    expect(on.row.memcpy_probe_mib).toBe(2);
    expect(on.row.memcpy_gib_s).toBeGreaterThan(0);
    const unsupported = await captureLocalFingerprint(request, { ...f.config, listen_port: 0 }, f.settings, {
      ...options, inspection: { platform: "win32" },
    });
    if (unsupported.status !== "written") throw new Error("Unavailable hardware is still a completed observation");
    expect(unsupported.row.l3_cache_bytes).toBeNull();
    expect(unsupported.row.machine_memory_total_mib).toBeNull();
    expect(unsupported.unavailable.machine_memory_total_mib).toBe("unsupported_platform");
    const report = formatResourceSummary({
      host_request: request, profile_requested: false, host: { ...unsupported, status: "recorded" },
      profile: { status: "disabled", reason: "profile_machine_memory=false" },
    }, undefined, false);
    expect(report.notice).toContain("L3 Unavailable");
    expect(report.notice).toContain("total RAM Unavailable");
    expect(report.notice).not.toContain("0.00 MiB");
  } finally { await f.cleanup(); }
});
