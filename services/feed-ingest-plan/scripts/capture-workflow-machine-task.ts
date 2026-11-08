/** Which finite machine task captures the fingerprint before planning starts? */
import { randomUUID } from "node:crypto";
import { join, relative } from "node:path";
import { SelectedSettingsSchema } from "@idhazh/host-fingerprints/config";
import { superviseMachineApiTask } from "@idhazh/host-probes/machine-supervisor";
import { loadHonoSettings } from "@idhazh/serve-pipeline-apis/settings";
import type { ServerRun } from "@idhazh/serve-pipeline-apis/evidence";
import { captureWorkflowHostFingerprint, retainWorkflowHostFailure } from "./feed-ingest-plan-host-fingerprint";

export async function captureWorkflowMachineTask(input: Omit<
  Parameters<typeof captureWorkflowHostFingerprint>[0], "origin"
> & { run: ServerRun; registryPath: string }) {
  try {
    const settings = SelectedSettingsSchema.parse(await Bun.file(join(input.root, "config", "idhazh.json")).json());
    if (!settings.observability.host_telemetry_enabled || !settings.observability.host_fingerprint) {
      return await captureWorkflowHostFingerprint(input);
    }
    return await superviseMachineApiTask({
      root: input.root,
      ...(input.signal === undefined ? {} : { signal: input.signal }),
      startup: {
        group: "machine", nonce: randomUUID(), server: await loadHonoSettings(input.root, "machine"),
        directory: relative(input.root, input.directory).replaceAll("\\", "/"),
        state_root: relative(input.root, input.stateRoot).replaceAll("\\", "/"),
        registry_path: input.registryPath, run: input.run,
      },
      request: (origin, signal) => captureWorkflowHostFingerprint({ ...input, origin, signal }),
    });
  } catch (error) {
    try { await retainWorkflowHostFailure(input, error); }
    catch (retention) { throw new AggregateError([error, retention], "Machine task failed and its fingerprint evidence could not be retained"); }
    throw error;
  }
}
