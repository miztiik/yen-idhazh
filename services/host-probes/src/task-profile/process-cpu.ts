/** How much CPU time did one pinned process consume over its actual observation interval? */
import type { Observation } from "../probe/proc-reader";
import type { ClockTicks, ProcessCpu, TaskUnavailableReason } from "./profile-schema";
import type { ProcessCpuCounters } from "./process-stat";

// These fixed unit conversions are not sampling controls.
const MILLISECONDS_PER_SECOND = 1000;
const PERCENT_PER_UNIT = 100;

export function calculateProcessCpu(
  start: Observation<ProcessCpuCounters, TaskUnavailableReason>,
  end: Observation<ProcessCpuCounters, TaskUnavailableReason>,
  elapsedMs: number,
  clock: ClockTicks,
): ProcessCpu {
  if (start.reason !== null) return start;
  if (end.reason !== null) return end;
  const user = end.value.user - start.value.user;
  const system = end.value.system - start.value.system;
  if (user < 0n || system < 0n) return { value: null, reason: "counter_reset" };
  if (!Number.isFinite(elapsedMs) || elapsedMs <= 0) return { value: null, reason: "no_interval" };
  if (clock.reason !== null) return clock;
  if (!Number.isSafeInteger(clock.value) || clock.value <= 0) return { value: null, reason: "invalid_data" };
  const cpu_time_ms = MILLISECONDS_PER_SECOND * Number(user + system) / clock.value;
  const percent_one_core = PERCENT_PER_UNIT * cpu_time_ms / elapsedMs;
  return Number.isFinite(cpu_time_ms) && Number.isFinite(percent_one_core)
    ? { value: { cpu_time_ms, percent_one_core }, reason: null } : { value: null, reason: "invalid_data" };
}
