/** How much total RAM did the Linux kernel expose at capture, in MiB? */
import type { ServiceConfig } from "../config";
import { parseInteger, readInput, unavailable } from "./bounded-input";
import type { Inspection } from "./bounded-input";

export function parseMemoryTotalMib(input: string): number | null {
  const lines = input.split(/\r?\n/).filter((line) => line.startsWith("MemTotal:"));
  const match = lines.length === 1 ? lines[0]?.match(/^MemTotal:\s+(\d+)\s+kB\s*$/) : null;
  const total = parseInteger(match?.[1]);
  // Linux meminfo kB are 1024-byte units; one MiB is 1024 of those units.
  return total !== null && total > 0 ? total / 1024 : null;
}

export async function collectMemoryCapacity(config: ServiceConfig, context: Inspection) {
  const input = await readInput("/proc/meminfo", config, context);
  const total = input === null ? null : parseMemoryTotalMib(input);
  return {
    machine_memory_total_mib: total ?? unavailable(
      context, "machine_memory_total_mib", input === null ? "meminfo_unavailable" : "meminfo_invalid",
    ),
  };
}
