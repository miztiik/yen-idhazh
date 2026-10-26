/** Hold a bounded set of current server-owned batches without archiving article populations. */
import { z } from "zod";
import { RequestIdSchema } from "@idhazh/common-contracts";
import type { PlannerStageContext } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import { PlanError } from "./plan-request";

export type BatchStage = "parsed" | "selected" | "partitioned";
type BatchIdentity = { batch_id: string; context: PlannerStageContext };
export type ExecutionOwnership = {
  selection_claimed: boolean; partition_claimed: boolean;
  scope: "plan" | "standalone"; health_fingerprint: string | null;
};
type HeldBatch = {
  stage: BatchStage; value: unknown; execution: string; run_id: string; ownership: ExecutionOwnership;
};
function executionKey(context: PlannerStageContext) { return `${context.run_id}:${context.writer.attempt}`; }
export class StageStore {
  private readonly batches = new Map<string, HeldBatch>();
  constructor(private readonly capacity: number) { z.int().positive().parse(capacity); }
  write<T extends BatchIdentity>(stage: BatchStage, schema: z.ZodType<T>, raw: unknown): T {
    const value = schema.parse(raw);
    if (this.batches.has(value.batch_id)) throw new PlanError("REQUEST_CONFLICT", "Batch identity already exists", "batch_id");
    const execution = executionKey(value.context);
    const ownership: ExecutionOwnership = [...this.batches.values()].find(batch => batch.execution === execution)?.ownership ?? {
      selection_claimed: false, partition_claimed: false, scope: "standalone", health_fingerprint: null,
    };
    if (stage !== "parsed") ownership.selection_claimed = true;
    if (stage === "partitioned") ownership.partition_claimed = true;
    while (this.batches.size >= this.capacity) this.batches.delete(this.batches.keys().next().value!);
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
