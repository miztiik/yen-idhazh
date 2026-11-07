/** Do recorded run results preserve saved identities and report unsuccessful work honestly? */
import { expect, test } from "bun:test";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import {
  DiscoveredArticleRowContract, FeedHealthStateRowContract, PlanRunRowContract, RejectedArticleRowContract,
  SelectedArticleRowContract, SelectedFeedBatchSchema, SelectedArticlesArtifactSchema, selectedArticleMetadata,
  PlannerRunResponseSchema, createChildContext, createRootContext, readFeedIngestEvent, readTraceContext, PLANNER_API_PATHS, PLANNER_API_PREFIX, writeTraceContext,
} from "@idhazh/common-contracts";
import { FeedHealthStateUpdateResponseSchema } from "../src/api/feed-health-state.schema";
import { ServiceSettingsSchema } from "../src/config/service-settings";
import { resolveRunContext } from "../src/resolve-run-context";
import { runFeedPlan, summarizePlan } from "../src/run-feed-plan";
import type { FeedPlanResult } from "../src/run-feed-plan";
import { createPlanApp } from "../src/api/server";
import { SelectionResponseSchema, PartitionResponseSchema, PersistenceResponseSchema } from "../src/api/stage-response.schema";
import { FetchResponseSchema, ParseResponseSchema } from "../src/api/document-response.schema";
import { stageStore } from "../src/api/stage-store";
import { recordedPlan } from "./plan-recordings";
import { summarizeSelectionMetrics } from "../src/summarize-selection-metrics";
import { readPlannerDayFiles, readPlannerParquet } from "@idhazh/ledger-file-writer";
import { operationLink, operationMetadata } from "../src/api/operation-context";
import { beginCollection, collectionForRun, getCollection, prepareCollectionContext } from "../src/api/collection-operation";
import { CollectionResponseSchema, CompletedCollectionSchema, FinalizedCollectionSchema, ReleasedCollectionSchema } from "../src/api/collection-contracts";
import { source } from "./harvest-recordings";
import { projectSelectedArticle, restoreSelectedArticle } from "../src/api/article-identity-projection";

const recordings = new URL("../../../tests/fixtures/feed-ingest-plan/entry-points/", import.meta.url);

async function recordedResult() {
  const [response, artifact, rows, settings, health, discovered, selectedRows, rejected, healthRows, events] = await Promise.all([
    Bun.file(new URL("response.json", recordings)).json().then(value => PlannerRunResponseSchema.parse(value)),
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
    Bun.file(new URL("../report-events.json", recordings)).json()
      .then((value: unknown[]) => value.map(readFeedIngestEvent)),
  ]);
  if (rows.length !== 1) throw new Error("The entry-point recording must contain its one actual saved run row");
  const planEvent = events.find(event => event.data.run_id === response.run_id
    && event.data.operation === "plan" && event.data.phase === "started");
  if (planEvent === undefined) throw new Error("The entry-point recording omitted its actual planning operation");
  const operation = readTraceContext({ traceparent: planEvent.traceparent, tracestate: planEvent.tracestate });
  if (operation === undefined || operation.traceId !== response.traceId) {
    throw new Error("The saved response and recorded planning operation must belong to the same execution");
  }
  const context = resolveRunContext(settings, "a".repeat(40), new Date(response.evaluated_at),
    response.run_id.slice(11), operation, undefined, response.attempt);
  const selected = selectedRows;
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
    result: { context, row: rows[0]!, files, selected, health: response.health,
      include_selected_urls: response.include_selected_urls } satisfies FeedPlanResult,
  };
}

test("one recorded saved run agrees with its public summary and selected identities", async () => {
  const { response, artifact, result, health, nativeRows } = await recordedResult();
  expect(result.row.run_id).toBe(artifact.run_id);
  expect(result.row.attempt).toBe(artifact.attempt);
  expect(result.row.selected_count).toBe(artifact.articles.length);
  expect(result.row.selection_metrics).toEqual(summarizeSelectionMetrics(artifact.articles, true));
  const summary = PlannerRunResponseSchema.parse(summarizePlan(result));
  expect(summary).toEqual(response);
  expect(result.selected.every(article => !("article_text" in article))).toBe(true);
  expect(health.rows).toEqual(nativeRows.feed_health_state);
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
  ]) expect(PlannerRunResponseSchema.safeParse(invalid).success).toBe(false);
});

test("URL display projects the same captured rows without changing selection or persisted data", async () => {
  const { result, nativeRows } = await recordedResult();
  const original = structuredClone({ result, nativeRows });
  for (const partitionEnabled of [true, false]) {
    const captured: FeedPlanResult = partitionEnabled ? result : {
      ...result, row: { ...result.row, dispatch_count: 0, strategy: "none" },
      selected: result.selected.map(row => ({ ...row, worker_assignment: null })),
    };
    const hidden = summarizePlan({ ...captured, include_selected_urls: false });
    const shown = summarizePlan({ ...captured, include_selected_urls: true });
    expect(hidden.selected_article_ids).toEqual(shown.selected_article_ids);
    expect(hidden.assignments).toEqual(shown.assignments.map(({ canonical_url: _url, ...assignment }) => assignment));
    expect(shown.assignments.map(row => row.canonical_url)).toEqual(captured.selected.map(row => row.canonical_url));
    expect(hidden.assignments.every(row => !Object.hasOwn(row, "canonical_url"))).toBe(true);
    expect(shown.files).toEqual(hidden.files);
    expect(shown.selection_metrics).toEqual(hidden.selection_metrics);
    expect(shown.selected_count).toBe(hidden.selected_count);
  }
  expect({ result, nativeRows }).toEqual(original);
});

test("uncertain collection startup uses its preallocated trace to recover ownership and release", async () => {
  for (const corruption of [
    "truncated", "foreign-execution", "unreadable-lookup", "unreadable-lookup-and-release",
    "cancelled-before-admission", "cancelled-preparation",
  ] as const) {
    const fixture = await recordedPlan();
    const app = createPlanApp(fixture.inputs, fixture.runtime);
    const cancellation = new AbortController();
    const expectedRun = resolveRunContext(fixture.inputs.settings, fixture.runtime.git_sha, fixture.runtime.clock!(),
      fixture.runtime.run_number, createRootContext()).run_id;
    let started: ReturnType<typeof CollectionResponseSchema.parse> | undefined;
    let startupRequest: Promise<Response> | undefined;
    let lookupTrace: string | undefined;
    let receiveStartup!: () => void;
    let releaseStartup!: () => void;
    const receivedStartup = new Promise<void>(resolve => { receiveStartup = resolve; });
    const startupGate = new Promise<void>(resolve => { releaseStartup = resolve; });
    let receivedCancellation = false;
    const paths: string[] = [];
    const terminal: { held: boolean; active: boolean }[] = [];
    const unreadableLookup = corruption.startsWith("unreadable-lookup");
    const server = Bun.serve({
      hostname: "127.0.0.1", port: 0, idleTimeout: 0,
      async fetch(request) {
        const path = new URL(request.url).pathname.slice(PLANNER_API_PREFIX.length);
        paths.push(path);
        if (path === PLANNER_API_PATHS.checkCollection) lookupTrace = (await request.clone().json()).traceId;
        const pending = (async () => {
          if (path === PLANNER_API_PATHS.startCollection && corruption === "cancelled-before-admission") {
            receiveStartup();
            await startupGate;
            receivedCancellation = request.signal.aborted;
          }
          return app.fetch(request);
        })();
        let responsePromise = pending;
        if (path === PLANNER_API_PATHS.startCollection) {
          responsePromise = pending.then(async response => {
            if (response.ok) started = CollectionResponseSchema.parse(await response.clone().json());
            return response;
          });
          startupRequest = responsePromise;
        }
        if (path === PLANNER_API_PATHS.startCollection && corruption === "cancelled-preparation") {
          let settled = false;
          const admitted = pending.finally(() => { settled = true; });
          while (!stageStore(fixture.inputs).isRunActive(expectedRun) && !settled) await Bun.sleep(0);
          expect(stageStore(fixture.inputs).isRunActive(expectedRun)).toBe(true);
          expect(collectionForRun(fixture.inputs, expectedRun)).toBeUndefined();
          cancellation.abort();
          await admitted;
        }
        const response = await responsePromise;
        if (path === PLANNER_API_PATHS.startCollection && response.ok) {
          if (corruption === "cancelled-preparation") return response;
          return new Response(corruption === "foreign-execution"
            ? JSON.stringify({ ...started, traceId: createRootContext().traceId })
            : (await response.text()).slice(0, -1),
          { status: response.status, headers: response.headers });
        }
        if (response.ok && ((path === PLANNER_API_PATHS.checkCollection && unreadableLookup)
          || (path === PLANNER_API_PATHS.releaseCollection && corruption === "unreadable-lookup-and-release"))) {
          return new Response((await response.text()).slice(0, -1), { status: response.status, headers: response.headers });
        }
        return response;
      },
    });
    try {
      const running = runFeedPlan({}, fixture.inputs, { ...fixture.runtime,
        stage_origin: `http://127.0.0.1:${server.port}`, signal: cancellation.signal, log(event) {
          fixture.runtime.log?.(event);
          if (event.data.operation === "plan" && event.data.phase !== "started") {
            paths.push("terminal");
            terminal.push({
              held: collectionForRun(fixture.inputs, event.data.run_id) !== undefined,
              active: stageStore(fixture.inputs).isRunActive(event.data.run_id),
            });
          }
        } });
      if (corruption === "cancelled-before-admission") {
        await receivedStartup;
        cancellation.abort();
      }
      const result = await running;
      releaseStartup();
      const startupReply = await startupRequest;
      expect(lookupTrace).toBe(result.context.traceId);
      expect(result.row.status).toBe("failed");
      expect(result.row.selected_count).toBe(0);
      expect(result.selected).toEqual([]);
      expect(result.health).toBeNull();
      expect(result.failure?.error_type).toBe(corruption === "foreign-execution" ? "PlanError"
        : corruption.startsWith("cancelled-") ? "AbortError" : "SyntaxError");
      expect(result.failure?.operation).toBe("collection-start");
      if (unreadableLookup) {
        expect(result.failure?.causes.some(cause => cause.operation === "collection-start")).toBe(true);
        expect(result.failure!.causes.length).toBeLessThanOrEqual(fixture.inputs.settings.diagnostics.failure.max_causes);
        expect(result.failure?.omitted_causes).toBe(0);
      }
      if (corruption === "unreadable-lookup-and-release") {
        expect(result.failure?.causes).toContainEqual(expect.objectContaining({
          operation: "collection-release", error_type: "SyntaxError",
        }));
      }
      if (corruption === "cancelled-before-admission") {
        expect(receivedCancellation).toBe(true);
        expect(startupReply?.ok).toBe(false);
        expect(started).toBeUndefined();
        expect(paths).toEqual([PLANNER_API_PATHS.startCollection, PLANNER_API_PATHS.checkCollection, "terminal"]);
        expect(result.files.feed_health_state).toBeUndefined();
      } else {
        expect(started?.traceId).toBe(result.context.traceId);
        expect(started?.spanId).not.toBe(result.context.spanId);
        expect(paths).toEqual([PLANNER_API_PATHS.startCollection, PLANNER_API_PATHS.checkCollection, PLANNER_API_PATHS.cancelCollection,
          PLANNER_API_PATHS.updateFeedHealth, PLANNER_API_PATHS.finalizeCollection, PLANNER_API_PATHS.releaseCollection, "terminal"]);
        expect(result.files.feed_health_state?.status).toBe("written");
      }
      expect(terminal).toEqual([{ held: false, active: false }]);
      expect(fixture.transport.requests).toHaveLength(0);
      expect(collectionForRun(fixture.inputs, result.context.run_id)).toBeUndefined();
      expect(stageStore(fixture.inputs).isRunActive(result.context.run_id)).toBe(false);
    } finally { releaseStartup(); await server.stop(true); await app.close(); await fixture.close(); }
  }
}, 120000);

async function completeHeldCollection(fixture: Awaited<ReturnType<typeof recordedPlan>>, traceId: string) {
  const collection = getCollection(fixture.inputs, traceId);
  const app = createPlanApp(fixture.inputs, fixture.runtime);
  const server = Bun.serve({ hostname: "127.0.0.1", port: 0, idleTimeout: 0, fetch: app.fetch });
  const started = performance.now();
  async function post(path: string, body: unknown) {
    const response = await fetch(`http://127.0.0.1:${server.port}${PLANNER_API_PREFIX}${path}`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
    });
    const value: unknown = await response.json();
    if (!response.ok) throw new Error(`Held collection ${path} failed with HTTP ${response.status}: ${JSON.stringify(value)}`);
    return value;
  }
  try {
    for (const feedId of collection.feeds.keys()) {
      const fetched = FetchResponseSchema.parse(await post(PLANNER_API_PATHS.fetch, { traceId, feed_id: feedId, fetch_item_type: "feed" }));
      const parsed = ParseResponseSchema.parse(await post(PLANNER_API_PATHS.parse, { links: [operationLink(fetched)] }));
      if (parsed.fetch_item_type !== "feed") throw new Error("The held collection must parse its recorded feed");
      for (const offer of parsed.offers) {
        const article = FetchResponseSchema.parse(await post(PLANNER_API_PATHS.fetch, {
          fetch_item_type: "article", links: [operationLink(parsed)], candidate_id: offer.candidate_id,
        }));
        if (article.body_sha256 !== null) await post(PLANNER_API_PATHS.parse, { links: [operationLink(article)] });
      }
    }
    const completed = CompletedCollectionSchema.parse(await post(PLANNER_API_PATHS.completeCollection, { traceId }));
    const selected = SelectionResponseSchema.parse(await post(PLANNER_API_PATHS.selectArticles, { links: [operationLink(completed)] }));
    const persisted = PersistenceResponseSchema.parse(await post(PLANNER_API_PATHS.persistSelectedArticles, { links: [operationLink(selected)] }));
    expect(selected.run_id).toBe(collection.context.run_id);
    expect(persisted.selected_count).toBeGreaterThan(0);
    expect(persisted.selected_count).toBe(selected.articles.length);
    expect(FinalizedCollectionSchema.parse(await post(PLANNER_API_PATHS.finalizeCollection, {
      traceId, failure_code: null,
      collection_timing: { duration_ms: Math.round(performance.now() - started), status: "completed" },
    })).status).toBe("completed");
    expect(ReleasedCollectionSchema.parse(await post(PLANNER_API_PATHS.releaseCollection, {
      run_id: collection.context.run_id, attempt: collection.context.writer.attempt,
    })).released).toBe(true);
    expect(stageStore(fixture.inputs).isRunActive(collection.context.run_id)).toBe(false);
  } finally { await server.stop(true); await app.close(); }
}

test("a rejected plan cannot take another operation's collection or write over its run", async () => {
  for (const sameTrace of [true, false]) {
    const fixture = await recordedPlan();
    fixture.inputs.harvest.config.partition.enabled = false;
    const caller = createRootContext();
    try {
      const first = await beginCollection({ request: {} }, fixture.inputs, { ...fixture.runtime, ...createChildContext(caller) });
      const original = getCollection(fixture.inputs, first.traceId);
      await expect(runFeedPlan({}, fixture.inputs, {
        ...fixture.runtime, ...(sameTrace ? createChildContext(caller) : createRootContext()),
      })).rejects.toMatchObject({ code: "REQUEST_CONFLICT" });
      expect(getCollection(fixture.inputs, first.traceId)).toBe(original);
      expect(original.status).toBe("collecting");
      expect(original.signal.signal.aborted).toBe(false);
      expect(original.closing).toBe(false);
      expect(original.finalization).toBeUndefined();
      expect(stageStore(fixture.inputs).isRunActive(first.context.run_id)).toBe(true);
      expect(fixture.transport.requests).toHaveLength(0);
      expect((await readPlannerDayFiles(fixture.inputs.root, fixture.inputs.registrations.plan_runs, first.context.date)).members).toEqual([]);
      await completeHeldCollection(fixture, first.traceId);
      expect(collectionForRun(fixture.inputs, first.context.run_id)).toBeUndefined();
    } finally { await fixture.close(); }
  }
}, 120000);

test("a rejected overlapping startup cannot discard or consume another operation's prepared context", async () => {
  const fixture = await recordedPlan();
  fixture.inputs.harvest.config.partition.enabled = false;
  const caller = createRootContext();
  const context = resolveRunContext(fixture.inputs.settings, fixture.runtime.git_sha, fixture.runtime.clock!(),
    fixture.runtime.run_number, createChildContext(caller));
  try {
    prepareCollectionContext(fixture.inputs, context);
    for (const operation of [createChildContext(caller), operationMetadata(context)]) {
      await expect(runFeedPlan({}, fixture.inputs, { ...fixture.runtime, ...operation }))
        .rejects.toMatchObject({ code: "REQUEST_CONFLICT" });
    }
    await expect(beginCollection({ request: {} }, fixture.inputs, { ...fixture.runtime, ...createChildContext(caller) }))
      .rejects.toMatchObject({ code: "REQUEST_CONFLICT" });
    const first = await beginCollection({ request: {} }, fixture.inputs, {
      ...fixture.runtime, ...createChildContext(operationMetadata(context)), run_number: "701",
    });
    expect(first.context.run_id).toBe(context.run_id);
    expect(first.parentSpanId).toBe(context.spanId);
    expect((await readPlannerDayFiles(fixture.inputs.root, fixture.inputs.registrations.plan_runs, context.date)).members).toEqual([]);
    await completeHeldCollection(fixture, first.traceId);
  } finally { await fixture.close(); }
}, 120000);

test("real stage responses supply saved timestamps and metadata to orchestration", async () => {
  for (const enabled of [true, false]) {
    const fixture = await recordedPlan();
    fixture.inputs.harvest.config.partition.enabled = enabled;
    fixture.runtime.selection_clock = () => new Date("2026-10-22T00:01:00Z");
    const app = createPlanApp(fixture.inputs, fixture.runtime);
    let selection: ReturnType<typeof SelectionResponseSchema.parse> | undefined;
    let partition: ReturnType<typeof PartitionResponseSchema.parse> | undefined;
    let persistenceInput: unknown;
    const server = Bun.serve({
      hostname: "127.0.0.1", port: 0, idleTimeout: 0,
      async fetch(request) {
        const path = new URL(request.url).pathname;
        if (path === `${PLANNER_API_PREFIX}${PLANNER_API_PATHS.persistSelectedArticles}`) {
          persistenceInput = await request.clone().json();
        }
        const response = await app.fetch(request);
        if (response.ok && path === `${PLANNER_API_PREFIX}${PLANNER_API_PATHS.selectArticles}`) {
          selection = SelectionResponseSchema.parse(await response.clone().json());
          const batch = stageStore(fixture.inputs).read("selected", selection, SelectedFeedBatchSchema);
          expect(selection.selection_started_at_utc).toBe(batch.selection_started_at_utc);
          expect(selection.evaluated_at).toBe(batch.evaluated_at);
          expect(selection.articles).toEqual(batch.articles.map(article => projectSelectedArticle({
            ...selectedArticleMetadata(article), run_id: article.run_id, attempt: article.attempt, date: article.date,
          })));
          expect(batch.articles.every(article => article.article_text.length > 0)).toBe(true);
          expect(SelectionResponseSchema.safeParse({ ...selection, articles: batch.articles }).success).toBe(false);
        }
        if (response.ok && path === `${PLANNER_API_PREFIX}${PLANNER_API_PATHS.partitionArticles}`) {
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
      expect(result.row.selection_metrics).toEqual(summarizeSelectionMetrics(selection!.articles.map(restoreSelectedArticle), true));
      expect(result.selected).toEqual((enabled ? partition : selection)!.articles.map(restoreSelectedArticle));
      expect(persistenceInput).toEqual({ links: [operationLink((enabled ? partition : selection)!)] });
      if (enabled) {
        expect(partition).toBeDefined();
        expect(partition!.links).toEqual([operationLink(selection!)]);
        expect(result.row.strategy).toBe(partition!.strategy);
        expect(result.row.dispatch_count).toBe(partition!.dispatch_count);
      } else {
        expect(partition).toBeUndefined();
        expect(result.row.strategy).toBe("none");
        expect(result.row.dispatch_count).toBe(0);
        expect(result.selected.every(article => article.worker_assignment === null)).toBe(true);
      }
      expect(PlannerRunResponseSchema.parse(summarizePlan(result)).assignments).toEqual(result.selected.map(article => ({
        article_id: article.url_key, editorial_rank: article.editorial_rank, worker_assignment: article.worker_assignment,
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
    expect(result.row.selection_metrics).toEqual({
      selected_website_groups: 0, selected_feeds: 0, mean_substance_score: null,
    });
    expect(result.selected).toEqual([]);
    expect(result.row.selection_started_at_utc).toBe("2026-10-22T00:01:00Z");
    expect(result.row.evaluated_at).toBe(result.context.now);
    expect(result.files.selected_articles).toEqual({ status: "empty", files: [] });
    expect(result.row.selected_articles_artifact).not.toBeNull();
    expect(result.row.api_timings.filter(timing => timing.operation === "fetch")).toHaveLength(1);
    expect(result.row.api_timings.find(timing => timing.operation === "fetch")).toMatchObject({ status: "completed" });
    expect(PlannerRunResponseSchema.parse(summarizePlan(result)).assignments).toEqual([]);
  } finally { await fixture.close(); }
});

test("cancelled startup and partial work do not invent a completed report input", async () => {
  for (const beforeFetch of [true, false]) {
  const fixture = await recordedPlan();
  const cancellation = new AbortController();
  if (beforeFetch) cancellation.abort(new Error("Recorded cancellation before source work"));
  try {
    const result = await runFeedPlan({}, fixture.inputs, {
      ...fixture.runtime, signal: cancellation.signal,
      progress: event => {
        if (event.eventType === "FEED_FETCH_COMPLETED") cancellation.abort(new Error("Recorded cancellation after feed parsing"));
      },
    });
    expect(result.row.status).toBe(beforeFetch ? "failed" : "partial");
    expect(result.row.selection_metrics).toBeNull();
    expect(result.row.selected_count).toBe(0);
    expect(result.row.selection_started_at_utc).toBeNull();
    expect(result.selected).toEqual([]);
    expect(result.health).toBeNull();
    expect(collectionForRun(fixture.inputs, result.row.run_id)).toBeUndefined();
    expect(stageStore(fixture.inputs).isRunActive(result.row.run_id)).toBe(false);
    if (!beforeFetch) expect(result.files.feed_health_state?.status).toBe("written");
    const native = await readPlannerParquet(join(fixture.inputs.outputRoot, result.files.plan_runs!.files[0]!.path),
      "plan-runs", PlanRunRowContract);
    expect(native.rows).toEqual([result.row]);
  } finally { await fixture.close(); }
  }
});

test("health and selected persistence failures preserve the independent successful output", async () => {
  for (const blocked of ["feed-health-state", "selected-articles"] as const) {
    const fixture = await recordedPlan();
    fixture.inputs.harvest.config.partition.enabled = false;
    const app = createPlanApp(fixture.inputs, fixture.runtime);
    const server = Bun.serve({
      hostname: "127.0.0.1", port: 0, idleTimeout: 0,
      async fetch(request, server) {
        const response = await app.fetch(request, { beginPlanning: () => server.timeout(request, 0),
          stage_origin: `http://127.0.0.1:${server.port}` });
        if (response.ok && new URL(request.url).pathname === `${PLANNER_API_PREFIX}${PLANNER_API_PATHS.selectArticles}`) {
          const obstruction = join(fixture.inputs.outputRoot, "raw", "feed-ingest-plan", blocked);
          await mkdir(dirname(obstruction), { recursive: true });
          await writeFile(obstruction, "recorded obstruction");
        }
        return response;
      },
    });
    try {
      const result = await runFeedPlan({}, fixture.inputs, {
        ...fixture.runtime, stage_origin: `http://127.0.0.1:${server.port}`,
      });
      expect(result.row.status).toBe("partial");
      expect(result.row.failure_code).not.toBeNull();
      expect(result.row.selected_count).toBeGreaterThan(0);
      expect(result.row.selection_metrics).toEqual(summarizeSelectionMetrics(result.selected, true));
      expect(result.health?.status).toBe("summarized");
      expect(collectionForRun(fixture.inputs, result.row.run_id)).toBeUndefined();
      const readback = await readPlannerParquet(join(fixture.inputs.outputRoot, result.files.plan_runs!.files[0]!.path),
        "plan-runs", PlanRunRowContract);
      expect(readback.rows).toEqual([result.row]);
      if (blocked === "feed-health-state") {
        expect(result.files.feed_health_state).toBeUndefined();
        expect(result.files.selected_articles?.status).toBe("written");
      } else {
        expect(result.files.feed_health_state?.status).toBe("written");
        expect(result.files.selected_articles).toBeUndefined();
      }
    } finally { await server.stop(true); await app.close(); await fixture.close(); }
  }
}, 120000);

test("a completed parsed collection supplies the report when actual selection fails", async () => {
  const fixture = await recordedPlan();
  const app = createPlanApp(fixture.inputs, fixture.runtime);
  let completedInput: ReturnType<typeof operationLink> | undefined;
  const server = Bun.serve({
    hostname: "127.0.0.1", port: 0, idleTimeout: 0,
    async fetch(request) {
      const path = new URL(request.url).pathname;
      const previous = fixture.runtime.selection_clock;
      if (path.endsWith(PLANNER_API_PATHS.selectArticles)) fixture.runtime.selection_clock = () => new Date(Number.NaN);
      try {
        const response = await app.fetch(request);
        if (path.endsWith(PLANNER_API_PATHS.completeCollection) && response.ok) {
          completedInput = operationLink(await response.clone().json());
        }
        return response;
      } finally {
        if (previous === undefined) delete fixture.runtime.selection_clock;
        else fixture.runtime.selection_clock = previous;
      }
    },
  });
  try {
    const result = await runFeedPlan({}, fixture.inputs, {
      ...fixture.runtime, stage_origin: `http://127.0.0.1:${server.port}`,
    });
    expect(result.row.status).toBe("partial");
    expect(result.row.selected_count).toBe(0);
    expect(result.row.selection_metrics).toBeNull();
    expect(result.failure?.error_type).toBe("RangeError");
    expect(result.health?.status).toBe("summarized");
    if (result.health?.status !== "summarized") throw new Error("Completed collection report was not captured");
    expect(result.health.links).toEqual([completedInput!]);
    expect(result.health.rows.reduce((total, row) => total + row.feed_requests!, 0)).toBe(1);
    expect(result.health.rows.reduce((total, row) => total + row.article_requests!, 0)).toBe(2);
    expect(result.health.rows.some(row => row.article_candidates! > 0)).toBe(true);
    expect(collectionForRun(fixture.inputs, result.row.run_id)).toBeUndefined();
    expect(stageStore(fixture.inputs).isRunActive(result.row.run_id)).toBe(false);
  } finally { await server.stop(true); await app.close(); await fixture.close(); }
});

test("offered articles start before another feed finishes and an independent collection stays isolated", async () => {
  const slow = source({ id: "recorded-slow", url: "https://slow.example/feed.xml" });
  const fixture = await recordedPlan([source(), slow]);
  delete fixture.runtime.run_number;
  fixture.inputs.harvest.config.harvest.fetch_timeout_ms = 30_000;
  fixture.transport.recordings.responses[slow.url] = [{ status: 200, fixture: "atom" }];
  let releaseFeed!: () => void;
  const unfinishedFeed = new Promise<void>(resolve => { releaseFeed = resolve; });
  let slowStarted = false;
  let slowFinished = false;
  let articleOverlapped = false;
  fixture.runtime.boundary = { transport: {
    request: async request => {
      if (request.url.href === slow.url) { slowStarted = true; await unfinishedFeed; }
      const result = await fixture.transport.request(request);
      if (request.url.href === slow.url) slowFinished = true;
      return result;
    },
  } };
  fixture.transport.on_request = request => {
    if (request.url.pathname === "/story/" || request.url.pathname === "/second") {
      articleOverlapped ||= slowStarted && !slowFinished;
      releaseFeed();
    }
  };
  const app = createPlanApp(fixture.inputs, fixture.runtime);
  const server = Bun.serve({ hostname: "127.0.0.1", port: 0, idleTimeout: 0, fetch: app.fetch });
  const origin = `http://127.0.0.1:${server.port}`;
  const otherCaller = createRootContext();
  const post = (path: string, body: unknown) => fetch(`${origin}${PLANNER_API_PREFIX}${path}`, {
    method: "POST", headers: { "content-type": "application/json", ...writeTraceContext(otherCaller) },
    body: JSON.stringify(body),
  });
  try {
    const begun = await post(PLANNER_API_PATHS.startCollection, { request: {} });
    expect(begun.status).toBe(200);
    const other = CollectionResponseSchema.parse(await begun.json());
    const independent = getCollection(fixture.inputs, other.traceId);
    const baseline = structuredClone(independent.state.baseline);
    const result = await runFeedPlan({}, fixture.inputs, { ...fixture.runtime, stage_origin: origin });
    expect(result.row.status).toBe("completed");
    expect(articleOverlapped).toBe(true);
    expect(slowFinished).toBe(true);
    expect(result.health?.status).toBe("summarized");
    expect(collectionForRun(fixture.inputs, result.row.run_id)).toBeUndefined();
    expect(result.context.traceId).not.toBe(other.traceId);
    expect(result.context.run_id).not.toBe(other.context.run_id);
    expect(getCollection(fixture.inputs, other.traceId)).toBe(independent);
    expect(independent.status).toBe("collecting");
    expect([...independent.feeds.values()].every(feed => feed.state === "pending")).toBe(true);
    expect(independent.state.baseline).toEqual(baseline);
    expect(stageStore(fixture.inputs).isRunActive(other.context.run_id)).toBe(true);
    expect((await post(PLANNER_API_PATHS.cancelCollection, { traceId: other.traceId })).status).toBe(200);
    expect((await post(PLANNER_API_PATHS.finalizeCollection, {
      traceId: other.traceId, failure_code: "PLANNER_EXECUTION_FAILED",
      collection_timing: { duration_ms: 0, status: "failed" },
    })).status).toBe(200);
    expect((await post(PLANNER_API_PATHS.releaseCollection, {
      run_id: other.context.run_id, attempt: other.context.writer.attempt,
    })).status).toBe(200);
  } finally { releaseFeed(); await server.stop(true); await app.close(); await fixture.close(); }
}, 120000);

test("partial and failed result models cannot claim completion or lose their failure cause", async () => {
  const { result } = await recordedResult();
  const original = structuredClone(result);
  for (const status of ["partial", "failed"] as const) {
    const row = PlanRunRowContract.schema.parse({
      ...result.row, status, failure_code: "PERSIST_FAILED",
      ...(status === "failed" ? {
        selected_count: 0, selection_metrics: null, dispatch_count: 0, selected_articles_artifact: null, selection_started_at_utc: null,
      } : {}),
    });
    const summary = PlannerRunResponseSchema.parse(summarizePlan({
      ...result, row, selected: status === "failed" ? [] : result.selected,
    }));
    expect(summary.planning_complete).toBe(false);
    expect(summary.status).toBe(status);
    expect(summary.failure_code).toBe(row.failure_code);
    expect(PlannerRunResponseSchema.safeParse({ ...summary, planning_complete: true }).success).toBe(false);
    expect(PlannerRunResponseSchema.safeParse({ ...summary, failure_code: null }).success).toBe(false);
  }
  expect(result).toEqual(original);
});
