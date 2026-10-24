/** Does one explicit PID still identify a process owned by this operator? */
import { readProcessIdentity } from "../task-profile/process-stat";
import { readProcFile } from "../probe/proc-reader";
import type { ProbeContext } from "../probe/proc-reader";
import type { OwnedProcess } from "../task-profile/profile-schema";
import type { CacheReason } from "./cache-schema";

export function validateCounterTarget(target: OwnedProcess, maxBytes: number, context: ProbeContext): CacheReason | null {
  const before = readProcessIdentity(target.pid, maxBytes, context);
  if (before.reason !== null) return before.reason === "permission_denied" ? "permission_denied"
    : before.reason === "process_exited" ? "process_exited" : "invalid_target";
  if (before.value.start_ticks !== target.start_ticks) return "pid_reused";
  const status = readProcFile(`${target.pid}/status`, maxBytes, context);
  if (status.reason !== null) return status.reason === "permission_denied" ? "permission_denied" : "invalid_target";
  const uid = /^Uid:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$/m.exec(status.value);
  const operator = process.geteuid?.();
  if (!uid || operator === undefined || uid.slice(1).some(value => Number(value) !== operator)) return "target_not_owned";
  const after = readProcessIdentity(target.pid, maxBytes, context);
  if (after.reason !== null) return after.reason === "process_exited" ? "process_exited" : "invalid_target";
  return after.value.start_ticks === target.start_ticks ? null : "pid_reused";
}
