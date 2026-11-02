/** Recognize original title and full sanitized body names without changing selection evidence. */
import nlp from "compromise";
import { ArticleEntitiesSchema } from "@idhazh/common-contracts";
import type { ArticleEntities, ArticleEntityLimits, PlannerFailure } from "@idhazh/common-contracts";
import { capturePlannerFailure, combinePlannerFailures } from "./api/plan-failure";
import type { FailureCaptureOptions } from "./api/plan-failure";

type EntityIdentity = Pick<ArticleEntities,
  "run_id" | "attempt" | "correlation_id" | "git_sha" | "article_id" | "candidate_id" | "feed_id" | "observed_at">;

export function recognizeArticleEntities(input: EntityIdentity & {
  title: string | null; article_text: string | null; limits: ArticleEntityLimits;
}, capture: FailureCaptureOptions): ArticleEntities {
  const entities: ArticleEntities["entities"] = [];
  let omitted_entities = 0;
  let oversized_entities = 0;
  let failure: PlannerFailure | null = null;
  function readScope(scope: "title" | "body", text: string | null): ArticleEntities["title_status"] {
    if (text === null) return "unavailable";
    try {
      const document = nlp(text);
      const names = [
        ["person", document.people()], ["place", document.places()], ["organization", document.organizations()],
      ] as const;
      for (const [kind, view] of names) {
        const distinct = new Set<string>();
        view.forEach(entity => {
          const name = entity.text({ keepEndPunct: false, keepSpace: false });
          if (name.length > 0) distinct.add(name);
        });
        for (const name of distinct) {
          const text = name;
          if (text.length > input.limits.max_entity_chars) { oversized_entities++; continue; }
          if (entities.length >= input.limits.max_entities) { omitted_entities++; continue; }
          entities.push({ kind, scope, text });
        }
      }
      return "complete";
    } catch (error) {
      const current = capturePlannerFailure(error, capture);
      failure = failure === null ? current : combinePlannerFailures(failure, current, capture.limits);
      return "failed";
    }
  }
  const title_status = readScope("title", input.title);
  const body_status = readScope("body", input.article_text);
  const { title: _title, article_text: _body, ...identity } = input;
  return ArticleEntitiesSchema.parse({
    ...identity, recognizer: "compromise", title_status, body_status, entities,
    status: title_status !== "complete" || body_status !== "complete" ? "incomplete"
      : omitted_entities > 0 || oversized_entities > 0 ? "truncated" : "complete",
    omitted_entities, oversized_entities, failure,
  });
}
