/** Which native machine fields does the Python workflow consume? */
import { z } from "../../services/host-probes/node_modules/zod";
import { HostFingerprintRowSchema } from "../../packages/common-contracts/src/schemas/host-fingerprint.schema";
import type { TaskProfile, TaskSample } from "../../services/host-probes/src/task-profile/profile-schema";
import { CurrentMachineServerEvidenceSchema } from "../../services/host-probes/src/api/create-machine-server-evidence";

const serverFields = CurrentMachineServerEvidenceSchema.shape;
export const MachineServerProjectionSchema = z.object({
  version: serverFields.version, server_name: serverFields.server_name, group: serverFields.group,
  pid: serverFields.pid, listener: serverFields.listener, identity: serverFields.identity,
  startup: serverFields.startup, startup_ms: serverFields.startup_ms, shutdown: serverFields.shutdown,
  exit_code: serverFields.exit_code, log_filename: serverFields.log_filename,
  log_available: serverFields.log_available, error_code: serverFields.error_code,
  cleanup_error_code: serverFields.cleanup_error_code,
});

export const HardwareSchema = z.object({
  cpu_model: HostFingerprintRowSchema.shape.cpu_model,
  cpu_logical_processors: HostFingerprintRowSchema.shape.cpu_logical_processors,
  cpu_physical_cores: HostFingerprintRowSchema.shape.cpu_physical_cores,
  machine_memory_total_mib: HostFingerprintRowSchema.shape.machine_memory_total_mib,
  status: z.enum(["collected", "disabled", "failed"]),
  unavailable: z.record(z.string(), z.string()),
  reason: z.enum(["configured_off", "collection_failed"]).nullable(),
});

export function projectMachineProfile(profile: TaskProfile) {
  const first = profile.samples[0], last = profile.samples.at(-1);
  if (first === undefined || last === undefined) throw new Error("Missing actual profile endpoints");
  const sample = (value: TaskSample) => ({
    phase: value.phase,
    memory_kb: { total: value.memory_kb.total, available: value.memory_kb.available },
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
