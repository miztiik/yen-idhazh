/** What copy buffer and measured bandwidth did the selected task request? */
import type { SelectedSettings, ServiceConfig } from "../config";
import type { Inspection } from "./bounded-input";
import { unavailable } from "./bounded-input";

export function probeBufferMib(floor: number, cache: number | null, multiple: number): number {
  return floor <= 0 || cache === null || cache <= 0 ? floor : Math.max(floor, multiple * Math.ceil(cache / 1024 ** 2));
}
export function measureCopy(task: string, cache: number | null, settings: SelectedSettings, config: ServiceConfig, context: Inspection) {
  const knobs = settings.observability;
  const floor = knobs.host_fingerprint_bandwidth_jobs.includes(task) ? knobs.host_fingerprint_bandwidth_floor_mib : 0;
  const mib = probeBufferMib(floor, cache, knobs.host_fingerprint_bandwidth_cache_multiple);
  if (!mib) return { memcpy_probe_mib: 0, memcpy_gib_s: unavailable(context, "memcpy_gib_s", "configured_off") };
  let source: Uint8Array, target: Uint8Array;
  try {
    source = new Uint8Array(mib * 1024 ** 2);
    target = new Uint8Array(source.length);
    source.fill(1);
    target.fill(0);
  } catch (error) {
    if (!(error instanceof RangeError)) throw error;
    return { memcpy_probe_mib: mib, memcpy_gib_s: unavailable(context, "memcpy_gib_s", "allocation_unavailable") };
  }
  const rates: number[] = [];
  for (let repeat = 0; repeat < config.copy_repeats; repeat++) {
    const start = performance.now();
    target.set(source);
    const elapsed = (performance.now() - start) / 1000;
    if (elapsed > 0) rates.push((2 * source.length / 1024 ** 3) / elapsed);
  }
  rates.sort((a, b) => a - b);
  const middle = Math.floor(rates.length / 2);
  const rate = rates.length % 2 ? rates[middle] : ((rates[middle - 1] ?? 0) + (rates[middle] ?? 0)) / 2;
  return { memcpy_probe_mib: mib, memcpy_gib_s: rate && Number.isFinite(rate) ? rate : unavailable(context, "memcpy_gib_s", "clock_unavailable") };
}
