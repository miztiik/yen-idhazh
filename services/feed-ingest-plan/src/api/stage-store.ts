/** Hold bounded live server references without evicting documents needed by active work. */
import { z } from "zod";
import { FetchedDocumentSchema } from "@idhazh/common-contracts";
import type { FetchedDocument, OperationLink, OperationMetadata, PlannerStageContext } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import { PlanError } from "./plan-request";
import type { DocumentOperationContext } from "./operation-context";
import { operationKey, operationMetadata } from "./operation-context";

export type BatchStage = "parsed" | "selected" | "partitioned";
type BatchIdentity = OperationMetadata & { context: PlannerStageContext; config_sha256: string };
export type ExecutionOwnership = {
  selection_claimed: boolean; partition_claimed: boolean;
  scope: "plan" | "standalone"; health_fingerprint: string | null;
};
type HeldBatch = {
  stage: BatchStage; contents: { kind: "materialized"; value: unknown } | { kind: "collection"; read: () => unknown };
  slot: string; execution: string; run_id: string; ownership: ExecutionOwnership;
};
export type FetchedDocumentReference = DocumentOperationContext & { document: FetchedDocument };
type HeldDocument = DocumentOperationContext & { document?: FetchedDocument; claimant?: string };
function executionKey(context: PlannerStageContext) { return `${context.run_id}:${context.writer.attempt}`; }
function collectionSlot(context: PlannerStageContext) { return `collection:${executionKey(context)}`; }
export class StageStore {
  private readonly batches = new Map<string, HeldBatch>();
  private readonly documents = new Map<string, HeldDocument>();
  private readonly documentRequests = new Set<string>();
  private readonly documentRuns = new Map<string, { run_id: string; fetch_item_type: "feed" | "article" }>();
  private readonly retainedRuns = new Map<string, string>();
  constructor(private readonly capacity: number) { z.int().positive().parse(capacity); }
  retainRun(context: PlannerStageContext) {
    const slot = collectionSlot(context);
    this.reserveSlot(slot);
    this.retainedRuns.set(context.run_id, slot);
  }
  releaseRun(runId: string) {
    this.retainedRuns.delete(runId);
    for (const [id, document] of this.documents) {
      if (document.context.run_id === runId && document.claimant === undefined && !this.documentRequests.has(id)) {
        this.documents.delete(id);
      }
    }
    this.forgetDocumentWork(runId);
  }
  isRunActive(runId: string) {
    return this.retainedRuns.has(runId)
      || [...this.documents.values()].some(document => document.context.run_id === runId);
  }
  forgetRun(runId: string) {
    if (this.isRunActive(runId)) throw new PlanError("REQUEST_BUSY", "Cannot expire an execution with active work", "links");
    for (const [id, batch] of this.batches) if (batch.run_id === runId) this.batches.delete(id);
    this.forgetDocumentWork(runId);
  }
  beginFetch(context: DocumentOperationContext) {
    const id = operationKey(context.context);
    if (this.documents.has(id) || this.documentRequests.has(id) || this.batches.has(id)) {
      throw new PlanError("REQUEST_CONFLICT", "Document operation is already owned by live work", "spanId");
    }
    if (this.documents.size >= this.capacity) {
      throw new PlanError("REQUEST_BUSY", "Live document capacity is occupied; consume current fetch references first", "spanId");
    }
    this.documentRequests.add(id);
    this.documents.set(id, structuredClone(context));
  }
  rememberFetchedDocument(reference: OperationLink, document: FetchedDocument) {
    const id = operationKey(reference);
    const held = this.documents.get(id);
    if (held === undefined) throw new PlanError("ARTIFACT_NOT_FOUND", "Fetch reference is no longer live", "links");
    const value = FetchedDocumentSchema.parse(document);
    if (operationKey(value.observation) !== id || value.observation.run_id !== held.context.run_id) {
      throw new PlanError("ARTIFACT_INVALID", "Fetched result differs from its producing operation", "links");
    }
    this.documents.set(id, { ...held, document: value });
  }
  fetchedDocument(reference: OperationLink): FetchedDocumentReference | undefined {
    const held = this.documents.get(operationKey(reference));
    return held?.document === undefined ? undefined : {
      context: structuredClone(held.context), config_sha256: held.config_sha256, document: structuredClone(held.document),
    };
  }
  finishFetch(reference: OperationLink, retain: boolean) {
    const id = operationKey(reference);
    this.documentRequests.delete(id);
    const document = this.documents.get(id)?.document;
    if (!retain || document?.body == null || document.failure !== null) this.documents.delete(id);
  }
  claimDocument(fetch: OperationLink, parse: OperationLink, fingerprint: string): FetchedDocumentReference {
    const fetchId = operationKey(fetch);
    const id = operationKey(parse);
    const held = this.documents.get(fetchId);
    if (held?.document === undefined) {
      throw new PlanError("ARTIFACT_NOT_FOUND", "No current completed fetched document exists", "links");
    }
    if (held.config_sha256 !== fingerprint) {
      throw new PlanError("REQUEST_CONFLICT", "Fetched configuration differs", "links");
    }
    if (held.claimant !== undefined || this.documentRequests.has(fetchId) || this.documentRequests.has(id)
      || this.documents.has(id) || this.batches.has(id)) {
      throw new PlanError("REQUEST_CONFLICT", "Document operation is already owned by live work", "spanId");
    }
    held.claimant = id;
    this.documentRequests.add(id);
    return { context: structuredClone(held.context), config_sha256: held.config_sha256, document: structuredClone(held.document) };
  }
  consumeDocument(fetch: OperationLink, parse: OperationLink) {
    const fetchId = operationKey(fetch);
    const parseId = operationKey(parse);
    if (this.documents.get(fetchId)?.claimant !== parseId) {
      throw new PlanError("REQUEST_CONFLICT", "Parse does not own this document claim", "links");
    }
    this.documents.delete(fetchId);
    this.documentRequests.delete(parseId);
  }
  rememberDocumentWork(reference: OperationLink, runId: string, fetchItemType: "feed" | "article") {
    this.documentRuns.set(operationKey(reference), { run_id: runId, fetch_item_type: fetchItemType });
  }
  documentRun(reference: OperationLink) { return this.documentRuns.get(operationKey(reference))?.run_id; }
  documentKind(reference: OperationLink) { return this.documentRuns.get(operationKey(reference))?.fetch_item_type; }
  forgetDocumentWork(runId: string) {
    for (const [id, run] of this.documentRuns) {
      if (run.run_id === runId) this.documentRuns.delete(id);
    }
  }
  releaseDocuments() {
    for (const [id, document] of this.documents) {
      if (this.retainedRuns.has(document.context.run_id)) continue;
      this.documents.delete(id);
      this.documentRequests.delete(id);
      if (document.claimant !== undefined) this.documentRequests.delete(document.claimant);
    }
    for (const [id, work] of this.documentRuns) {
      if (this.retainedRuns.has(work.run_id)) continue;
      this.documentRuns.delete(id);
      this.documentRequests.delete(id);
    }
  }
  write<T extends BatchIdentity>(stage: BatchStage, schema: z.ZodType<T>, raw: unknown): T {
    const value = schema.parse(raw);
    return this.retain(stage, value, { kind: "materialized", value: structuredClone(value) }, operationKey(value));
  }
  writeCollectionResult<T extends BatchIdentity>(schema: z.ZodType<T>, read: () => unknown): T {
    const value = schema.parse(read());
    const slot = this.retainedRuns.get(value.context.run_id);
    if (slot !== collectionSlot(value.context)) {
      throw new PlanError("REQUEST_CONFLICT", "Parsed result requires its active collection reservation", "links");
    }
    return this.retain("parsed", value, { kind: "collection", read: () => schema.parse(read()) }, slot);
  }
  private reserveSlot(slot: string) {
    if ([...this.retainedRuns.values()].includes(slot)) return;
    const slots = new Set([...this.retainedRuns.values(), ...[...this.batches.values()].map(batch => batch.slot)]);
    while (!slots.has(slot) && slots.size >= this.capacity) {
      const expired = [...this.batches.values()].find(batch => !this.isRunActive(batch.run_id));
      if (expired === undefined) throw new PlanError("REQUEST_BUSY", "Stage capacity is occupied by active work", "spanId");
      for (const [id, batch] of this.batches) if (batch.slot === expired.slot) this.batches.delete(id);
      slots.delete(expired.slot);
    }
  }
  private retain<T extends BatchIdentity>(stage: BatchStage, value: T, contents: HeldBatch["contents"], slot: string): T {
    const id = operationKey(value);
    if (this.batches.has(id)) throw new PlanError("REQUEST_CONFLICT", "Stage operation already exists", "spanId");
    const execution = executionKey(value.context);
    const ownership: ExecutionOwnership = [...this.batches.values()].find(batch => batch.execution === execution)?.ownership ?? {
      selection_claimed: false, partition_claimed: false, scope: "standalone", health_fingerprint: null,
    };
    this.reserveSlot(slot);
    if (stage !== "parsed") ownership.selection_claimed = true;
    if (stage === "partitioned") ownership.partition_claimed = true;
    this.batches.set(id, { stage, contents, slot, execution, run_id: value.context.run_id, ownership });
    return value;
  }
  private value(batch: HeldBatch) {
    return batch.contents.kind === "collection" ? batch.contents.read() : structuredClone(batch.contents.value);
  }
  read<T extends OperationLink>(stage: BatchStage, reference: OperationLink, schema: z.ZodType<T>): T {
    const batch = this.batches.get(operationKey(reference));
    if (batch === undefined || batch.stage !== stage) {
      throw new PlanError("ARTIFACT_NOT_FOUND", "No current server-owned result exists for this stage", "links");
    }
    return schema.parse(this.value(batch));
  }
  inspect(reference: OperationLink) {
    const batch = this.batches.get(operationKey(reference));
    if (batch === undefined) throw new PlanError("ARTIFACT_NOT_FOUND", "No current server-owned result exists", "links");
    return { stage: batch.stage, value: this.value(batch) };
  }
  has(reference: OperationLink) { return this.batches.has(operationKey(reference)); }
  isCollectionResult(reference: OperationLink) { return this.batches.get(operationKey(reference))?.contents.kind === "collection"; }
  ownership(reference: OperationLink): ExecutionOwnership {
    const held = this.batches.get(operationKey(reference));
    if (held === undefined) throw new PlanError("ARTIFACT_NOT_FOUND", "Current result has expired", "links");
    return held.ownership;
  }
  claimSelection(reference: OperationLink) {
    const claim = this.ownership(reference);
    if (claim.selection_claimed) return false;
    claim.selection_claimed = true;
    return true;
  }
  claimPartition(reference: OperationLink) {
    const claim = this.ownership(reference);
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
    const id = operationKey(value);
    const held = this.batches.get(id);
    if (held === undefined || held.stage !== stage) throw new PlanError("ARTIFACT_NOT_FOUND", "Current result has expired", "links");
    const original = schema.parse(this.value(held));
    if (held.execution !== executionKey(value.context) || original.config_sha256 !== value.config_sha256
      || JSON.stringify(operationMetadata(original)) !== JSON.stringify(operationMetadata(value))) {
      throw new PlanError("ARTIFACT_INVALID", "Stage update changed its operation or execution ownership", "links");
    }
    if (held.contents.kind === "collection") {
      throw new PlanError("REQUEST_CONFLICT", "Captured collection results cannot be replaced", "links");
    }
    this.batches.set(id, { ...held, contents: { kind: "materialized", value: structuredClone(value) } });
    return value;
  }
  update<T extends BatchIdentity>(stage: BatchStage, reference: OperationLink, schema: z.ZodType<T>, update: (current: T) => T) {
    const value = schema.parse(update(this.read(stage, reference, schema)));
    if (operationKey(value) !== operationKey(reference)) {
      throw new PlanError("ARTIFACT_INVALID", "Stage update changed its server-owned operation identity", "links");
    }
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
