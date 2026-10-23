/** Does the real Hono handler reject invalid requests before recorded harvesting? */
import { expect, test } from "bun:test";
import { fileURLToPath } from "node:url";
import { createPlanApp } from "../src/api/server";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { RecordedTransport, readRecordings } from "./harvest-recordings";
import { recordedPlan } from "./plan-recordings";
import { main } from "../src/index";
import { mkdir, mkdtemp, rm, unlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import type { PersistedLedgerFile } from "@idhazh/ledger-file-writer";
import { readLedgerParquet } from "../src/read-ledger-history/read-parquet";
import { SeenRowSchema } from "../src/screen-article-candidates/seen-evidence";
import { source } from "./harvest-recordings";
import { existsSync } from "node:fs";
import { readPlanningHistory } from "../src/metrics/planning-populations";
import { selectCompleteAttempt } from "../src/read-ledger-history/complete-attempt";
import {
  ArticleAssessmentContract, DiversityMetricContract, SourceRunContract,
} from "../src/metrics/audit-contracts";
import { randomUUID } from "node:crypto";
import { openOperationStore } from "../src/api/operation-store";
import { proposedOperation } from "../src/api/document-operations";
import { FetchRequestSchema } from "../src/api/operation-contracts";
import type { FeedWriteReceipt } from "../src/read-ledger-history/own-feed-receipts";

test("health is explicit; disabled, malformed, oversized and unknown controls cannot fetch", async () => {
  const inputs = await loadPlanInputs(fileURLToPath(new URL("../../../", import.meta.url)));
  const transport = new RecordedTransport(await readRecordings());
  const app = createPlanApp(inputs, {
    git_sha: "a".repeat(40), boundary: { transport, resolve: transport.resolve },
  });

  const health = await app.request("/api/2026-10-20/health");
  expect(health.status).toBe(200);
  expect(await health.json()).toEqual({
    status: "available", planner_enabled: false, audited_completion_available: false,
  });
  const post = (body: string) => app.request("/api/2026-10-20/plan", {
    method: "POST", headers: { "Content-Type": "application/json" }, body,
  });
  const disabled = await post("{}");
  expect(disabled.status).toBe(503);
  expect((await disabled.json()).code).toBe("PLANNER_DISABLED");
  for (const request of [
    { freshness_hours: "18" }, { article_limit: null }, { shards: 1.5 },
    { date: "2026-10-21" }, { freshness_hours: 0 }, { partition_strategy: "random" },
    { partition_strategy: "none", shards: 2 }, { shards: inputs.harvest.config.partition.max_shards + 1 },
  ]) {
    const refused = await post(JSON.stringify(request));
    expect(refused.status).toBe(400);
    expect((await refused.json()).issues.length).toBeGreaterThan(0);
  }
  const malformed = await post("{");
  expect(malformed.status).toBe(400);
  expect((await malformed.json()).issues[0].field).toBe("body");
  const oversized = await post(" ".repeat(inputs.settings.listener.max_body_bytes + 1));
  expect(oversized.status).toBe(413);
  expect((await oversized.json()).code).toBe("BODY_TOO_LARGE");
  expect((await app.request("/api/old/health")).status).toBe(404);
  expect(transport.requests).toHaveLength(0);
  expect(() => createPlanApp(inputs, {
    git_sha: "a".repeat(40),
    feed_history_receipts: [{ ledger: "feed-health", day: "2026-10-21", files: ["../outside.parquet"] }],
  })).toThrow("relative POSIX");
  for (const route of ["fetch", "parse"]) {
    expect((await app.request(`/api/2026-10-20/${route}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{",
    })).status).toBe(400);
    expect((await app.request(`/api/2026-10-20/${route}`, {
      method: "POST", body: " ".repeat(inputs.settings.listener.max_body_bytes + 1),
    })).status).toBe(413);
  }
  const disabledFetch = await app.request("/api/2026-10-20/fetch", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request_id: randomUUID(), correlation_id: randomUUID(), source_id: "recorded-news", kind: "feed" }),
  });
  expect(disabledFetch.status).toBe(503);
  expect(transport.requests).toHaveLength(0);
});

test("actual API and awaited CLI compose the same recorded plan and disclose the same audit limit", async () => {
  const api = await recordedPlan();
  const cli = await recordedPlan();
  try {
    const app = createPlanApp(api.inputs, api.runtime);
    const key = randomUUID();
    const response = await app.request("/api/2026-10-20/plan", {
      method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": key },
      body: JSON.stringify({ freshness_hours: 18, article_limit: 1, partition_strategy: "none" }),
    });
    expect(response.status).toBe(200);
    const apiResult = await response.json();
    const requestCount = api.transport.requests.length;
    const restarted = createPlanApp(api.inputs, api.runtime);
    const replayed = await restarted.request("/api/2026-10-20/plan", {
      method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": key },
      body: JSON.stringify({ freshness_hours: 18, article_limit: 1, partition_strategy: "none" }),
    });
    expect(replayed.status).toBe(200);
    expect(await replayed.json()).toEqual(apiResult);
    expect(api.transport.requests).toHaveLength(requestCount);
    const printed: unknown[] = [];
    const cliResult = await main([
      "--cli", "--freshness-hours", "18", "--article-limit=1", "--partition-strategy", "none",
    ], { inputs: cli.inputs, runtime: cli.runtime, output: value => { printed.push(value); } });
    if (!("audited_complete" in cliResult)) throw new Error("CLI unexpectedly started a server");
    expect(cliResult.audited_complete).toBe(false);
    expect(cliResult.planning_complete).toBe(true);
    expect(cliResult.status).toBe("planning_complete_audit_pending");
    expect(printed).toEqual([cliResult]);
    for (const field of ["run_id", "correlation_id", "date", "observed_at", "request",
      "strategy", "dispatch_count", "selected_candidate_ids", "assignments", "audit", "status"] as const) {
      expect(apiResult[field]).toEqual(cliResult[field]);
    }
    expect(apiResult.files.dispatches.status).toBe("written");
    expect(cliResult.files.dispatches.status).toBe("written");
    expect(api.transport.requests.length).toBeGreaterThan(0);
    expect(cli.transport.requests.map(request => request.url.href)).toEqual(api.transport.requests.map(request => request.url.href));
    expect(apiResult).not.toHaveProperty("article_text");
    expect(JSON.stringify(apiResult)).not.toContain(api.directory);
    expect(apiResult.audit.status).toBe("assessment_diversity_recorded_audit_pending");
    for (const summary of [apiResult, cliResult]) {
      expect(summary.metrics.audited_complete).toBe(false);
      expect(summary.metrics.status).toBe("assessment_diversity_recorded_audit_pending");
      expect(summary.metrics.source_summaries).toHaveLength(1);
    }
    for (const [recorded, summary] of [[api, apiResult], [cli, cliResult]] as const) {
      const metrics = summary.metrics!;
      const assessment = metrics.files.assessments.files[0]!;
      const diversity = metrics.files.diversity.files[0]!;
      const assessed = await readLedgerParquet(join(recorded.inputs.outputRoot, assessment.path), "article-assessments", ArticleAssessmentContract);
      const measured = await readLedgerParquet(join(recorded.inputs.outputRoot, diversity.path), "diversity", DiversityMetricContract);
      expect(assessed.rows.length).toBe(metrics.receipts.assessments.row_count);
      expect(measured.rows.length).toBe(metrics.receipts.diversity.row_count);
      expect(metrics.receipts.assessments.files[0]!.content_sha256).toBe(assessed.envelope.content_sha256);
      expect(metrics.receipts.diversity.files[0]!.content_sha256).toBe(measured.envelope.content_sha256);
      const sourceFile = summary.files.source_runs!.files[0]!;
      const sources = await readLedgerParquet(join(recorded.inputs.outputRoot, sourceFile.path), "source-runs", SourceRunContract);
      expect(sources.rows.map(row => row.row)).toEqual(summary.source_records!);
      expect(sources.envelope.content_sha256).toBe(sourceFile.content_sha256);
      const paths = (files: readonly { path: string }[]) => ({
        day: summary.date, rawFiles: files.map(file => join(recorded.inputs.outputRoot, file.path)),
      });
      const history = await readPlanningHistory({
        sources: paths(summary.files.source_runs!.files),
        ledgers: {
          "article-assessments": paths(metrics.files.assessments.files),
          diversity: paths(metrics.files.diversity.files),
          "editorial-selections": paths(summary.files.selections.files),
          dispatches: paths(summary.files.dispatches.files),
          rejections: paths([
            ...summary.files.harvest_rejections.files, ...summary.files.screening_rejections.files,
            ...summary.files.curation_rejections.files,
          ]),
        },
      });
      const selected = selectCompleteAttempt(history, summary.run_id).selected!;
      expect(selected).not.toBeNull();
      expect(summary.planning_completion).toMatchObject({
        status: "complete", date: selected.date, run_id: selected.run_id,
        attempt: selected.attempt, correlation_id: selected.correlation_id, source_count: selected.sources.length,
      });
      expect(selected.sources).toEqual(summary.source_records!);
      expect(summary.planning_completion!.completion_evidence).toHaveLength(5);
    }
    const post = (route: string, value: unknown, app = restarted) => app.request(`/api/2026-10-20/${route}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(value),
    });
    const correlation_id = randomUUID();
    const fetchRequest = {
      request_id: randomUUID(), correlation_id, source_id: "recorded-news",
      kind: "article", url: "https://news.example/second",
    };
    const fetchedResponse = await post("fetch", fetchRequest);
    expect(fetchedResponse.status).toBe(200);
    const fetched = await fetchedResponse.json();
    expect(fetched).not.toHaveProperty("body");
    expect(fetched.observation.operation).toBe("fetch");
    expect(fetched.article_id).toBe(fetched.observation.article_id);
    expect(fetched.attempts.length).toBeGreaterThan(0);
    expect(fetched.attempt_observations.every((event: { caused_by_event_id: string; event_id: string }) =>
      event.caused_by_event_id === fetched.observation.event_id && event.event_id !== fetched.observation.event_id)).toBe(true);
    const afterFetch = api.transport.requests.length;
    const newApp = createPlanApp(api.inputs, api.runtime);
    expect(await (await post("fetch", fetchRequest, newApp)).json()).toEqual(fetched);
    expect(api.transport.requests).toHaveLength(afterFetch);
    const parseRequest = {
      request_id: randomUUID(), fetch_request_id: fetchRequest.request_id,
      article_id: fetched.article_id, correlation_id,
    };
    const parsedResponse = await post("parse", parseRequest, newApp);
    expect(parsedResponse.status).toBe(200);
    const parsed = await parsedResponse.json();
    expect(parsed.failure).toBeNull();
    expect(parsed.parsed.article_text.length).toBeGreaterThan(0);
    expect(parsed.observation).toMatchObject({
      article_id: fetched.article_id, correlation_id, run_id: fetched.observation.run_id,
      caused_by_event_id: fetched.observation.event_id, operation: "parse",
    });
    expect(parsed.observation.event_id).not.toBe(fetched.observation.event_id);
    expect(await (await post("parse", parseRequest, createPlanApp(api.inputs, api.runtime))).json()).toEqual(parsed);
    expect(api.transport.requests).toHaveLength(afterFetch);
    for (const changed of [
      { ...fetchRequest, url: "https://news.example/not-found" },
      { ...fetchRequest, correlation_id: randomUUID() },
    ]) expect((await post("fetch", changed)).status).toBe(409);
    expect((await post("parse", { ...parseRequest, article_id: "a".repeat(64) })).status).toBe(409);
    expect((await post("parse", { ...parseRequest, request_id: randomUUID(), article_id: "a".repeat(64) })).status).toBe(400);
    expect((await post("parse", { ...parseRequest, request_id: randomUUID(), fetch_request_id: randomUUID() })).status).toBe(404);
    expect((await post("parse", { ...parseRequest, request_id: randomUUID(), path: "../secret" })).status).toBe(400);
    expect((await post("fetch", { ...fetchRequest, request_id: randomUUID(), url: "http://127.0.0.1/private" })).status).toBe(400);
    const original = api.inputs.harvest.config_sha256;
    api.inputs.harvest.config_sha256 = "b".repeat(64);
    expect((await post("fetch", fetchRequest)).status).toBe(409);
    expect((await post("parse", { ...parseRequest, request_id: randomUUID() })).status).toBe(409);
    api.inputs.harvest.config_sha256 = original;
    const feedRequest = { request_id: randomUUID(), correlation_id, source_id: "recorded-news", kind: "feed" };
    const feed = await (await post("fetch", feedRequest)).json();
    const entries = await (await post("parse", {
      request_id: randomUUID(), fetch_request_id: feedRequest.request_id, article_id: feed.article_id, correlation_id,
    })).json();
    expect(entries.parsed.length).toBeGreaterThan(0);
    expect(api.transport.requests.length).toBeGreaterThan(afterFetch);
    // A committed start with no response represents a process that stopped before completion.
    const interrupted = FetchRequestSchema.parse({ ...fetchRequest, request_id: randomUUID() });
    const store = await openOperationStore(api.inputs.outputRoot);
    try {
      await expect(store.execute(proposedOperation("fetch", interrupted.request_id, interrupted,
        correlation_id, api.inputs, api.runtime), async () => { throw new Error("interrupted"); })).rejects.toThrow("interrupted");
    } finally { store.close(); }
    const resumed = await post("fetch", interrupted, createPlanApp(api.inputs, api.runtime));
    expect(resumed.status).toBe(200);
    expect((await resumed.json()).observation.correlation_id).toBe(correlation_id);
    const concurrentRequest = { ...fetchRequest, request_id: randomUUID() };
    const concurrentCount = api.transport.requests.length;
    const parallel = await Promise.all([post("fetch", concurrentRequest), post("fetch", concurrentRequest)]);
    expect(parallel.map(response => response.status).sort()).toEqual([200, 409]);
    expect(api.transport.requests.length - concurrentCount).toBe(2);
    const winner = await parallel.find(response => response.status === 200)!.json();
    const completedCount = api.transport.requests.length;
    const completed = await Promise.all([
      post("fetch", concurrentRequest, createPlanApp(api.inputs, api.runtime)),
      post("fetch", concurrentRequest, createPlanApp(api.inputs, api.runtime)),
    ]);
    expect(completed.map(response => response.status)).toEqual([200, 200]);
    expect(await Promise.all(completed.map(response => response.json()))).toEqual([winner, winner]);
    expect(api.transport.requests).toHaveLength(completedCount);
    const failedFetchRequest = { ...fetchRequest, request_id: randomUUID(), url: "https://news.example/not-found" };
    const failedFetch = await (await post("fetch", failedFetchRequest)).json();
    expect(failedFetch.failure).toBe("http");
    expect((await post("parse", {
      ...parseRequest, request_id: randomUUID(), fetch_request_id: failedFetchRequest.request_id, article_id: failedFetch.article_id,
    })).status).toBe(409);
  } finally { await Promise.all([api.close(), cli.close()]); }
}, 30000);

test("a required source write failure returns an API error, not proven planning completion", async () => {
  const recorded = await recordedPlan();
  try {
    const raw = join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan");
    await mkdir(raw, { recursive: true });
    await writeFile(join(raw, "source-runs"), "A file cannot hold source records.");
    const app = createPlanApp(recorded.inputs, recorded.runtime);
    const requestKey = randomUUID();
    const response = await app.request("/api/2026-10-20/plan", {
      method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": requestKey }, body: "{}",
    });
    expect(response.status).toBe(500);
    const failed = await response.json();
    expect(failed.code).toBe("PLAN_FAILED");
    expect(failed).not.toHaveProperty("planning_complete");
    expect(failed).not.toHaveProperty("planning_completion");
    expect(existsSync(join(raw, "article-assessments"))).toBe(true);
    expect(existsSync(join(raw, "diversity"))).toBe(true);
    const requests = recorded.transport.requests.length;
    const stopped = await createPlanApp(recorded.inputs, recorded.runtime).request("/api/2026-10-20/plan", {
      method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": requestKey }, body: "{}",
    });
    expect(stopped.status).toBe(409);
    expect((await stopped.json()).code).toBe("REQUEST_INCOMPLETE");
    expect(recorded.transport.requests).toHaveLength(requests);
  } finally { await recorded.close(); }
}, 30000);

test("one listener retains durable seen receipts from an output root outside the checkout", async () => {
  const recorded = await recordedPlan([
    source({ url: "https://news.example/article-failures.xml" }),
    source({ id: "rest-cycle", url: "https://news.example/empty.xml" }),
    source({ id: "retire-cycle", url: "https://news.example/gone.xml" }),
  ]);
  const outputRoot = await mkdtemp(join(tmpdir(), "planner-output-root-"));
  const receipts: { day: string; files: readonly PersistedLedgerFile[] }[] = [];
  const feedReceipts: FeedWriteReceipt[] = [];
  let clocks = 0;
  try {
    recorded.inputs.outputRoot = outputRoot;
    recorded.inputs.clock_config.collect.seen_window_days = 1;
    recorded.inputs.clock_config.collect.availability_strikes_before_rest = 1;
    recorded.inputs.clock_config.collect.feed_http_410_runs_before_retirement = 1;
    recorded.inputs.settings.inputs.seen_days = [{ day: "2026-10-21", raw_files: [] }];
    delete recorded.runtime.run_number;
    recorded.runtime.clock = () => new Date(`2026-10-21T12:00:00.${String(clocks++).padStart(3, "0")}Z`);
    recorded.runtime.on_seen_persisted = receipt => { receipts.push(receipt); };
    recorded.runtime.on_feed_history_persisted = receipt => { feedReceipts.push(receipt); };
    const app = createPlanApp(recorded.inputs, recorded.runtime);
    const post = () => app.request("/api/2026-10-20/plan", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
    });
    const responses = await Promise.all([post(), post()]);
    const [first, second] = await Promise.all(responses.map(response => response.json()));
    expect(responses.map(response => response.status)).toEqual([200, 200]);
    expect(clocks).toBe(2);
    expect(first).not.toHaveProperty("issues");
    expect(second).not.toHaveProperty("issues");
    expect(first.first_sight.absence_proof).toBe("unavailable");
    expect(first.first_sight.created_count).toBeGreaterThan(0);
    expect(second.first_sight.created_count).toBe(0);
    expect(second.source_records.find((row: { source_id: string }) => row.source_id === "rest-cycle").fetch_status).toBe("not_requested");
    expect(second.source_records.find((row: { source_id: string }) => row.source_id === "retire-cycle").fetch_status).toBe("not_requested");
    expect(second.feed_history.own_receipts.filter((receipt: { ledger: string }) => receipt.ledger === "feed-health")).toHaveLength(1);
    const thirdResponse = await post();
    expect(thirdResponse.status).toBe(200);
    const third = await thirdResponse.json();
    expect(third.source_records.find((row: { source_id: string }) => row.source_id === "rest-cycle").fetch_status).toBe("success");
    expect(third.source_records.find((row: { source_id: string }) => row.source_id === "retire-cycle").fetch_status).toBe("not_requested");
    expect(third.feed_history.own_receipts.filter((receipt: { ledger: string }) => receipt.ledger === "feed-retirements")).toHaveLength(1);
    expect(recorded.transport.requests.filter(request => request.url.pathname === "/gone.xml")).toHaveLength(1);
    expect(recorded.transport.requests.filter(request => request.url.pathname === "/empty.xml")).toHaveLength(2);
    expect(feedReceipts.flatMap(receipt => receipt.files).every(file => !file.path.includes("\\") && !file.path.includes(":"))).toBe(true);
    expect(receipts).toHaveLength(1);
    const file = await readLedgerParquet(join(recorded.inputs.outputRoot, receipts[0]!.files[0]!.path), "seen", {
      schema: SeenRowSchema, schemaVersion: "2026-08-31",
    });
    expect(file.rows.every(row => row.row.first_seen_at === "2026-10-21T12:00:00Z")).toBe(true);
    expect(new Set(file.rows.map(row => row.row.first_seen_run)).size).toBe(1);
    expect(existsSync(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan", "article-assessments"))).toBe(true);
    expect(existsSync(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan", "diversity"))).toBe(true);
    const fetched = recorded.transport.requests.length;
    recorded.runtime.clock = () => new Date("2026-10-21T11:59:59Z");
    const backwards = await post();
    expect(backwards.status).toBe(500);
    expect((await backwards.json()).issues[0].field).toBe("now");
    recorded.runtime.clock = () => new Date(Number.NaN);
    expect((await post()).status).toBe(500);
    expect(recorded.transport.requests).toHaveLength(fetched);
  } finally {
    await Promise.all([recorded.close(), rm(outputRoot, { recursive: true, force: true })]);
  }
}, 30000);

test("a later dispatch failure does not lose already durable first sight from this listener", async () => {
  const recorded = await recordedPlan([
    source({ url: "https://news.example/article-failures.xml" }),
    source({ id: "rest-cycle", url: "https://news.example/empty.xml" }),
    source({ id: "retire-cycle", url: "https://news.example/gone.xml" }),
  ]);
  const receipts: { day: string; files: readonly PersistedLedgerFile[] }[] = [];
  const feedReceipts: FeedWriteReceipt[] = [];
  let clocks = 0;
  try {
    recorded.inputs.clock_config.collect.seen_window_days = 0;
    recorded.inputs.clock_config.collect.availability_strikes_before_rest = 1;
    recorded.inputs.clock_config.collect.feed_http_410_runs_before_retirement = 1;
    recorded.inputs.settings.inputs.seen_days = [{ day: "2026-10-21", raw_files: [] }];
    delete recorded.runtime.run_number;
    recorded.runtime.clock = () => new Date(`2026-10-21T12:0${clocks++}:00Z`);
    recorded.runtime.on_seen_persisted = receipt => { receipts.push(receipt); };
    recorded.runtime.on_feed_history_persisted = receipt => { feedReceipts.push(receipt); };
    const blocked = join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan", "dispatches");
    await mkdir(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan"), { recursive: true });
    await writeFile(blocked, "A file cannot hold dispatches.");
    const app = createPlanApp(recorded.inputs, recorded.runtime);
    const post = () => app.request("/api/2026-10-20/plan", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
    });
    const failed = await post();
    expect(failed.status).toBe(500);
    expect((await failed.json()).code).toBe("PLAN_FAILED");
    expect(receipts).toHaveLength(1);
    const failedAgain = await post();
    expect(failedAgain.status).toBe(500);
    expect(feedReceipts.filter(receipt => receipt.ledger === "feed-retirements")).toHaveLength(1);
    await unlink(blocked);
    const retried = await post();
    expect(retried.status).toBe(200);
    const recovered = await retried.json();
    expect(recovered).not.toHaveProperty("issues");
    expect(recovered.feed_history.own_receipts.filter((receipt: { ledger: string }) => receipt.ledger === "feed-retirements")).toHaveLength(1);
    expect(recovered.files.feed_retirements.status).toBe("empty");
    expect(recorded.transport.requests.filter(request => request.url.pathname === "/gone.xml")).toHaveLength(1);
    expect(receipts).toHaveLength(1);
    const native = await readLedgerParquet(join(recorded.inputs.outputRoot, receipts[0]!.files[0]!.path), "seen", {
      schema: SeenRowSchema, schemaVersion: "2026-08-31",
    });
    expect(native.rows.every(row => row.row.first_seen_at === "2026-10-21T12:00:00Z")).toBe(true);
  } finally { await recorded.close(); }
}, 30000);

test("a listener keeps first-seen evidence stable across UTC midnight", async () => {
  const recorded = await recordedPlan([source({ url: "https://news.example/article-failures.xml" })]);
  const receipts: { day: string; files: readonly PersistedLedgerFile[] }[] = [];
  try {
    recorded.inputs.clock_config.collect.seen_window_days = 1;
    const authored = [
      { day: "2026-10-20", raw_files: [] as string[] },
      { day: "2026-10-21", raw_files: [] as string[] },
    ];
    recorded.inputs.settings.inputs.seen_days = authored;
    delete recorded.runtime.run_number;
    recorded.runtime.clock = () => new Date("2026-10-21T23:59:59Z");
    recorded.runtime.on_seen_persisted = receipt => { receipts.push(receipt); };
    const app = createPlanApp(recorded.inputs, recorded.runtime);
    const post = () => app.request("/api/2026-10-20/plan", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
    });
    const before = await post();
    expect(before.status).toBe(200);
    const first = await before.json();
    expect(first).not.toHaveProperty("issues");
    expect(receipts).toHaveLength(1);

    recorded.runtime.clock = () => new Date("2026-10-22T00:00:01Z");
    recorded.inputs.harvest.sources.push(source({ id: "new-feed" }));
    const fetched = recorded.transport.requests.length;
    const after = await post();
    expect(after.status).toBe(200);
    const second = await after.json();
    expect(recorded.transport.requests.length).toBeGreaterThan(fetched);
    expect(second).not.toHaveProperty("issues");
    expect(receipts).toHaveLength(2);
    expect(receipts[1]!.day).toBe("2026-10-22");
    const newlySeen = await readLedgerParquet(join(recorded.inputs.outputRoot, receipts[1]!.files[0]!.path), "seen", {
      schema: SeenRowSchema, schemaVersion: "2026-08-31",
    });
    expect(newlySeen.rows.every(row => row.row.first_seen_at === "2026-10-22T00:00:01Z")).toBe(true);
    const settled = await readLedgerParquet(join(recorded.inputs.outputRoot, receipts[0]!.files[0]!.path), "seen", {
      schema: SeenRowSchema, schemaVersion: "2026-08-31",
    });
    expect(settled.rows.every(row => row.row.first_seen_at === "2026-10-21T23:59:59Z")).toBe(true);
    expect(recorded.inputs.settings.inputs.seen_days).toEqual(authored);

    recorded.inputs.settings.inputs.seen_days = [
      ...authored, { day: "2026-10-22", raw_files: [] },
    ];
    const supplied = await post();
    expect(supplied.status).toBe(200);
    expect(await supplied.json()).not.toHaveProperty("issues");
    expect(receipts).toHaveLength(2);
    const retained = await readLedgerParquet(join(recorded.inputs.outputRoot, receipts[0]!.files[0]!.path), "seen", {
      schema: SeenRowSchema, schemaVersion: "2026-08-31",
    });
    expect(retained.rows.map(row => row.row.first_seen_at)).toEqual(
      settled.rows.map(row => row.row.first_seen_at));
    expect(retained.rows.every(row => row.row.first_seen_at === "2026-10-21T23:59:59Z")).toBe(true);
    expect(receipts[1]!.day).toBe("2026-10-22");
    const requests = recorded.transport.requests.length;
    recorded.inputs.settings.inputs.seen_days = [authored[0]!, authored[0]!, authored[1]!];
    expect((await post()).status).toBe(500);
    recorded.inputs.settings.inputs.seen_days[0] = { day: "2026-10-19", raw_files: [] };
    recorded.inputs.settings.inputs.seen_days.splice(1, 1);
    expect((await post()).status).toBe(500);
    recorded.inputs.settings.inputs.seen_days = [...authored, { day: "2026-10-23", raw_files: [] }];
    expect((await post()).status).toBe(500);
    expect(recorded.transport.requests).toHaveLength(requests);
  } finally { await recorded.close(); }
}, 30000);
