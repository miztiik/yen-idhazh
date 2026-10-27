/** Dispatch a validated document request to its shared fetch or parse execution unit. */
import { FetchRequestSchema, ParseRequestSchema } from "./operation-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { openOperationStore } from "./operation-store";
import { prepareOperation, operationConfigFingerprint } from "./operation-context";
import { fetchDocument, resolveFetchParent } from "./fetch-operation";
import { parseFetchedDocument } from "./parse-operation";
import { documentState, checkFetchedDocument, appendDocumentTiming } from "./document-state";
import { PlanError } from "./plan-request";
import { FetchResponseSchema, ParseResponseSchema } from "./document-response.schema";
import { stageStore } from "./stage-store";

export { proposedOperation, prepareOperation, operationConfigFingerprint } from "./operation-context";
export async function executeDocumentOperation(
  operation: "fetch" | "parse", raw: unknown, inputs: PlanInputs, runtime: PlanRuntime, signal?: AbortSignal,
) {
  const request = operation === "fetch" ? FetchRequestSchema.parse(raw) : ParseRequestSchema.parse(raw);
  if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled", "enabled");
  const store = await openOperationStore(inputs.outputRoot);
  try {
    if ("feed_id" in request) {
      const parent = resolveFetchParent(request, inputs, runtime, store);
      const proposed = prepareOperation("fetch", request.request_id, request, request.correlation_id, inputs, runtime, parent?.root.run_id);
      const record = await store.execute(proposed, async record => {
        const begin = performance.now();
        try {
          const result = await fetchDocument(request, record, inputs, runtime, parent, store, signal);
          await appendDocumentTiming(inputs, record.run_id, { operation: "fetch", duration_ms: Math.round(performance.now() - begin),
            status: result.artifact.failure === null ? "completed" : "failed" });
          return result;
        } catch (error) {
          await appendDocumentTiming(inputs, record.run_id, { operation: "fetch", duration_ms: Math.round(performance.now() - begin), status: "failed" });
          throw error;
        }
      });
      FetchResponseSchema.parse(JSON.parse(record.response_json!));
      return record.response_json!;
    }
    const fetched = store.get(request.fetch_request_id);
    if (fetched === null) throw new PlanError("ARTIFACT_NOT_FOUND", "No completed fetch exists", "fetch_request_id");
    const proposed = prepareOperation("parse", request.request_id, request, request.correlation_id, inputs, runtime, fetched.run_id);
    const record = await store.execute(proposed, async record => {
      const begin = performance.now();
      try {
        const result = await parseFetchedDocument(request, record, fetched, inputs, runtime, store, signal);
        await appendDocumentTiming(inputs, record.run_id, { operation: "parse", duration_ms: Math.round(performance.now() - begin),
          status: ParseResponseSchema.parse(JSON.parse(result.response_json)).failure === null ? "completed" : "failed" });
        return result;
      } catch (error) {
        await appendDocumentTiming(inputs, record.run_id, { operation: "parse", duration_ms: Math.round(performance.now() - begin), status: "failed" });
        throw error;
      }
    });
    const response = ParseResponseSchema.parse(JSON.parse(record.response_json!));
    if (!stageStore(inputs).has(response.batch_id)) throw new PlanError("REQUEST_INCOMPLETE", "Parsed batch has expired; parse its saved response with a new request key", "request_id");
    return record.response_json!;
  } finally { store.close(); }
}
export async function readDocumentHealthBatch(batchId: string, inputs: PlanInputs, runtime: PlanRuntime) {
  const store = await openOperationStore(inputs.outputRoot);
  try {
    const record = store.get(batchId);
    if (record === null || record.operation !== "fetch" || record.state !== "complete") throw new PlanError("ARTIFACT_NOT_FOUND", "No completed document work batch exists", "batch_id");
    if (record.config_sha256 !== operationConfigFingerprint(inputs, runtime)) throw new PlanError("REQUEST_CONFLICT", "Document configuration differs", "batch_id");
    const artifact = checkFetchedDocument(record, inputs);
    const parent = artifact.parent_fetch_request_id === null ? undefined : store.get(artifact.parent_fetch_request_id);
    if (parent === null) throw new PlanError("ARTIFACT_NOT_FOUND", "Fetched article parent is missing", "batch_id");
    return await documentState(record, inputs, runtime, store, parent);
  } finally { store.close(); }
}
