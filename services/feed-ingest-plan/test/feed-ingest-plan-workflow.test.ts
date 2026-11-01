/** Does the manual workflow keep current history bounded and selected text out of delivered metadata? */
import { expect, test } from "bun:test";
import { copyFile, mkdir, mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import {
  COMPACT_INDEX_VERSION, CompactIndexSchema,
  FeedHealthStateRowContract, FeedHealthStateRowSchema, FeedIngestConfigSchema, PUBLICATION_INVENTORY_VERSION,
} from "../../../packages/common-contracts/src/index";
import { persistLedger } from "../../../packages/ledger-file-writer/src/index";
import { plannerRecordings } from "../../../packages/ledger-file-writer/test/planner-recordings";
import { PlanRequestSchema } from "../src/api/plan-request";
import { ServiceSettingsSchema } from "../src/config/service-settings";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { LedgerHistoryReadError } from "../src/read-ledger-history/ledger-history-error";
import { requiredUtcDays } from "../src/utc-instant";
import { resolveHealthDays } from "../src/read-ledger-history/resolve-health-days";
import { preparePlannerWorkflow, readWorkflowRequest } from "../scripts/feed-ingest-plan-workflow-inputs";
import { completeHistoryDayInputs, historyIndexPaths, resolveHistoryInventory } from "../scripts/feed-ingest-plan-outputs";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { recordedPlannerProcess } from "./planner-process-recordings";

const root = fileURLToPath(new URL("../../../", import.meta.url));

test("workflow preparation, supervised missing-history refusal, reports and output identity work without Git", async () => {
  const fixture = await recordedPlannerProcess();
  try {
    await copyFile(new URL("../../../config/host-fingerprints.json", import.meta.url),
      join(fixture.directory, "config", "host-fingerprints.json"));
    await writeFile(join(fixture.directory, "config", "sources.json"),
      JSON.stringify({ feeds: [], retired: [], publishers: [] }));
    const script = [
      'import assert from "node:assert/strict";',
      'import { join } from "node:path";',
      `import { preparePlannerWorkflow } from ${JSON.stringify(new URL("../scripts/feed-ingest-plan-workflow-inputs.ts", import.meta.url).href)};`,
      `import { invokePlannerHttp } from ${JSON.stringify(new URL("../scripts/feed-ingest-plan-supervisor.ts", import.meta.url).href)};`,
      `import { readWorkflowDeliveryContext } from ${JSON.stringify(new URL("../scripts/feed-ingest-plan-current-files.ts", import.meta.url).href)};`,
      `import { writeWorkflowReport } from ${JSON.stringify(new URL("../scripts/feed-ingest-plan-report.ts", import.meta.url).href)};`,
      `import { prepareWorkflowArtifacts } from ${JSON.stringify(new URL("../scripts/feed-ingest-plan-artifacts.ts", import.meta.url).href)};`,
      'assert.equal(Bun.which("git"), null);',
      'const controls = JSON.parse(await Bun.stdin.text());',
      'const prepared = await preparePlannerWorkflow(process.cwd(), controls.environment);',
      'const result = await invokePlannerHttp(prepared.inputs, prepared.startup, prepared.request, prepared.directory, { serverEntry: controls.serverEntry });',
      'assert.equal(result.summary.planning_complete, false);',
      'assert.equal(result.summary.status, "failed");',
      'assert.equal(result.summary.failure_code, "HISTORY_WINDOW_UNAVAILABLE");',
      'const input = { root: prepared.root, directory: prepared.directory, runNumber: controls.environment.GITHUB_RUN_ID, attempt: 3, gitSha: controls.environment.GITHUB_SHA, summaryPath: join(prepared.directory, "job-summary.md") };',
      'const context = await readWorkflowDeliveryContext(input);',
      'assert.equal(context.identity.git_sha, input.gitSha);',
      'await assert.rejects(readWorkflowDeliveryContext({ ...input, gitSha: "b".repeat(40) }));',
      'await writeWorkflowReport(input);',
      'const artifacts = await prepareWorkflowArtifacts(input);',
      'assert.equal(artifacts.artifact_directory, "artifacts");',
      'assert.equal(Bun.which("git"), null);',
      'console.log(JSON.stringify({ git_unavailable: true, startup_and_http: true, missing_history_refused: true, supplied_identity: true, report_and_artifacts: true }));',
    ].join("\n");
    const child = Bun.spawn([process.execPath, "-e", script], {
      cwd: fixture.directory, env: { ...process.env, PATH: "", Path: "" },
      stdin: new Blob([JSON.stringify({
        environment: {
          RUNNER_TEMP: join(fixture.directory, "runner"),
          GITHUB_OUTPUT: join(fixture.directory, "workflow-outputs"),
          GITHUB_RUN_ID: "700", GITHUB_RUN_ATTEMPT: "3", GITHUB_SHA: fixture.runtime.git_sha,
        },
        serverEntry: fixture.serverEntry,
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
      git_unavailable: true, startup_and_http: true, missing_history_refused: true,
      supplied_identity: true, report_and_artifacts: true,
    });
  } finally { await fixture.close(); }
});

const StepSchema = z.object({
  id: z.string().optional(), name: z.string().optional(), run: z.string().optional(), uses: z.string().optional(),
  if: z.string().optional(), "continue-on-error": z.boolean().optional(),
  env: z.record(z.string(), z.string()).optional(),
  with: z.record(z.string(), z.union([z.string(), z.boolean(), z.number().finite()])).optional(),
});
const WorkflowSchema = z.object({
  on: z.strictObject({ workflow_dispatch: z.object({ inputs: z.record(z.string(), z.object({
    default: z.union([z.string(), z.boolean()]), type: z.string(), required: z.boolean(), description: z.string(),
    options: z.array(z.string()).optional(),
  })) }) }),
  permissions: z.record(z.string(), z.string()),
  jobs: z.object({ "isolated-plan": z.object({ "timeout-minutes": z.number(), steps: z.array(StepSchema) }) }),
});
async function workflow() {
  const text = await readFile(join(root, ".github", "workflows", "feed-ingest-plan-test.yml"), "utf8");
  const parsed = WorkflowSchema.parse(Bun.YAML.parse(text));
  return { text, parsed, steps: parsed.jobs["isolated-plan"].steps };
}

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

test("manual controls exercise the planner API and keep only required outputs", async () => {
  const { text, parsed, steps } = await workflow();
  expect(parsed.permissions).toEqual({ contents: "write" });
  expect(parsed.jobs["isolated-plan"]["timeout-minutes"]).toBe(360);
  const controls = parsed.on.workflow_dispatch.inputs;
  expect(Object.keys(controls)).toEqual([
    "article_limit", "shards", "institutional_age_hours", "trade_press_age_hours", "community_age_hours", "partition_strategy",
    "dump_raw_document_contents", "write_report",
  ]);
  for (const [field, description] of [
    ["institutional_age_hours", "Institutional sources - article age windows (hours)"],
    ["trade_press_age_hours", "Trade press - article age windows (hours)"],
    ["community_age_hours", "Community sources - article age windows (hours)"],
  ] as const) {
    expect(controls[field]!.description).toBe(`${description}; increasing comma-separated steps; blank uses configuration`);
    expect(controls[field]!.default).toBe("");
    expect(controls[field]!.required).toBe(false);
  }
  const config = FeedIngestConfigSchema.parse(await Bun.file(join(root, "config", "feed-ingest-plan.json")).json());
  for (const [field, value] of Object.entries({
    article_limit: config.curate_articles.article_limit,
    shards: config.partition.default_shards, partition_strategy: config.partition.default_strategy,
  })) expect(controls[field]!.default).toBe(String(value));
  expect(controls.partition_strategy!.options).toEqual(PlanRequestSchema.shape.partition_strategy.unwrap().options);
  const serviceManifest = await Bun.file(join(root, "services", "feed-ingest-plan", "package.json")).json();
  expect(serviceManifest.exports["./markdown"]).toBe("./src/reporting/index.ts");
  const plan = steps.find(step => step.id === "plan")!;
  expect(plan.run).toBe("bun run services/feed-ingest-plan/scripts/run-feed-ingest-plan.ts");
  expect(plan.env).toEqual({
    ARTICLE_LIMIT: "${{ inputs.article_limit }}",
    SHARDS: "${{ inputs.shards }}", PARTITION_STRATEGY: "${{ inputs.partition_strategy }}",
    INSTITUTIONAL_AGE_HOURS: "${{ inputs.institutional_age_hours }}",
    TRADE_PRESS_AGE_HOURS: "${{ inputs.trade_press_age_hours }}",
    COMMUNITY_AGE_HOURS: "${{ inputs.community_age_hours }}",
    DUMP_RAW_DOCUMENT_CONTENTS: "${{ inputs.dump_raw_document_contents }}",
  });
  expect(plan.run).not.toContain("${{");
  const closing = steps.slice(steps.indexOf(plan) + 1);
  expect(closing).toHaveLength(7);
  const [cancellation, commit, report, finalize, upload, , finish] = closing;
  expect(controls.write_report).toMatchObject({ default: true, type: "boolean", required: false });
  expect(commit?.id).toBe("commit");
  expect(commit?.if).toBe("${{ always() }}");
  expect(commit?.run).toBe("bun run services/feed-ingest-plan/scripts/finalize-run-output.ts");
  expect(commit?.env).toEqual({
    FINALIZATION_OPERATION: "commit-ledgers",
    CURRENT_RUN_FILES: "${{ steps.plan.outputs.current_run_files }}",
    RUN_CANCELLED: "${{ steps.cancellation.outputs.cancelled == 'true' }}",
  });
  expect(report?.id).toBe("report");
  expect(report?.if).toBe("${{ always() && inputs.write_report }}");
  expect(report?.run).toBe("bun run services/feed-ingest-plan/scripts/finalize-run-output.ts");
  expect(report?.env).toEqual({
    FINALIZATION_OPERATION: "write-report",
    RUN_CANCELLED: "${{ steps.cancellation.outputs.cancelled == 'true' }}",
    RUN_ID: "${{ steps.plan.outputs.run_id }}",
  });
  expect(cancellation?.id).toBe("cancellation");
  expect(cancellation?.if).toBe("${{ cancelled() }}");
  expect(cancellation?.run).toBe('echo "cancelled=true" >> "$GITHUB_OUTPUT"');
  expect(steps.flatMap(step => Object.values(step.env ?? {})).join("\n")).not.toContain("cancelled()");
  expect(finalize?.id).toBe("finalize");
  expect(finalize?.if).toContain("always()");
  expect(finalize?.env).toEqual({
    FINALIZATION_OPERATION: "prepare-artifacts",
    RUN_CANCELLED: "${{ steps.cancellation.outputs.cancelled == 'true' }}",
    DUMP_RAW_DOCUMENT_CONTENTS: "${{ inputs.dump_raw_document_contents }}",
    RUN_ID: "${{ steps.plan.outputs.run_id }}",
    REPORT_FILENAME: "${{ steps.report.outputs.report_filename }}",
  });
  expect(finalize?.run).toBe("bun run services/feed-ingest-plan/scripts/finalize-run-output.ts");
  expect(finalize?.run).not.toContain("git push");
  expect(upload?.id).toBe("upload");
  expect(upload?.uses).toBe("actions/upload-artifact@v7");
  expect(steps.filter(step => step.uses === upload?.uses)).toHaveLength(2);
  expect(upload?.with?.archive).not.toBe(false);
  expect(upload?.with?.name).toBe("collect-and-select-articles-${{ github.run_id }}-${{ github.run_attempt }}");
  expect(upload?.with?.path).toBe("${{ runner.temp }}/feed-ingest-plan/${{ steps.finalize.outputs.artifact_directory }}");
  expect(upload?.if).toContain("always()");
  expect(upload?.if).toContain("steps.finalize.outputs.artifact_directory != ''");
  expect(upload?.with?.["if-no-files-found"]).toBe("error");
  expect(upload?.with?.["include-hidden-files"]).toBe(false);
  expect(finish?.if).toContain("always()");
  expect(finish?.run).toBe("bun run services/feed-ingest-plan/scripts/finish-run-output.ts");
  expect(finish?.env).toEqual({
    COLLECTION_OUTCOME: "${{ steps.plan.outcome }}", PLANNING_COMPLETE: "${{ steps.plan.outputs.planning_complete }}",
    FINALIZATION_OUTCOME: "${{ steps.finalize.outcome }}", UPLOAD_OUTCOME: "${{ steps.upload.outcome }}",
    COMMIT_OUTCOME: "${{ steps.commit.outcome }}", REPORT_OUTCOME: "${{ steps.report.outcome }}",
    WRITE_REPORT: "${{ inputs.write_report }}",
    UPLOAD_ARTIFACT_ID: "${{ steps.upload.outputs.artifact-id }}",
    DUMP_RAW_DOCUMENT_CONTENTS: "${{ inputs.dump_raw_document_contents }}",
    RAW_DOCUMENT_CONTENTS: "${{ steps.finalize.outputs.raw_document_contents }}",
    RAW_UPLOAD_OUTCOME: "${{ steps.upload-raw-documents.outcome }}",
    RAW_UPLOAD_ARTIFACT_ID: "${{ steps.upload-raw-documents.outputs.artifact-id }}",
  });
  expect(text).toContain("/state/raw/feed-ingest-plan/");
  expect(text).toContain("/state/compact/feed-ingest-plan/");
  expect(steps.some(step => step.name === "Check isolated adapters")).toBe(false);
  expect(steps.some(step => step.name?.includes("native compatibility"))).toBe(false);
  const optional = steps.filter(step => step["continue-on-error"]);
  expect(optional).toHaveLength(0);
  expect(text).not.toContain("profile_machine_memory");
  expect(text).not.toContain("services/host-probes");
  expect(text).not.toContain("runtime.log");
  expect(text).not.toContain("delivery.log");
  expect(text).not.toContain("audited_complete");
  expect(text).not.toContain("persist-dispatches");
  expect(text).not.toContain(".github/scripts/");
  const ci = z.object({ jobs: z.record(z.string(), z.object({ steps: z.array(StepSchema).optional() })) })
    .parse(Bun.YAML.parse(await readFile(join(root, ".github", "workflows", "ci.yml"), "utf8")));
  const plannerChecks = Object.values(ci.jobs).flatMap(job => job.steps ?? []);
  const plannerTest = plannerChecks.find(step => step.name === "TypeScript feed planner and native audit evidence")!;
  expect(plannerTest.run).toContain("bun run check");
  expect(plannerTest.run).toContain("bun run test");
  for (const name of ["site", "browser"]) {
    const steps = ci.jobs[name]!.steps ?? [];
    expect(steps.some(step => step.uses === "./.github/actions/publication-runtime")).toBe(true);
  }
});

test("planner configuration refuses retired acquisition controls", async () => {
  const settings = ServiceSettingsSchema.parse(await Bun.file(join(root, "config", "feed-ingest-plan-service.json")).json());
  expect(ServiceSettingsSchema.safeParse({
    ...settings, inputs: { ...settings.inputs, digest_root: "frontend/public/digest" },
  }).success).toBe(false);
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
  expect(JSON.parse(errors)).toEqual({ event: "planner_workflow_failed", code: "INVALID_INPUT" });
  expect(errors).not.toContain("injected");
});

test("the initial workflow checkout includes runtime code and every registered saved input", async () => {
  const { steps } = await workflow();
  expect(steps.filter(step => step.uses?.startsWith("actions/checkout@"))).toHaveLength(1);
  const selection = steps.find(step => step.uses?.startsWith("actions/checkout@"))!.with?.["sparse-checkout"];
  if (typeof selection !== "string") throw new Error("Expected a named sparse selection");
  expect(selection).not.toContain("/services/feed-ingest-plan/test/");
  expect(selection).not.toContain("/services/host-probes/");
  expect(selection).not.toContain("/tests/");
  const inputs = await loadPlanInputs(root);
  const entries = selection.trim().split("\n").map(value => value.trim());
  for (const registration of Object.values(inputs.registrations)) {
    for (const tier of ["raw", "compact"]) {
      const path = `/state/${tier}/${registration.prefix.join("/")}/`;
      expect(entries.some(entry => entry.endsWith("/") && path.startsWith(entry)), path).toBe(true);
    }
  }
  const required = new Set([
    "services/feed-ingest-plan/package.json",
    "services/feed-ingest-plan/bun.lock",
    "services/feed-ingest-plan/scripts/run-feed-ingest-plan.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-http-client.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-workflow-inputs.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-supervisor.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-server.ts",
    "services/feed-ingest-plan/scripts/http-child-lifetime.ts",
    "services/feed-ingest-plan/scripts/safe-persist-http-api.ts",
    "services/feed-ingest-plan/scripts/safe-persist-http-client.ts",
    "services/feed-ingest-plan/scripts/safe-persist-http-server.ts",
    "services/feed-ingest-plan/src/config/planner-startup.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-deliver.ts",
    "services/feed-ingest-plan/scripts/finalize-run-output.ts",
    "services/feed-ingest-plan/scripts/finish-run-output.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-delivery-result.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-current-files.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-host-fingerprint.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-metadata.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-host-verification.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-verification.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-artifacts.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-report.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-policy-report.ts",
    "services/feed-ingest-plan/src/website-group.ts",
    "services/feed-ingest-plan/src/config/service-settings.ts",
    "services/feed-ingest-plan/src/reporting/index.ts",
    "services/feed-ingest-plan/src/reporting/plan-markdown.ts",
    "services/host-fingerprints/package.json",
    "services/host-fingerprints/bun.lock",
    "services/host-fingerprints/src/api/local-fingerprint.ts",
    "config/feed-ingest-plan-service.json",
    "config/feed-ingest-plan.json",
    "config/taxonomy.json",
    "config/sources.json",
    "config/idhazh.json",
    "config/ledgers.json",
    "config/host-fingerprints.json",
    "config/data-delivery.json",
    "config/push-retry.json",
    "packages/common-contracts/package.json",
    "packages/common-contracts/bun.lock",
    "packages/common-contracts/src/index.ts",
    "packages/data-delivery/package.json",
    "packages/data-delivery/bun.lock",
    "packages/data-delivery/src/index.ts",
    "packages/data-delivery/src/safe-persist-data.ts",
    "packages/ledger-file-writer/package.json",
    "packages/ledger-file-writer/bun.lock",
    "packages/ledger-file-writer/src/index.ts",
    "frontend/public/publication.json",
  ]);
  for (const entry of selection.trim().split("\n").map(value => value.trim())) {
    if (!/^\/[\w./-]+$/.test(entry) || entry.split("/").includes("..")) {
      throw new Error("Sparse input must be a literal rooted name");
    }
    const path = entry.slice(1);
    for (const name of required) {
      if (entry.endsWith("/") ? name.startsWith(path) : path === name) {
        expect((await stat(join(root, ...name.split("/")))).isFile()).toBe(true);
        required.delete(name);
      }
    }
  }
  expect([...required], "Every required adapter and test input must be named in the checkout").toEqual([]);
});
