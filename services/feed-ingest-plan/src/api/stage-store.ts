/** Hold bounded live server references without evicting documents needed by active work. */
import { z } from "zod";
import { FetchedDocumentSchema, RequestIdSchema } from "@idhazh/common-contracts";
import type { FetchedDocument, PlannerStageContext } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import { PlanError } from "./plan-request";
import type { DocumentOperationContext } from "./operation-context";

export type BatchStage = "parsed" | "selected" | "partitioned";
type BatchIdentity = { batch_id: string; context: PlannerStageContext };
export type ExecutionOwnership = {
  selection_claimed: boolean; partition_claimed: boolean;
  scope: "plan" | "standalone"; health_fingerprint: string | null;
};
type HeldBatch = {
  stage: BatchStage; value: unknown; execution: string; run_id: string; ownership: ExecutionOwnership;
};
export type FetchedDocumentReference = DocumentOperationContext & { document: FetchedDocument };
type HeldDocument = DocumentOperationContext & { document?: FetchedDocument; claimed: boolean };
function executionKey(context: PlannerStageContext) { return `${context.run_id}:${context.writer.attempt}`; }
export class StageStore {
  private readonly batches = new Map<string, HeldBatch>();
  private readonly documents = new Map<string, HeldDocument>();
  private readonly documentRequests = new Set<string>();
  private readonly documentRuns = new Map<string, string>();
  private readonly retainedRuns = new Set<string>();
  constructor(private readonly capacity: number) { z.int().positive().parse(capacity); }
  retainRun(runId: string) { this.retainedRuns.add(runId); }
  releaseRun(runId: string) {
    this.retainedRuns.delete(runId);
    for (const [id, document] of this.documents) {
      if (document.context.run_id === runId && !document.claimed && !this.documentRequests.has(id)) {
        this.documents.delete(id);
      }
    }
  }
  isRunActive(runId: string) {
    return this.retainedRuns.has(runId)
      || [...this.documents.values()].some(document => document.context.run_id === runId);
  }
  beginFetch(context: DocumentOperationContext) {
    const id = RequestIdSchema.parse(context.request_id);
    if (this.documents.has(id) || this.documentRequests.has(id)) {
      throw new PlanError("REQUEST_CONFLICT", "Document request is already owned by live work", "request_id");
    }
    if (this.documents.size >= this.capacity) {
      throw new PlanError("REQUEST_BUSY", "Live document capacity is occupied; consume current fetch references first", "request_id");
    }
    this.documentRequests.add(id);
    this.documents.set(id, { ...context, claimed: false });
  }
  rememberFetchedDocument(id: string, document: FetchedDocument) {
    const held = this.documents.get(id);
    if (held === undefined) throw new PlanError("ARTIFACT_NOT_FOUND", "Fetch reference is no longer live", "fetch_request_id");
    this.documents.set(id, { ...held, document: FetchedDocumentSchema.parse(document) });
  }
  fetchedDocument(id: string): FetchedDocumentReference | undefined {
    const held = this.documents.get(id);
    return held?.document === undefined ? undefined : {
      request_id: held.request_id, context: held.context, config_sha256: held.config_sha256, document: held.document,
    };
  }
  finishFetch(id: string, retain: boolean) {
    this.documentRequests.delete(id);
    const document = this.documents.get(id)?.document;
    if (!retain || document?.body == null || document.failure !== null) this.documents.delete(id);
  }
  claimDocument(fetchId: string, requestId: string, articleId: string, correlationId: string, fingerprint: string): FetchedDocumentReference {
    const id = RequestIdSchema.parse(requestId);
    const held = this.documents.get(RequestIdSchema.parse(fetchId));
    if (held?.document === undefined) {
      throw new PlanError("ARTIFACT_NOT_FOUND", "No current completed fetched document exists", "fetch_request_id");
    }
    if (held.document.article_id !== articleId || held.context.correlation_id !== correlationId) {
      throw new PlanError("INVALID_REQUEST", "Parse identity differs from its fetched document", "article_id");
    }
    if (held.config_sha256 !== fingerprint) {
      throw new PlanError("REQUEST_CONFLICT", "Fetched configuration differs", "fetch_request_id");
    }
    if (held.claimed || this.documentRequests.has(fetchId) || this.documentRequests.has(id) || this.documents.has(id)) {
      throw new PlanError("REQUEST_CONFLICT", "Document request is already owned by live work", "request_id");
    }
    held.claimed = true;
    this.documentRequests.add(id);
    return { request_id: held.request_id, context: held.context, config_sha256: held.config_sha256, document: held.document };
  }
  consumeDocument(fetchId: string, requestId: string) {
    this.documents.delete(fetchId);
    this.documentRequests.delete(requestId);
  }
  rememberDocumentWork(fetchId: string, runId: string) { this.documentRuns.set(fetchId, runId); }
  documentRun(fetchId: string) { return this.documentRuns.get(RequestIdSchema.parse(fetchId)); }
  forgetDocumentWork(runId: string) {
    for (const [id, run] of this.documentRuns) {
      if (run === runId) this.documentRuns.delete(id);
    }
  }
  releaseDocuments() {
    this.documents.clear();
    this.documentRequests.clear();
    this.retainedRuns.clear();
    this.documentRuns.clear();
  }
  write<T extends BatchIdentity>(stage: BatchStage, schema: z.ZodType<T>, raw: unknown): T {
    const value = schema.parse(raw);
    if (this.batches.has(value.batch_id)) throw new PlanError("REQUEST_CONFLICT", "Batch identity already exists", "batch_id");
    const execution = executionKey(value.context);
    const ownership: ExecutionOwnership = [...this.batches.values()].find(batch => batch.execution === execution)?.ownership ?? {
      selection_claimed: false, partition_claimed: false, scope: "standalone", health_fingerprint: null,
    };
    if (stage !== "parsed") ownership.selection_claimed = true;
    if (stage === "partitioned") ownership.partition_claimed = true;
    while (this.batches.size >= this.capacity) {
      const expired = [...this.batches].find(([, batch]) => !this.isRunActive(batch.run_id));
      if (expired === undefined) throw new PlanError("REQUEST_BUSY", "Stage capacity is occupied by active work", "batch_id");
      this.batches.delete(expired[0]);
    }
    this.batches.set(value.batch_id, { stage, value: structuredClone(value), execution, run_id: value.context.run_id, ownership });
    return value;
  }
  read<T extends { batch_id: string }>(stage: BatchStage, id: string, schema: z.ZodType<T>): T {
    const batch = this.batches.get(RequestIdSchema.parse(id));
    if (batch === undefined || batch.stage !== stage) {
      throw new PlanError("ARTIFACT_NOT_FOUND", "No current server-owned batch exists for this stage", "batch_id");
    }
    return schema.parse(structuredClone(batch.value));
  }
  inspect(id: string) {
    const batch = this.batches.get(RequestIdSchema.parse(id));
    if (batch === undefined) throw new PlanError("ARTIFACT_NOT_FOUND", "No current server-owned batch exists", "batch_id");
    return { stage: batch.stage, value: structuredClone(batch.value) };
  }
  has(id: string) { return this.batches.has(RequestIdSchema.parse(id)); }
  ownership(id: string): ExecutionOwnership {
    const held = this.batches.get(RequestIdSchema.parse(id));
    if (held === undefined) throw new PlanError("ARTIFACT_NOT_FOUND", "Current batch has expired", "batch_id");
    return held.ownership;
  }
  claimSelection(id: string) {
    const claim = this.ownership(id);
    if (claim.selection_claimed) return false;
    claim.selection_claimed = true;
    return true;
  }
  claimPartition(id: string) {
    const claim = this.ownership(id);
    if (claim.partition_claimed) return false;
    claim.partition_claimed = true;
    return true;
  }
  rememberHealth(runId: string, fingerprint: string) {
    for (const batch of this.batches.values()) {
      if (batch.run_id === runId) batch.ownership.health_fingerprint = fingerprint;
    }
  }
  replace<T extends BatchIdentity>(stage: BatchStage, schema: z.ZodType<T>, raw: unknown): T {
    const value = schema.parse(raw);
    const held = this.batches.get(value.batch_id);
    if (held === undefined || held.stage !== stage) throw new PlanError("ARTIFACT_NOT_FOUND", "Current batch has expired", "batch_id");
    if (held.execution !== executionKey(value.context)) throw new PlanError("ARTIFACT_INVALID", "Stage update changed its execution ownership", "batch_id");
    this.batches.set(value.batch_id, { ...held, value: structuredClone(value) });
    return value;
  }
  update<T extends BatchIdentity>(stage: BatchStage, id: string, schema: z.ZodType<T>, update: (current: T) => T) {
    const value = schema.parse(update(this.read(stage, id, schema)));
    if (value.batch_id !== id) throw new PlanError("ARTIFACT_INVALID", "Stage update changed its server-owned batch identity", "batch_id");
    return this.replace(stage, schema, value);
  }
}
const stores = new WeakMap<PlanInputs, StageStore>();
export function stageStore(inputs: PlanInputs) {
  let store = stores.get(inputs);
  if (store === undefined) {
    store = new StageStore(inputs.settings.listener.max_stage_batches);
    stores.set(inputs, store);
  }
  return store;
}
