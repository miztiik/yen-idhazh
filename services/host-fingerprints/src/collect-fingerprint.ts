/** Which hardware facts describe this caller's execution? */
import { fingerprintV2, HostHardwareRowSchema, HOST_HARDWARE_VERSION } from "@idhazh/common-contracts";
import { CaptureContextSchema } from "./config";
import type { SelectedSettings, ServiceConfig } from "./config";
import type { Inspection } from "./inspect/bounded-input";
import { readInput } from "./inspect/bounded-input";
import { parseCpuModel } from "./inspect/cpu-model";
import { collectTopology } from "./inspect/cpu-topology";
import { collectCapacity } from "./inspect/cpu-capacity";
import { collectHardware } from "./inspect/hardware-identity";
import { collectMemoryCapacity } from "./inspect/memory-capacity";
import { collectPlacement } from "./inspect/placement";
import { measureCopy } from "./inspect/copy-bandwidth";
import { runnerName } from "./inspect/runner-env";

export async function collectFingerprint(
  input: unknown, config: ServiceConfig, settings: SelectedSettings,
  inspection: Inspection = {}, collectSelf = true,
) {
  const capture = CaptureContextSchema.parse(input);
  const unavailable: Record<string, string> = {};
  const context = { ...inspection, unavailable };
  const measured_at = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const { run_id, job, pipeline_name, task_name, shard } = capture.writer;
  const rowInput = {
    version: HOST_HARDWARE_VERSION, date: capture.date, run_id, job, pipeline_name, task_name, shard, measured_at,
    runner_name: runnerName(inspection.environment ?? process.env),
  };
  if ((inspection.platform ?? process.platform) !== "linux") {
    unavailable.platform = "unsupported_platform";
    unavailable.machine_memory_total_mib = "unsupported_platform";
    return { row: HostHardwareRowSchema.parse(rowInput), unavailable };
  }
  const frequency = settings.observability.host_fingerprint_frequency_enabled;
  const model = parseCpuModel(await readInput("/proc/cpuinfo", config, context), frequency);
  for (const [field, value] of Object.entries(model)) {
    if (value === null) unavailable[field] = field === "cpu_observed_mhz" && !frequency ? "configured_off" : "cpuinfo_unavailable";
  }
  const topology = await collectTopology(config, context, frequency);
  const hardware = await collectHardware(config, context);
  const target = capture.target === undefined && collectSelf ? "self" : capture.target ?? null;
  const capacity = await collectCapacity(topology.ids, config, context, target);
  const memory = await collectMemoryCapacity(config, context);
  if (capture.ask_placement === false) unavailable.placement = "configured_off";
  const placement = capture.ask_placement === false ? null : await collectPlacement(config, settings, context);
  if (placement) {
    for (const [field, value] of Object.entries(placement)) {
      if (value === null) unavailable[field] = "metadata_field_unavailable";
    }
  }
  const row = HostHardwareRowSchema.parse({
    ...rowInput, ...model, ...hardware, ...capacity, ...memory,
    cpu_logical_processors: topology.cpu_logical_processors,
    cpu_physical_cores: topology.cpu_physical_cores,
    cpu_reported_max_mhz: topology.cpu_reported_max_mhz,
    ...placement, ...measureCopy(task_name, hardware.l3_cache_bytes, settings, config, context),
  });
  const fingerprint = fingerprintV2(row);
  return {
    row: HostHardwareRowSchema.parse({ ...row, fingerprint, fingerprint_version: fingerprint === null ? null : 2 }),
    unavailable,
  };
}
