/** Do bulk and standalone entry points apply the same document policy without rewriting receipts? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { createPlanApp } from "../src/api/server";
import { openOperationStore } from "../src/api/operation-store";
import { harvestFeeds } from "../src/harvest-feeds/harvest-pool";
import { context } from "./harvest-recordings";
import { recordedPlan } from "./plan-recordings";

test("bulk and standalone feed reads enforce denial even when article robots is observed", async () => {
  for (const entry of ["bulk", "standalone"] as const) {
    const recorded = await recordedPlan();
    const app = createPlanApp(recorded.inputs, recorded.runtime);
    try {
      recorded.transport.recordings.responses["https://news.example/robots.txt"] = [{
        status: 200, body: "User-agent: *\nDisallow: /\n",
      }];
      if (entry === "bulk") {
        const result = await harvestFeeds(recorded.inputs.harvest, context(), recorded.runtime.boundary);
        expect(result.feed_outcomes[0]?.fetch_status).toBe("network_failure");
        expect(result.candidates).toEqual([]);
      } else {
        const response = await app.request("/api/2026-10-20/fetch", {
          method: "POST", headers: { "content-type": "application/json" },
          body: JSON.stringify({
            request_id: randomUUID(), correlation_id: randomUUID(), feed_id: "recorded-news", fetch_item_type: "feed",
          }),
        });
        expect(response.status).toBe(200);
        expect(await response.json()).toMatchObject({ failure: "robots-denied", http_status: null });
      }
      expect(recorded.transport.requests.map(request => request.url.href)).toEqual(["https://news.example/robots.txt"]);
    } finally { app.close(); await recorded.close(); }
  }
});

test("standalone observed success extracts real text, retains the warning and replays without a request", async () => {
  const recorded = await recordedPlan();
  const app = createPlanApp(recorded.inputs, recorded.runtime);
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
    const fetch = () => app.request("/api/2026-10-20/fetch", {
      method: "POST", headers: { "content-type": "application/json" }, body,
    });
    const response = await fetch();
    expect(response.status).toBe(200);
    const result = await response.json();
    expect(result).toMatchObject({ failure: null, http_status: 200 });
    const requests = recorded.transport.requests.length;
    expect(await (await fetch()).json()).toEqual(result);
    expect(recorded.transport.requests).toHaveLength(requests);
    const parsed = await app.request("/api/2026-10-20/parse", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({
        request_id: randomUUID(), fetch_request_id: requestId,
        article_id: result.article_id, correlation_id: correlation,
      }),
    });
    expect(parsed.status).toBe(200);
    const store = await openOperationStore(recorded.inputs.outputRoot);
    try {
      expect(store.get(requestId)).toMatchObject({
        source_outcome: { disposition: "admitted", reason_code: null },
        artifact: { robots: "denied", robots_http_status: 200, robots_failure: null, failure: null, http_status: 200 },
      });
      expect(store.get(requestId)!.artifact!.body!.length).toBeGreaterThan(0);
    } finally { store.close(); }
  } finally { app.close(); await recorded.close(); }
});

test("a saved enforced refusal replays as unrequested and never gains target attempts", async () => {
  const recorded = await recordedPlan();
  recorded.inputs.harvest.config.harvest.article_robots_policy = "enforce";
  recorded.transport.recordings.responses["https://news.example/robots.txt"] = [{
    status: 200, body: "User-agent: *\nDisallow: /\n",
  }];
  const app = createPlanApp(recorded.inputs, recorded.runtime);
  try {
    const requestId = randomUUID();
    const body = JSON.stringify({
      request_id: requestId, correlation_id: randomUUID(), feed_id: "recorded-news",
      fetch_item_type: "article", url: "https://news.example/second",
    });
    const fetch = () => app.request("/api/2026-10-20/fetch", {
      method: "POST", headers: { "content-type": "application/json" }, body,
    });
    expect(await (await fetch()).json()).toMatchObject({ failure: "robots-denied", http_status: null });
    const store = await openOperationStore(recorded.inputs.outputRoot);
    try {
      const saved = store.get(requestId);
      expect(saved!.artifact!.attempts.some(attempt => attempt.phase === "target")).toBe(false);
      expect((await fetch()).status).toBe(200);
      expect(store.get(requestId)).toEqual(saved);
      expect(recorded.transport.requests.map(request => request.url.href)).toEqual(["https://news.example/robots.txt"]);
    } finally { store.close(); }
  } finally { app.close(); await recorded.close(); }
});
