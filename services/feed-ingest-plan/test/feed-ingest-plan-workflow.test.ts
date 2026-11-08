/** Do planner input, history, delivery and report boundaries preserve their contracts? */
import { expect, test } from "bun:test";
import { copyFile, mkdir, mkdtemp, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { loadHonoSettings } from "@idhazh/serve-pipeline-apis/settings";
import {
  COMPACT_INDEX_VERSION, CompactIndexSchema,
  FeedHealthStateRowContract, FeedHealthStateRowSchema, PUBLICATION_INVENTORY_VERSION,
} from "../../../packages/common-contracts/src/index";
import { persistLedger } from "../../../packages/ledger-file-writer/src/index";
import { plannerRecordings } from "../../../packages/ledger-file-writer/test/planner-recordings";
import { ServiceSettingsSchema } from "../src/config/service-settings";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { LedgerHistoryReadError } from "../src/read-ledger-history/ledger-history-error";
import { requiredUtcDays } from "../src/utc-instant";
import { resolveHealthDays } from "../src/read-ledger-history/resolve-health-days";
import { preparePlannerWorkflow, readWorkflowRequest } from "../scripts/feed-ingest-plan-workflow-inputs";
import { completeHistoryDayInputs, historyIndexPaths, resolveHistoryInventory } from "../scripts/feed-ingest-plan-outputs";
import { recordedPlannerProcess } from "./planner-process-recordings";

const root = fileURLToPath(new URL("../../../", import.meta.url));

test("workflow preparation, supervised missing-history refusal, reports and output identity work without Git", async () => {
  const fixture = await recordedPlannerProcess();
  try {
    await copyFile(new URL("../../../config/host-fingerprints.json", import.meta.url),
      join(fixture.directory, "config", "host-fingerprints.json"));
    await writeFile(join(fixture.directory, "config", "sources.json"),
      JSON.stringify({ feeds: [], retired: [], publishers: [] }));
    const selected = await Bun.file(join(fixture.directory, "config", "idhazh.json")).json();
    selected.observability.host_telemetry_enabled = true;
    selected.observability.host_fingerprint = true;
    selected.observability.host_fingerprint_placement_enabled = false;
    selected.observability.host_fingerprint_bandwidth_jobs = [];
    await writeFile(join(fixture.directory, "config", "idhazh.json"), JSON.stringify(selected));
    const script = [
      'import assert from "node:assert/strict";',
      'import { join } from "node:path";',
      `import { readWorkflowDeliveryContext } from ${JSON.stringify(new URL("../scripts/feed-ingest-plan-current-files.ts", import.meta.url).href)};`,
      `import { writeWorkflowReport } from ${JSON.stringify(new URL("../scripts/feed-ingest-plan-report.ts", import.meta.url).href)};`,
      `import { prepareWorkflowArtifacts } from ${JSON.stringify(new URL("../scripts/feed-ingest-plan-artifacts.ts", import.meta.url).href)};`,
      'assert.equal(Bun.which("git"), null);',
      'const controls = JSON.parse(await Bun.stdin.text());',
      `const taskProgram = ${JSON.stringify(`import { runWorkflow } from ${JSON.stringify(new URL("../scripts/run-feed-ingest-plan.ts", import.meta.url).href)}; await runWorkflow(new AbortController().signal, { serverEntry: ${JSON.stringify(fixture.serverEntry)} });`)};`,
      'const task = Bun.spawn([process.execPath, "-e", taskProgram], { cwd: process.cwd(), env: { ...process.env, ...controls.environment }, stdout: "pipe", stderr: "pipe" });',
      'const [output, error, code] = await Promise.all([new Response(task.stdout).text(), new Response(task.stderr).text(), task.exited]);',
      'assert.equal(code, 2, output + error);',
      'const directory = join(controls.environment.RUNNER_TEMP, "feed-ingest-plan");',
      'const result = await Bun.file(join(directory, "response.json")).json();',
      'assert.equal(result.planning_complete, false);',
      'assert.equal(result.status, "failed");',
      'assert.equal(result.failure_code, "HISTORY_WINDOW_UNAVAILABLE");',
      'const host = await Bun.file(join(directory, "host-fingerprint.json")).json();',
      'assert.equal(host.host.status, "recorded");',
      'const server = await Bun.file(join(directory, "hono-server-planning.json")).json();',
      'assert.equal(server.startup, "ready");',
      'assert.equal(server.shutdown, "stopped");',
      'const input = { root: process.cwd(), directory, runNumber: controls.environment.GITHUB_RUN_ID, attempt: 3, gitSha: controls.environment.GITHUB_SHA, summaryPath: join(directory, "job-summary.md") };',
      'const context = await readWorkflowDeliveryContext(input);',
      'assert.equal(context.identity.git_sha, input.gitSha);',
      'await assert.rejects(readWorkflowDeliveryContext({ ...input, gitSha: "b".repeat(40) }));',
      'await writeWorkflowReport(input);',
      'const artifacts = await prepareWorkflowArtifacts(input);',
      'assert.equal(artifacts.artifact_directory, "artifacts");',
      'assert.equal(Bun.which("git"), null);',
      'console.log(JSON.stringify({ git_unavailable: true, startup_and_http: true, fingerprint_http: true, missing_history_refused: true, supplied_identity: true, report_and_artifacts: true }));',
    ].join("\n");
    const child = Bun.spawn([process.execPath, "-e", script], {
      cwd: fixture.directory, env: { ...process.env, PATH: "", Path: "" },
      stdin: new Blob([JSON.stringify({
        environment: {
          RUNNER_TEMP: join(fixture.directory, "runner"),
          GITHUB_OUTPUT: join(fixture.directory, "workflow-outputs"),
          GITHUB_RUN_ID: "700", GITHUB_RUN_ATTEMPT: "3", GITHUB_SHA: fixture.runtime.git_sha,
        },
      })]),
      stdout: "pipe", stderr: "pipe",
    });
    const [output, error, status] = await Promise.all([
      new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited,
    ]);
    expect(status, error).toBe(0);
    const result = output.trim().split("\n").at(-1);
    if (result === undefined) throw new Error("The workflow boundary child returned no oracle result");
    expect(JSON.parse(result)).toEqual({
      git_unavailable: true, startup_and_http: true, fingerprint_http: true, missing_history_refused: true,
      supplied_identity: true, report_and_artifacts: true,
    });
  } finally { await fixture.close(); }
});

test("workflow preparation validates dispatch data and requires execution controls before loading files", async () => {
  expect(readWorkflowRequest({ ARTICLE_LIMIT: "", SHARDS: "  " })).toEqual({ request: {}, policy_overrides: {} });
  expect(readWorkflowRequest({
    ARTICLE_LIMIT: "5", SHARDS: "2", PARTITION_STRATEGY: "round-robin",
  })).toEqual({ request: { article_limit: 5, shards: 2, partition_strategy: "round-robin" }, policy_overrides: {} });
  expect(() => readWorkflowRequest({ ARTICLE_LIMIT: "0" })).toThrow();
  expect(() => readWorkflowRequest({ PARTITION_STRATEGY: "unknown" })).toThrow();
  expect(readWorkflowRequest({ FRESHNESS_HOURS: "12" })).toEqual({ request: {}, policy_overrides: {} });
  await expect(preparePlannerWorkflow(root, {})).rejects.toThrow("Workflow execution controls are missing");
});

test("planner configuration refuses retired acquisition controls", async () => {
  const settings = ServiceSettingsSchema.parse(await Bun.file(join(root, "config", "feed-ingest-plan-service.json")).json());
  expect(ServiceSettingsSchema.safeParse({
    ...settings, inputs: { ...settings.inputs, digest_root: "frontend/public/digest" },
  }).success).toBe(false);
});

test("planner settings reject the shared supervision authority", async () => {
  const settings = ServiceSettingsSchema.parse(await Bun.file(join(root, "config", "feed-ingest-plan-service.json")).json());
  const server = await loadHonoSettings(root, "planning");
  expect(ServiceSettingsSchema.safeParse({ ...settings, supervision: server.supervision }).success).toBe(false);
});

test("bounded discovery history preserves covered-day membership and planner raw overlap", async () => {
  const discoveredDays = requiredUtcDays("2026-01-01T00:00:00Z", 2);
  expect(discoveredDays).toEqual(["2025-12-30", "2025-12-31", "2026-01-01"]);
  expect(completeHistoryDayInputs(["feed-ingest-plan", "discovered-articles"], discoveredDays, [], "discovered_days")).toHaveLength(3);
  expect(() => historyIndexPaths([".."], discoveredDays)).toThrow("prefix");
  const rawName = "01a1592e-c600-84d0-96e4-7bb01708ce01.parquet";
  for (const ledger of ["feed-health-state", "published"] as const) {
    const prefix = ledger === "published" ? ["published"] : ["feed-ingest-plan", ledger];
    const rawPath = `state/raw/${prefix.join("/")}/2026/01/01/${rawName}`;
    const compact = CompactIndexSchema.parse({ version: COMPACT_INDEX_VERSION, ledger, period: "monthly",
      entries: [{ covers: "2026-01", rows: 1, bytes: 20 }] });
    const inventory = resolveHistoryInventory({ ledger, prefix, days: ["2026-01-01"], compact: [compact], rawFiles: [rawPath] });
    expect(inventory).toContain(`state/compact/${prefix.join("/")}/monthly/2026/01.parquet`);
    expect(inventory.includes(`state/raw/${prefix.join("/")}/2026/01/01/${rawName}`)).toBe(ledger === "feed-health-state");
    expect(() => resolveHistoryInventory({ ledger, prefix, days: ["2026-01-01"], compact: [],
      rawFiles: ["state/raw/foreign/2026/01/01/member.parquet"] })).toThrow("outside");
  }
  const directory = await mkdtemp(join(tmpdir(), "planner-history-"));
  try {
    const registration = { name: "feed-health-state", family: "feed-ingest-plan", prefix: ["feed-ingest-plan", "feed-health-state"],
      grain: "raw-and-compact" as const, lifecycle_status: "active" as const };
    const ledgerSettings = { format: "parquet" as const, compression_raw: "snappy" as const, compression_compact: "zstd" as const };
    const entries: { root: string; path: string; bytes: number; items: number }[] = [];
    let monthPath = "";
    for (const day of ["2024-01-01", "2026-01-01"]) {
      const row = FeedHealthStateRowSchema.parse(plannerRecordings(day).find(value => value.name === "feed-health-state")!.row);
      const raw = await persistLedger({ ledger: registration.name, rowContract: FeedHealthStateRowContract,
        rows: [row], outputRoot: join(directory, "state"), registryEntry: registration, ledgerSettings,
        period: { tier: "raw", covers: day }, updatedAt: row.checked_at! });
      entries.push({ root: "state", path: raw.files[0]!.path, bytes: (await stat(join(directory, "state", raw.files[0]!.path))).size, items: 1 });
      if (day === "2024-01-01") {
        const monthly = await persistLedger({ ledger: registration.name, rowContract: FeedHealthStateRowContract,
          rows: [row], outputRoot: join(directory, "state"), registryEntry: registration, ledgerSettings,
          period: { tier: "compact", period: "monthly", covers: "2024-01", builtFrom: 1 }, updatedAt: row.checked_at! });
        monthPath = `state/${monthly.files[0]!.path}`;
        const index = join(directory, "state", "compact", ...registration.prefix, "index", "monthly.json");
        await mkdir(dirname(index), { recursive: true });
        await writeFile(index, JSON.stringify(CompactIndexSchema.parse({
          version: COMPACT_INDEX_VERSION, ledger: registration.name, period: "monthly",
          entries: [{ covers: "2024-01", rows: 1, bytes: (await stat(join(directory, monthPath))).size }],
        })));
      }
    }
    await mkdir(join(directory, "frontend", "public"), { recursive: true });
    await writeFile(join(directory, "frontend", "public", "publication.json"), JSON.stringify({ version: PUBLICATION_INVENTORY_VERSION, entries }));
    const stage = () => resolveHealthDays({
      ledger: "feed-health-state", prefix: registration.prefix, now: "2026-01-01T23:59:59Z",
      health_window_days: 2, request_report_closed_days: 7, period_limit: 3, authored: [],
      raw_files: async day => entries.filter(entry => entry.path.includes(`/${day.replaceAll("-", "/")}/`))
        .map(entry => `state/${entry.path}`),
      read: async path => {
        const file = Bun.file(join(directory, path));
        return await file.exists() ? file.json() : undefined;
      },
      read_period: async path => (await readPlannerParquet(join(directory, path), "feed-health-state", FeedHealthStateRowContract)).rows,
    });
    const first = await stage();
    expect(first.represented_days).toEqual(["2024-01-31", "2026-01-01"]);
    expect(first.files).toContain(monthPath);
    expect(first.files).not.toContain(`state/${entries[0]!.path}`);
    await writeFile(join(directory, monthPath), "invalid Parquet");
    const partial = await stage();
    expect(partial.notices).toContain("health_period_refused:2024-01");
    expect(partial.represented_days).toEqual(["2024-01-31", "2026-01-01"]);
    expect(partial.represented_days).toContain("2026-01-01");
    const inertIndex = join(directory, "state", "raw", ...registration.prefix, "2026", "01", "01", "index.json");
    await writeFile(inertIndex, JSON.stringify({ invalid: true }));
    expect((await stage()).notices).not.toContain("health_index_refused:2026-01-01");
    await expect(resolveHealthDays({
      ledger: "feed-health-state", prefix: registration.prefix, now: "2026-01-01T23:59:59Z",
      health_window_days: 2, request_report_closed_days: 7, period_limit: 3, authored: [],
      raw_files: async () => [],
      read: async () => { throw new TypeError("Unexpected implementation failure"); },
      read_period: async () => { throw new LedgerHistoryReadError("Not reached"); },
    })).rejects.toThrow("Unexpected implementation failure");
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test("hostile dispatch strings fail in the actual adapter before loading inputs or making requests", async () => {
  const child = Bun.spawn([process.execPath, join(root, "services", "feed-ingest-plan", "scripts", "run-feed-ingest-plan.ts")], {
    cwd: root, stdout: "pipe", stderr: "pipe",
    env: { ...Bun.env, ARTICLE_LIMIT: '24; throw new Error("injected")', SHARDS: "", PARTITION_STRATEGY: "" },
  });
  const [output, errors] = await Promise.all([new Response(child.stdout).text(), new Response(child.stderr).text()]);
  expect(await child.exited).toBe(2);
  expect(output).toBe("");
  expect(JSON.parse(errors)).toMatchObject({ event: "planner_workflow_failed", code: "INVALID_INPUT",
    failure: { error_type: "ZodError", safe_cause: "invalid-input" } });
  expect(errors).not.toContain("injected");
});
