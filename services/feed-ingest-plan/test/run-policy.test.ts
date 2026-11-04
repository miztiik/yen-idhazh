/** Does the one run age override remain validated and isolated through the private child boundary? */
import { expect, test } from "bun:test";
import { FeedIngestConfigSchema } from "@idhazh/common-contracts";
import { createPlannerStartup } from "../scripts/feed-ingest-plan-supervisor";
import { restorePlannerStartup } from "../scripts/restore-planner-startup";
import { PlannerStartupSchema } from "../src/config/planner-startup";
import { stageConfigFingerprint } from "../src/api/operation-context";
import { PlanRequestSchema } from "../src/api/plan-request";
import { readPlannerStartupRecording } from "./planner-process-recordings";
import { parseGlobalAgeCeiling, resolveRunPolicy, RunPolicyOverridesSchema } from "../src/config/resolve-run-policy";
import { rejectArticleAge } from "../src/article-freshness-policy";
import { readWorkflowRequest } from "../scripts/feed-ingest-plan-workflow-inputs";

async function config() {
  return FeedIngestConfigSchema.parse(await Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json());
}

test("the single age control accepts positive hours and rejects retired or invalid controls", async () => {
  expect(parseGlobalAgeCeiling(" \t")).toBeUndefined();
  expect(parseGlobalAgeCeiling(undefined)).toBeUndefined();
  expect(parseGlobalAgeCeiling("36.5")).toBe(36.5);
  for (const value of ["0", "-1", "24,36", "NaN", "Infinity", "0x18", "1e2", "one"]) {
    expect(() => parseGlobalAgeCeiling(value)).toThrow();
  }
  for (const value of [0, -1, NaN, Infinity, null, "36"]) {
    expect(RunPolicyOverridesSchema.safeParse({ global_age_ceiling_hours: value }).success).toBe(false);
  }
  for (const name of ["institutional_age_hours", "trade_press_age_hours", "community_age_hours"]) {
    expect(() => RunPolicyOverridesSchema.parse({ [name]: [12, 24] })).toThrow(name);
  }
  const workflow = readWorkflowRequest({ ARTICLE_LIMIT: "2", GLOBAL_AGE_CEILING_HOURS: "12.5" });
  expect(workflow.policy_overrides).toEqual({ global_age_ceiling_hours: 12.5 });
  expect(PlanRequestSchema.parse(workflow.request)).toEqual({ article_limit: 2 });
  const original = await config();
  expect(rejectArticleAge(original, 36)).toBeNull();
  expect(rejectArticleAge(original, null)).toBeNull();
  expect(rejectArticleAge(original, -1)).toBeNull();
  expect(rejectArticleAge(original, 36.1)?.details.max_age_hours).toBe(36);
});

test("effective settings do not mutate shared config or another request", async () => {
  const original = await config();
  const before = structuredClone(original);
  const [first, second] = await Promise.all([
    Promise.resolve().then(() => resolveRunPolicy(original, { global_age_ceiling_hours: 12 })),
    Promise.resolve().then(() => resolveRunPolicy(original, { global_age_ceiling_hours: 72 })),
  ]);
  expect(original).toEqual(before);
  expect(first.curate_articles.global_age_ceiling_hours).toBe(12);
  expect(second.curate_articles.global_age_ceiling_hours).toBe(72);
  expect(first.curate_articles.source_authority_weight).toBe(original.curate_articles.source_authority_weight);
  first.curate_articles.diversity.lambda_domain = 99;
  expect(second.curate_articles.diversity).toEqual(original.curate_articles.diversity);
  expect(original).toEqual(before);
  expect(() => resolveRunPolicy(original, { global_age_ceiling_hours: 0 })).toThrow("global_age_ceiling_hours");
});

test("private children preserve the age override and fence different effective policies", async () => {
  const fixture = await readPlannerStartupRecording();
  const original = structuredClone(fixture.inputs.harvest.config);
  const baseline = await config();
  const narrowed = resolveRunPolicy(baseline, { global_age_ceiling_hours: 2 });
  const startup = createPlannerStartup({
    ...fixture.inputs, harvest: { ...fixture.inputs.harvest, config: narrowed },
  }, fixture.startup.runtime);
  const first = await restorePlannerStartup(PlannerStartupSchema.parse(JSON.parse(JSON.stringify(startup))), fixture.inputs.root);
  const second = await restorePlannerStartup(createPlannerStartup({
    ...fixture.inputs, harvest: { ...fixture.inputs.harvest, config: baseline },
  }, fixture.startup.runtime), fixture.inputs.root);
  expect(first.inputs.harvest.config.curate_articles.global_age_ceiling_hours).toBe(2);
  expect(second.inputs.harvest.config).toEqual(baseline);
  expect(stageConfigFingerprint(first.inputs, first.runtime)).not.toBe(stageConfigFingerprint(second.inputs, second.runtime));
  expect(fixture.inputs.harvest.config).toEqual(original);
});
