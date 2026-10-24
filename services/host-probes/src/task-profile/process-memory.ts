/** What RAM belongs to one pinned Linux process, without finding other processes? */
import { parseMemoryFields } from "../probe/memory-probe";
import { readProcFile } from "../probe/proc-reader";
import type { Observation, ProbeContext } from "../probe/proc-reader";
import type { OwnedProcess, ProcessSample, TaskUnavailableReason } from "./profile-schema";

// Linux process field names and stat positions are operating-system protocol constants.
const MEMORY_FIELDS = { rss: "VmRSS", hwm_lifetime: "VmHWM", anon: "RssAnon" } as const;

export function readProcessIdentity(pid: number, maxBytes: number, context: ProbeContext, scratch?: Buffer): Observation<OwnedProcess & { major_faults: number }, TaskUnavailableReason> {
  const text = readProcFile(`${pid}/stat`, maxBytes, context, scratch);
  if (text.reason !== null) return { value: null, reason: text.reason === "missing_file" ? "process_exited" : text.reason };
  const end = text.value.lastIndexOf(")");
  const fields = text.value.slice(end + 1).trim().split(/\s+/);
  const start_ticks = fields[19];
  const faults = fields[9];
  if (end < 0 || !text.value.startsWith(`${pid} (`) || !start_ticks || !/^\d+$/.test(start_ticks)
    || !faults || !/^\d+$/.test(faults) || !Number.isSafeInteger(Number(faults))) {
    return { value: null, reason: "invalid_data" };
  }
  if (fields[0] === "Z" || fields[0] === "X") return { value: null, reason: "process_exited" };
  return { value: { pid, start_ticks, major_faults: Number(faults) }, reason: null };
}

export function unavailableProcess(pid: number | null, start_ticks: string | null, reason: TaskUnavailableReason): ProcessSample {
  return {
    pid, start_ticks, memory_kb: { rss: null, hwm_lifetime: null, anon: null }, major_faults: null,
    unavailable: { "memory_kb.rss": reason, "memory_kb.hwm_lifetime": reason, "memory_kb.anon": reason, major_faults: reason },
  };
}

export function readProcessMemory(target: OwnedProcess, maxBytes: number, context: ProbeContext, scratch?: Buffer): ProcessSample {
  const before = readProcessIdentity(target.pid, maxBytes, context, scratch);
  if (before.reason !== null) return unavailableProcess(target.pid, target.start_ticks, before.reason);
  if (before.value.start_ticks !== target.start_ticks) return unavailableProcess(target.pid, target.start_ticks, "pid_reused");
  const status = readProcFile(`${target.pid}/status`, maxBytes, context, scratch);
  const after = readProcessIdentity(target.pid, maxBytes, context, scratch);
  if (after.reason !== null) return unavailableProcess(target.pid, target.start_ticks, after.reason);
  if (after.value.start_ticks !== target.start_ticks) return unavailableProcess(target.pid, target.start_ticks, "pid_reused");
  if (status.reason !== null) return unavailableProcess(target.pid, target.start_ticks,
    status.reason === "missing_file" ? "process_exited" : status.reason);
  const memory = parseMemoryFields(status.value, MEMORY_FIELDS);
  return {
    ...target, memory_kb: memory.value, major_faults: after.value.major_faults,
    unavailable: Object.fromEntries(Object.entries(memory.unavailable).map(([key, value]) => [`memory_kb.${key}`, value])),
  };
}
