/** Route run-owned collection lifecycle changes without exposing article text. */
import { Hono } from "hono";
import type { PlanInputs } from "../../load-plan-inputs";
import type { PlanRuntime } from "../../run-feed-plan";
import {
  beginCollection, cancelCollection, collectionExists, completeCollection, finalizeCollection, releaseCollection,
} from "../collection-operation";
import {
  CollectionExistsResponseSchema, CollectionReferenceSchema, CollectionResponseSchema,
  CompletedCollectionSchema, CancelledCollectionSchema,
  FinalizeCollectionRequestSchema, FinalizedCollectionSchema, ReleaseCollectionRequestSchema, ReleasedCollectionSchema,
} from "../collection-contracts";
import { readRequestBody } from "./stages.route";

export function collectionRoute(inputs: PlanInputs, runtime: () => PlanRuntime) {
  const app = new Hono();
  app.post("/collections", async c => c.json(CollectionResponseSchema.parse(
    await beginCollection(await readRequestBody(c.req.raw), inputs, runtime()),
  )));
  app.post("/collections/exists", async c => c.json(CollectionExistsResponseSchema.parse(
    collectionExists(await readRequestBody(c.req.raw), inputs),
  )));
  app.post("/collections/complete", async c => {
    const request = CollectionReferenceSchema.parse(await readRequestBody(c.req.raw));
    return c.json(CompletedCollectionSchema.parse(await completeCollection(inputs, request.collection_id)));
  });
  app.post("/collections/cancel", async c => {
    const request = CollectionReferenceSchema.parse(await readRequestBody(c.req.raw));
    return c.json(CancelledCollectionSchema.parse(await cancelCollection(inputs, request.collection_id)));
  });
  app.post("/collections/finalize", async c => {
    const request = FinalizeCollectionRequestSchema.parse(await readRequestBody(c.req.raw));
    return c.json(FinalizedCollectionSchema.parse(await finalizeCollection(request, inputs)));
  });
  app.post("/collections/release", async c => {
    const request = ReleaseCollectionRequestSchema.parse(await readRequestBody(c.req.raw));
    return c.json(ReleasedCollectionSchema.parse(releaseCollection(request, inputs)));
  });
  return app;
}
