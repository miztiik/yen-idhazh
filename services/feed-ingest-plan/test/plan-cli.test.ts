/** Do CLI controls share strict API semantics and await the actual one-shot entry? */
import { expect, test } from "bun:test";
import { fileURLToPath } from "node:url";
import { PlanRequestSchema, parseCliRequest, resolvePlanRequest } from "../src/api/plan-request";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { resolveRunContext } from "../src/resolve-run-context";

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
