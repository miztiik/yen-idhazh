/** Validate diagnostic bounds and read earlier saved responses without invented evidence. */
import { expect, test } from "bun:test";
import {
  ARTICLE_ENTITIES_VERSION, ArticleEntitiesSchema, PlannerErrorResponseSchema,
  PlannerFailureSchema, PlannerSavedResponseSchema, deriveCandidateId, readArticleEntities,
} from "../src/index";

async function responseRecording() {
  return Bun.file(new URL("../../../tests/fixtures/feed-ingest-plan/entry-points/response.json", import.meta.url)).json();
}

test("earlier outcome and refusal responses retain explicitly unavailable failure evidence", async () => {
  const original = await responseRecording();
  const legacy = Object.fromEntries(Object.entries(original).filter(([field]) => field !== "failure"));
  const read = PlannerSavedResponseSchema.parse(legacy);
  expect(read.failure).toBeNull();
  expect(PlannerErrorResponseSchema.parse({
    code: "PLAN_FAILED", issues: [{ field: null, message: "Planner operation did not complete" }],
  }).failure).toBeNull();
});

test("entity records require scoped bounds, explicit omissions and current version on read", async () => {
  const recorded = PlannerSavedResponseSchema.parse(await responseRecording());
  if (!("planning_complete" in recorded)) throw new Error("Expected the recorded planner outcome");
  const record = ArticleEntitiesSchema.parse({
    schema_version: ARTICLE_ENTITIES_VERSION,
    run_id: recorded.run_id, attempt: recorded.attempt, correlation_id: recorded.correlation_id,
    git_sha: "a".repeat(40), article_id: recorded.selected_url_keys[0],
    candidate_id: deriveCandidateId(recorded.run_id, "recorded-news", 0), feed_id: "recorded-news",
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
    execution: { run_id: "2026-11-02-700", attempt: 1, correlation_id: null, git_sha: "a".repeat(40) },
    causes: [], omitted_causes: 0,
  });
  expect(() => PlannerFailureSchema.parse({ ...failure, stack: "Private raw stack" })).toThrow();
  expect(() => PlannerFailureSchema.parse({
    ...failure, source: { file: "C:/private/article.ts", line: 1 },
  })).toThrow();
  expect(() => PlannerFailureSchema.parse({
    ...failure, source: { file: "../article.ts", line: 1 },
  })).toThrow();
  const { execution: _execution, causes: _causes, omitted_causes: _omitted, schema_version: _version, ...detail } = failure;
  expect(() => PlannerFailureSchema.parse({ ...failure, causes: [detail, detail, detail, detail] })).toThrow();
});
