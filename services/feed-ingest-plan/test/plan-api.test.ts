/** Does the real Hono handler reject invalid requests before recorded harvesting? */
import { expect, test } from "bun:test";
import { fileURLToPath } from "node:url";
import { createPlanApp } from "../src/api/server";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { RecordedTransport, readRecordings } from "./harvest-recordings";
import { recordedPlan } from "./plan-recordings";
import { main } from "../src/index";

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
});

test("actual API and awaited CLI compose the same recorded plan and disclose the same audit limit", async () => {
  const api = await recordedPlan();
  const cli = await recordedPlan();
  try {
    const app = createPlanApp(api.inputs, api.runtime);
    const response = await app.request("/api/2026-10-20/plan", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ freshness_hours: 18, article_limit: 1, partition_strategy: "none" }),
    });
    expect(response.status).toBe(409);
    const apiResult = await response.json();
    const printed: unknown[] = [];
    const cliResult = await main([
      "--cli", "--freshness-hours", "18", "--article-limit=1", "--partition-strategy", "none",
    ], { inputs: cli.inputs, runtime: cli.runtime, output: value => { printed.push(value); } });
    if (!("audited_complete" in cliResult)) throw new Error("CLI unexpectedly started a server");
    expect(cliResult.audited_complete).toBe(false);
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
    expect(apiResult.audit.status).toBe("unavailable");
  } finally { await Promise.all([api.close(), cli.close()]); }
}, 30000);
