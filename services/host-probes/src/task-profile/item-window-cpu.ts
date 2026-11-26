/** What do opening, periodic and closing Linux CPU counters say about an item? */
import { CPU_COUNTERS } from "../probe/cpu-sampler";

const ITEM_COUNTERS = [...CPU_COUNTERS, "guest", "guest_nice"] as const;
// Linux counts guest time inside user/nice and also reports it separately.
const GUEST = new Set<string>(["guest", "guest_nice"]);
const IDLE = new Set<string>(["idle", "iowait"]);
type ItemTicks = Partial<Record<typeof ITEM_COUNTERS[number], bigint>>;

export function parseItemTicks(text: string | null): ItemTicks | null {
  const line = text?.split(/\r?\n/).find(candidate => /^\s*cpu\s/.test(candidate));
  const fields = line?.trim().split(/\s+/).slice(1);
  if (fields === undefined || fields.length < 4) return null;
  const result: ItemTicks = {};
  for (const [index, name] of ITEM_COUNTERS.entries()) {
    const value = fields[index];
    if (value === undefined) break;
    if (!/^\d+$/.test(value)) return null;
    result[name] = BigInt(value);
  }
  return result;
}

function roundedShare(ticks: bigint, total: bigint): number {
  const numerator = 100n * ticks;
  if (1000n * numerator < total) return 0;
  // Match Python's integer division to a binary64 before rounding decimal places.
  let exponent = numerator.toString(2).length - total.toString(2).length;
  if (exponent < 0 ? (numerator << BigInt(-exponent)) < total : numerator < (total << BigInt(exponent))) exponent--;
  const shift = 52 - exponent;
  const scaled = numerator << BigInt(shift);
  const quotient = scaled / total;
  const remainder = 2n * (scaled % total);
  const nearest = remainder > total || (remainder === total && quotient % 2n === 1n) ? quotient + 1n : quotient;
  const percent = Number(nearest) / 2 ** shift;
  // At exact binary half-cent ties Python rounds to even, unlike toFixed.
  const eighths = percent * 8;
  if (Number.isInteger(eighths) && eighths % 2 === 1) {
    const cents = Math.floor(percent * 100);
    return (cents + cents % 2) / 100;
  }
  return Number(percent.toFixed(2));
}

export function itemCpuShares(start: ItemTicks | null, end: ItemTicks | null) {
  if (start === null || end === null) return null;
  let total = 0n;
  let idle = 0n;
  let steal: bigint | null = null;
  for (const key of ITEM_COUNTERS) {
    const first = start[key], last = end[key];
    if (first === undefined || last === undefined) continue;
    const delta = last - first;
    if (delta < 0n) return null;
    total += GUEST.has(key) ? 0n : delta;
    if (IDLE.has(key)) idle += delta;
    if (key === "steal") steal = delta;
  }
  const busy = total - idle - (steal ?? 0n);
  if (total <= 0n || busy < 0n) return null;
  return { busy: roundedShare(busy, total), steal: steal === null ? null : roundedShare(steal, total) };
}
