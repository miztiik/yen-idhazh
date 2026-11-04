/** Which original sanitized article entities may enter one private per-run JSONL record? */
import { z } from "zod";
import { CommitShaSchema, CountSchema, PositiveCountSchema, RunIdSchema, Sha256Schema, SlugSchema } from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";
import { PlannerFailureSchema } from "./planner-failure.schema";
import { TraceIdSchema } from "./operation-metadata.schema";

export const ARTICLE_ENTITIES_VERSION = "2026-11-03" as const;
// The private JSONL protocol caps a record; authored limits may select smaller output.
export const MAX_ARTICLE_ENTITIES = 1024;
export const MAX_ARTICLE_ENTITY_CHARS = 512;
export const ArticleEntityLimitsSchema = z.strictObject({
  max_entities: PositiveCountSchema.max(MAX_ARTICLE_ENTITIES),
  max_entity_chars: PositiveCountSchema.max(MAX_ARTICLE_ENTITY_CHARS),
});
export const ArticleEntitiesSchema = z.strictObject({
  schema_version: z.literal(ARTICLE_ENTITIES_VERSION).default(ARTICLE_ENTITIES_VERSION),
  run_id: RunIdSchema, attempt: PositiveCountSchema, traceId: TraceIdSchema,
  git_sha: CommitShaSchema, article_id: Sha256Schema, candidate_id: Sha256Schema, feed_id: SlugSchema,
  observed_at: RecordedInstantSchema.describe("Actual recorded UTC entity analysis instant."),
  recognizer: z.literal("compromise"),
  title_status: z.enum(["complete", "unavailable", "failed"]),
  body_status: z.enum(["complete", "unavailable", "failed"]),
  status: z.enum(["complete", "truncated", "incomplete"]),
  limits: ArticleEntityLimitsSchema,
  entities: z.array(z.strictObject({
    kind: z.enum(["person", "place", "organization"]), scope: z.enum(["title", "body"]),
    text: z.string().min(1).max(MAX_ARTICLE_ENTITY_CHARS),
  })).max(MAX_ARTICLE_ENTITIES),
  omitted_entities: CountSchema, oversized_entities: CountSchema,
  failure: PlannerFailureSchema.nullable(),
}).superRefine((value, ctx) => {
  const incomplete = value.title_status !== "complete" || value.body_status !== "complete" || value.failure !== null;
  const truncated = value.omitted_entities > 0 || value.oversized_entities > 0;
  if (value.status !== (incomplete ? "incomplete" : truncated ? "truncated" : "complete")) {
    ctx.addIssue({ code: "custom", message: "Entity status must state missing, failed or truncated evidence" });
  }
  if (value.entities.length > value.limits.max_entities
    || value.entities.some(entity => entity.text.length > value.limits.max_entity_chars)) {
    ctx.addIssue({ code: "custom", message: "Entity output exceeds its recorded authored limits" });
  }
  const keys = value.entities.map(entity => `${entity.scope}\n${entity.kind}\n${entity.text}`);
  if (new Set(keys).size !== keys.length) {
    ctx.addIssue({ code: "custom", message: "Entity names must be distinct within their kind and title/body scope" });
  }
  if (value.failure !== null && (value.failure.execution.run_id !== value.run_id
    || value.failure.execution.attempt !== value.attempt)) {
    ctx.addIssue({ code: "custom", message: "Entity failure belongs to another execution" });
  }
}).meta({
  version: ARTICLE_ENTITIES_VERSION,
  changelog: [
    { version: ARTICLE_ENTITIES_VERSION, change: "Associate entity output with its producing execution." },
    { version: "2026-11-02", change: "Declare scoped rule-based entities with explicit incomplete and truncated evidence." },
  ],
});
export type ArticleEntities = z.infer<typeof ArticleEntitiesSchema>;
export type ArticleEntityLimits = z.infer<typeof ArticleEntityLimitsSchema>;
export function readArticleEntities(raw: unknown): ArticleEntities {
  return ArticleEntitiesSchema.safeExtend({
    schema_version: ArticleEntitiesSchema.shape.schema_version.unwrap(),
  }).parse(raw);
}
