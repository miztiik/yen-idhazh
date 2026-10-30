/** Route run-owned collection lifecycle changes without exposing article text. */
import { Hono } from "hono";
import type { PlanInputs } from "../../load-plan-inputs";
import type { PlanRuntime } from "../../run-feed-plan";
import { beginCollection, cancelCollection, completeCollection } from "../collection-operation";
import { CollectionReferenceSchema, CollectionResponseSchema, CompletedCollectionSchema, CancelledCollectionSchema } from "../collection-contracts";
import { readRequestBody } from "./stages.route";

export function collectionRoute(inputs: PlanInputs, runtime: () => PlanRuntime) {
  const app = new Hono();
  app.post("/collections", async c => c.json(CollectionResponseSchema.parse(
    await beginCollection(await readRequestBody(c.req.raw), inputs, runtime()),
  )));
  app.post("/collections/complete", async c => {
    const request = CollectionReferenceSchema.parse(await readRequestBody(c.req.raw));
    return c.json(CompletedCollectionSchema.parse(await completeCollection(inputs, request.collection_id)));
  });
  app.post("/collections/cancel", async c => {
    const request = CollectionReferenceSchema.parse(await readRequestBody(c.req.raw));
    return c.json(CancelledCollectionSchema.parse(await cancelCollection(inputs, request.collection_id)));
  });
  return app;
}
