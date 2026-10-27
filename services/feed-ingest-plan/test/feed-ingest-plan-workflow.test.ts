/** Does the manual workflow keep current history bounded and selected text out of delivered metadata? */
import { expect, test } from "bun:test";
import { mkdir, mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
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
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { LedgerHistoryReadError } from "../src/read-ledger-history/ledger-history-error";
import { requiredUtcDays } from "../src/utc-instant";
import { stageFeedHistory } from "../scripts/feed-ingest-plan-feed-history";
import { completeHistoryDayInputs, historyIndexPaths, resolveHistoryInventory, sparseCheckoutPath } from "../scripts/feed-ingest-plan-outputs";
import { loadConfig as loadProbeConfig } from "../../host-probes/src/config";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const StepSchema = z.object({
  id: z.string().optional(), name: z.string().optional(), run: z.string().optional(), uses: z.string().optional(),
  if: z.string().optional(), "continue-on-error": z.boolean().optional(),
  env: z.record(z.string(), z.string()).optional(),
  with: z.record(z.string(), z.union([z.string(), z.boolean(), z.number().finite()])).optional(),
});
const WorkflowSchema = z.object({
  on: z.strictObject({ workflow_dispatch: z.object({ inputs: z.record(z.string(), z.object({
    default: z.union([z.string(), z.boolean()]), type: z.string(), required: z.boolean(), options: z.array(z.string()).optional(),
  })) }) }),
  permissions: z.record(z.string(), z.string()),
  jobs: z.object({ "isolated-plan": z.object({ "timeout-minutes": z.number(), steps: z.array(StepSchema) }) }),
});
async function workflow() {
  const text = await readFile(join(root, ".github", "workflows", "feed-ingest-plan-test.yml"), "utf8");
  const parsed = WorkflowSchema.parse(Bun.YAML.parse(text));
  return { text, parsed, steps: parsed.jobs["isolated-plan"].steps };
}

test("manual controls deliver only current metadata and keep optional host tools independent", async () => {
  const { text, parsed, steps } = await workflow();
  expect(parsed.permissions).toEqual({ contents: "write" });
  expect(parsed.jobs["isolated-plan"]["timeout-minutes"]).toBe(360);
  const controls = parsed.on.workflow_dispatch.inputs;
  expect(Object.keys(controls)).toEqual(["freshness_hours", "article_limit", "shards", "partition_strategy", "profile_machine_memory"]);
  const config = FeedIngestConfigSchema.parse(await Bun.file(join(root, "config", "feed-ingest-plan.json")).json());
  for (const [field, value] of Object.entries({
    freshness_hours: config.curate_articles.feed_quality_tiers[0]!.ladder_hours[0]!, article_limit: config.curate_articles.article_limit,
    shards: config.partition.default_shards, partition_strategy: config.partition.default_strategy,
  })) expect(controls[field]!.default).toBe(String(value));
  expect(controls.partition_strategy!.options).toEqual(PlanRequestSchema.shape.partition_strategy.unwrap().options);
  expect(controls.profile_machine_memory!.default).toBe((await loadProbeConfig()).task_profile.machine_memory_enabled);
  const plan = steps.find(step => step.id === "plan")!;
  expect(plan.run).toContain("set -o pipefail");
  expect(plan.run).toContain('bun run services/feed-ingest-plan/scripts/feed-ingest-plan-http-proof.ts 2>&1 | tee "$RUNNER_TEMP/feed-ingest-plan/runtime.log"');
  expect(plan.env).toEqual({
    FRESHNESS_HOURS: "${{ inputs.freshness_hours }}", ARTICLE_LIMIT: "${{ inputs.article_limit }}",
    SHARDS: "${{ inputs.shards }}", PARTITION_STRATEGY: "${{ inputs.partition_strategy }}",
    PROFILE_MACHINE_MEMORY: "${{ inputs.profile_machine_memory }}",
  });
  expect(plan.run).not.toContain("${{");
  const delivery = steps.find(step => step.name === "Deliver exact current planner and host metadata")!;
  expect(delivery.if).toContain("!cancelled()");
  expect(delivery.if).toContain("current_run_files");
  expect(delivery.if).not.toContain("planning_complete");
  expect(delivery.run).toContain("set -o pipefail");
  expect(delivery.run).toContain("scripts/feed-ingest-plan-deliver.ts");
  expect(delivery.run).toContain('tee "$RUNNER_TEMP/feed-ingest-plan/delivery.log"');
  expect(delivery.run).not.toContain("git push");
  const textArtifact = steps.find(step => step.name === "Preserve selected text for the summarizer")!;
  expect(textArtifact.with?.path).toBe("${{ runner.temp }}/feed-ingest-plan/${{ steps.evidence.outputs.selected }}");
  const individual = steps.filter(step => step.uses === "actions/upload-artifact@v7" && step.with?.archive === false);
  expect(individual).toHaveLength(11);
  for (const artifact of individual) {
    expect(artifact.with?.name).toBeUndefined();
    expect(String(artifact.with?.path)).not.toMatch(/[\n*]/);
    expect(artifact.if).toContain("always()");
    expect(artifact.with?.["if-no-files-found"]).toBe("error");
  }
  const recovery = steps.find(step => step.name === "Preserve uncommitted metadata recovery only")!;
  expect(recovery.with?.name).toBe("uncommitted-metadata-recovery-${{ github.run_id }}-${{ github.run_attempt }}");
  expect(recovery.with?.path).toBe("${{ runner.temp }}/feed-ingest-plan/${{ steps.evidence.outputs.metadata_recovery }}");
  expect(steps.find(step => step.id === "evidence")?.if).toContain("always()");
  const report = steps.findIndex(step => step.name === "Write the public planner summary and grouped annotations");
  expect(report).toBeGreaterThan(steps.findIndex(step => step.name === "Run independent optional host proof"));
  expect(steps[report]?.run).toBe("bun run services/feed-ingest-plan/scripts/feed-ingest-plan-report.ts");
  expect(steps[report]?.if).toContain("always()");
  expect(text).not.toContain("/state/raw/feed-ingest-plan/");
  expect(steps.some(step => step.name === "Check isolated adapters")).toBe(true);
  expect(steps.some(step => step.name?.includes("native compatibility"))).toBe(false);
  const optional = steps.filter(step => step["continue-on-error"]);
  expect(optional).toHaveLength(2);
  expect(optional.every(step => step.if?.includes("inputs.profile_machine_memory"))).toBe(true);
  expect(steps.at(-1)?.env).toEqual({ PLANNING_COMPLETE: "${{ steps.plan.outputs.planning_complete }}" });
  expect(text).not.toContain("audited_complete");
  expect(text).not.toContain("persist-dispatches");
  expect(text).not.toContain(".github/scripts/");
  const ci = z.object({ jobs: z.object({
    site: z.object({ steps: z.array(StepSchema) }), browser: z.object({ steps: z.array(StepSchema) }),
  }) }).parse(Bun.YAML.parse(await readFile(join(root, ".github", "workflows", "ci.yml"), "utf8")));
  for (const job of [ci.jobs.site, ci.jobs.browser]) {
    expect(job.steps.some(step => step.uses === "oven-sh/setup-bun@v2")).toBe(true);
    const install = job.steps.find(step => step.name === "Install the native planner fixture writer")!;
    expect(install.run).toContain("bun install --frozen-lockfile --cwd packages/common-contracts");
    expect(install.run).toContain("bun install --frozen-lockfile --cwd packages/data-delivery");
    expect(install.run).toContain("bun install --frozen-lockfile --cwd packages/ledger-file-writer");
  }
});

test("bounded discovery history preserves covered-day membership and planner raw overlap", async () => {
  const discoveredDays = requiredUtcDays("2026-01-01T00:00:00Z", 2);
  expect(discoveredDays).toEqual(["2025-12-30", "2025-12-31", "2026-01-01"]);
  expect(completeHistoryDayInputs(["feed-ingest-plan", "discovered-articles"], discoveredDays, [], "discovered_days")).toHaveLength(3);
  expect(sparseCheckoutPath("state/raw/discovered-articles/[literal]*?.parquet"))
    .toBe("/state/raw/discovered-articles/\\[literal\\]\\*\\?.parquet");
  expect(() => sparseCheckoutPath("state/raw/discovered-articles/a\nstate/")).toThrow("control");
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
    const stage = () => stageFeedHistory({
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
    await expect(stageFeedHistory({
      ledger: "feed-health-state", prefix: registration.prefix, now: "2026-01-01T23:59:59Z",
      health_window_days: 2, request_report_closed_days: 7, period_limit: 3, authored: [],
      raw_files: async () => [],
      read: async () => { throw new TypeError("Unexpected implementation failure"); },
      read_period: async () => { throw new LedgerHistoryReadError("Not reached"); },
    })).rejects.toThrow("Unexpected implementation failure");
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test("hostile dispatch strings fail in the actual adapter before loading inputs or making requests", async () => {
  const child = Bun.spawn([process.execPath, join(root, "services", "feed-ingest-plan", "scripts", "feed-ingest-plan-http-proof.ts")], {
    cwd: root, stdout: "pipe", stderr: "pipe",
    env: { ...Bun.env, FRESHNESS_HOURS: '24; throw new Error("injected")', ARTICLE_LIMIT: "", SHARDS: "", PARTITION_STRATEGY: "" },
  });
  const [output, errors] = await Promise.all([new Response(child.stdout).text(), new Response(child.stderr).text()]);
  expect(await child.exited).toBe(2);
  expect(output).toBe("");
  expect(JSON.parse(errors)).toEqual({ event: "planner_workflow_failed", code: "INVALID_INPUT" });
  expect(errors).not.toContain("injected");
});

test("the workflow checkout names every delivery adapter and focused test input", async () => {
  const { steps } = await workflow();
  const selection = steps.find(step => step.uses?.startsWith("actions/checkout@"))!.with?.["sparse-checkout"];
  if (typeof selection !== "string") throw new Error("Expected a named sparse selection");
  const required = new Set([
    "services/feed-ingest-plan/scripts/feed-ingest-plan-http-proof.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-deliver.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-delivery-result.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-current-files.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-metadata.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-verification.ts",
    "services/feed-ingest-plan/test/feed-ingest-plan-outputs.test.ts",
    "services/feed-ingest-plan/test/feed-ingest-plan-report.test.ts",
    "services/feed-ingest-plan/test/feed-ingest-plan-workflow.test.ts",
    "services/feed-ingest-plan/scripts/feed-ingest-plan-artifacts.ts",
    "services/feed-ingest-plan/src/website-group.ts",
    "services/host-probes/scripts/feed-ingest-plan-profile-proof.ts",
    "services/feed-ingest-plan/test/feed-ingest-plan-host.test.ts",
    "services/feed-ingest-plan/test/feed-ingest-plan-delivery.test.ts",
    "services/feed-ingest-plan/test/website-group.test.ts",
    "config/data-delivery.json",
    "config/push-retry.json",
    "packages/data-delivery/package.json",
    "packages/data-delivery/bun.lock",
    "packages/data-delivery/tsconfig.json",
    "packages/data-delivery/src/index.ts",
    "packages/data-delivery/src/safe-persist-data-contract.ts",
    "packages/data-delivery/src/safe-persist-data.ts",
    "packages/data-delivery/test/safe-persist-data.test.ts",
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
