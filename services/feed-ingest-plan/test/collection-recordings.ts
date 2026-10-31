/** Complete a bounded recorded collection through its public stages, without choosing or planning. */
import { randomUUID } from "node:crypto";
import { ParsedFeedBatchSchema } from "@idhazh/common-contracts";
import type { PlanInputs } from "../src/load-plan-inputs";
import type { PlanRuntime } from "../src/run-feed-plan";
import { FetchResponseSchema, ParseResponseSchema } from "../src/api/document-response.schema";
import { getCollection } from "../src/api/collection-operation";
import { stageStore } from "../src/api/stage-store";
import { createPlanTestServer } from "./plan-test-server";

export async function collectRecordedFeeds(inputs: PlanInputs, runtime: PlanRuntime) {
  const app = createPlanTestServer(inputs, runtime);
  const collectionId = randomUUID();
  async function post(operation: string, value: unknown) {
    const response = await app.request(`/api/2026-10-31/${operation}`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(value),
    });
    const body: unknown = await response.json();
    if (response.status !== 200) throw new Error(`Recorded ${operation} refused HTTP ${response.status}: ${JSON.stringify(body)}`);
    return body;
  }
  try {
    await post("collections", { collection_id: collectionId, request: {} });
    const collection = getCollection(inputs, collectionId);
    for (const feedId of collection.feeds.keys()) {
      const fetched = FetchResponseSchema.parse(await post("fetch", {
        request_id: randomUUID(), collection_id: collectionId, feed_id: feedId,
        correlation_id: collection.context.correlation_id, fetch_item_type: "feed",
      }));
      const parsed = ParseResponseSchema.parse(await post("parse", {
        request_id: randomUUID(), fetch_request_id: fetched.fetch_request_id,
        article_id: fetched.article_id, correlation_id: fetched.correlation_id,
      }));
      if (parsed.fetch_item_type !== "feed") throw new Error("The recorded source must parse as a feed");
      for (const offer of parsed.offers) {
        const article = FetchResponseSchema.parse(await post("fetch", {
          request_id: randomUUID(), feed_id: feedId, fetch_item_type: "article",
          batch_id: parsed.batch_id, offer_id: offer.offer_id, correlation_id: collection.context.correlation_id,
        }));
        if (article.body_sha256 !== null) await post("parse", {
          request_id: randomUUID(), fetch_request_id: article.fetch_request_id,
          article_id: article.article_id, correlation_id: article.correlation_id,
        });
      }
    }
    const completion = await post("collections/complete", { collection_id: collectionId });
    return { collection, completion, batch: stageStore(inputs).read("parsed", collection.parsed_batch_id, ParsedFeedBatchSchema) };
  } finally { await app.close(); }
}
