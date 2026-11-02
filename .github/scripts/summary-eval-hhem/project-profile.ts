/** Which native machine observations fit the workflow's private control packet? */
import type { TaskProfile, TaskSample } from "../../../services/host-probes/src/task-profile/profile-schema";

export function projectMachineProfile(profile: TaskProfile) {
  const first = profile.samples[0];
  const last = profile.samples.at(-1);
  if (first === undefined || last === undefined) throw new Error("Missing actual profile endpoints");
  const sample = (value: TaskSample) => ({
    phase: value.phase, memory_kb: {
      total: value.memory_kb.total, available: value.memory_kb.available,
    },
    unavailable: value.unavailable,
  });
  return {
    outcome: profile.outcome, end_reason: profile.end_reason,
    started_at: profile.started_at, finished_at: profile.finished_at, elapsed_ms: profile.elapsed_ms,
    cpu: profile.cpu.reason === null ? {
      reason: null, value: { user: profile.cpu.value.user, system: profile.cpu.value.system },
    } : profile.cpu,
    machine_available_min_kb: profile.machine_available_min_kb,
    unavailable: profile.unavailable, samples: [sample(first), sample(last)],
  };
}
