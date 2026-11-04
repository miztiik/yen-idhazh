/** Retain each analyzed article's private entity record until its run writer has drained. */
import { ArticleEntitiesSchema } from "@idhazh/common-contracts";
import type { ArticleEntities } from "@idhazh/common-contracts";
import type { PlanInputs } from "./load-plan-inputs";
import type { RunContext } from "./resolve-run-context";
import { articleEntitiesPath } from "./selected-artifact-path";
import { createPrivateJsonlWriter } from "./write-private-jsonl";
import { recognizeArticleEntities } from "./recognize-article-entities";
import { withPlannerFailure } from "./api/plan-failure";
import { writeJsonLine } from "./logging/structured-logger";

type EntityInput = Pick<ArticleEntities, "article_id" | "candidate_id" | "feed_id" | "observed_at"> & {
  title: string | null; article_text: string | null;
};
type Writer = {
  context: RunContext; output: ReturnType<typeof createPrivateJsonlWriter<ArticleEntities>>;
  failure?: unknown;
};
const writers = new WeakMap<PlanInputs, Map<string, Writer>>();
const executionKey = (context: RunContext) => `${context.run_id}:${context.writer.attempt}`;

export async function recordArticleEntities(inputs: PlanInputs, context: RunContext, input: EntityInput) {
  let current = writers.get(inputs);
  if (current === undefined) { current = new Map(); writers.set(inputs, current); }
  const key = executionKey(context);
  let writer = current.get(key);
  if (writer === undefined) {
    writer = { context, output: createPrivateJsonlWriter(inputs.root,
      articleEntitiesPath(inputs.settings.inputs.artifact_root, context), ArticleEntitiesSchema) };
    current.set(key, writer);
  }
  const capture = { operation: "recognize-entities" as const,
    execution: context, limits: inputs.settings.diagnostics.failure };
  try {
    const record = recognizeArticleEntities({
      ...input, run_id: context.run_id, traceId: context.traceId,
      attempt: context.writer.attempt, git_sha: context.writer.git_sha,
      limits: inputs.settings.diagnostics.named_entities,
    }, capture);
    await writer.output.append(record);
    if (record.failure !== null) writeJsonLine({ event: "planner_entity_analysis_incomplete", failure: record.failure });
  } catch (error) {
    const failure = withPlannerFailure(error, { ...capture, operation: "write-entities" });
    writer.failure ??= failure;
    writeJsonLine({ event: "planner_entity_append_failed", failure: failure.failure });
  }
}

export async function finishArticleEntities(inputs: PlanInputs, context?: RunContext) {
  const current = writers.get(inputs);
  if (current === undefined) return;
  const key = context === undefined ? undefined : executionKey(context);
  const writer = key === undefined ? undefined : current.get(key);
  const selected = key === undefined ? [...current] : writer === undefined ? [] : [[key, writer] as const];
  const failures: unknown[] = [];
  await Promise.all(selected.map(async ([key, writer]) => {
    let failed = false;
    try { await writer.output.finish(); }
    catch (error) {
      failed = true;
      const failure = withPlannerFailure(writer.failure === undefined ? error
        : new AggregateError([writer.failure, error], "Entity output could not be completed"), {
        operation: "write-entities", execution: writer.context, limits: inputs.settings.diagnostics.failure,
      });
      failures.push(failure);
      writeJsonLine({ event: "planner_entity_finish_failed", failure: failure.failure });
    } finally { current.delete(key); }
    if (!failed && writer.failure !== undefined) failures.push(writer.failure);
  }));
  if (failures.length) throw new AggregateError(failures, "Article entity artifact preparation failed");
}
