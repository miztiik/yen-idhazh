/** Append body-free failure metadata and close its writer before artifact delivery. */
import { RawDocumentFailureSchema, FetchedDocumentSchema } from "@idhazh/common-contracts";
import type { RawDocumentFailure, FetchedDocument } from "@idhazh/common-contracts";
import { diagnosticUrl } from "./logging/diagnostic-url";
import type { PlanInputs } from "./load-plan-inputs";
import type { RunContext } from "./resolve-run-context";
import { rawDocumentContentsPath } from "./selected-artifact-path";
import { withPlannerFailure } from "./api/plan-failure";
import { writeJsonLine } from "./logging/structured-logger";
import { createPrivateJsonlWriter } from "./write-private-jsonl";

type FailureInput = Omit<RawDocumentFailure, "schema_version" | "document"> & { document: FetchedDocument };

export function failureMetadata(raw: FailureInput): RawDocumentFailure {
  const { body: _body, observation, attempt_observations, canonical_url, ...document } = FetchedDocumentSchema.parse(raw.document);
  const withoutRun = ({ run_id: _run, ...value }: FetchedDocument["observation"]) => value;
  const safe = (url: string | null) => url === null ? null : diagnosticUrl(url) ?? null;
  return RawDocumentFailureSchema.parse({
    ...raw, document: { ...document, canonical_url: diagnosticUrl(canonical_url) ?? null,
      requested_url: safe(document.requested_url), final_attempted_url: safe(document.final_attempted_url),
      failed_url: safe(document.failed_url),
      attempts: document.attempts.map(attempt => ({ ...attempt, request_url: safe(attempt.request_url) })),
      redirects: document.redirects.map(redirect => ({ ...redirect,
        request_url: safe(redirect.request_url), destination_url: safe(redirect.destination_url) })),
      observation: withoutRun(observation), attempt_observations: attempt_observations.map(withoutRun) },
  });
}

function createFailureWriter(inputs: PlanInputs, context: RunContext) {
  const output = createPrivateJsonlWriter(inputs.root,
    rawDocumentContentsPath(inputs.settings.inputs.artifact_root, context),
    RawDocumentFailureSchema.safeExtend({ document: FetchedDocumentSchema }).transform(failureMetadata));
  return {
    append(raw: FailureInput) {
      return output.append(raw);
    },
    finish: () => output.finish(),
    context,
  };
}

const writers = new WeakMap<PlanInputs, Map<string, ReturnType<typeof createFailureWriter>>>();
const executionKey = (context: RunContext) => `${context.run_id}:${context.writer.attempt}`;

export async function dumpRawDocumentFailure(inputs: PlanInputs, context: RunContext, raw: FailureInput) {
  if (!inputs.settings.dump_raw_document_contents) return;
  let current = writers.get(inputs);
  if (current === undefined) { current = new Map(); writers.set(inputs, current); }
  const key = executionKey(context);
  let writer = current.get(key);
  if (writer === undefined) { writer = createFailureWriter(inputs, context); current.set(key, writer); }
  try { await writer.append(raw); }
  catch (error) {
    const failure = withPlannerFailure(error, {
      operation: "write-document-failures", execution: context, limits: inputs.settings.diagnostics.failure,
    });
    writeJsonLine({ event: "planner_raw_document_append_failed", failure: failure.failure });
  }
}

export async function finishRawDocumentFailures(inputs: PlanInputs, context?: RunContext) {
  const current = writers.get(inputs);
  if (current === undefined) return;
  const key = context === undefined ? undefined : executionKey(context);
  const writer = key === undefined ? undefined : current.get(key);
  const selected = key === undefined ? [...current] : writer === undefined ? [] : [[key, writer] as const];
  const results = await Promise.allSettled(selected.map(([, writer]) => writer.finish()));
  const failures: unknown[] = [];
  for (const [index, result] of results.entries()) {
    current.delete(selected[index]![0]);
    if (result.status === "rejected") {
      const failure = withPlannerFailure(result.reason, {
        operation: "write-document-failures", execution: selected[index]![1].context,
        limits: inputs.settings.diagnostics.failure,
      });
      failures.push(failure);
      writeJsonLine({ event: "planner_raw_document_finish_failed", failure: failure.failure });
    }
  }
  if (failures.length) throw new AggregateError(failures, "Raw document artifact preparation failed");
}
