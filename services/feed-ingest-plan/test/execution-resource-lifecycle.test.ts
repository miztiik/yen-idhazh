/** Do bounded execution owners await recorded transport disposal without closing sibling work? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { createPlanApp } from "../src/api/server";
import {
  currentExecutionState, documentState, registerStageExecution,
} from "../src/api/document-state";
import {
  beginCollection, cancelCollection, finalizeCollection, getCollection, releaseCollection,
} from "../src/api/collection-operation";
import { captureDocumentContext } from "../src/api/operation-context";
import { stageStore } from "../src/api/stage-store";
import { resolveRunContext } from "../src/resolve-run-context";
import { createBrowserRuntime } from "../src/harvest-feeds/browser-runtime";
import { harvestFeeds } from "../src/harvest-feeds/harvest-pool";
import { context as harvestContext, RecordedTransport } from "./harvest-recordings";
import { recordedPlan } from "./plan-recordings";

class DisposableRecordedTransport extends RecordedTransport {
  closes = 0;
  private releaseClose!: () => void;
  private readonly closing = new Promise<void>(resolve => { this.releaseClose = resolve; });
  private beginClose!: () => void;
  readonly closeStarted = new Promise<void>(resolve => { this.beginClose = resolve; });
  finishClose() { this.releaseClose(); }
  async close() {
    this.closes++;
    this.beginClose();
    await this.closing;
  }
}

test("direct harvesting awaits recorded transport cleanup without starting a supplied closed browser", async () => {
  const fixture = await recordedPlan();
  const transport = new DisposableRecordedTransport(fixture.transport.recordings);
  const browser = createBrowserRuntime(fixture.inputs.harvest.config.harvest.browser);
  await browser.close();
  let settled = false;
  const harvesting = harvestFeeds(fixture.inputs.harvest, harvestContext(), {
    transport, browser_runtime: browser,
  }).finally(() => { settled = true; });
  try {
    await transport.closeStarted;
    expect(settled).toBe(false);
    transport.finishClose();
    const result = await harvesting;
    expect(result.feed_outcomes).toHaveLength(1);
    expect(result.candidates.length).toBeGreaterThan(0);
    expect(transport.closes).toBe(1);
  } finally { transport.finishClose(); await harvesting; await fixture.close(); }
}, 120000);

test("execution eviction awaits disposal and does not evict active document work", async () => {
  const fixture = await recordedPlan();
  fixture.inputs.settings.listener.max_stage_batches = 1;
  const transport = new DisposableRecordedTransport(fixture.transport.recordings);
  const runtime = { ...fixture.runtime, boundary: { transport } };
  const context = resolveRunContext(fixture.inputs.settings, runtime.git_sha, runtime.clock!());
  const record = captureDocumentContext(randomUUID(), context.correlation_id, fixture.inputs, runtime, context);
  try {
    const state = await documentState(record, fixture.inputs, runtime);
    stageStore(fixture.inputs).retainRun(context.run_id);
    const next = resolveRunContext(fixture.inputs.settings, runtime.git_sha, runtime.clock!());
    await expect(registerStageExecution(fixture.inputs, next, "selection", null)).rejects.toMatchObject({
      code: "REQUEST_BUSY",
    });
    expect(transport.closes).toBe(0);
    stageStore(fixture.inputs).releaseRun(context.run_id);
    const eviction = registerStageExecution(fixture.inputs, next, "selection", null);
    await transport.closeStarted;
    expect(await currentExecutionState(fixture.inputs, context.run_id)).toBe(state);
    expect(currentExecutionState(fixture.inputs, next.run_id)).toBeUndefined();
    transport.finishClose();
    await eviction;
    expect(currentExecutionState(fixture.inputs, context.run_id)).toBeUndefined();
    expect((await currentExecutionState(fixture.inputs, next.run_id))?.kind).toBe("selection");
    expect(transport.closes).toBe(1);
  } finally { transport.finishClose(); await fixture.close(); }
});

test("only the last listener disposes execution fetchers and close remains awaited and idempotent", async () => {
  const fixture = await recordedPlan();
  const transport = new DisposableRecordedTransport(fixture.transport.recordings);
  const runtime = { ...fixture.runtime, boundary: { transport } };
  const first = createPlanApp(fixture.inputs, runtime);
  const second = createPlanApp(fixture.inputs, runtime);
  const context = resolveRunContext(fixture.inputs.settings, runtime.git_sha, runtime.clock!());
  const record = captureDocumentContext(randomUUID(), context.correlation_id, fixture.inputs, runtime, context);
  try {
    await documentState(record, fixture.inputs, runtime);
    await first.close();
    expect(transport.closes).toBe(0);
    const closing = second.close();
    await transport.closeStarted;
    expect(second.close()).toBe(closing);
    transport.finishClose();
    await closing;
    expect(transport.closes).toBe(1);
    await second.close();
    expect(transport.closes).toBe(1);
  } finally {
    transport.finishClose();
    await first.close();
    await second.close();
    await fixture.close();
  }
});

test("collection cancellation closes its fetcher before final accounting and release removes execution state", async () => {
  const fixture = await recordedPlan();
  const transport = new DisposableRecordedTransport(fixture.transport.recordings);
  const runtime = { ...fixture.runtime, boundary: { transport } };
  const collectionId = randomUUID();
  try {
    await beginCollection({ collection_id: collectionId, request: {} }, fixture.inputs, runtime);
    const collection = getCollection(fixture.inputs, collectionId);
    const cancelled = cancelCollection(fixture.inputs, collectionId);
    await transport.closeStarted;
    expect(collection.signal.signal.aborted).toBe(true);
    transport.finishClose();
    await cancelled;
    await finalizeCollection({
      collection_id: collectionId, failure_code: "PLANNER_EXECUTION_FAILED",
      collection_timing: { duration_ms: 0, status: "failed" },
    }, fixture.inputs);
    const request = { run_id: collection.context.run_id, attempt: collection.context.writer.attempt };
    expect(await releaseCollection(request, fixture.inputs)).toMatchObject({ released: true });
    expect(currentExecutionState(fixture.inputs, collection.context.run_id)).toBeUndefined();
    expect(await releaseCollection(request, fixture.inputs)).toMatchObject({ released: false });
    expect(transport.closes).toBe(1);
  } finally { transport.finishClose(); await fixture.close(); }
});
