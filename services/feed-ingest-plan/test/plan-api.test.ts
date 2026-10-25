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
import { parseDocument } from "../src/harvest-feeds/parse-document";
import { redactProofResponse, requireExactReplay, requireReadableArticle, selectVerifiedArticle } from "../../../.github/scripts/feed-ingest-plan-http-proof";
import { FeedHealthContract, PLANNER_OPERATION_VERSION } from "@idhazh/common-contracts";
import { loadHarvestInputs } from "../src/harvest-feeds/load-harvest-inputs";
import { loadConfig as loadProbeConfig } from "../../host-probes/src/config";
import { TaskProfileSchema } from "../../host-probes/src/task-profile/profile-schema";
import type { TaskProfile } from "../../host-probes/src/task-profile/profile-schema";
import { verifyStageApis } from "./stage-api-cases";
import { readObservationFiles } from "./observation-recordings";

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
  const authority = await recordedPlan([
    source(), source({ id: "draft-source", status: "draft" }),
    source({ id: "retired-in-feeds", status: "retired", retired_on: "2026-10-20" }),
  ]);
  try {
    const profiles: TaskProfile[] = [];
    const config = await loadProbeConfig();
    config.task_profile.enabled = true;
    authority.runtime.task_profiling = { config, report: profile => { profiles.push(profile); } };
    const retired = source({ id: "curated-retired", status: "retired", retired_on: "2026-10-20" });
    const rawSources = { feeds: authority.inputs.harvest.sources, retired: [retired] };
    const before = JSON.stringify(rawSources);
    const rawInputs = {
      config: authority.inputs.harvest.config,
      taxonomy: { ...authority.inputs.harvest.taxonomy, ...authority.inputs.harvest.registry },
      sources: rawSources,
      extraction: { ...authority.inputs.harvest.extraction_settings, extract: authority.inputs.harvest.extraction },
    };
    authority.inputs.harvest = loadHarvestInputs(rawInputs);
    expect(authority.inputs.harvest.sources).toHaveLength(rawSources.feeds.length);
    expect(authority.inputs.harvest.retired_sources).toHaveLength(1);
    const guarded = createPlanApp(authority.inputs, authority.runtime);
    for (const source_id of ["curated-retired", "retired-in-feeds", "draft-source"]) {
      const result = await guarded.request("/api/2026-10-20/fetch", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_id: randomUUID(), correlation_id: randomUUID(), source_id, kind: "feed" }),
      });
      expect(result.status).toBe(400);
      expect((await result.json()).issues[0].field).toBe("source_id");
    }
    expect(authority.transport.requests).toHaveLength(0);
    expect(profiles).toHaveLength(0);
    expect(JSON.stringify(rawSources)).toBe(before);
    expect(() => loadHarvestInputs({ ...rawInputs,
      sources: { ...rawSources, retired: [{ ...retired, retired_on: null }] } })).toThrow();
    expect(() => loadHarvestInputs({ ...rawInputs,
      sources: { ...rawSources, retired: [{ ...retired, status: "active", retired_on: null }] } })).toThrow();
  } finally { await authority.close(); }
});

test("actual API and awaited CLI compose the same recorded plan and disclose the same audit limit", async () => {
  await verifyStageApis();
  const api = await recordedPlan();
  const cli = await recordedPlan();
  const profiles: TaskProfile[] = [];
  const probeConfig = await loadProbeConfig();
  api.runtime.task_profiling = { config: probeConfig, report: profile => { profiles.push(TaskProfileSchema.parse(profile)); } };
  try {
    const app = createPlanApp(api.inputs, api.runtime);
    const key = randomUUID();
    const response = await app.request("/api/2026-10-20/plan", {
      method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": key },
      body: JSON.stringify({ freshness_hours: 18, article_limit: 1, partition_strategy: "none" }),
    });
    expect(response.status).toBe(200);
    const apiResult = await response.json();
    const planFacts = await readObservationFiles(api.inputs.outputRoot, apiResult.files.document_observations.files);
    expect(planFacts.length).toBeGreaterThan(0);
    expect(api.observation_files).toEqual(apiResult.files.document_observations.files);
    const requests = planFacts.filter(({ row }) => row.operation === "attempt");
    expect(requests.reduce((count, { row }) => count + row.dispatched_request_count!, 0)).toBe(api.transport.requests.length);
    expect(requests.filter(({ row }) => row.request_phase === "validation")
      .every(({ row }) => row.dispatched_request_count === 0)).toBe(true);
    expect(planFacts.every(({ row, identity }) =>
      row.observed_run_id === apiResult.run_id && row.observed_attempt === identity.attempt
      && row.occurred_at === "2026-10-21T23:59:59Z")).toBe(true);
    expect(planFacts.filter(({ row }) => row.document_kind === "feed").every(({ row }) => row.candidate_id === null)).toBe(true);
    expect(planFacts.some(({ row }) => row.document_kind === "article" && row.candidate_id !== null)).toBe(true);
    expect(new Set(planFacts.map(({ row }) => row.event_id)).size).toBe(planFacts.length);
    const observationFilesBeforeReplay = [...api.observation_files];
    const capturedHealth = await readLedgerParquet(join(api.inputs.outputRoot, apiResult.files.feed_health.files[0].path),
      "feed-health", FeedHealthContract);
    expect(capturedHealth.rows.every(({ row }) => row.checked_at === "2026-10-21T23:59:59.999Z")).toBe(true);
    const saved = await openOperationStore(api.inputs.outputRoot);
    try {
      expect(saved.get(key)).toMatchObject({
        version: PLANNER_OPERATION_VERSION, created_at: "2026-10-21T23:59:59.999Z",
      });
    } finally { saved.close(); }
    const requestCount = api.transport.requests.length;
    const restarted = createPlanApp(api.inputs, api.runtime);
    const replayed = await createPlanApp(api.inputs, {
      ...api.runtime, clock: () => { throw new Error("Completed replay must not acquire a new run clock"); },
    }).request("/api/2026-10-20/plan", {
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
    const selectedArticle = await selectVerifiedArticle(cli.inputs, cliResult, cli.inputs.outputRoot);
    expect(selectedArticle.selection).toMatchObject({
      run_id: cliResult.run_id, correlation_id: cliResult.correlation_id,
      candidate_id: cliResult.selected_candidate_ids[0],
    });
    expect(selectedArticle.canonical_url).toBe("https://news.example/second");
    await expect(selectVerifiedArticle(cli.inputs, {
      ...cliResult, selected_candidate_ids: ["0".repeat(64)],
    }, cli.inputs.outputRoot)).rejects.toThrow("DISPATCH_MEMBERSHIP_MISMATCH");
    await expect(selectVerifiedArticle(cli.inputs, {
      ...cliResult, correlation_id: randomUUID(),
    }, cli.inputs.outputRoot)).rejects.toThrow("INVALID_PLANNING_COMPLETION");
    await expect(selectVerifiedArticle(cli.inputs, {
      ...cliResult, planning_completion: {
        ...cliResult.planning_completion!, attempt: cliResult.planning_completion!.attempt + 1,
      },
    }, cli.inputs.outputRoot)).rejects.toThrow("DISPATCH_MEMBERSHIP_MISMATCH");
    expect(printed).toEqual([cliResult]);
    for (const field of ["run_id", "correlation_id", "date", "observed_at", "request",
      "strategy", "dispatch_count", "selected_candidate_ids", "assignments", "audit", "status"] as const) {
      expect(apiResult[field]).toEqual(cliResult[field]);
    }
    expect(apiResult.files.dispatches.status).toBe("written");
    expect(cliResult.files.dispatches.status).toBe("written");
    expect(api.transport.requests.length).toBeGreaterThan(0);
    expect(api.observation_files.slice(0, observationFilesBeforeReplay.length)).toEqual(observationFilesBeforeReplay);
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
    expect(profiles).toHaveLength(0);
    probeConfig.task_profile = { ...probeConfig.task_profile, enabled: true, memory_enabled: true,
      cpu_window_ms: 20, poll_interval_ms: 5 };
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
    expect(profiles).toHaveLength(1);
    expect(profiles[0]?.identity).toMatchObject({
      task_name: "fetch", request_id: fetchRequest.request_id, correlation_id, run_id: fetched.observation.run_id,
    });
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
    expect(profiles).toHaveLength(1);
    const parseRequest = {
      request_id: randomUUID(), fetch_request_id: fetchRequest.request_id,
      article_id: fetched.article_id, correlation_id,
    };
    const parsedResponse = await post("parse", parseRequest, newApp);
    expect(parsedResponse.status).toBe(200);
    const privateParseBytes = Buffer.from(await parsedResponse.arrayBuffer());
    const parsed = JSON.parse(privateParseBytes.toString("utf8"));
    expect(profiles).toHaveLength(2);
    expect(profiles[1]?.identity).toMatchObject({
      task_name: "parse", request_id: parseRequest.request_id, correlation_id, run_id: fetched.observation.run_id,
    });
    expect(profiles[1]?.processes.worker.closing.pid).toBe(process.pid);
    const standaloneFiles = api.observation_files.slice(observationFilesBeforeReplay.length);
    const standaloneFacts = await readObservationFiles(api.inputs.outputRoot, standaloneFiles);
    expect(standaloneFacts.some(({ row }) => row.event_id === fetched.observation.event_id)).toBe(true);
    expect(standaloneFacts.some(({ row }) => row.event_id === parsed.observation.event_id
      && row.caused_by_event_id === fetched.observation.event_id)).toBe(true);
    expect(standaloneFacts.every(({ row }) =>
      row.observed_run_id === null && row.observed_attempt === null && row.candidate_id === null
      && row.source_id === "recorded-news" && row.publisher_id === null)).toBe(true);
    const standaloneFileCount = api.observation_files.length;
    expect(profiles[1]?.config.machine_memory_enabled).toBe(false);
    expect(profiles[1]?.machine_available_min_kb).toBeNull();
    expect(profiles[1]?.samples.at(-1)?.unavailable["memory_kb.total"]).toBe("configured_off");
    expect(profiles[1]?.started_at).not.toBe(api.runtime.clock!().toISOString());
    expect(parsed.failure).toBeNull();
    expect(parsed.parsed.article_text.length).toBeGreaterThan(0);
    const shared = await parseDocument("article", api.transport.recordings.bodies.article,
      "https://news.example/second", api.inputs.harvest.extraction, "article");
    expect(parsed.parsed).toEqual(shared);
    expect(parsed.parsed.quality).toMatchObject({
      source_word_count: parsed.parsed.word_count, word_count: parsed.parsed.word_count,
      token_count: null, truncated: null, boilerplate: null,
    });
    expect(() => requireReadableArticle(shared)).not.toThrow();
    for (const unavailable of [
      { ...shared, quality: null },
      { ...shared, paywall: true, quality: null },
      { ...shared, article_text: "", word_count: 0, quality: null },
    ]) expect(() => requireReadableArticle(unavailable)).toThrow("HTML_EXTRACTION_UNAVAILABLE");
    for (const invalid of [
      { ...shared, quality: {} },
      { ...shared, paywall: true, quality: {} },
      { ...shared, article_text: null, quality: null },
    ]) {
      expect(() => requireReadableArticle(invalid)).toThrow();
      expect(() => requireReadableArticle(invalid)).not.toThrow("HTML_EXTRACTION_UNAVAILABLE");
    }
    expect(parsed.observation).toMatchObject({
      article_id: fetched.article_id, correlation_id, run_id: fetched.observation.run_id,
      caused_by_event_id: fetched.observation.event_id, operation: "parse",
    });
    expect(parsed.observation.event_id).not.toBe(fetched.observation.event_id);
    const privateReplayBytes = Buffer.from(await (await post("parse", parseRequest, createPlanApp(api.inputs, api.runtime))).arrayBuffer());
    requireExactReplay(privateParseBytes, privateReplayBytes);
    probeConfig.task_profile.machine_memory_enabled = true;
    requireExactReplay(privateParseBytes, Buffer.from(await (await post("parse", parseRequest)).arrayBuffer()));
    expect(await (await post("fetch", fetchRequest)).json()).toEqual(fetched);
    probeConfig.task_profile.enabled = false;
    requireExactReplay(privateParseBytes, Buffer.from(await (await post("parse", parseRequest)).arrayBuffer()));
    probeConfig.task_profile.enabled = true;
    expect(profiles).toHaveLength(2);
    const redacted = redactProofResponse("parse", "article", privateParseBytes, 200);
    const redactedReplay = redactProofResponse("parse", "article", privateReplayBytes, 200);
    expect(redacted.response_json).toBeNull();
    expect(redacted.response_sha256).toBe(new Bun.CryptoHasher("sha256").update(privateParseBytes).digest("hex"));
    expect(redactedReplay).toEqual(redacted);
    expect(redacted.response_metadata).toMatchObject({
      fetch_request_id: fetchRequest.request_id, observation: parsed.observation, failure: null,
      parsed: { word_count: shared.word_count, quality: shared.quality,
        article_text_length: shared.article_text.length, article_text_sha256: new Bun.CryptoHasher("sha256").update(shared.article_text).digest("hex") },
    });
    const publicBytes = JSON.stringify(redacted);
    expect(publicBytes).not.toContain(shared.article_text);
    expect(publicBytes).not.toContain('"article_text":');
    expect(publicBytes).not.toContain('"page_title":');
    expect(publicBytes).not.toContain('"author":');
    const changedBytes = Buffer.from(JSON.stringify({ ...parsed, parsed: { ...parsed.parsed, article_text: `${shared.article_text} changed` } }));
    expect(redactProofResponse("parse", "article", changedBytes, 200).response_json).toBeNull();
    expect(() => requireExactReplay(privateParseBytes, changedBytes)).toThrow("private response bytes");
    const privateErrorBytes = Buffer.from(JSON.stringify({
      code: "REQUEST_CONFLICT", issues: [{ field: "secret", message: shared.article_text }],
    }));
    expect(redactProofResponse("parse", "article", privateErrorBytes, 409)).toEqual({
      response_sha256: new Bun.CryptoHasher("sha256").update(privateErrorBytes).digest("hex"),
      response_json: null, response_metadata: { code: "REQUEST_CONFLICT" },
    });
    expect(() => redactProofResponse("parse", "feed", privateParseBytes, 200)).toThrow("document parse");
    expect(api.transport.requests).toHaveLength(afterFetch);
    expect(api.observation_files).toHaveLength(standaloneFileCount);
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
    expect(profiles).toHaveLength(2);
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
    const failedFacts = await readObservationFiles(api.inputs.outputRoot, api.observation_files);
    expect(failedFacts.find(({ row }) => row.event_id === failedFetch.observation.event_id)?.row).toMatchObject({
      outcome: "failed", failure_code: "http", attribution: "source", http_status: 404,
    });
    expect(profiles.at(-1)?.outcome).toBe("error");
    const afterFailedFetch = profiles.length;
    expect((await post("parse", {
      ...parseRequest, request_id: randomUUID(), fetch_request_id: failedFetchRequest.request_id, article_id: failedFetch.article_id,
    })).status).toBe(409);
    expect(profiles).toHaveLength(afterFailedFetch);
    const rootlessRequest = { ...fetchRequest, request_id: randomUUID(), url: "https://news.example/rootless" };
    const rootless = await (await post("fetch", rootlessRequest)).json();
    const rootlessParsed = await (await post("parse", {
      ...parseRequest, request_id: randomUUID(), fetch_request_id: rootlessRequest.request_id, article_id: rootless.article_id,
    })).json();
    expect(rootlessParsed.failure).toBe("missing-document-root");
    const parseFacts = await readObservationFiles(api.inputs.outputRoot, api.observation_files);
    expect(parseFacts.find(({ row }) => row.event_id === rootlessParsed.observation.event_id)?.row).toMatchObject({
      operation: "parse", outcome: "failed", failure_code: "missing-document-root", attribution: "unresolved",
      caused_by_event_id: rootless.observation.event_id,
    });
    expect(profiles.at(-1)?.outcome).toBe("error");
    const originalRetries = api.inputs.harvest.extraction.max_retries;
    api.inputs.harvest.extraction.max_retries = 1;
    for (const [url, targetRequests, expectedFailure] of [
      ["https://news.example/safe-redirect", 2, null],
      ["https://news.example/retry", 2, null],
      ["https://news.example/denied", 0, "robots-denied"],
      ["https://inward.example/feed.xml", 0, "unsafe-target"],
    ] as const) {
      const fileCount = api.observation_files.length;
      const requestCount = api.transport.requests.length;
      const receipt = await (await post("fetch", { ...fetchRequest, request_id: randomUUID(), url })).json();
      expect(receipt.failure).toBe(expectedFailure);
      const rows = (await readObservationFiles(api.inputs.outputRoot, api.observation_files.slice(fileCount))).map(held => held.row);
      const attempts = rows.filter(row => row.operation === "attempt");
      expect(attempts.reduce((count, row) => count + row.dispatched_request_count!, 0))
        .toBe(api.transport.requests.length - requestCount);
      expect(attempts.filter(row => row.request_phase === "target")
        .reduce((count, row) => count + row.dispatched_request_count!, 0)).toBe(targetRequests);
      expect(attempts.every(row => row.request_coverage === "complete")).toBe(true);
      expect(attempts.every(row => row.caused_by_event_id === receipt.observation.event_id)).toBe(true);
      expect(rows.every(row => row.document_kind === "article" && row.candidate_id === null)).toBe(true);
      if (url.endsWith("/retry")) expect(attempts.filter(row => row.request_phase === "target").map(row => row.retry)).toEqual([0, 1]);
      if (url.includes("inward.example")) expect(attempts).toMatchObject([{
        request_phase: "validation", dispatched_request_count: 0, failure_code: "unsafe-target",
      }]);
    }
    api.inputs.harvest.extraction.max_retries = originalRetries;
    // A bounded recorded document exercises actual synchronous parsing, not a padded live operation.
    const paragraph = api.transport.recordings.bodies.article.match(/<p>[\s\S]*?<\/p>/)![0];
    const repeats = Math.min(1024, Math.floor(api.inputs.harvest.extraction.max_body_bytes / (2 * paragraph.length)));
    api.transport.recordings.bodies.article = `<html><body><article>${paragraph.repeat(repeats)}</article></body></html>`;
    const boundedRequest = { ...fetchRequest, request_id: randomUUID() };
    const bounded = await (await post("fetch", boundedRequest)).json();
    const boundedParse = await post("parse", {
      ...parseRequest, request_id: randomUUID(), fetch_request_id: boundedRequest.request_id, article_id: bounded.article_id,
    });
    expect(boundedParse.status).toBe(200);
    expect((await boundedParse.json()).failure).toBeNull();
    const measured = profiles.at(-1)!;
    expect(measured.identity.task_name).toBe("parse");
    expect(measured.periodic_sample_count).toBeGreaterThan(0);
    expect(measured.samples.some(sample => sample.phase === "poll")).toBe(true);
    if (process.platform === "linux") {
      expect(measured.cpu.reason).toBeNull();
      expect(measured.processes.worker.closing.memory_kb.rss).toBeGreaterThan(0);
      expect(measured.full_window_count).toBeGreaterThan(0);
      expect(measured.machine_available_min_kb).toBeGreaterThan(0);
    }
    console.error(JSON.stringify({ event: "recorded_parse_profile", platform: process.platform, arch: process.arch, profile: measured }));
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
    const retained = await readObservationFiles(recorded.inputs.outputRoot, recorded.observation_files);
    expect(retained.some(({ row }) => row.operation === "fetch" && row.outcome === "success")).toBe(true);
    expect(retained.some(({ row }) => row.operation === "parse" && row.outcome === "success")).toBe(true);
    const filesBeforeReplay = [...recorded.observation_files];
    const requests = recorded.transport.requests.length;
    const stopped = await createPlanApp(recorded.inputs, recorded.runtime).request("/api/2026-10-20/plan", {
      method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": requestKey }, body: "{}",
    });
    expect(stopped.status).toBe(409);
    expect((await stopped.json()).code).toBe("REQUEST_INCOMPLETE");
    expect(recorded.transport.requests).toHaveLength(requests);
    expect(recorded.observation_files).toEqual(filesBeforeReplay);
    await expect(readObservationFiles(recorded.inputs.outputRoot, filesBeforeReplay)).resolves.toEqual(retained);
    const refusing = await recordedPlan();
    try {
      const nativeRoot = join(refusing.inputs.outputRoot, "raw", "feed-ingest-plan");
      await mkdir(nativeRoot, { recursive: true });
      const blocker = join(nativeRoot, "document-observations");
      await writeFile(blocker, "Observation saves must report this failure.");
      const fetchRequest = {
        request_id: randomUUID(), correlation_id: randomUUID(), source_id: "recorded-news", kind: "feed",
      };
      const postFetch = () => createPlanApp(refusing.inputs, refusing.runtime).request("/api/2026-10-20/fetch", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(fetchRequest),
      });
      const unsaved = await postFetch();
      expect(unsaved.status).toBe(500);
      expect((await unsaved.json()).issues[0].message).toContain("document-observations save failed");
      const dispatched = refusing.transport.requests.length;
      expect(dispatched).toBeGreaterThan(0);
      await unlink(blocker);
      // A telemetry save failure does not invalidate the completed factual receipt.
      expect((await postFetch()).status).toBe(200);
      expect(refusing.transport.requests).toHaveLength(dispatched);
      expect(refusing.observation_files).toHaveLength(0);
    } finally { await refusing.close(); }
  } finally { await recorded.close(); }
}, 30000);

test("one listener retains durable seen receipts from an output root outside the checkout", async () => {
  const recorded = await recordedPlan([
    source({ url: "https://news.example/article-failures.xml" }),
    source({ id: "rest-cycle", url: "https://news.example/empty.xml" }),
    source({ id: "gone-health", url: "https://news.example/gone.xml" }),
  ]);
  const outputRoot = await mkdtemp(join(tmpdir(), "planner-output-root-"));
  const receipts: { day: string; files: readonly PersistedLedgerFile[] }[] = [];
  const feedReceipts: FeedWriteReceipt[] = [];
  let clocks = 0;
  try {
    recorded.inputs.outputRoot = outputRoot;
    recorded.inputs.clock_config.collect.seen_window_days = 1;
    recorded.inputs.clock_config.collect.availability_strikes_before_rest = 1;
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
    const reselected = await createPlanApp(recorded.inputs, recorded.runtime)
      .request("/api/2026-10-20/select-articles", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ batch_id: second.batches.parsed_batch_id }),
      });
    expect(reselected.status).toBe(200);
    expect(first.first_sight.absence_proof).toBe("unavailable");
    expect(first.first_sight.created_count).toBeGreaterThan(0);
    expect(second.first_sight.created_count).toBe(0);
    expect(second.source_records.find((row: { source_id: string }) => row.source_id === "rest-cycle").fetch_status).toBe("not_requested");
    expect(second.source_records.find((row: { source_id: string }) => row.source_id === "gone-health").fetch_status).toBe("not_requested");
    expect(second.feed_history.own_receipts.filter((receipt: { ledger: string }) => receipt.ledger === "feed-health")).toHaveLength(1);
    const thirdResponse = await post();
    expect(thirdResponse.status).toBe(200);
    const third = await thirdResponse.json();
    expect(third.source_records.find((row: { source_id: string }) => row.source_id === "rest-cycle").fetch_status).toBe("success");
    expect(third.source_records.find((row: { source_id: string }) => row.source_id === "gone-health").fetch_status).toBe("http_failure");
    expect(third.feed_history.own_receipts.every((receipt: { ledger: string }) => receipt.ledger === "feed-health")).toBe(true);
    expect(recorded.transport.requests.filter(request => request.url.pathname === "/gone.xml")).toHaveLength(2);
    expect(third.files).not.toHaveProperty("feed_retirements");
    expect(recorded.transport.requests.filter(request => request.url.pathname === "/empty.xml")).toHaveLength(2);
    recorded.runtime.clock = () => new Date("2026-10-21T12:00:00.002Z");
    expect((await post()).status).toBe(200);
    const frozen = await post();
    expect(frozen.status).toBe(200);
    expect((await frozen.json()).source_records.find((row: { source_id: string }) => row.source_id === "rest-cycle").fetch_status)
      .toBe("success");
    const unknown = recorded.events.filter(event => event.source_id === "rest-cycle" && event.payload.kind === "feed_outcome").at(-1);
    if (unknown?.payload.kind !== "feed_outcome") throw new Error("Missing frozen-clock feed observation");
    expect(unknown.payload.history?.lifecycle).toBe("unknown");
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
    source({ id: "gone-health", url: "https://news.example/gone.xml" }),
  ]);
  const receipts: { day: string; files: readonly PersistedLedgerFile[] }[] = [];
  const feedReceipts: FeedWriteReceipt[] = [];
  let clocks = 0;
  try {
    recorded.inputs.clock_config.collect.seen_window_days = 0;
    recorded.inputs.clock_config.collect.availability_strikes_before_rest = 1;
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
    expect(feedReceipts).toHaveLength(2);
    await unlink(blocked);
    const retried = await post();
    expect(retried.status).toBe(200);
    const recovered = await retried.json();
    expect(recovered).not.toHaveProperty("issues");
    expect(recovered.feed_history.own_receipts.every((receipt: { ledger: string }) => receipt.ledger === "feed-health")).toBe(true);
    expect(recovered.files).not.toHaveProperty("feed_retirements");
    expect(recorded.transport.requests.filter(request => request.url.pathname === "/gone.xml")).toHaveLength(2);
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
