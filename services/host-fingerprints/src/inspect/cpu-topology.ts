/** Which online processors have complete topology and reported frequency? */
import type { ServiceConfig } from "../config";
import { parseInteger, parsePositive, readInput, unavailable } from "./bounded-input";
import type { Inspection } from "./bounded-input";

export function parseCpuIds(text: string | null, maximum: number): number[] | null {
  if (!text?.trim()) return null;
  const ids = new Set<number>();
  for (const part of text.trim().split(",")) {
    if (!/^\d+(?:-\d+)?$/.test(part)) return null;
    const [lowText, highText] = part.split("-");
    const low = Number(lowText), high = Number(highText ?? lowText);
    if (!Number.isSafeInteger(low) || !Number.isSafeInteger(high) || high < low || high - low + 1 > maximum) return null;
    for (let id = low; id <= high; id++) {
      if (ids.has(id) || ids.size >= maximum) return null;
      ids.add(id);
    }
  }
  return [...ids].sort((a, b) => a - b);
}
export async function collectTopology(config: ServiceConfig, context: Inspection, frequency: boolean) {
  const ids = parseCpuIds(await readInput("/sys/devices/system/cpu/online", config, context), config.max_online_processors);
  const pairs = new Set<string>(), maxima: number[] = [];
  let complete = ids !== null, frequencyComplete = ids !== null;
  for (const id of ids ?? []) {
    const root = `/sys/devices/system/cpu/cpu${id}`;
    const packageId = parseInteger(await readInput(`${root}/topology/physical_package_id`, config, context));
    const core = parseInteger(await readInput(`${root}/topology/core_id`, config, context));
    if (packageId === null || core === null || packageId < 0 || core < 0) complete = false;
    else pairs.add(`${packageId}:${core}`);
    if (frequency) {
      const khz = parsePositive(await readInput(`${root}/cpufreq/cpuinfo_max_freq`, config, context));
      if (khz === null) frequencyComplete = false;
      else maxima.push(khz / 1000);
    }
  }
  return {
    ids,
    cpu_logical_processors: ids?.length ?? unavailable(context, "cpu_logical_processors", "online_list_unavailable"),
    cpu_physical_cores: complete && pairs.size ? pairs.size : unavailable(context, "cpu_physical_cores", "incomplete_topology"),
    cpu_reported_max_mhz: frequency && frequencyComplete && maxima.length ? Math.max(...maxima) :
      unavailable(context, "cpu_reported_max_mhz", frequency ? "incomplete_frequency" : "configured_off"),
  };
}
