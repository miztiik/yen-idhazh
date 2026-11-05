/** Which diagnostic bounds and unavailable evidence must current planner readers preserve? */
import { expect, test } from "bun:test";
import {
  ARTICLE_ENTITIES_VERSION, ArticleEntitiesSchema, PlannerErrorResponseSchema,
  PlannerFailureSchema, PlannerRunResponseSchema, PlannerSavedResponseSchema, createCandidateId, readArticleEntities,
} from "../src/index";

async function responseRecording() {
  return Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/entry-points/response.json", import.meta.url)).json();
}

test("outcome and refusal responses without captured failures retain unavailable evidence", async () => {
  const original = await responseRecording();
  const withoutFailure = Object.fromEntries(Object.entries(original).filter(([field]) => field !== "failure"));
  const read = PlannerSavedResponseSchema.parse(withoutFailure);
  expect(read.failure).toBeNull();
  expect(PlannerErrorResponseSchema.parse({
    code: "PLAN_FAILED", issues: [{ field: null, message: "Planner operation did not complete" }],
  }).failure).toBeNull();
});

test("the complete result requires its actual report outcome and keeps report failure separate from planning facts", async () => {
  const recorded = PlannerRunResponseSchema.parse(await responseRecording());
  const failure = PlannerFailureSchema.parse({
    operation: "feed-health-summary", error_type: "RangeError", safe_cause: "out-of-range",
    system_code: null, source: null,
    execution: { run_id: recorded.run_id, attempt: recorded.attempt, traceId: recorded.traceId, spanId: null, git_sha: null },
    causes: [], omitted_causes: 0,
  });
  const health = { status: "failed" as const, failure };
  expect(PlannerRunResponseSchema.safeParse({ ...recorded, health, failure: null }).success).toBe(false);
  expect(PlannerRunResponseSchema.safeParse({ ...recorded, health: undefined }).success).toBe(false);
  expect(PlannerRunResponseSchema.safeParse({ ...recorded, health: null }).success).toBe(false);
  const result = PlannerRunResponseSchema.parse({ ...recorded, health, failure });
  expect(result.health).toEqual(health);
  expect(result.planning_complete).toBe(recorded.planning_complete);
  expect(result.status).toBe(recorded.status);
  expect(result.failure_code).toBe(recorded.failure_code);
  expect(result.files).toEqual(recorded.files);
  expect(result.assignments).toEqual(recorded.assignments);
  expect(result.duration_ms).toBe(recorded.duration_ms);
});

test("entity records require scoped bounds, explicit omissions and current version on read", async () => {
  const recorded = PlannerSavedResponseSchema.parse(await responseRecording());
  if (!("planning_complete" in recorded)) throw new Error("Expected the recorded planner outcome");
  const record = ArticleEntitiesSchema.parse({
    schema_version: ARTICLE_ENTITIES_VERSION,
    run_id: recorded.run_id, attempt: recorded.attempt, traceId: recorded.traceId,
    git_sha: "a".repeat(40), article_id: recorded.selected_article_ids[0],
    candidate_id: createCandidateId(), feed_id: "recorded-news",
    observed_at: recorded.started_at, recognizer: "compromise",
    title_status: "complete", body_status: "complete", status: "complete",
    limits: { max_entities: 1, max_entity_chars: 20 },
    entities: [], omitted_entities: 0, oversized_entities: 0, failure: null,
  });
  expect(readArticleEntities(record)).toEqual(record);
  const { schema_version: _version, ...withoutVersion } = record;
  expect(() => readArticleEntities(withoutVersion)).toThrow();
  expect(() => readArticleEntities({ ...record, schema_version: "2026-11-01" })).toThrow();
  expect(() => readArticleEntities({ ...record, article_text: "Private article text" })).toThrow();
  expect(() => readArticleEntities({ ...record, omitted_entities: 1 })).toThrow();
  expect(() => readArticleEntities({ ...record, body_status: "unavailable" })).toThrow();
  expect(readArticleEntities({ ...record, body_status: "unavailable", status: "incomplete" }).status).toBe("incomplete");
  expect(() => readArticleEntities({ ...record, entities: [
    { kind: "person", scope: "title", text: "Ada Lovelace" },
    { kind: "person", scope: "body", text: "Ada Lovelace" },
  ] })).toThrow();
  expect(() => readArticleEntities({ ...record, entities: [
    { kind: "organization", scope: "body", text: "a".repeat(21) },
  ] })).toThrow();
});

test("safe failures reject raw stacks, absolute sources and unbounded causes", () => {
  const failure = PlannerFailureSchema.parse({
    operation: "select", error_type: "TypeError", safe_cause: "undefined-value",
    system_code: null, source: null,
    execution: { run_id: "2026-11-02-700", attempt: 1, traceId: null, spanId: null, git_sha: "a".repeat(40) },
    causes: [], omitted_causes: 0,
  });
  expect(() => PlannerFailureSchema.parse({ ...failure, stack: "Private raw stack" })).toThrow();
  const { schema_version: _missing, ...unversioned } = failure;
  expect(() => PlannerErrorResponseSchema.parse({
    code: "PLAN_FAILED", issues: [{ field: null, message: "Planner operation did not complete" }], failure: unversioned,
  })).toThrow();
  expect(() => PlannerFailureSchema.parse({
    ...failure, source: { file: "C:/private/article.ts", line: 1 },
  })).toThrow();
  expect(() => PlannerFailureSchema.parse({
    ...failure, source: { file: "../article.ts", line: 1 },
  })).toThrow();
  const { execution: _execution, causes: _causes, omitted_causes: _omitted, schema_version: _version, ...detail } = failure;
  expect(() => PlannerFailureSchema.parse({ ...failure, causes: [detail, detail, detail, detail] })).toThrow();
});
