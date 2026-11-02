/** Which existing hardware API result belongs to this workflow? */
import { z } from "../../../services/host-probes/node_modules/zod";
import { HostFingerprintRowSchema } from "../../../packages/common-contracts/src/schemas/host-fingerprint.schema";
import {
  loadConfig, loadSettings,
} from "../../../services/host-fingerprints/src/config";
import { captureLocalFingerprint } from "../../../services/host-fingerprints/src/api/local-fingerprint";
import { join } from "node:path";

export const HardwareFieldsSchema = z.object({
  cpu_model: HostFingerprintRowSchema.shape.cpu_model,
  cpu_logical_processors: HostFingerprintRowSchema.shape.cpu_logical_processors,
  cpu_physical_cores: HostFingerprintRowSchema.shape.cpu_physical_cores,
  machine_memory_total_mib: HostFingerprintRowSchema.shape.machine_memory_total_mib,
});
export const HardwareSchema = HardwareFieldsSchema.extend({
  status: z.enum(["collected", "disabled", "failed"]),
  unavailable: z.record(z.string(), z.string()),
  reason: z.enum(["configured_off", "collection_failed"]).nullable(),
});
export type Hardware = z.infer<typeof HardwareSchema>;

export async function captureHardware(
  root: string, directory: string, writer: {
    run_id: string; attempt: number; git_sha: string;
    pipeline_name: string; task_name: string;
  },
): Promise<Hardware> {
  try {
    const result = await captureLocalFingerprint({
      date: writer.run_id.slice(0, 10),
      writer: { ...writer, job: null, shard: 0, producer: "telemetry.silicon" },
    }, await loadConfig(join(root, "config", "host-fingerprints.json")),
    await loadSettings(join(root, "config", "idhazh.json")), {
      outputRoot: join(directory, "host"),
    });
    if (result.status === "written") return HardwareSchema.parse({
      ...HardwareFieldsSchema.parse(result.row),
      status: "collected", unavailable: result.unavailable, reason: null,
    });
    return HardwareSchema.parse({
      status: "disabled", unavailable: {}, reason: "configured_off",
    });
  } catch {
    // The parent receives a structured failure, never native diagnostics or file paths.
    return HardwareSchema.parse({
      status: "failed", unavailable: {}, reason: "collection_failed",
    });
  }
}
