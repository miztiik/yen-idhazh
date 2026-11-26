/** Which cells from a closed task profile are safe to file as performance evidence? */
import type { TaskPerformanceRow } from "@idhazh/common-contracts";
import type { TaskProfile } from "./profile-schema";

type ClosedProfileSummary = Pick<TaskPerformanceRow,
  "outcome" | "started_at" | "finished_at" | "elapsed_ms" | "machine_cpu_busy_pct" | "machine_cpu_steal_pct"
  | "machine_memory_available_min_kib" | "worker_rss_peak_kib" | "worker_cpu_time_ms">;

export function summarizeClosedTaskProfile(profile: TaskProfile): ClosedProfileSummary {
  const machineCpu = profile.cpu.value;
  return {
    outcome: profile.outcome,
    started_at: profile.started_at,
    finished_at: profile.finished_at,
    elapsed_ms: profile.elapsed_ms,
    machine_cpu_busy_pct: machineCpu === null ? null : Math.min(100, machineCpu.user + machineCpu.system),
    machine_cpu_steal_pct: machineCpu?.steal ?? null,
    machine_memory_available_min_kib: profile.machine_available_min_kb,
    worker_rss_peak_kib: profile.processes.worker.sampled_rss_max_kb,
    worker_cpu_time_ms: profile.processes.worker.cpu.value?.cpu_time_ms ?? null,
  };
}
