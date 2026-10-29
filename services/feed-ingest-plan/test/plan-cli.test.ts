/** Do CLI controls share strict API semantics and await the actual one-shot entry? */
import { expect, test } from "bun:test";
import { fileURLToPath } from "node:url";
import { PlanError, PlanRequestSchema, parseCliRequest, resolvePlanRequest } from "../src/api/plan-request";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { resolveRunContext } from "../src/resolve-run-context";
import { main } from "../src/index";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
import {
  DiscoveredArticleRowContract, PlanRunRowContract, SelectedArticleRowContract,
} from "@idhazh/common-contracts";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { ServiceSettingsSchema } from "../src/config/service-settings";

const root = fileURLToPath(new URL("../../../", import.meta.url));

test("CLI blanks are absent; typed API strings, nulls, unknown fields and invalid numbers refuse", async () => {
  expect(parseCliRequest(["--cli", "--article-limit", "", "--shards="])).toEqual({
    mode: "cli", request: {},
  });
  expect(parseCliRequest(["--cli", "--article-limit", "2", "--shards", "1",
    "--partition-strategy", "none"]).request).toEqual({
    article_limit: 2, shards: 1, partition_strategy: "none",
  });
  try {
    parseCliRequest(["--cli", "--freshness-hours=18"]);
    throw new Error("unknown CLI control was accepted");
  } catch (error) {
    expect(error).toBeInstanceOf(PlanError);
    expect((error as PlanError).field).toBe("freshness_hours");
  }
  for (const field of ["article_limit", "shards"]) {
    for (const value of ["12", null, 0, -1, Number.NaN, Number.POSITIVE_INFINITY]) {
      const result = PlanRequestSchema.safeParse({ [field]: value });
      expect(result.success).toBe(false);
      if (!result.success) expect(result.error.issues[0]!.path[0]).toBe(field);
    }
  }
  for (const field of ["article_limit", "shards"]) expect(PlanRequestSchema.safeParse({ [field]: 1.5 }).success).toBe(false);
  expect(PlanRequestSchema.safeParse({ date: "2026-10-21" }).success).toBe(false);
  expect(PlanRequestSchema.safeParse({ vertical: "world" }).success).toBe(false);
  expect(PlanRequestSchema.safeParse({ freshness_hours: 18 }).success).toBe(false);
  expect(PlanRequestSchema.safeParse({ partition_strategy: "random" }).success).toBe(false);
  for (const args of [
    ["--cli", "--shards", "bad"], ["--cli", "--article-limit=-1"],
    ["--cli", "--freshness-hours=Infinity"],
    ["--cli", "--shards=1.2"], ["--cli", "--date=2026-10-21"], ["--cli", "--vertical=world"], ["--cli", "--cli"],
    ["--serve", "--cli"], ["--serve", "--shards=1"], ["--cli", "--shards=1", "--shards=2"], [],
  ]) expect(() => parseCliRequest(args)).toThrow();
  const inputs = await loadPlanInputs(root);
  const globalConfig = await Bun.file(join(root, "config", "idhazh.json")).json();
  expect(globalConfig.collect.published_window_days).toBe(730);
  expect(inputs.settings.inputs.published_url_lookback_days).toBe(7);
  expect(inputs.clock_config.collect.published_window_days).toBe(7);
  expect(inputs.settings.listener.parser_concurrency).toBe(10);
  expect(inputs.settings.listener.max_body_bytes).toBe(2_000_000);
  expect(inputs.settings).not.toHaveProperty("run");
  expect(inputs.settings.inputs.discovered_files).toEqual([]);
  expect(inputs.settings.inputs.discovered_days).toEqual([]);
  for (const artifact_root of ["folder with spaces", "/tmp/artifacts", "../artifacts", "a".repeat(500)]) {
    expect(ServiceSettingsSchema.safeParse({ ...inputs.settings, inputs: { ...inputs.settings.inputs, artifact_root } }).success).toBe(false);
  }
  expect(ServiceSettingsSchema.parse({ ...inputs.settings, inputs: {
    ...inputs.settings.inputs, artifact_root: "backend/var/selected-output", output_root: "local state",
  } }).inputs.output_root).toBe("local state");
  const config = inputs.harvest.config;
  expect(resolvePlanRequest({}, config)).toMatchObject({
    article_limit: config.curate_articles.article_limit, shards: config.partition.default_shards,
    partition_strategy: config.partition.default_strategy,
  });
  expect(resolvePlanRequest({ partition_strategy: "none" }, config).shards).toBe(1);
  expect(resolvePlanRequest({ partition_strategy: "none", shards: 1 }, config).shards).toBe(1);
  for (const value of [
    { partition_strategy: "none", shards: 2 }, { shards: config.partition.max_shards + 1 },
    { shards: 0 }, { article_limit: 0 },
  ]) expect(() => resolvePlanRequest(value, config)).toThrow();
});

test("one captured UTC day determines identity while independent runs have distinct numeric IDs", async () => {
  const { settings } = await loadPlanInputs(root);
  const now = new Date("2026-10-21T23:59:59.999Z");
  const context = resolveRunContext(settings, "a".repeat(40), now, "700");
  expect(context.now).toBe("2026-10-21T23:59:59Z");
  expect(context.run_id).toBe("2026-10-21-700");
  expect(context.writer.shard).toBe(0);
  expect(resolveRunContext(settings, "a".repeat(40), now, "700", undefined, undefined, 2).writer.attempt).toBe(2);
  expect(resolveRunContext(settings, "a".repeat(40), now, "700", undefined, undefined, 1, "parent.runner").writer.producer)
    .toBe("parent.runner");
  expect(resolveRunContext(settings, "a".repeat(40), now).run_id)
    .not.toBe(resolveRunContext(settings, "a".repeat(40), now).run_id);
});

test("real CLI process refuses disabled or invalid requests without Python or network", async () => {
  for (const [args, code, field] of [
    [["--cli"], "PLANNER_DISABLED", "enabled"],
    [["--cli", "--freshness-hours=18"], "INVALID_REQUEST", "freshness_hours"],
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

test("the awaited entrypoint records configured selection counts, signed ages and global discovery", async () => {
  for (const mode of ["counts", "negative_age", "first_seen"] as const) {
    const recorded = await recordedPlan(mode === "first_seen"
      ? [source({ url: "https://news.example/article-failures.xml" })] : undefined);
    const printed: unknown[] = [];
    try {
      if (mode === "counts") {
        recorded.inputs.harvest.config.feedback.lifecycle_window_days = 5;
        recorded.inputs.harvest.config.feedback.request_report_closed_days = 2;
      }
      if (mode === "negative_age") recorded.runtime.clock = () => new Date("2026-10-21T09:00:00Z");
      if (mode === "first_seen") {
        recorded.inputs.harvest.config.discovered_articles.lookback_days = 0;
        recorded.inputs.settings.inputs.discovered_days = [{ day: "2026-10-21", raw_files: [] }];
      }
      const summary = await main(["--cli", "--partition-strategy=none", "--article-limit=1"], {
        inputs: recorded.inputs, runtime: recorded.runtime, output: value => { printed.push(value); },
      });
      if (!("planning_complete" in summary)) throw new Error("Expected the one-shot CLI summary");
      expect(printed).toHaveLength(1);
      expect(summary.planning_complete).toBe(true);
      expect(summary.selected_count).toBe(1);
      for (const ledger of ["discovered-articles", "selected-articles", "feed-health-state", "plan-runs"]) {
        expect(existsSync(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan", ledger))).toBe(true);
      }
      const selectedFile = summary.files.selected_articles!.files[0]!;
      const selected = await readPlannerParquet(join(recorded.inputs.outputRoot, selectedFile.path),
        "selected-articles", SelectedArticleRowContract);
      expect(selected.rows).toHaveLength(1);
      expect(selected.rows[0]).not.toHaveProperty("article_text");
      if (mode === "negative_age") expect(selected.rows[0]!.age_hours).toBeLessThan(0);
      if (mode === "counts") expect(summary).toMatchObject({ lifecycle_window_days: 5, request_report_closed_days: 2 });
      if (mode === "first_seen") {
        const file = summary.files.discovered_articles!.files[0]!;
        const discovered = await readPlannerParquet(join(recorded.inputs.outputRoot, file.path),
          "discovered-articles", DiscoveredArticleRowContract);
        expect(discovered.rows.some(row => row.url_key === selected.rows[0]!.url_key)).toBe(true);
      }
      expect(recorded.events.some(event => event.operation === "persist" && event.phase === "completed")).toBe(true);
    } finally { await recorded.close(); }
  }
}, 30000);

test("a real selected-metadata write failure prints an explicit partial run instead of success", async () => {
  const recorded = await recordedPlan();
  const printed: unknown[] = [];
  try {
    const raw = join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan");
    await mkdir(raw, { recursive: true });
    await writeFile(join(raw, "selected-articles"), "A file cannot hold selected metadata.");
    const summary = await main(["--cli"], {
      inputs: recorded.inputs, runtime: recorded.runtime, output: value => { printed.push(value); },
    });
    if (!("planning_complete" in summary)) throw new Error("Expected the one-shot CLI summary");
    expect(printed).toEqual([summary]);
    expect(summary).toMatchObject({ planning_complete: false, status: "partial", selected_articles_artifact: null });
    expect(summary.failure_code).not.toBeNull();
    expect(summary.files.selected_articles).toBeUndefined();
    const file = summary.files.plan_runs!.files[0]!;
    const saved = await readPlannerParquet(join(recorded.inputs.outputRoot, file.path), "plan-runs", PlanRunRowContract);
    expect(saved.rows[0]).toMatchObject({ status: "partial", failure_code: summary.failure_code, selected_count: summary.selected_count });
    expect(existsSync(join(raw, "feed-health-state"))).toBe(true);
    expect(existsSync(join(raw, "discovered-articles"))).toBe(true);
  } finally { await recorded.close(); }
}, 30000);
