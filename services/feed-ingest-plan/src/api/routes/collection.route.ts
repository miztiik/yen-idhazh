/** Route run-owned collection lifecycle changes without exposing article text. */
import { Hono } from "hono";
import { PLANNER_API_PATHS } from "@idhazh/common-contracts";
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
import { captureRequestRuntime } from "../operation-context";

export function collectionRoute(inputs: PlanInputs, runtime: () => PlanRuntime) {
  const app = new Hono();
  app.post(PLANNER_API_PATHS.startCollection, async c => {
    const captured = captureRequestRuntime(runtime(), c.req.raw.headers);
    return c.json(CollectionResponseSchema.parse(await beginCollection(await readRequestBody(c.req.raw), inputs, {
      ...captured, signal: captured.signal === undefined ? c.req.raw.signal
        : AbortSignal.any([captured.signal, c.req.raw.signal]),
    })));
  });
  app.post(PLANNER_API_PATHS.checkCollection, async c => c.json(CollectionExistsResponseSchema.parse(
    collectionExists(await readRequestBody(c.req.raw), inputs),
  )));
  app.post(PLANNER_API_PATHS.completeCollection, async c => {
    const request = CollectionReferenceSchema.parse(await readRequestBody(c.req.raw));
    return c.json(CompletedCollectionSchema.parse(await completeCollection(inputs, request.traceId)));
  });
  app.post(PLANNER_API_PATHS.cancelCollection, async c => {
    const request = CollectionReferenceSchema.parse(await readRequestBody(c.req.raw));
    return c.json(CancelledCollectionSchema.parse(await cancelCollection(inputs, request.traceId)));
  });
  app.post(PLANNER_API_PATHS.finalizeCollection, async c => {
    const request = FinalizeCollectionRequestSchema.parse(await readRequestBody(c.req.raw));
    return c.json(FinalizedCollectionSchema.parse(await finalizeCollection(request, inputs)));
  });
  app.post(PLANNER_API_PATHS.releaseCollection, async c => {
    const request = ReleaseCollectionRequestSchema.parse(await readRequestBody(c.req.raw));
    return c.json(ReleasedCollectionSchema.parse(releaseCollection(request, inputs)));
  });
  return app;
}
