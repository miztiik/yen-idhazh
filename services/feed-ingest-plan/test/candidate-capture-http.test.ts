/** Do captured article inputs retain their identity and live ownership through the real local API? */
import { expect, test } from "bun:test";
import {
  CandidateIdSchema, createCandidateId, createRootContext, ParsedFeedBatchSchema, PLANNER_API_PREFIX, writeTraceContext,
} from "@idhazh/common-contracts";
import { CompletedCollectionSchema } from "../src/api/collection-contracts";
import { FetchResponseSchema, ParseResponseSchema } from "../src/api/document-response.schema";
import { operationLink } from "../src/api/operation-context";
import { stageStore } from "../src/api/stage-store";
import { PlanError } from "../src/api/plan-request";
import { createPlanTestServer } from "./plan-test-server";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";

test("two direct URLs in one collection retain two inputs; a fresh repeated URL is a third input", async () => {
  const fixture = await recordedPlan([source({ url: "https://news.example/empty.xml" })]);
  const app = createPlanTestServer(fixture.inputs, fixture.runtime);
  const caller = createRootContext();
  async function post(operation: string, value: unknown) {
    const response = await app.request(`${PLANNER_API_PREFIX}/${operation}`, {
      method: "POST", headers: { "content-type": "application/json", ...writeTraceContext(caller) },
      body: JSON.stringify(value),
    });
    const body: unknown = await response.json();
    expect(response.status, JSON.stringify(body)).toBe(200);
    return body;
  }
  try {
    await post("collections", { request: {} });
    const feed = FetchResponseSchema.parse(await post("fetch", {
      traceId: caller.traceId, feed_id: "recorded-news", fetch_item_type: "feed",
    }));
    await post("parse", { links: [operationLink(feed)] });
    const captured = [];
    for (const url of ["https://news.example/story?id=one", "https://news.example/story?id=two",
      "https://news.example/story?id=one"]) {
      const fetched = FetchResponseSchema.parse(await post("fetch", {
        traceId: caller.traceId, feed_id: "recorded-news", fetch_item_type: "article", url,
      }));
      const parsed = ParseResponseSchema.parse(await post("parse", { links: [operationLink(fetched)] }));
      if (fetched.fetch_item_type !== "article" || parsed.fetch_item_type !== "article") {
        throw new Error("Direct article work must retain its captured article identity");
      }
      const batch = stageStore(fixture.inputs).read("parsed", parsed, ParsedFeedBatchSchema);
      expect(batch.candidates).toHaveLength(1);
      expect(CandidateIdSchema.parse(fetched.candidate_id)).toBe(parsed.candidate_id);
      expect(batch.candidates[0]!.candidate_id).toBe(fetched.candidate_id);
      expect(batch.candidates[0]!.entry_ordinal).toBeNull();
      captured.push(batch.candidates[0]!);
    }
    const completion = CompletedCollectionSchema.parse(await post("collections/complete", { traceId: caller.traceId }));
    const batch = stageStore(fixture.inputs).read("parsed", completion, ParsedFeedBatchSchema);
    expect(batch.candidates).toHaveLength(3);
    expect(batch.candidates.map(candidate => candidate.candidate_id).sort())
      .toEqual(captured.map(candidate => candidate.candidate_id).sort());
    expect(new Set(batch.candidates.map(candidate => candidate.candidate_id)).size).toBe(3);
    expect(new Set(batch.candidates.map(candidate => candidate.url_key)).size).toBe(2);
    expect(captured[0]!.url_key).toBe(captured[2]!.url_key);
    expect(captured[0]!.candidate_id).not.toBe(captured[2]!.candidate_id);
  } finally { await app.close(); await fixture.close(); }
});

test("a valid candidate cannot replace its producing parse, captured document or one-shot claim", async () => {
  const fixture = await recordedPlan();
  const app = createPlanTestServer(fixture.inputs, fixture.runtime);
  const post = (operation: string, value: unknown) => app.request(`${PLANNER_API_PREFIX}/${operation}`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(value),
  });
  try {
    const feed = FetchResponseSchema.parse(await (await post("fetch", {
      feed_id: "recorded-news", fetch_item_type: "feed",
    })).json());
    const parsedFeed = ParseResponseSchema.parse(await (await post("parse", { links: [operationLink(feed)] })).json());
    if (parsedFeed.fetch_item_type !== "feed") throw new Error("Recorded feed must return captured offers");
    const offer = parsedFeed.offers[0]!;
    const request = { fetch_item_type: "article", candidate_id: offer.candidate_id, links: [operationLink(parsedFeed)] };
    const unknown = await post("fetch", { ...request, candidate_id: createCandidateId() });
    expect(unknown.status).toBe(400);
    expect(await unknown.json()).toMatchObject({ code: "INVALID_REQUEST" });
    expect((await post("fetch", { ...request, links: [operationLink(feed)] })).status).toBe(404);
    expect((await post("fetch", { ...request, candidate_id: "a".repeat(64) })).status).toBe(400);
    const { candidate_id, ...retired } = request;
    expect((await post("fetch", { ...retired, offer_id: candidate_id })).status).toBe(400);
    expect(fixture.transport.requests).toHaveLength(1);

    const fetched = FetchResponseSchema.parse(await (await post("fetch", request)).json());
    if (fetched.fetch_item_type !== "article") throw new Error("Offered article must retain its captured candidate");
    expect(fetched.candidate_id).toBe(offer.candidate_id);
    const store = stageStore(fixture.inputs);
    const held = store.fetchedDocument(fetched)!;
    const captured = store.read("parsed", parsedFeed, ParsedFeedBatchSchema).offers
      .find(value => value.candidate_id === offer.candidate_id)!;
    expect(held.document.entry_ordinal).toBe(captured.entry.entry_ordinal);
    expect((await post("fetch", request)).status).toBe(409);
    const forgedId = createCandidateId();
    expect(() => store.rememberFetchedDocument(fetched, {
      ...held.document, candidate_id: forgedId,
      observation: { ...held.document.observation, candidate_id: forgedId },
      attempt_observations: held.document.attempt_observations.map(value => ({ ...value, candidate_id: forgedId })),
    })).toThrow(PlanError);
    expect(store.fetchedDocument(fetched)?.candidate_id).toBe(offer.candidate_id);

    const parse = { links: [operationLink(fetched)] };
    const concurrency = fixture.inputs.harvest.config.harvest.concurrency;
    fixture.inputs.harvest.config.harvest.concurrency++;
    expect((await post("parse", parse)).status).toBe(409);
    fixture.inputs.harvest.config.harvest.concurrency = concurrency;
    const attempt = fixture.runtime.attempt;
    fixture.runtime.attempt = (attempt ?? 1) + 1;
    expect((await post("parse", parse)).status).toBe(409);
    if (attempt === undefined) delete fixture.runtime.attempt;
    else fixture.runtime.attempt = attempt;
    const parsed = ParseResponseSchema.parse(await (await post("parse", parse)).json());
    if (parsed.fetch_item_type !== "article") throw new Error("Article parse must retain its captured candidate");
    expect(parsed.candidate_id).toBe(offer.candidate_id);
    expect((await post("parse", parse)).status).toBe(404);
    expect(fixture.transport.requests).toHaveLength(2);
  } finally { await app.close(); await fixture.close(); }
});
