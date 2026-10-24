/** Which machine memory and virtual-memory counters did Linux report? */
import type { Observation, UnavailableReason } from "./proc-reader";

// These are Linux field names and units, not application tuning controls.
const MEMORY_FIELDS = { total: "MemTotal", free: "MemFree", available: "MemAvailable" } as const;
const VMSTAT_FIELDS = ["pgfault", "pgmajfault", "pswpin", "pswpout"] as const;
type MemoryName = keyof typeof MEMORY_FIELDS;
export type MemoryKb = Record<MemoryName, number | null>;
export type Vmstat = Record<typeof VMSTAT_FIELDS[number], number>;

export function parseMemoryInfo(text: string): {
  value: MemoryKb;
  unavailable: Partial<Record<MemoryName, UnavailableReason>>;
} {
  return parseMemoryFields(text, MEMORY_FIELDS);
}

export function parseMemoryFields<Name extends string>(text: string, fields: Record<Name, string>) {
  const value = {} as Record<Name, number | null>;
  const unavailable: Partial<Record<Name, UnavailableReason>> = {};
  const lines = text.split(/\r?\n/);
  for (const name of Object.keys(fields) as Name[]) {
    value[name] = null;
    const matches = lines.filter((line) => line.startsWith(`${fields[name]}:`));
    const match = matches.length === 1 ? matches[0]?.match(/^\w+:\s+(\d+)\s+kB\s*$/) : null;
    const number = match?.[1] === undefined ? NaN : Number(match[1]);
    if (!Number.isSafeInteger(number) || number < 0) {
      unavailable[name] = matches.length === 0 ? "missing_field" : "invalid_data";
    } else {
      value[name] = number;
    }
  }
  return { value, unavailable };
}

export function parseVmstat(text: string): Observation<Vmstat> {
  const value: Vmstat = { pgfault: 0, pgmajfault: 0, pswpin: 0, pswpout: 0 };
  const lines = text.split(/\r?\n/);
  for (const name of VMSTAT_FIELDS) {
    const matches = lines.filter((line) => line.split(/\s+/, 1)[0] === name);
    if (matches.length === 0) return { value: null, reason: "missing_field" };
    const match = matches.length === 1 ? matches[0]?.match(/^\w+\s+(\d+)\s*$/) : null;
    const number = match?.[1] === undefined ? NaN : Number(match[1]);
    if (!Number.isSafeInteger(number) || number < 0) return { value: null, reason: "invalid_data" };
    value[name] = number;
  }
  return { value, reason: null };
}
