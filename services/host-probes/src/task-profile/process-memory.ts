/** What RAM belongs to one pinned Linux process, without finding other processes? */
import { parseMemoryFields } from "../probe/memory-probe";
import { readProcFile } from "../probe/proc-reader";
import type { ProbeContext } from "../probe/proc-reader";
import type { OwnedProcess, ProcessSample, TaskUnavailableReason } from "./profile-schema";
import { readPinnedProcess } from "./process-stat";

// Linux process field names and stat positions are operating-system protocol constants.
const MEMORY_FIELDS = { rss: "VmRSS", hwm_lifetime: "VmHWM", anon: "RssAnon" } as const;
type ProcessMemory = Pick<ProcessSample, "pid" | "start_ticks" | "memory_kb" | "major_faults" | "unavailable">;

export function unavailableProcess(pid: number | null, start_ticks: string | null, reason: TaskUnavailableReason): ProcessMemory {
  return {
    pid, start_ticks, memory_kb: { rss: null, hwm_lifetime: null, anon: null }, major_faults: null,
    unavailable: { "memory_kb.rss": reason, "memory_kb.hwm_lifetime": reason, "memory_kb.anon": reason, major_faults: reason },
  };
}

export function readProcessMemory(target: OwnedProcess, maxBytes: number, context: ProbeContext, scratch?: Buffer): ProcessMemory {
  const before = readPinnedProcess(target, maxBytes, context, scratch);
  if (before.reason !== null) return unavailableProcess(target.pid, target.start_ticks, before.reason);
  const status = readProcFile(`${target.pid}/status`, maxBytes, context, scratch);
  const after = readPinnedProcess(target, maxBytes, context, scratch);
  if (after.reason !== null) return unavailableProcess(target.pid, target.start_ticks, after.reason);
  const memory = parseMemoryFields(status.value ?? "", MEMORY_FIELDS);
  const unavailable: ProcessMemory["unavailable"] = {};
  for (const key of Object.keys(MEMORY_FIELDS) as (keyof typeof MEMORY_FIELDS)[]) {
    const reason = status.reason ?? memory.unavailable[key];
    if (reason) unavailable[`memory_kb.${key}`] = reason;
  }
  if (after.value.major_faults.reason !== null) unavailable.major_faults = after.value.major_faults.reason;
  return {
    ...target, memory_kb: memory.value, major_faults: after.value.major_faults.value, unavailable,
  };
}
