/** Do CLI controls share strict API semantics and await the actual one-shot entry? */
import { expect, test } from "bun:test";
import { fileURLToPath } from "node:url";
import { PlanRequestSchema, parseCliRequest, resolvePlanRequest } from "../src/api/plan-request";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { resolveRunContext } from "../src/resolve-run-context";
import { main } from "../src/index";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { mkdir, writeFile } from "node:fs/promises";

const root = fileURLToPath(new URL("../../../", import.meta.url));

test("CLI blanks are absent; typed API strings, nulls, unknown fields and invalid numbers refuse", async () => {
  expect(parseCliRequest(["--cli", "--freshness-hours=", "--article-limit", "", "--shards="])).toEqual({
    mode: "cli", request: {},
  });
  expect(parseCliRequest(["--cli", "--freshness-hours=18", "--article-limit", "2", "--shards", "1",
    "--partition-strategy", "none"]).request).toEqual({
    freshness_hours: 18, article_limit: 2, shards: 1, partition_strategy: "none",
  });
  for (const field of ["freshness_hours", "article_limit", "shards"]) {
    for (const value of ["12", null, 0, -1, Number.NaN, Number.POSITIVE_INFINITY]) {
      const result = PlanRequestSchema.safeParse({ [field]: value });
      expect(result.success).toBe(false);
      if (!result.success) expect(result.error.issues[0]!.path[0]).toBe(field);
    }
  }
  for (const field of ["article_limit", "shards"]) expect(PlanRequestSchema.safeParse({ [field]: 1.5 }).success).toBe(false);
  expect(PlanRequestSchema.safeParse({ date: "2026-10-21" }).success).toBe(false);
  expect(PlanRequestSchema.safeParse({ partition_strategy: "random" }).success).toBe(false);
  for (const args of [
    ["--cli", "--shards", "bad"], ["--cli", "--article-limit=-1"], ["--cli", "--freshness-hours=Infinity"],
    ["--cli", "--shards=1.2"], ["--cli", "--date=2026-10-21"], ["--cli", "--cli"],
    ["--serve", "--cli"], ["--serve", "--shards=1"], ["--cli", "--shards=1", "--shards=2"], [],
  ]) expect(() => parseCliRequest(args)).toThrow();
  const inputs = await loadPlanInputs(root);
  const config = inputs.harvest.config;
  expect(resolvePlanRequest({}, config)).toMatchObject({
    article_limit: config.curate.article_limit, shards: config.partition.default_shards,
    partition_strategy: config.partition.default_strategy,
  });
  expect(resolvePlanRequest({ partition_strategy: "none" }, config).shards).toBe(1);
  expect(resolvePlanRequest({ partition_strategy: "none", shards: 1 }, config).shards).toBe(1);
  for (const value of [
    { partition_strategy: "none", shards: 2 }, { shards: config.partition.max_shards + 1 },
    { shards: 0 }, { article_limit: 0 }, { freshness_hours: -1 },
  ]) expect(() => resolvePlanRequest(value, config)).toThrow();
});

test("one captured UTC day determines identity while independent runs have distinct numeric IDs", async () => {
  const { settings } = await loadPlanInputs(root);
  const now = new Date("2026-10-21T23:59:59.999Z");
  const context = resolveRunContext(settings, "a".repeat(40), now, "700");
  expect(context.now).toBe("2026-10-21T23:59:59Z");
  expect(context.run_id).toBe("2026-10-21-700");
  expect(context.writer.shard).toBe(0);
  expect(resolveRunContext(settings, "a".repeat(40), now).run_id)
    .not.toBe(resolveRunContext(settings, "a".repeat(40), now).run_id);
});

test("real CLI process refuses disabled or invalid requests without Python or network", async () => {
  for (const [args, code, field] of [
    [["--cli"], "PLANNER_DISABLED", "enabled"],
    [["--cli", "--freshness-hours=0"], "INVALID_INPUT", "freshness_hours"],
    [["--cli", "--shards=2", "--partition-strategy=none"], "INVALID_REQUEST", "shards"],
  ] as const) {
    const child = Bun.spawn([process.execPath, fileURLToPath(new URL("../src/index.ts", import.meta.url)), ...args], {
      cwd: root, stdout: "pipe", stderr: "pipe",
    });
    const [stdout, stderr, exit] = await Promise.all([
      new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited,
    ]);
    expect(exit).toBe(1);
    expect(stdout).toBe("");
    const failure = JSON.parse(stderr.trim());
    expect(failure.code).toBe(code);
    expect(failure.issues[0].field).toBe(field);
    expect(stderr).not.toContain(root);
  }
}, 30000);

test("the awaited entrypoint refuses unsupported audit values before any audit write or summary", async () => {
  for (const mode of ["top_k", "negative_age", "first_seen"] as const) {
    const recorded = await recordedPlan(mode === "first_seen"
      ? [source({ url: "https://news.example/article-failures.xml" })] : undefined);
    const printed: unknown[] = [];
    try {
      if (mode === "top_k") recorded.inputs.harvest.config.metrics.top_source_counts = [1, 2, 5];
      if (mode === "negative_age") recorded.runtime.clock = () => new Date("2026-10-21T09:00:00Z");
      if (mode === "first_seen") {
        recorded.inputs.clock_config.collect.seen_window_days = 0;
        recorded.inputs.settings.inputs.seen_days = [{ day: "2026-10-21", raw_files: [] }];
      }
      await expect(main(["--cli", "--partition-strategy=none"], {
        inputs: recorded.inputs, runtime: recorded.runtime, output: value => { printed.push(value); },
      })).rejects.toThrow(mode === "top_k" ? "top_k" : mode === "negative_age" ? "signed negative" : "first_seen");
      expect(printed).toEqual([]);
      for (const ledger of ["article-assessments", "diversity", "source-runs"]) {
        expect(existsSync(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan", ledger))).toBe(false);
      }
      expect(recorded.events.some(event => event.stage === "seal-article-ledger")).toBe(true);
    } finally { await recorded.close(); }
  }
}, 30000);

test("a real required assessment write failure cannot print a successful CLI summary", async () => {
  const recorded = await recordedPlan();
  const printed: unknown[] = [];
  try {
    const raw = join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan");
    await mkdir(raw, { recursive: true });
    await writeFile(join(raw, "article-assessments"), "A file cannot hold assessment output.");
    await expect(main(["--cli"], {
      inputs: recorded.inputs, runtime: recorded.runtime, output: value => { printed.push(value); },
    })).rejects.toThrow();
    expect(printed).toEqual([]);
    expect(existsSync(join(raw, "diversity"))).toBe(false);
    expect(existsSync(join(raw, "source-runs"))).toBe(false);
  } finally { await recorded.close(); }
}, 30000);
