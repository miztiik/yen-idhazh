/** What share of a Linux CPU interval belongs to each accounting bucket? */
import type { Observation } from "./proc-reader";

// Linux /proc/stat positions; guest and guest_nice are already in user and nice.
const COUNTERS = ["user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal"] as const;
type CounterName = typeof COUNTERS[number];
export type CpuCounters = Record<CounterName, bigint>;
export interface CpuPercentages {
  user: number;
  system: number;
  idle: number;
  iowait: number;
  steal: number;
}

export function parseCpuCounters(text: string): Observation<CpuCounters> {
  const fields = text.split(/\r?\n/, 1)[0]?.trim().split(/\s+/) ?? [];
  if (fields[0] !== "cpu" || fields.length < COUNTERS.length + 1) {
    return { value: null, reason: "invalid_data" };
  }
  const counters: CpuCounters = { user: 0n, nice: 0n, system: 0n, idle: 0n, iowait: 0n, irq: 0n, softirq: 0n, steal: 0n };
  for (const [index, name] of COUNTERS.entries()) {
    const field = fields[index + 1];
    if (field === undefined || !/^\d+$/.test(field)) return { value: null, reason: "invalid_data" };
    counters[name] = BigInt(field);
  }
  return { value: counters, reason: null };
}

export function calculateCpuPercentages(
  start: Observation<CpuCounters>,
  end: Observation<CpuCounters>,
): Observation<CpuPercentages> {
  if (start.reason !== null) return start;
  if (end.reason !== null) return end;
  const delta = { ...end.value };
  for (const name of COUNTERS) {
    delta[name] -= start.value[name];
    if (delta[name] < 0n) return { value: null, reason: "counter_reset" };
  }
  const buckets = {
    user: delta.user + delta.nice,
    system: delta.system + delta.irq + delta.softirq,
    idle: delta.idle,
    iowait: delta.iowait,
    steal: delta.steal,
  };
  const total = Object.values(buckets).reduce((sum, value) => sum + value, 0n);
  if (total === 0n) return { value: null, reason: "no_ticks" };
  const denominator = Number(total);
  if (!Number.isFinite(denominator)) return { value: null, reason: "invalid_data" };
  return {
    value: {
      user: Number(buckets.user) / denominator * 100,
      system: Number(buckets.system) / denominator * 100,
      idle: Number(buckets.idle) / denominator * 100,
      iowait: Number(buckets.iowait) / denominator * 100,
      steal: Number(buckets.steal) / denominator * 100,
    },
    reason: null,
  };
}
