/** Hold a bounded set of current server-owned batches without archiving article populations. */
import { z } from "zod";
import { RequestIdSchema } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import { PlanError } from "./plan-request";

export type BatchStage = "parsed" | "selected" | "partitioned";
export class StageStore {
  private readonly batches = new Map<string, { stage: BatchStage; value: unknown }>();
  constructor(private readonly capacity: number) { z.int().positive().parse(capacity); }
  write<T extends { batch_id: string }>(stage: BatchStage, schema: z.ZodType<T>, raw: unknown): T {
    const value = schema.parse(raw);
    if (this.batches.has(value.batch_id)) throw new PlanError("REQUEST_CONFLICT", "Batch identity already exists", "batch_id");
    while (this.batches.size >= this.capacity) this.batches.delete(this.batches.keys().next().value!);
    this.batches.set(value.batch_id, { stage, value: structuredClone(value) });
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
    return structuredClone(batch);
  }
  has(id: string) { return this.batches.has(RequestIdSchema.parse(id)); }
  replace<T extends { batch_id: string }>(stage: BatchStage, schema: z.ZodType<T>, raw: unknown): T {
    const value = schema.parse(raw);
    const held = this.batches.get(value.batch_id);
    if (held === undefined || held.stage !== stage) throw new PlanError("ARTIFACT_NOT_FOUND", "Current batch has expired", "batch_id");
    this.batches.set(value.batch_id, { stage, value: structuredClone(value) });
    return value;
  }
  update<T extends { batch_id: string }>(stage: BatchStage, id: string, schema: z.ZodType<T>, update: (current: T) => T) {
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
