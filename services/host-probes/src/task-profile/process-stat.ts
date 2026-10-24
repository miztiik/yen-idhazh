/** Which identity and counters belong to one named Linux process? */
import { readProcFile } from "../probe/proc-reader";
import type { Observation, ProbeContext } from "../probe/proc-reader";
import type { OwnedProcess, TaskUnavailableReason } from "./profile-schema";

// Positions after comm in Linux proc_pid_stat(5); child and guest counters are excluded.
const STAT_FIELDS = { major_faults: 9, user: 11, system: 12, start_ticks: 19 } as const;
export type ProcessCpuCounters = { user: bigint; system: bigint };
export type ProcessStat = OwnedProcess & {
  cpu: Observation<ProcessCpuCounters, TaskUnavailableReason>;
  major_faults: Observation<number, TaskUnavailableReason>;
};

export class ProcessPinError extends Error {
  constructor(readonly reason: TaskUnavailableReason) {
    super(`Task process pin cannot be verified: ${reason}`);
    this.name = "ProcessPinError";
  }
}

export function parseProcessStat(pid: number, text: string): Observation<ProcessStat, TaskUnavailableReason> {
  const end = text.lastIndexOf(")");
  const fields = text.slice(end + 1).trim().split(/\s+/);
  const start_ticks = fields[STAT_FIELDS.start_ticks];
  if (end < 0 || !text.startsWith(`${pid} (`) || !start_ticks || !/^\d+$/.test(start_ticks)
    || !fields[0] || !/^[A-Za-z]$/.test(fields[0])) return { value: null, reason: "invalid_data" };
  if (["Z", "X", "x"].includes(fields[0])) return { value: null, reason: "process_exited" };
  const user = fields[STAT_FIELDS.user];
  const system = fields[STAT_FIELDS.system];
  const faults = fields[STAT_FIELDS.major_faults];
  return {
    value: {
      pid, start_ticks,
      cpu: user !== undefined && system !== undefined && /^\d+$/.test(user) && /^\d+$/.test(system)
        ? { value: { user: BigInt(user), system: BigInt(system) }, reason: null }
        : { value: null, reason: "invalid_data" },
      major_faults: faults !== undefined && /^\d+$/.test(faults) && Number.isSafeInteger(Number(faults))
        ? { value: Number(faults), reason: null } : { value: null, reason: "invalid_data" },
    },
    reason: null,
  };
}

export function readProcessIdentity(
  pid: number, maxBytes: number, context: ProbeContext, scratch?: Buffer,
): Observation<ProcessStat, TaskUnavailableReason> {
  const text = readProcFile(`${pid}/stat`, maxBytes, context, scratch);
  return text.reason === null ? parseProcessStat(pid, text.value)
    : { value: null, reason: text.reason === "missing_file" ? "process_exited" : text.reason };
}

export function readPinnedProcess(
  target: OwnedProcess, maxBytes: number, context: ProbeContext, scratch?: Buffer,
): Observation<ProcessStat, TaskUnavailableReason> {
  const stat = readProcessIdentity(target.pid, maxBytes, context, scratch);
  return stat.reason === null && stat.value.start_ticks !== target.start_ticks
    ? { value: null, reason: "pid_reused" } : stat;
}

export function verifyProcessPin(target: OwnedProcess, maxBytes: number, context: ProbeContext): void {
  const stat = readPinnedProcess(target, maxBytes, context);
  if (stat.reason !== null) throw new ProcessPinError(stat.reason);
}
