/** Which trusted launcher inputs own the private shard memory command? */
import { join } from "node:path";
import { z } from "zod";
import type { ProbeConfig } from "../config";
import { loadTaskPerformanceSettings } from "../config";
import { readLinuxFile } from "../probe/proc-reader";
import { finishShardMemory, recordShardMemory } from "./shard-memory";

// Private counterpart of ModelServerPin, not an operator-supplied PID or path.
const ModelServerPinSchema = z.strictObject({
  version: z.literal("2026-11-26"), pid: z.int().positive(), start_ticks: z.int().nonnegative(), started_at: z.iso.datetime(),
});
const MemoryChoice = z.enum(["inherit", "on", "off"]);

export async function runShardMemory(
  command: "sample" | "finish", config: ProbeConfig, root = process.cwd(), environment = process.env,
): Promise<void> {
  const { observability } = await loadTaskPerformanceSettings();
  const memory = MemoryChoice.parse(environment.MEMORY_PROFILING ?? "inherit");
  if (environment.IDHAZH_HOST_TELEMETRY_MODE !== "typescript" || !observability.host_telemetry_enabled
    || !(memory === "inherit" ? observability.memory_profiling_enabled : memory === "on")) {
    console.error("Shard memory diagnostics configured off");
    return;
  }
  if (command === "sample") {
    const pin = readLinuxFile(join(root, "llama-server.pin.json"), config.max_proc_bytes);
    if (pin.value === null) throw new Error("Shard memory model-server launch pin unavailable");
    const { pid, start_ticks } = ModelServerPinSchema.parse(JSON.parse(pin.value));
    await recordShardMemory(config, { root }, { pid, start_ticks: String(start_ticks) });
  } else {
    const receipt = await finishShardMemory(config, { root });
    // Keep individual process readings in the named private artifact, not the job log.
    if (receipt === null) console.error("Shard memory sampler unavailable");
    else console.error(JSON.stringify({ event: "shard_memory_completed", ...receipt }));
  }
}
