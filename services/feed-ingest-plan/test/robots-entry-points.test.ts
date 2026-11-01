/** Do bulk and standalone entry points apply the same document policy? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { join } from "node:path";
import { FeedHealthStateRowContract, PLANNER_API_PREFIX } from "@idhazh/common-contracts";
import { createPlanTestServer } from "./plan-test-server";
import { stageStore } from "../src/api/stage-store";
import { harvestFeeds } from "../src/harvest-feeds/harvest-pool";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { context } from "./harvest-recordings";
import { recordedPlan } from "./plan-recordings";

test("bulk and standalone feed reads dispatch targets after denied or failed robots checks", async () => {
  const cases = [
    { permission: "denied", response: { status: 200, body: "User-agent: *\nDisallow: /\n" },
      robots_http_status: 200, robots_failure: null },
    { permission: "unknown", response: { status: 503, body: "" },
      robots_http_status: 503, robots_failure: "http" },
  ] as const;
  for (const entry of ["bulk", "standalone"] as const) {
    for (const scenario of cases) {
      const recorded = await recordedPlan();
      const app = entry === "standalone" ? createPlanTestServer(recorded.inputs, recorded.runtime) : null;
      try {
        recorded.inputs.harvest.config.harvest.request_headers.secondary = null;
        recorded.transport.recordings.responses["https://news.example/robots.txt"] = [scenario.response];
        recorded.transport.recordings.responses["https://news.example/feed.xml"] = [{
          status: 200, body: "<rss version=\"2.0\"><channel><title>Recorded empty feed</title></channel></rss>",
        }];
        if (entry === "bulk") {
          const result = await harvestFeeds(recorded.inputs.harvest, context(), recorded.runtime.boundary);
          expect(result.feed_outcomes[0]).toMatchObject({
            fetch_status: "success", parse_status: "empty",
            diagnostics: { robots: scenario.permission, robots_http_status: scenario.robots_http_status },
          });
          expect(result.candidates).toEqual([]);
        } else {
          const requestId = randomUUID();
          const response = await app!.request(`${PLANNER_API_PREFIX}/fetch`, {
            method: "POST", headers: { "content-type": "application/json" },
            body: JSON.stringify({
              request_id: requestId, correlation_id: randomUUID(),
              feed_id: "recorded-news", fetch_item_type: "feed",
            }),
          });
          expect(response.status).toBe(200);
          expect(await response.json()).toMatchObject({ failure: null, http_status: 200 });
          expect(stageStore(recorded.inputs).fetchedDocument(requestId)?.document).toMatchObject({
            failure: null, http_status: 200, robots: scenario.permission,
            robots_http_status: scenario.robots_http_status, robots_failure: scenario.robots_failure,
          });
        }
        expect(recorded.transport.requests.map(request => request.url.href))
          .toEqual(["https://news.example/robots.txt", "https://news.example/feed.xml"]);
      } finally {
        if (app !== null) await app.close();
        await recorded.close();
      }
    }
  }
});

test("the plan records target work after robots denial without inventing a failed feed check", async () => {
  for (const targetStatus of [200, 403] as const) {
    const recorded = await recordedPlan();
    recorded.inputs.harvest.config.harvest.request_headers.secondary = null;
    recorded.transport.recordings.responses["https://news.example/robots.txt"] = [{
      status: 200, body: "User-agent: *\nDisallow: /\n",
    }];
    recorded.transport.recordings.responses["https://news.example/feed.xml"] = [{
      status: targetStatus,
      body: targetStatus === 200
        ? "<rss version=\"2.0\"><channel><title>Recorded feed</title><item><title>Recorded story</title><link>https://news.example/second</link></item></channel></rss>"
        : "",
    }];
    const app = createPlanTestServer(recorded.inputs, recorded.runtime);
    try {
      const response = await app.request(`${PLANNER_API_PREFIX}/plan`, {
        method: "POST", headers: { "content-type": "application/json" }, body: "{}",
      });
      expect(response.status).toBe(200);
      const result = await response.json();
      const saved = await readPlannerParquet(
        join(recorded.inputs.outputRoot, result.files.feed_health_state.files[0].path),
        "feed-health-state", FeedHealthStateRowContract,
      );
      const row = saved.rows.find(item => item.feed_id === "recorded-news");
      expect(row).toMatchObject({
        permission: "denied", status: targetStatus, feed_reads: 1, feed_requests: 1,
        robots_requests: 1, counts_complete: true,
        outcome: targetStatus === 200 ? "ok" : "permanent",
        check_result: targetStatus === 200 ? "valid-feed" : "other-http-failure",
        productive_reads: targetStatus === 200 ? 1 : 0,
        failed_reads: targetStatus === 200 ? 0 : 1,
        last_failure_code: targetStatus === 200 ? null : "FETCH_FAILED_HTTP",
      });
      expect(recorded.transport.requests.map(request => request.url.href)).toEqual(
        targetStatus === 200
          ? ["https://news.example/robots.txt", "https://news.example/feed.xml", "https://news.example/second"]
          : ["https://news.example/robots.txt", "https://news.example/feed.xml"],
      );
    } finally { await app.close(); await recorded.close(); }
  }
});

test("standalone observed success parses its live input without another request", async () => {
  const recorded = await recordedPlan();
  const app = createPlanTestServer(recorded.inputs, recorded.runtime);
  try {
    recorded.transport.recordings.responses["https://news.example/robots.txt"] = [{
      status: 200, body: "User-agent: *\nDisallow: /\n",
    }];
    const requestId = randomUUID();
    const correlation = randomUUID();
    const body = JSON.stringify({
      request_id: requestId, correlation_id: correlation, feed_id: "recorded-news",
      fetch_item_type: "article", url: "https://news.example/second",
    });
    const fetch = () => app.request("/api/2026-10-31/fetch", {
      method: "POST", headers: { "content-type": "application/json" }, body,
    });
    const response = await fetch();
    expect(response.status).toBe(200);
    const result = await response.json();
    expect(result).toMatchObject({ failure: null, http_status: 200 });
    const requests = recorded.transport.requests.length;
    const parsed = await app.request("/api/2026-10-31/parse", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({
        request_id: randomUUID(), fetch_request_id: requestId,
        article_id: result.article_id, correlation_id: correlation,
      }),
    });
    expect(parsed.status).toBe(200);
    expect(await parsed.json()).toMatchObject({ parsed_count: 1, failure: null });
    expect(recorded.transport.requests).toHaveLength(requests);
  } finally { await app.close(); await recorded.close(); }
});

test("an enforced standalone refusal never dispatches the article target", async () => {
  const recorded = await recordedPlan();
  recorded.inputs.harvest.config.harvest.article_robots_policy = "enforce";
  recorded.transport.recordings.responses["https://news.example/robots.txt"] = [{
    status: 200, body: "User-agent: *\nDisallow: /\n",
  }];
  const app = createPlanTestServer(recorded.inputs, recorded.runtime);
  try {
    const requestId = randomUUID();
    const body = JSON.stringify({
      request_id: requestId, correlation_id: randomUUID(), feed_id: "recorded-news",
      fetch_item_type: "article", url: "https://news.example/second",
    });
    const fetch = () => app.request("/api/2026-10-31/fetch", {
      method: "POST", headers: { "content-type": "application/json" }, body,
    });
    expect(await (await fetch()).json()).toMatchObject({ failure: "robots-denied", http_status: null });
    expect(recorded.transport.requests.map(request => request.url.href)).toEqual(["https://news.example/robots.txt"]);
  } finally { await app.close(); await recorded.close(); }
});
