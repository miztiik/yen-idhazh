/** Do saved batches pass through real stage APIs into validated dispatch Parquet? */
import { expect } from "bun:test";
import { randomUUID } from "node:crypto";
import { dirname, join } from "node:path";
import { rename, writeFile } from "node:fs/promises";
import {
  deriveCandidateId, ParsedFeedBatchSchema, PartitionedFeedBatchSchema, SelectedFeedBatchSchema,
} from "@idhazh/common-contracts";
import { createPlanApp } from "../src/api/server";
import { runFeedPlan } from "../src/run-feed-plan";
import { readStageBatch, writeStageBatch } from "../src/api/stage-store";
import {
  FeedHealthStateUpdateRequestSchema, FeedHealthStateUpdateResponseSchema,
} from "../src/api/feed-health-state.schema";
import {
  SelectionResponseSchema, PartitionResponseSchema, PersistenceResponseSchema, StageErrorResponseSchema,
} from "../src/api/stage-response.schema";
import { readLedgerParquet } from "../src/read-ledger-history/read-parquet";
import { DispatchContract } from "../src/metrics/audit-contracts";
import { recordedPlan } from "./plan-recordings";

type App = ReturnType<typeof createPlanApp>;
function post(app: App, route: string, body: unknown) {
  return app.request(`/api/2026-10-20/${route}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
}

async function verifySavedStageFlow() {
  const fixture = await recordedPlan();
  try {
    const plan = await runFeedPlan({ article_limit: 1, partition_strategy: "none" }, fixture.inputs, fixture.runtime);
    const requests = fixture.transport.requests.length;
    const selectedResponse = await post(createPlanApp(fixture.inputs, fixture.runtime), "select-articles", {
      batch_id: plan.batches.parsed_batch_id,
    });
    expect(selectedResponse.status).toBe(200);
    const selected = SelectionResponseSchema.parse(await selectedResponse.json());
    expect(selected.publisher_history).toEqual({
      day: plan.context.date, availability: "unavailable", gaps: ["publication_history_unavailable"],
    });
    expect(selected.selection_state.capture_status).toBe("captured");
    expect(typeof selected.selection_state.selection_started_at_utc).toBe("string");
    expect(selected.selection_state.state).toMatchObject({
      status: "unavailable",
      lifecycle_window_days: fixture.inputs.harvest.config.feedback.lifecycle_window_days,
      request_window_days: fixture.inputs.harvest.config.feedback.window_days,
    });
    expect(FeedHealthStateUpdateRequestSchema.parse({ batch_id: selected.batch_id })).toEqual({
      batch_id: selected.batch_id,
    });
    expect(FeedHealthStateUpdateRequestSchema.safeParse({
      batch_id: selected.batch_id, path: "state/raw/arbitrary.parquet",
    }).success).toBe(false);
    const saved = FeedHealthStateUpdateResponseSchema.parse({
      batch_id: selected.batch_id,
      selection_state: selected.selection_state,
      update: {
        status: "saved", state_revision: 1, attempted_revision: 1,
        parent_revision: null, changed_days: ["2026-10-24"], diagnostics: [],
      },
    });
    expect(saved.update.status).toBe("saved");
    expect(FeedHealthStateUpdateResponseSchema.safeParse({
      batch_id: selected.batch_id,
      selection_state: selected.selection_state,
      update: {
        status: "saved", state_revision: 2, attempted_revision: 2,
        parent_revision: null, changed_days: [], diagnostics: [],
      },
    }).success).toBe(false);
    expect(FeedHealthStateUpdateResponseSchema.parse({
      batch_id: selected.batch_id,
      selection_state: selected.selection_state,
      update: {
        status: "unchanged", state_revision: 1, attempted_revision: null,
        parent_revision: null, changed_days: [], diagnostics: [],
      },
    }).update.status).toBe("unchanged");
    const failedSave = FeedHealthStateUpdateResponseSchema.parse({
      batch_id: selected.batch_id,
      selection_state: selected.selection_state,
      update: {
        status: "save_failed", state_revision: null, attempted_revision: 1,
        parent_revision: null, changed_days: ["2026-10-24"], diagnostics: ["retry_exhausted"],
      },
    });
    expect(failedSave.update.status).toBe("save_failed");
    const unavailableState = FeedHealthStateUpdateResponseSchema.parse({
      batch_id: selected.batch_id,
      selection_state: selected.selection_state,
      update: {
        status: "unavailable", state_revision: null, attempted_revision: null,
        parent_revision: null, changed_days: [], diagnostics: ["input_gap"],
      },
    });
    expect(unavailableState.update).toMatchObject({
      status: "unavailable", diagnostics: ["input_gap"],
    });
    expect(selected.selections).toEqual(plan.evidence.curation.rows);
    expect(selected.exclusions).toEqual([
      ...plan.evidence.harvest.rejections, ...plan.evidence.screening.rejections, ...plan.evidence.curation.rejections,
    ]);
    const repeated = SelectionResponseSchema.parse(await (await post(
      createPlanApp(fixture.inputs, fixture.runtime), "select-articles", { batch_id: plan.batches.parsed_batch_id },
    )).json());
    expect(repeated.batch_id).not.toBe(selected.batch_id);
    expect(repeated.selections).toEqual(selected.selections);

    const partitionResponse = await post(createPlanApp(fixture.inputs, fixture.runtime), "partition-articles", {
      batch_id: selected.batch_id, strategy: "bin-pack", shards: 2,
    });
    expect(partitionResponse.status).toBe(200);
    const partition = PartitionResponseSchema.parse(await partitionResponse.json());
    expect(partition.dispatch_count).toBe(2);
    expect(partition.dispatches.map(row => row.selection)).toEqual(selected.selections);
    expect(partition.work.reduce((a, b) => a + b, 0)).toBe(
      selected.selections.reduce((sum, row) => sum + row.estimated_work, 0),
    );
    const persistedResponse = await post(createPlanApp(fixture.inputs, fixture.runtime), "persist-dispatches", {
      batch_id: partition.batch_id,
    });
    expect(persistedResponse.status).toBe(200);
    const persisted = PersistenceResponseSchema.parse(await persistedResponse.json());
    expect(persisted.files.status).toBe("written");
    const actual = [];
    for (const receipt of persisted.files.files) {
      const file = await readLedgerParquet(join(fixture.inputs.outputRoot, receipt.path), "article-dispatches", DispatchContract);
      expect(file.envelope.content_sha256).toBe(receipt.content_sha256);
      expect(file.rows.length).toBe(receipt.row_count);
      actual.push(...file.rows.map(row => row.row));
    }
    expect(actual).toEqual(partition.dispatches);
    expect(fixture.transport.requests.length).toBe(requests);
  } finally { await fixture.close(); }
}

async function verifyWholeBatchSelection() {
  const fixture = await recordedPlan();
  try {
    const plan = await runFeedPlan({ article_limit: 1, partition_strategy: "none" }, fixture.inputs, fixture.runtime);
    const original = await readStageBatch(fixture.inputs.outputRoot, "parsed",
      plan.batches.parsed_batch_id, ParsedFeedBatchSchema);
    const candidate = original.candidates[0]!;
    // A generated single-run batch proves input count is independent of output count.
    const candidates = Array.from({ length: 205 }, (_, index) => ({
      ...candidate, entry_ordinal: index, candidate_id: deriveCandidateId(candidate.run_id, candidate.source_id, index),
      ...(index === 0 ? { word_count: 0, article_text: "" } : {}),
    }));
    const batch = await writeStageBatch(fixture.inputs.outputRoot, "parsed", ParsedFeedBatchSchema, {
      ...original, batch_id: randomUUID(), candidates,
      observations: Object.fromEntries(candidates.map(row => [
        row.candidate_id, { ...original.observations[candidate.candidate_id], candidate_id: row.candidate_id },
      ])),
      evidence: {}, rejections: [],
    });
    const response = await post(createPlanApp(fixture.inputs, fixture.runtime), "select-articles", { batch_id: batch.batch_id });
    expect(response.status).toBe(200);
    const selected = SelectionResponseSchema.parse(await response.json());
    expect(selected.selections).toHaveLength(1);
    expect(selected.exclusions.some(row =>
      row.candidate_id === candidates[0]!.candidate_id && row.drop_reason === "STUB_CONTENT")).toBe(true);
    expect(selected.exclusions.length + selected.selections.length).toBe(candidates.length);
  } finally { await fixture.close(); }
}

async function verifyEmptyStages() {
  const fixture = await recordedPlan();
  try {
    const plan = await runFeedPlan({ partition_strategy: "none" }, fixture.inputs, fixture.runtime);
    const original = await readStageBatch(fixture.inputs.outputRoot, "parsed",
      plan.batches.parsed_batch_id, ParsedFeedBatchSchema);
    const batch = await writeStageBatch(fixture.inputs.outputRoot, "parsed", ParsedFeedBatchSchema, {
      ...original, batch_id: randomUUID(), candidates: [], observations: {}, evidence: {},
    });
    const app = createPlanApp(fixture.inputs, fixture.runtime);
    const selected = SelectionResponseSchema.parse(await (await post(app, "select-articles", { batch_id: batch.batch_id })).json());
    expect(selected.selections).toEqual([]);
    expect(selected.selection_state.capture_status).toBe("captured");
    expect(selected.exclusions).toEqual(original.rejections);
    const partition = PartitionResponseSchema.parse(await (await post(app, "partition-articles", {
      batch_id: selected.batch_id, strategy: "none",
    })).json());
    expect(partition.work).toEqual([0]);
    const persisted = PersistenceResponseSchema.parse(await (await post(app, "persist-dispatches", {
      batch_id: partition.batch_id,
    })).json());
    expect(persisted.files).toEqual({ status: "empty", files: [] });
  } finally { await fixture.close(); }
}

async function verifyStageFailures() {
  const fixture = await recordedPlan();
  try {
    const app = createPlanApp(fixture.inputs, fixture.runtime);
    for (const route of ["select-articles", "partition-articles", "persist-dispatches"]) {
      for (const body of [
        {}, { batch_id: "../outside" }, { batch_id: randomUUID(), path: "outside.json" },
        { batch_id: randomUUID(), request_id: randomUUID() },
        { batch_id: randomUUID(), articles: [] },
      ]) {
        const response = await post(app, route, body);
        expect(response.status).toBe(400);
        StageErrorResponseSchema.parse(await response.json());
      }
      expect((await post(app, route, { batch_id: randomUUID() })).status).toBe(404);
      expect((await app.request(`/api/2026-10-20/${route}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: "{",
      })).status).toBe(400);
      expect((await app.request(`/api/2026-10-20/${route}`, {
        method: "POST", body: " ".repeat(fixture.inputs.settings.listener.max_body_bytes + 1),
      })).status).toBe(413);
    }
    const plan = await runFeedPlan({ partition_strategy: "none" }, fixture.inputs, fixture.runtime);
    expect((await post(app, "partition-articles", { batch_id: plan.batches.parsed_batch_id })).status).toBe(404);
    expect((await post(app, "partition-articles", {
      batch_id: plan.batches.selection_batch_id, strategy: "none", shards: 2,
    })).status).toBe(400);
    const changed = createPlanApp(fixture.inputs, { ...fixture.runtime, git_sha: "b".repeat(40) });
    expect((await post(changed, "select-articles", { batch_id: plan.batches.parsed_batch_id })).status).toBe(409);
    const disabled = createPlanApp({
      ...fixture.inputs, settings: { ...fixture.inputs.settings, enabled: false },
    }, fixture.runtime);
    for (const route of ["select-articles", "partition-articles", "persist-dispatches"]) {
      expect((await post(disabled, route, { batch_id: plan.batches.parsed_batch_id })).status).toBe(503);
    }
    const selected = await readStageBatch(fixture.inputs.outputRoot, "selected",
      plan.batches.selection_batch_id, SelectedFeedBatchSchema);
    const selectionPath = join(fixture.inputs.outputRoot, "planner-batches", "selected", `${selected.batch_id}.json`);
    await writeFile(selectionPath, JSON.stringify({
      ...selected, context: { ...selected.context, captured_at: "2026-10-21T23:59:59.998Z" },
    }));
    expect((await post(app, "partition-articles", { batch_id: selected.batch_id })).status).toBe(500);
    await writeFile(selectionPath, JSON.stringify(selected));
    const batch = await readStageBatch(fixture.inputs.outputRoot, "partitioned",
      plan.batches.partition_batch_id, PartitionedFeedBatchSchema);
    const path = join(fixture.inputs.outputRoot, "planner-batches", "partitioned", `${batch.batch_id}.json`);
    await writeFile(path, JSON.stringify({ ...batch, batch_id: randomUUID() }));
    expect((await post(app, "persist-dispatches", { batch_id: batch.batch_id })).status).toBe(500);
    await writeFile(path, JSON.stringify({ ...batch, work: batch.work.map(value => value + 1) }));
    expect((await post(app, "persist-dispatches", { batch_id: batch.batch_id })).status).toBe(500);
    await writeFile(path, "{");
    expect((await post(app, "persist-dispatches", { batch_id: batch.batch_id })).status).toBe(500);
    await writeFile(path, JSON.stringify(batch));
    const dispatchDirectory = dirname(join(fixture.inputs.outputRoot, plan.files.dispatches.files[0]!.path));
    await rename(dispatchDirectory, `${dispatchDirectory}.saved`);
    await writeFile(dispatchDirectory, "not a directory");
    expect((await post(app, "persist-dispatches", { batch_id: batch.batch_id })).status).toBe(500);
  } finally { await fixture.close(); }
}

export async function verifyStageApis() {
  await verifySavedStageFlow();
  await verifyWholeBatchSelection();
  await verifyEmptyStages();
  await verifyStageFailures();
}
