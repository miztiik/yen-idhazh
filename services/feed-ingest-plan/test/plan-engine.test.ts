/** Do recorded run results preserve saved identities and report unsuccessful work honestly? */
import { expect, test } from "bun:test";
import {
  DiscoveredArticleRowContract, FeedHealthStateRowContract, PlanRunRowContract, RejectedArticleRowContract,
  SelectedArticleRowContract, SelectedArticleContentSchema, SelectedArticlesArtifactSchema, selectedArticleMetadata,
} from "@idhazh/common-contracts";
import { PlanResponseSchema } from "../src/api/plan-response.schema";
import { FeedHealthStateUpdateResponseSchema } from "../src/api/feed-health-state.schema";
import { ServiceSettingsSchema } from "../src/config/service-settings";
import { resolveRunContext } from "../src/resolve-run-context";
import { summarizePlan } from "../src/run-feed-plan";
import type { FeedPlanResult } from "../src/run-feed-plan";

const recordings = new URL("../../../tests/fixtures/feed-ingest-plan/entry-points/", import.meta.url);

async function recordedResult() {
  const [response, artifact, rows, settings, health, discovered, selectedRows, rejected, healthRows] = await Promise.all([
    Bun.file(new URL("response.json", recordings)).json().then(value => PlanResponseSchema.parse(value)),
    Bun.file(new URL("selected-articles.json", recordings)).json().then(value => SelectedArticlesArtifactSchema.parse(value)),
    Bun.file(new URL("plan-runs.rows.json", recordings)).json().then(value => PlanRunRowContract.schema.array().parse(value)),
    Bun.file(new URL("../../../config/feed-ingest-plan-service.json", import.meta.url)).json()
      .then(value => ServiceSettingsSchema.parse(value)),
    Bun.file(new URL("health.json", recordings)).json().then(value => FeedHealthStateUpdateResponseSchema.parse(value)),
    Bun.file(new URL("discovered-articles.rows.json", recordings)).json()
      .then(value => DiscoveredArticleRowContract.schema.array().parse(value)),
    Bun.file(new URL("selected-articles.rows.json", recordings)).json()
      .then(value => SelectedArticleRowContract.schema.array().parse(value)),
    Bun.file(new URL("rejected-articles.rows.json", recordings)).json()
      .then(value => RejectedArticleRowContract.schema.array().parse(value)),
    Bun.file(new URL("feed-health-state.rows.json", recordings)).json()
      .then(value => FeedHealthStateRowContract.schema.array().parse(value)),
  ]);
  if (rows.length !== 1) throw new Error("The entry-point recording must contain its one actual saved run row");
  const context = resolveRunContext(settings, "a".repeat(40), new Date(response.evaluated_at),
    response.run_id.slice(11), response.correlation_id, undefined, response.attempt);
  const selected = SelectedArticleContentSchema.array().parse(artifact.articles.map(article => ({
    ...article, run_id: artifact.run_id, attempt: artifact.attempt, date: artifact.date,
  })));
  const batches: FeedPlanResult["batches"] = {};
  for (const key of ["parsed_batch_id", "selection_batch_id", "partition_batch_id"] as const) {
    const value = response.batches[key];
    if (value !== undefined) batches[key] = value;
  }
  const files: FeedPlanResult["files"] = {};
  for (const key of ["discovered_articles", "selected_articles", "rejected_articles", "feed_health_state", "plan_runs"] as const) {
    const receipt = response.files[key];
    if (receipt !== undefined) files[key] = receipt;
  }
  return {
    response, artifact, health,
    nativeRows: {
      discovered_articles: discovered, selected_articles: selectedRows, rejected_articles: rejected,
      feed_health_state: healthRows, plan_runs: rows,
    },
    result: { context, row: rows[0]!, batches, files, selected } satisfies FeedPlanResult,
  };
}

test("one recorded saved run agrees with its public summary and selected identities", async () => {
  const { response, artifact, result, health, nativeRows } = await recordedResult();
  expect(result.row.run_id).toBe(artifact.run_id);
  expect(result.row.attempt).toBe(artifact.attempt);
  expect(result.row.selected_count).toBe(artifact.articles.length);
  const summary = PlanResponseSchema.parse(summarizePlan(result));
  expect(summary).toEqual(response);
  expect(health.batch_id).toBe(response.batches.selection_batch_id);
  expect(nativeRows.selected_articles).toEqual(result.selected.map(article => ({
    ...selectedArticleMetadata(article), run_id: article.run_id, attempt: article.attempt, date: article.date,
  })));
  for (const key of ["discovered_articles", "selected_articles", "rejected_articles", "feed_health_state", "plan_runs"] as const) {
    const receipt = response.files[key];
    if (receipt === undefined) throw new Error(`The API recording omitted ${key} receipts`);
    expect(nativeRows[key].length).toBe(receipt.files.reduce((total, file) => total + file.row_count, 0));
  }
  for (const invalid of [
    { ...summary, selected_count: summary.selected_count + 1 },
    { ...summary, assignments: summary.assignments.map(assignment => ({ ...assignment, editorial_rank: 2 })) },
    { ...summary, assignments: summary.assignments.map(assignment => ({
      ...assignment, worker_assignment: summary.dispatch_count,
    })) },
  ]) expect(PlanResponseSchema.safeParse(invalid).success).toBe(false);
});

test("partial and failed result models cannot claim completion or lose their failure cause", async () => {
  const { result } = await recordedResult();
  const original = structuredClone(result);
  for (const status of ["partial", "failed"] as const) {
    const row = PlanRunRowContract.schema.parse({
      ...result.row, status, failure_code: "PERSIST_FAILED",
      ...(status === "failed" ? {
        selected_count: 0, dispatch_count: 0, selected_articles_artifact: null, selection_started_at_utc: null,
      } : {}),
    });
    const summary = PlanResponseSchema.parse(summarizePlan({
      ...result, row, selected: status === "failed" ? [] : result.selected,
    }));
    expect(summary.planning_complete).toBe(false);
    expect(summary.status).toBe(status);
    expect(summary.failure_code).toBe(row.failure_code);
    expect(PlanResponseSchema.safeParse({ ...summary, planning_complete: true }).success).toBe(false);
    expect(PlanResponseSchema.safeParse({ ...summary, failure_code: null }).success).toBe(false);
  }
  expect(result).toEqual(original);
});
