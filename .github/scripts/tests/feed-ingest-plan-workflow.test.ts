/** Does the isolated workflow preserve its manual, bounded and TypeScript-only execution boundary? */
import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { copyFile, mkdir, mkdtemp, readFile, readdir, rm, stat, symlink, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { CompactIndexSchema, RawDayIndexSchema, FeedHealthContract } from "../../../packages/common-contracts/src/index";
import { persistLedger } from "../../../packages/ledger-file-writer/src/index";
import { stageFeedHistory } from "../feed-ingest-plan-feed-history";
import { selectHealthDays } from "../../../services/feed-ingest-plan/src/read-ledger-history/select-health-days";
import { readLedgerParquet } from "../../../services/feed-ingest-plan/src/read-ledger-history/read-parquet";
import { verifyHealthOrderCompaction } from "../../../services/feed-ingest-plan/test/health-order-recording";
import { completeHistoryDayInputs, createSeenDayInputs, historyDays, historyIndexPaths, resolveHistoryInventory, sparseCheckoutPath } from "../feed-ingest-plan-outputs";
import { requiredSeenDays } from "../../../services/feed-ingest-plan/src/read-ledger-history/read-seen-evidence";
import { utcTimestamp } from "../../../services/feed-ingest-plan/src/harvest-feeds/harvest-types";

const root = fileURLToPath(new URL("../../../", import.meta.url));
type Workflow = {
  on: { workflow_dispatch: { inputs: Record<string, { default: string; type: string }> } };
  permissions: Record<string, string>;
  jobs: { "isolated-plan": { steps: {
    id?: string; name?: string; run?: string; uses?: string;
    "continue-on-error"?: boolean;
    env?: Record<string, string>; if?: string; with?: Record<string, string | boolean>;
  }[] } };
};
function record(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("Expected a workflow mapping");
  return value as Record<string, unknown>;
}
function assertWorkflow(value: unknown): asserts value is Workflow {
  const workflow = record(value);
  const inputs = record(record(record(workflow.on).workflow_dispatch).inputs);
  for (const input of Object.values(inputs)) {
    const fields = record(input);
    if (typeof fields.default !== "string" || typeof fields.type !== "string") throw new Error("Invalid dispatch input");
  }
  if (Object.values(record(workflow.permissions)).some(value => typeof value !== "string")) throw new Error("Invalid permissions");
  const steps = record(record(workflow.jobs)["isolated-plan"]).steps;
  if (!Array.isArray(steps)) throw new Error("Expected workflow steps");
  for (const step of steps) {
    const fields = record(step);
    for (const name of ["id", "name", "run", "uses", "if"]) {
      if (fields[name] !== undefined && typeof fields[name] !== "string") throw new Error(`Invalid step ${name}`);
    }
    if (fields.env !== undefined && Object.values(record(fields.env)).some(value => typeof value !== "string")) {
      throw new Error("Invalid step environment");
    }
    if (fields.with !== undefined && Object.values(record(fields.with)).some(value => !["string", "boolean"].includes(typeof value))) {
      throw new Error("Invalid step action inputs");
    }
  }
}
async function workflow() {
  const text = await readFile(join(root, ".github", "workflows", "feed-ingest-plan-test.yml"), "utf8");
  const parsed = Bun.YAML.parse(text);
  assertWorkflow(parsed);
  return { text, parsed, steps: parsed.jobs["isolated-plan"].steps };
}

test("offers four manual controls and commits only genuine planner and host files", async () => {
  const ci = record(Bun.YAML.parse(await readFile(join(root, ".github", "workflows", "ci.yml"), "utf8")));
  const gateSteps = record(record(ci.jobs).gates).steps;
  if (!Array.isArray(gateSteps)) throw new Error("Expected CI gate steps");
  const preflight = gateSteps.map(record).find(step => step.name === "Isolated planner workflow preflight");
  expect(preflight?.if).toBe("needs.scope.outputs.code == 'true'");
  expect(preflight?.["continue-on-error"]).not.toBe(true);
  expect(preflight?.run).toContain("bun test ./.github/scripts/tests/feed-ingest-plan-report.test.ts");
  expect(preflight?.run).toContain("./.github/scripts/tests/feed-ingest-plan-outputs.test.ts");
  expect(preflight?.run).toContain("./.github/scripts/tests/feed-ingest-plan-workflow.test.ts --timeout 30000");
  expect(preflight?.run).toContain("bun run .github/scripts/feed-ingest-plan-verification.ts");
  const { parsed, steps } = await workflow();
  expect(Object.keys(parsed.on)).toEqual(["workflow_dispatch"]);
  const inputs = parsed.on.workflow_dispatch.inputs;
  expect(Object.keys(inputs)).toEqual(["freshness_hours", "article_limit", "shards", "partition_strategy"]);
  expect(inputs.freshness_hours?.default).toBe("24");
  for (const field of ["article_limit", "shards", "partition_strategy"]) expect(inputs[field]?.default).toBe("");
  expect(parsed.permissions).toEqual({ contents: "write" });
  const plan = steps.find(step => step.id === "plan")!;
  expect(plan.env).toEqual({
    FRESHNESS_HOURS: "${{ inputs.freshness_hours }}", ARTICLE_LIMIT: "${{ inputs.article_limit }}",
    SHARDS: "${{ inputs.shards }}", PARTITION_STRATEGY: "${{ inputs.partition_strategy }}",
  });
  expect(plan.run).not.toContain("${{");
  expect(plan.run).toContain("parseCliRequest(args)");
  expect(plan.run).toContain("const server = servePlan(");
  expect(plan.run).toContain('await fetch(new URL("/api/2026-10-20/plan", server.url)');
  expect(plan.run).toContain("timeout: false");
  expect(plan.run).toContain("await server.stop(true)");
  expect(plan.run).toContain("await verifyLiveDocumentHttp({ ...inputs, settings }");
  expect(plan.run).toContain('await writeGitHubOutputs(GITHUB_OUTPUT, { stage_api_complete: "true" })');
  expect(plan.run!.indexOf("await verifyPlanningCompletion(")).toBeLessThan(plan.run!.indexOf("await verifyLiveDocumentHttp("));
  const httpProof = await readFile(join(root, ".github", "scripts", "feed-ingest-plan-http-proof.ts"), "utf8");
  expect(httpProof).toContain('mkdtemp(join(runnerTemp, "feed-stage-api-private-"))');
  expect(httpProof).toContain("const apiInputs = { ...inputs, outputRoot }");
  expect(httpProof).toContain("return networkTransport.request(request)");
  expect(httpProof).toContain("return resolveAddresses(hostname)");
  expect(httpProof).toContain('post("fetch", "fetch", fetchRequest)');
  expect(httpProof).toContain('post("parse", "parse", parseRequest)');
  expect(httpProof).toContain("replay.response_json !== original.response_json");
  expect(httpProof).toContain("beforeRestart !== afterChecks");
  expect(httpProof).toContain("requireOffline(parsed)");
  expect(httpProof).toContain("requireOffline(replay)");
  expect(httpProof).toContain('post("changed_config_conflict", "fetch", fetchRequest)');
  expect(httpProof).toContain('join(artifactRoot, "stage-api-proof.json")');
  expect(httpProof).not.toContain("app.request(");
  expect(plan.run).toContain('appendFileSync(join(artifactRoot, "audit-events.jsonl")');
  expect(plan.run).toContain('appendFileSync(join(artifactRoot, "progress.jsonl")');
  expect(plan.run).not.toContain("await main(");
  expect(plan.run).not.toContain("app.request(");
  expect(steps.find(step => step.name === "Preserve isolated test evidence")!.if).toBe("${{ always() }}");
  expect(plan.run).not.toContain("recordPlanningMetrics(");
  expect(plan.run).toContain("verifyParquetFiles(");
  expect(plan.run).toContain("summary.metrics.files[key]");
  expect(plan.run).toContain("verifyLedgerReceipt(");
  expect(plan.run).toContain('verifyParquetFiles(join(artifactRoot, "state"), "source-runs"');
  expect(plan.run).toContain('await verifyPlanningCompletion(join(artifactRoot, "state"), summary)');
  expect(plan.run!.indexOf("await verifyPlanningCompletion(")).toBeLessThan(plan.run!.indexOf("await writeGitHubOutputs("));
  expect(plan.run).toContain("stageConfiguredDays(\"published\"");
  expect(plan.run).toContain("stageConfiguredDays(\"item-health\"");
  expect(plan.run).toContain("inputs: { ...inputs.settings.inputs, seen_days, published_days, settled_failure_days, feed_health_days }");
  expect(plan.run).not.toContain("feed-ingest-plan-report");
  const reporting = steps.find(step => step.name === "Optional GitHub report")!;
  expect(reporting.if).toContain("workflow_reporting == 'true'");
  expect(reporting["continue-on-error"]).toBe(true);
  expect(steps.filter(step => step["continue-on-error"] === true)).toEqual([reporting]);
  const completion = steps.find(step => step.name === "Require genuine audited completion")!;
  expect(completion.run).toContain('process.env.AUDITED_COMPLETE !== "true"');
  expect(completion.run).toContain("process.exitCode = 2");
  expect(completion.env).toEqual({
    PLANNING_COMPLETE: "${{ steps.plan.outputs.planning_complete }}",
    STAGE_API_COMPLETE: "${{ steps.plan.outputs.stage_api_complete }}",
    AUDITED_COMPLETE: "${{ steps.audit_fixture.outputs.audited_complete }}",
    AUDIT_SCOPE: "${{ steps.audit_fixture.outputs.scope }}",
  });
  expect(completion.run).toContain('process.env.PLANNING_COMPLETE !== "true"');
  expect(completion.run).toContain('process.env.STAGE_API_COMPLETE !== "true"');
  expect(completion.run).toContain('process.env.AUDIT_SCOPE !== "generated_fixture"');
  expect(steps.find(step => step.id === "audit_fixture")!.run).toContain("await verifyFullAuditFixture(");
  const host = steps.find(step => step.id === "host")!;
  expect(host.run).toContain("await persistFingerprint(");
  expect(host.run).toContain('producer: "telemetry.silicon"');
  expect(host.run).toContain('pipeline_name: "feed-ingest-plan", task_name: "isolated-plan"');
  expect(steps.find(step => step.name === "Install declared TypeScript dependencies")!.run)
    .toContain("bun install --frozen-lockfile --cwd services/host-fingerprints");
  const commit = steps.find(step => step.name === "Commit exact live planner and host files")!;
  expect(commit.if).toContain("steps.audit_fixture.outputs.scope == 'generated_fixture'");
  expect(commit.if).toContain("steps.plan.outputs.stage_api_complete == 'true'");
  expect(commit.env).toEqual({
    CURRENT_RUN_FILES: "${{ steps.plan.outputs.current_run_files }}", HOST_FILES: "${{ steps.host.outputs.host_files }}",
  });
  expect(commit.run).toContain("paths: [...paths(CURRENT_RUN_FILES), ...paths(HOST_FILES)]");
  expect(commit.run).not.toContain("generated-full-audit");
  expect(steps.indexOf(commit)).toBeLessThan(steps.indexOf(steps.find(step => step.name === "Preserve isolated test evidence")!));
  const runs = steps.flatMap(step => step.run === undefined ? [] : [step.run]).join("\n");
  expect(runs).not.toMatch(/\b(python|pip|pytest|uv)\b|git\s+(commit|push)|\beval\s*\(/i);
  const checkout = steps.find(step => step.uses?.startsWith("actions/checkout@"))!;
  expect(checkout.with?.["sparse-checkout"]).toContain("/.github/workflows/ci.yml");
  expect(checkout.with?.["sparse-checkout-cone-mode"]).toBe(false);
  expect(checkout.with?.["persist-credentials"]).toBe(true);
  expect(checkout.with?.["sparse-checkout"]).toContain("/packages/common-contracts/");
  expect(checkout.with?.["sparse-checkout"]).toContain("/.github/scripts/feed-ingest-plan-http-proof.ts");
  expect(checkout.with?.["sparse-checkout"]).not.toContain("/backend/");
  expect(steps.find(step => step.name === "Preserve isolated test evidence")!.with?.path)
    .toBe("${{ runner.temp }}/feed-ingest-plan/");
});

test("derives UTC windows and stages indexed compact files before considering raw evidence", async () => {
  await verifyHealthOrderCompaction();
  const days = historyDays("2026-01-01T00:00:00Z", 1, [1]);
  expect(days).toEqual(["2026-01-01", "2025-12-31"]);
  expect(historyDays(utcTimestamp(() => new Date("2026-01-01T00:00:00.999Z")), 1, [1])).toEqual(days);
  expect(() => historyDays("2026-02-31T00:00:00Z", 1, [1])).toThrow();
  const seenDays = requiredSeenDays("2026-01-01T00:00:00Z", 90);
  expect(seenDays).toHaveLength(91);
  expect([seenDays[0], seenDays.at(-1)]).toEqual(["2025-10-03", "2026-01-01"]);
  expect(completeHistoryDayInputs(["seen"], requiredSeenDays("2026-01-01T00:00:00Z", 2), [], "seen_days"))
    .toHaveLength(3);
  expect(createSeenDayInputs(["seen"], ["2026-01-01"])).toEqual([{
    day: "2026-01-01",
    indexes: { yearly: "state/compact/seen/index/yearly.json", monthly: "state/compact/seen/index/monthly.json",
      daily: "state/compact/seen/index/daily.json" },
    raw_index: "state/raw/seen/2026/01/01/index.json",
  }]);
  expect(completeHistoryDayInputs(["published"], ["2026-01-01"], [], "published_days")).toEqual(
    createSeenDayInputs(["published"], ["2026-01-01"]),
  );
  expect(sparseCheckoutPath("state/raw/seen/[literal]*?.json")).toBe("/state/raw/seen/\\[literal\\]\\*\\?.json");
  expect(() => sparseCheckoutPath("state/raw/seen/a\nstate/")).toThrow("control");
  expect(historyIndexPaths(["feed-ingest-plan", "dispatches"], days)).toContain(
    "state/compact/feed-ingest-plan/dispatches/index/yearly.json",
  );
  const compact = [
    CompactIndexSchema.parse({ version: "2026-10-07", ledger: "dispatches", period: "yearly",
      entries: [{ covers: "2025", rows: 1, bytes: 10 }] }),
    CompactIndexSchema.parse({ version: "2026-10-07", ledger: "dispatches", period: "monthly",
      entries: [{ covers: "2026-01", rows: 1, bytes: 11 }] }),
    CompactIndexSchema.parse({ version: "2026-10-07", ledger: "dispatches", period: "daily",
      entries: [{ covers: "2026-01-01", rows: 1, bytes: 12 }] }),
  ];
  const inventory = resolveHistoryInventory({ ledger: "dispatches",
    prefix: ["feed-ingest-plan", "dispatches"], days, compact, raw: [] });
  expect(inventory).toContain("state/compact/feed-ingest-plan/dispatches/yearly/2025/2025.parquet");
  expect(inventory).toContain("state/compact/feed-ingest-plan/dispatches/monthly/2026/01.parquet");
  expect(inventory).not.toContain("state/compact/feed-ingest-plan/dispatches/daily/2026/01/01.parquet");
  const rawName = "01a1592e-c600-84d0-96e4-7bb01708ce01.parquet";
  const raw = RawDayIndexSchema.parse({
    version: "2026-10-03", ledger: "dispatches", date: "2026-01-01", files: [rawName], bytes: [10],
    content_sha256: createHash("sha256").update(rawName).digest("hex"), listed_at: "2026-01-01T00:00:00Z",
  });
  expect(resolveHistoryInventory({ ledger: "dispatches", prefix: ["feed-ingest-plan", "dispatches"],
    days: ["2026-01-01"], compact: [], raw: [raw] })).toContain(`state/raw/feed-ingest-plan/dispatches/2026/01/01/${rawName}`);
  const empty = CompactIndexSchema.parse({ version: "2026-10-07", ledger: "dispatches", period: "daily",
    entries: [{ covers: "2026-01-01", rows: 0, bytes: 0, state: "empty" }] });
  const emptyInventory = resolveHistoryInventory({ ledger: "dispatches", prefix: ["feed-ingest-plan", "dispatches"],
    days: ["2026-01-01"], compact: [empty], raw: [raw] });
  expect(emptyInventory).not.toContain(`state/raw/feed-ingest-plan/dispatches/2026/01/01/${rawName}`);
  expect(emptyInventory).toContain("state/compact/feed-ingest-plan/dispatches/daily/2026/01/01.parquet");
  expect(() => resolveHistoryInventory({ ledger: "dispatches", prefix: ["dispatches"], days,
    compact: [{ ...empty, version: "2099-01-01" }], raw: [] })).toThrow("version");
  expect(() => historyIndexPaths([".."], days)).toThrow("prefix");
  expect(() => resolveHistoryInventory({ ledger: "dispatches", prefix: ["dispatches"], days,
    compact: [], raw: [{ ...raw, content_sha256: "a".repeat(64) }] })).toThrow("content_sha256");
  const directory = await mkdtemp(join(tmpdir(), "native-feed-history-"));
  try {
    const fixture = FeedHealthContract.schema.parse(await Bun.file(join(root,
      "tests", "fixtures", "feed-ingest-plan", "feed-health-row.json")).json());
    const registration = {
      name: "feed-health", family: "feed-health", grain: "raw-and-compact" as const,
      lifecycle_status: "active" as const, prefix: ["feed-health"],
    };
    for (const day of ["2024-01-01", "2026-01-01"]) {
      const writerContext = {
        run_id: `${day}-1`, attempt: 1, job: "plan" as const, shard: 0,
        pipeline_name: null, task_name: null, producer: "tests.native-history", git_sha: "a".repeat(40),
      };
      const written = await persistLedger({
        ledger: "feed-health", registryEntry: registration, outputRoot: join(directory, "state"),
        ledgerSettings: { format: "parquet", compression_raw: "snappy", compression_compact: "snappy" },
        writerContext, rowContract: FeedHealthContract, period: { tier: "raw", covers: day },
        rows: [{ ...fixture, date: day, run_id: writerContext.run_id, checked_at: `${day}T00:00:00Z` }],
      });
      if (day === "2024-01-01") {
        const original = await readLedgerParquet(join(directory, "state", written.files[0]!.path), "feed-health", FeedHealthContract);
        const compact = await persistLedger({
          ledger: "feed-health", registryEntry: registration, outputRoot: join(directory, "state"),
          ledgerSettings: { format: "parquet", compression_raw: "snappy", compression_compact: "snappy" },
          writerContext: { ...writerContext, producer: "tests.compactor" }, rowContract: FeedHealthContract,
          period: { tier: "compact", period: "daily", covers: day, builtFrom: 1 }, rows: original.rows,
        });
        const file = compact.files[0]!;
        const index = join(directory, "state", "compact", "feed-health", "index", "daily.json");
        await mkdir(dirname(index), { recursive: true });
        await writeFile(index, JSON.stringify({
          version: "2026-10-07", ledger: "feed-health", period: "daily",
          entries: [{ covers: day, state: "packed", rows: 1, bytes: (await stat(join(directory, "state", file.path))).size }],
        }));
      }
    }
    const stage = () => stageFeedHistory({
      ledger: "feed-health", prefix: ["feed-health"], now: "2026-01-01T00:00:00Z",
      raw_discovery_days: 1, authored: [],
      read: async path => {
        const file = Bun.file(join(directory, ...path.split("/")));
        return await file.exists() ? file.json() : undefined;
      },
      listRawDay: async path => {
        try {
          return (await readdir(join(directory, ...path.split("/")))).map(name => `${path}/${name}`);
        } catch (error) {
          if (error instanceof Error && "code" in error && error.code === "ENOENT") return undefined;
          throw error;
        }
      },
    });
    const staged = await stage();
    expect(staged.files).toContain("state/compact/feed-health/daily/2024/01/01.parquet");
    const recorded = await selectHealthDays(directory, registration,
      staged.inputs.filter(day => staged.represented_days.includes(day.day)), 2);
    expect(recorded.map(day => day.day)).toEqual(["2024-01-01", "2026-01-01"]);
    expect(staged.inputs.find(day => day.day === "2025-12-31")?.raw_files).toBeUndefined();
    expect(staged.inventory_complete).toBe(false);
    const original = await readLedgerParquet(join(directory, "state", "compact", "feed-health", "daily",
      "2024", "01", "01.parquet"), "feed-health", FeedHealthContract);
    const monthly = await persistLedger({
      ledger: "feed-health", registryEntry: registration, outputRoot: join(directory, "state"),
      ledgerSettings: { format: "parquet", compression_raw: "snappy", compression_compact: "snappy" },
      writerContext: { ...original.envelope.identity, producer: "tests.monthly-history" },
      rowContract: FeedHealthContract, period: { tier: "compact", period: "monthly", covers: "2024-01", builtFrom: 1 },
      rows: original.rows,
    });
    await writeFile(join(directory, "state", "compact", "feed-health", "index", "monthly.json"), JSON.stringify({
      version: "2026-10-07", ledger: "feed-health", period: "monthly",
      entries: [{ covers: "2024-01", state: "packed", rows: 1,
        bytes: (await stat(join(directory, "state", monthly.files[0]!.path))).size }],
    }));
    const representedMonth = await stage();
    const representedSelection = await selectHealthDays(directory, registration,
      representedMonth.inputs.filter(day => representedMonth.represented_days.includes(day.day)), 2);
    expect(representedSelection.map(day => day.day)).toEqual(["2024-01-31", "2026-01-01"]);
    await writeFile(join(directory, "state", "compact", "feed-health", "index", "daily.json"), JSON.stringify({
      version: "2026-10-07", ledger: "feed-health", period: "daily",
      entries: [{ covers: "2026-02-31", state: "packed", rows: 1, bytes: 10 }],
    }));
    await expect(stage()).rejects.toThrow("calendar period");
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test("rejects hostile dispatch strings before any input load or network request", async () => {
  const { steps } = await workflow();
  const script = steps.find(step => step.id === "plan")!.run!;
  const start = script.indexOf("\n") + 1;
  const end = script.lastIndexOf("\nTS");
  const code = script.slice(start, end);
  const directory = await mkdtemp(join(tmpdir(), "feed-workflow-hostile-"));
  try {
    const process = Bun.spawn(["bun", "run", "-"], {
      cwd: root, stdin: "pipe", stdout: "pipe", stderr: "pipe",
      env: { ...Bun.env, FRESHNESS_HOURS: '24; throw new Error("injected")', ARTICLE_LIMIT: "",
        SHARDS: "", PARTITION_STRATEGY: "", RUNNER_TEMP: directory },
    });
    process.stdin.write(code);
    process.stdin.end();
    const [output, errors] = await Promise.all([new Response(process.stdout).text(), new Response(process.stderr).text()]);
    expect(await process.exited).toBe(1);
    expect(output).toBe("");
    const error = JSON.parse(errors);
    expect(error.code).toBe("INVALID_INPUT");
    expect(error.issues[0].field).toBe("freshness_hours");
    expect(errors).not.toContain('"injected"');
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("strict-checks adapters, tests and the actual inline program in one compiler invocation", async () => {
  const { steps } = await workflow();
  const directory = await mkdtemp(join(root, ".row12-typecheck-"));
  try {
    const generated: string[] = [];
    for (const [index, step] of steps.entries()) {
      if (!step.run?.startsWith("bun run - <<'TS'")) continue;
      const script = step.run;
      const code = script.slice(script.indexOf("\n") + 1, script.lastIndexOf("\nTS"));
      const path = join(directory, `workflow-${index}.ts`);
      await writeFile(path, code.replaceAll('from "./', 'from "../'), "utf8");
      generated.push(path);
    }
    const service = join(root, "services", "feed-ingest-plan");
    const child = Bun.spawn([
      "bun", "run", "tsc", "--noEmit", "--target", "ESNext", "--module", "ESNext",
      "--moduleResolution", "Bundler", "--strict", "--noUncheckedIndexedAccess",
      "--exactOptionalPropertyTypes", "--noFallthroughCasesInSwitch", "--noUnusedLocals",
      "--noUnusedParameters", "--verbatimModuleSyntax", "--skipLibCheck",
      "--types", "bun", "--typeRoots", join(service, "node_modules", "@types"), ...generated,
      ...["feed-ingest-plan-outputs.ts", "feed-ingest-plan-feed-history.ts", "feed-ingest-plan-report.ts", "feed-ingest-plan-commit.ts", "feed-ingest-plan-verification.ts", "feed-ingest-plan-audit-fixture.ts",
        "feed-ingest-plan-http-proof.ts",
        "tests/feed-ingest-plan-outputs.test.ts", "tests/feed-ingest-plan-report.test.ts",
        "tests/feed-ingest-plan-workflow.test.ts"].map(path => join(root, ".github", "scripts", ...path.split("/"))),
    ], { cwd: service, stdout: "pipe", stderr: "pipe" });
    const [output, errors] = await Promise.all([new Response(child.stdout).text(), new Response(child.stderr).text()]);
    expect({ exit: await child.exited, output, errors }).toEqual({ exit: 0, output: "", errors: "" });
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("runs the native compatibility verifier in a named-input copy with no backend directory", async () => {
  const directory = await mkdtemp(join(tmpdir(), "feed-verifier-isolated-"));
  try {
    const common = [
      "index", "version", "schemas/article-assessment.schema", "schemas/candidate.schema",
      "schemas/config.schema", "schemas/dispatch.schema", "schemas/diversity.schema",
      "schemas/editorial-selection.schema", "schemas/envelope.schema", "schemas/event.schema",
      "schemas/ledger-index.schema", "schemas/partition.schema", "schemas/policy.schema",
      "schemas/primitives", "schemas/rejection.schema", "schemas/source-run.schema",
      "schemas/source.schema", "schemas/telemetry.schema", "schemas/host-fingerprint.schema",
      "schemas/harvest-diagnostics.schema", "schemas/item-health-failure.schema", "schemas/feed-health.schema",
      "schemas/planner-operation.schema", "schemas/recorded-instant.schema", "observation-order",
    ].map(name => `packages/common-contracts/src/${name}.ts`);
    const writer = [
      "atomic-file", "index", "ledger-paths", "ledger-types", "persist-compact", "persist-ledger",
      "persist-raw", "registration", "render-ledger-file", "row-identity", "row-schema",
      "parquet/arrow-builder", "parquet/envelope-footer", "parquet/row-digest",
      "parquet/wasm-serializer", "uuid/file-id", "uuid/unit-id", "uuid/name-id",
    ].map(name => `packages/ledger-file-writer/src/${name}.ts`);
    const named = [
      ...common, ...writer, "packages/common-contracts/package.json", "packages/ledger-file-writer/package.json",
      ".github/scripts/feed-ingest-plan-verification.ts",
      "services/feed-ingest-plan/src/read-ledger-history/read-parquet.ts",
      "services/feed-ingest-plan/src/metrics/audit-contracts.ts",
      "tests/fixtures/ledger-file-writer/feed-ingest-dispatch-row.json",
      "tests/fixtures/ledger-file-writer/legacy-seen-day.parquet",
      "services/feed-ingest-plan/src/screen-article-candidates/seen-evidence.ts",
      "tests/fixtures/contracts/feed-ingest-dispatch/one-article.json",
    ];
    for (const path of named) {
      const target = join(directory, ...path.split("/"));
      await mkdir(dirname(target), { recursive: true });
      await copyFile(join(root, ...path.split("/")), target);
    }
    const modules = join(directory, "node_modules");
    await mkdir(join(modules, "@idhazh"), { recursive: true });
    for (const packageName of ["common-contracts", "ledger-file-writer"]) {
      await symlink(join(directory, "packages", packageName), join(modules, "@idhazh", packageName), "junction");
    }
    for (const packageName of ["apache-arrow", "parquet-wasm", "zod"]) {
      await symlink(join(root, "packages", "ledger-file-writer", "node_modules", packageName),
        join(modules, packageName), "junction");
    }
    await expect(stat(join(directory, "backend"))).rejects.toMatchObject({ code: "ENOENT" });
    const child = Bun.spawn([process.execPath, join(directory, ".github", "scripts", "feed-ingest-plan-verification.ts")], {
      cwd: directory, stdout: "pipe", stderr: "pipe",
    });
    const [output, errors] = await Promise.all([new Response(child.stdout).text(), new Response(child.stderr).text()]);
    expect({ exit: await child.exited, errors }).toEqual({ exit: 0, errors: "" });
    expect(JSON.parse(output)).toMatchObject({ status: "verified", row_count: 1, legacy_row_count: 1 });
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
