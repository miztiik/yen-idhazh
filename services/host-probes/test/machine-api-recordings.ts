/** Materialize only named machine configuration for real isolated child tasks. */
import { randomUUID } from "node:crypto";
import { copyFile, mkdir, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRootContext } from "@idhazh/common-contracts";
import { loadHonoSettings } from "@idhazh/serve-pipeline-apis/settings";
import { MachineApiStartupSchema } from "../src/api/read-machine-api-startup";

export async function recordedMachineTask() {
  const root = await mkdtemp(join(tmpdir(), "machine-api-task-"));
  try {
    await mkdir(join(root, "config"));
    await mkdir(join(root, "logs"));
    for (const name of [
      "hono-server.json", "typescript-event-sources.json", "host-fingerprints.json",
      "host-probes.json", "idhazh.json", "ledgers.json",
    ]) await copyFile(new URL(`../../../config/${name}`, import.meta.url), join(root, "config", name));
    const authored = await loadHonoSettings(root);
    const reservation = Bun.serve({ hostname: authored.hostname, port: 0, fetch: () => new Response() });
    const server = { ...authored, port: reservation.port! };
    await reservation.stop(true);
    await Bun.write(join(root, "config", "hono-server.json"), JSON.stringify(server));
    const settings = await Bun.file(join(root, "config", "idhazh.json")).json();
    Object.assign(settings.observability, {
      host_telemetry_enabled: true, host_fingerprint: true,
      host_fingerprint_placement_enabled: false, host_fingerprint_bandwidth_jobs: [],
    });
    await Bun.write(join(root, "config", "idhazh.json"), JSON.stringify(settings));
    const fingerprint = await Bun.file(join(root, "config", "host-fingerprints.json")).json();
    fingerprint.metadata_url = null;
    await Bun.write(join(root, "config", "host-fingerprints.json"), JSON.stringify(fingerprint));
    const probes = await Bun.file(join(root, "config", "host-probes.json")).json();
    probes.task_profile.enabled = true;
    await Bun.write(join(root, "config", "host-probes.json"), JSON.stringify(probes));
    const startup = MachineApiStartupSchema.parse({
      group: "machine", nonce: randomUUID(), state_root: "state", directory: "logs", server,
      run: { run_id: "700", attempt: 3, started_at: "2026-11-04T00:00:00Z", context: createRootContext() },
    });
    return {
      root, startup, evidence: join(root, "logs"),
      entry: fileURLToPath(new URL("../src/api/serve-machine-apis.ts", import.meta.url)),
      close: () => rm(root, { recursive: true, force: true }),
    };
  } catch (original) {
    try { await rm(root, { recursive: true, force: true }); }
    catch (cleanup) { throw new AggregateError([original, cleanup], "Machine recording preparation and cleanup failed"); }
    throw original;
  }
}
