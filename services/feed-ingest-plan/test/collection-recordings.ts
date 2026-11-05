/** Complete a bounded recorded collection through its public stages, without choosing or planning. */
import { createRootContext, ParsedFeedBatchSchema, PLANNER_API_PREFIX, writeTraceContext } from "@idhazh/common-contracts";
import type { PlanInputs } from "../src/load-plan-inputs";
import type { PlanRuntime } from "../src/run-feed-plan";
import { FetchResponseSchema, ParseResponseSchema } from "../src/api/document-response.schema";
import { getCollection } from "../src/api/collection-operation";
import { stageStore } from "../src/api/stage-store";
import { createPlanTestServer } from "./plan-test-server";
import { CompletedCollectionSchema } from "../src/api/collection-contracts";

export async function collectRecordedFeeds(inputs: PlanInputs, runtime: PlanRuntime) {
  const app = createPlanTestServer(inputs, runtime);
  const caller = createRootContext();
  async function post(operation: string, value: unknown) {
    const response = await app.request(`${PLANNER_API_PREFIX}/${operation}`, {
      method: "POST", headers: { "content-type": "application/json", ...writeTraceContext(caller) }, body: JSON.stringify(value),
    });
    const body: unknown = await response.json();
    if (response.status !== 200) throw new Error(`Recorded ${operation} refused HTTP ${response.status}: ${JSON.stringify(body)}`);
    return body;
  }
  try {
    await post("collections", { request: {} });
    const collection = getCollection(inputs, caller.traceId);
    for (const feedId of collection.feeds.keys()) {
      const fetched = FetchResponseSchema.parse(await post("fetch", {
        traceId: caller.traceId, feed_id: feedId, fetch_item_type: "feed",
      }));
      const parsed = ParseResponseSchema.parse(await post("parse", {
        links: [{ traceId: fetched.traceId, spanId: fetched.spanId }],
      }));
      if (parsed.fetch_item_type !== "feed") throw new Error("The recorded source must parse as a feed");
      for (const offer of parsed.offers) {
        const article = FetchResponseSchema.parse(await post("fetch", {
          fetch_item_type: "article", links: [{ traceId: parsed.traceId, spanId: parsed.spanId }], candidate_id: offer.candidate_id,
        }));
        if (article.body_sha256 !== null) await post("parse", {
          links: [{ traceId: article.traceId, spanId: article.spanId }],
        });
      }
    }
    const completion = CompletedCollectionSchema.parse(await post("collections/complete", { traceId: caller.traceId }));
    return { collection, completion, batch: stageStore(inputs).read("parsed", completion, ParsedFeedBatchSchema) };
  } finally { await app.close(); }
}
