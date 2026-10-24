/** Does one explicit PID still identify a process owned by this operator? */
import { readPinnedProcess } from "../task-profile/process-stat";
import { readProcFile } from "../probe/proc-reader";
import type { ProbeContext } from "../probe/proc-reader";
import type { OwnedProcess } from "../task-profile/profile-schema";
import type { CacheReason } from "./cache-schema";

export function validateCounterTarget(target: OwnedProcess, maxBytes: number, context: ProbeContext): CacheReason | null {
  const before = readPinnedProcess(target, maxBytes, context);
  if (before.reason !== null) return before.reason === "permission_denied" ? "permission_denied"
    : before.reason === "process_exited" || before.reason === "pid_reused" ? before.reason : "invalid_target";
  const status = readProcFile(`${target.pid}/status`, maxBytes, context);
  if (status.reason !== null) return status.reason === "permission_denied" ? "permission_denied" : "invalid_target";
  const uid = /^Uid:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$/m.exec(status.value);
  const operator = process.geteuid?.();
  if (!uid || operator === undefined || uid.slice(1).some(value => Number(value) !== operator)) return "target_not_owned";
  const after = readPinnedProcess(target, maxBytes, context);
  if (after.reason !== null) return after.reason === "process_exited" || after.reason === "pid_reused" ? after.reason : "invalid_target";
  return null;
}
