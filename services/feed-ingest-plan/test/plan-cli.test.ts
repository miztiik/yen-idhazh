/** Do CLI controls share strict API semantics and disclose failures safely? */
import { expect, test } from "bun:test";
import { fileURLToPath } from "node:url";
import { PlanError, PlanRequestSchema, describePlanError, parseCliRequest, resolvePlanRequest } from "../src/api/plan-request";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { resolveRunContext } from "../src/resolve-run-context";
import { join } from "node:path";
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

test("public request errors retain their fields without exposing checkout paths", () => {
  const invalid = PlanRequestSchema.safeParse({ article_limit: "2" });
  if (invalid.success) throw new Error("The typed request must refuse a numeric string");
  expect(describePlanError(invalid.error).issues[0]!.field).toBe("article_limit");
  expect(describePlanError(new PlanError("PLANNER_DISABLED", "Planner is disabled", "enabled")))
    .toEqual({ code: "PLANNER_DISABLED", issues: [{ field: "enabled", message: "Planner is disabled" }] });
  try {
    parseCliRequest(["--cli", "--freshness-hours=18"]);
    throw new Error("The CLI must refuse an unknown control");
  } catch (error) {
    expect(describePlanError(error)).toMatchObject({
      code: "INVALID_REQUEST", issues: [{ field: "freshness_hours" }],
    });

  }
  const failure = describePlanError(Object.assign(new Error(`Cannot write ${join(root, "state", "blocked")}`), {
    path: join(root, "state", "blocked"),
  }), root);
  expect(failure.code).toBe("PLAN_FAILED");
  expect(failure.issues[0]!.field).toBe("state/blocked");
  expect(JSON.stringify(failure)).not.toContain(root);
});

test("standalone startup refuses missing or invalid supplied code identity with Git unavailable", async () => {
  for (const identity of [undefined, "not-a-commit"]) {
    const environment: Record<string, string | undefined> = { ...process.env, PATH: "", Path: "" };
    if (identity === undefined) delete environment.GITHUB_SHA;
    else environment.GITHUB_SHA = identity;
    const child = Bun.spawn([process.execPath, fileURLToPath(new URL("../src/index.ts", import.meta.url)), "--cli"], {
      cwd: root, env: environment, stdout: "pipe", stderr: "pipe",
    });
    const [output, error, status] = await Promise.all([
      new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited,
    ]);
    expect(status).toBe(1);
    expect(output).toBe("");
    expect(JSON.parse(error.trim())).toMatchObject({
      event: "planner_error", issues: [expect.objectContaining({ message: expect.stringContaining("GITHUB_SHA") })],
    });
  }
});
