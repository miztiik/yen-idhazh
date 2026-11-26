/** Which transient cells can the digest file on an existing item-health row? */
import { z } from "zod";
import { OperationMetadataSchema } from "@idhazh/common-contracts/schemas/operation-metadata";
import { MAX_TIMER_DELAY_MS } from "../config";

export const ITEM_WINDOW_VERSION = "2026-11-26";
export const ItemPollMsSchema = z.int().nonnegative().max(MAX_TIMER_DELAY_MS);
export const ItemHeartbeatSecondsSchema = z.int().nonnegative().max(Math.floor(MAX_TIMER_DELAY_MS / 1000));

const share = z.number().min(0).max(100).nullable();
const count = z.int().nonnegative().nullable();
const memory = (field: string) => count.describe(`${field}, in bytes.`);

export const ItemHostCellsSchema = z.strictObject({
  cpu_busy_pct: share, cpu_busy_max: share, cpu_busy_min: share, cpu_steal_pct: share,
  load_1m: z.number().nonnegative().nullable(),
  llama_rss_bytes: memory("Closing server resident memory"),
  llama_rss_anon_bytes: memory("Closing server anonymous resident memory"),
  llama_rss_peak_bytes: memory("Largest server lifetime high-water mark at either endpoint"),
  llama_major_faults: count,
  python_rss_bytes: memory("Closing worker resident memory"),
  python_rss_anon_bytes: memory("Closing worker anonymous resident memory"),
  os_mem_available_bytes: memory("Closing available machine memory"),
  os_mem_total_bytes: memory("Closing total machine memory"),
  os_mem_cached_bytes: memory("Closing cached machine memory"),
  os_swap_free_bytes: memory("Closing free swap"),
  os_swap_total_bytes: memory("Closing total swap"),
  os_mem_available_min_bytes: memory("Minimum available machine memory across observations"),
}).meta({
  version: ITEM_WINDOW_VERSION,
  readCompatibility: "current_only; file these cells on the unchanged ItemHealthRow, not as a separate ledger row",
  changelog: [{ version: ITEM_WINDOW_VERSION, change: "Project the item window without raw samples or process identity." }],
});

export const ItemWindowMetadataSchema = OperationMetadataSchema.safeExtend({
  version: z.literal(ITEM_WINDOW_VERSION),
  cells: ItemHostCellsSchema,
});
