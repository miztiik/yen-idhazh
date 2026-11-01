/** Do recorded run results preserve saved identities and report unsuccessful work honestly? */
import { expect, test } from "bun:test";
import {
  DiscoveredArticleRowContract, FeedHealthStateRowContract, PlanRunRowContract, RejectedArticleRowContract,
  SelectedArticleRowContract, SelectedFeedBatchSchema, SelectedArticlesArtifactSchema, selectedArticleMetadata,
  PLANNER_API_PREFIX,
} from "@idhazh/common-contracts";
import { PlanResponseSchema } from "../src/api/plan-response.schema";
import { FeedHealthStateUpdateResponseSchema } from "../src/api/feed-health-state.schema";
import { ServiceSettingsSchema } from "../src/config/service-settings";
import { resolveRunContext } from "../src/resolve-run-context";
import { runFeedPlan, summarizePlan } from "../src/run-feed-plan";
import type { FeedPlanResult } from "../src/run-feed-plan";
import { createPlanApp } from "../src/api/server";
import { SelectionResponseSchema, PartitionResponseSchema } from "../src/api/stage-response.schema";
import { stageStore } from "../src/api/stage-store";
import { recordedPlan } from "./plan-recordings";

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
  const selected = selectedRows;
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
  expect(result.selected.every(article => !("article_text" in article))).toBe(true);
  const selectedBatch = response.batches.selection_batch_id;
  if (selectedBatch === undefined) throw new Error("The API recording omitted its selected batch");
  expect(health.batch_id).toBe(selectedBatch);
  expect(result.selected).toEqual(artifact.articles.map(article => ({
    ...selectedArticleMetadata(article), run_id: artifact.run_id, attempt: artifact.attempt, date: artifact.date,
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

test("real stage responses supply saved timestamps and metadata to orchestration", async () => {
  for (const enabled of [true, false]) {
    const fixture = await recordedPlan();
    fixture.inputs.harvest.config.partition.enabled = enabled;
    fixture.runtime.selection_clock = () => new Date("2026-10-22T00:01:00Z");
    const app = createPlanApp(fixture.inputs, fixture.runtime);
    let selection: ReturnType<typeof SelectionResponseSchema.parse> | undefined;
    let partition: ReturnType<typeof PartitionResponseSchema.parse> | undefined;
    const server = Bun.serve({
      hostname: "127.0.0.1", port: 0, idleTimeout: 0,
      async fetch(request) {
        const response = await app.fetch(request);
        const path = new URL(request.url).pathname;
        if (response.ok && path === `${PLANNER_API_PREFIX}/select-articles`) {
          selection = SelectionResponseSchema.parse(await response.clone().json());
          const batch = stageStore(fixture.inputs).read("selected", selection.batch_id, SelectedFeedBatchSchema);
          expect(selection.selection_started_at_utc).toBe(batch.selection_started_at_utc);
          expect(selection.evaluated_at).toBe(batch.evaluated_at);
          expect(selection.articles).toEqual(batch.articles.map(article => ({
            ...selectedArticleMetadata(article), run_id: article.run_id, attempt: article.attempt, date: article.date,
          })));
          expect(batch.articles.every(article => article.article_text.length > 0)).toBe(true);
          expect(SelectionResponseSchema.safeParse({ ...selection, articles: batch.articles }).success).toBe(false);
        }
        if (response.ok && path === `${PLANNER_API_PREFIX}/partition-articles`) {
          partition = PartitionResponseSchema.parse(await response.clone().json());
          expect(partition.articles.every(article => !("article_text" in article))).toBe(true);
          expect(PartitionResponseSchema.safeParse({
            ...partition, articles: partition.articles.map(article => ({ ...article, article_text: "private" })),
          }).success).toBe(false);
        }
        return response;
      },
    });
    try {
      const result = await runFeedPlan({ article_limit: 2, shards: 2, partition_strategy: "round-robin" },
        fixture.inputs, { ...fixture.runtime, stage_origin: `http://127.0.0.1:${server.port}` });
      expect(result.row.status).toBe("completed");
      expect(selection).toBeDefined();
      expect(result.row.selection_started_at_utc).toBe(selection!.selection_started_at_utc);
      expect(result.row.selection_started_at_utc).toBe("2026-10-22T00:01:00Z");
      expect(result.row.evaluated_at).toBe(selection!.evaluated_at);
      expect(result.row.evaluated_at).toBe(result.context.now);
      expect(result.selected.length).toBeGreaterThan(0);
      expect(result.selected).toEqual((enabled ? partition : selection)!.articles);
      expect(result.batches.selection_batch_id).toBe(selection!.batch_id);
      if (enabled) {
        expect(partition).toBeDefined();
        expect(result.batches.partition_batch_id).toBe(partition!.batch_id);
        expect(result.row.strategy).toBe(partition!.strategy);
        expect(result.row.dispatch_count).toBe(partition!.dispatch_count);
      } else {
        expect(partition).toBeUndefined();
        expect(result.batches.partition_batch_id).toBeUndefined();
        expect(result.row.strategy).toBe("none");
        expect(result.row.dispatch_count).toBe(0);
        expect(result.selected.every(article => article.worker_assignment === null)).toBe(true);
      }
      expect(PlanResponseSchema.parse(summarizePlan(result)).assignments).toEqual(result.selected.map(article => ({
        url_key: article.url_key, editorial_rank: article.editorial_rank, worker_assignment: article.worker_assignment,
      })));
    } finally { await server.stop(true); await app.close(); await fixture.close(); }
  }
});

test("an empty real selection retains timestamps and its text-artifact receipt", async () => {
  const fixture = await recordedPlan();
  fixture.inputs.harvest.config.partition.enabled = false;
  fixture.inputs.harvest.config.triage.min_words = 1_000_000;
  fixture.runtime.selection_clock = () => new Date("2026-10-22T00:01:00Z");
  try {
    const result = await runFeedPlan({}, fixture.inputs, fixture.runtime);
    expect(result.row.status).toBe("completed");
    expect(result.row.selected_count).toBe(0);
    expect(result.selected).toEqual([]);
    expect(result.row.selection_started_at_utc).toBe("2026-10-22T00:01:00Z");
    expect(result.row.evaluated_at).toBe(result.context.now);
    expect(result.files.selected_articles).toEqual({ status: "empty", files: [] });
    expect(result.row.selected_articles_artifact).not.toBeNull();
    expect(PlanResponseSchema.parse(summarizePlan(result)).assignments).toEqual([]);
  } finally { await fixture.close(); }
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
