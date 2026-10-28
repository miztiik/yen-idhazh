/** How does the real host HTTP service write one named Linux transcript for a workflow? */
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fixture } from "../../host-fingerprints/test/fixture";
import { captureLocalFingerprint } from "../../host-fingerprints/src/api/local-fingerprint";
import { hostWriter, readMetadataRegistrations } from "../scripts/feed-ingest-plan-metadata";
import type { ExecutionIdentity } from "../scripts/feed-ingest-plan-metadata";
import { WorkflowHostFingerprintSchema } from "../scripts/feed-ingest-plan-host-fingerprint";

export function metadataRegistrations() {
  return readMetadataRegistrations(new URL("../../../config/ledgers.json", import.meta.url));
}
export async function recordedWorkflowHost(directory: string, identity: ExecutionIdentity) {
  const recording = await fixture();
  try {
    await mkdir(directory, { recursive: true });
    const request = { date: identity.run_id.slice(0, 10), writer: hostWriter(identity) };
    const response = await captureLocalFingerprint(request, { ...recording.config, listen_port: 0 }, recording.settings, {
      outputRoot: join(directory, "state"), inspection: recording.inspection,
    });
    if (response.status !== "written") throw new Error("The recorded host HTTP request must persist");
    const evidence = WorkflowHostFingerprintSchema.parse({
      host_request: request,
      host: { ...response, status: "recorded" },
    });
    await writeFile(join(directory, "host-fingerprint.json"), JSON.stringify(evidence));
    return { response, evidence, identity, registrations: await metadataRegistrations() };
  } finally { await recording.cleanup(); }
}
