/** Start the real shared machine routes with recorded process counters and owned cleanup. */
import { randomUUID } from "node:crypto";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { loadConfig as loadFingerprintConfig, loadSettings } from "@idhazh/host-fingerprints/config";
import { loadConfig as loadProbeConfig } from "@idhazh/host-probes/config";
import { parseProcessStat } from "../src/task-profile/process-stat";
import { createApiApp, serveApiApp } from "@idhazh/serve-pipeline-apis/app";
import type { HonoServerSettings } from "@idhazh/serve-pipeline-apis/settings";
import { createMachineApp } from "../src/api/create-machine-app";

export async function serveRecordedMachine(root: string, listener: HonoServerSettings, nonce: string = randomUUID()) {
  const directory = await mkdtemp(join(tmpdir(), "api-profile-report-"));
  try {
    const config = await loadProbeConfig(join(root, "config", "host-probes.json"));
    config.task_profile.enabled = true;
    const recorded = await Bun.file(new URL("../../../tests/fixtures/host-probes/process-inputs.json", import.meta.url)).json();
    const stat = recorded.stat.replace("4242 ", `${process.pid} `);
    await mkdir(join(directory, String(process.pid)));
    await writeFile(join(directory, String(process.pid), "stat"), stat);
    const pin = parseProcessStat(process.pid, stat);
    if (pin.reason !== null) throw new Error("The named process recording must contain its PID pin");
    const identity = {
      event: "typescript_api_ready" as const, nonce, pid: process.pid,
      port: listener.port, group: "machine" as const, modules: ["machine" as const], enabled: true,
    };
    const fingerprint = {
      config: await loadFingerprintConfig(join(root, "config", "host-fingerprints.json")),
      settings: await loadSettings(join(root, "config", "idhazh.json")),
      options: { outputRoot: join(directory, "state"), registryPath: join(root, "config", "ledgers.json") },
    };
    const server = await serveApiApp(listener, createApiApp({
      identity, create: () => createMachineApp({
        fingerprint, probes: { config, context: { platform: "linux", procRoot: directory } },
      }),
    }));
    return {
      identity, target: { pid: process.pid, start_ticks: pin.value.start_ticks },
      port: server.port,
      async stop(force = false) {
        try { await server.stop(force); }
        finally { await rm(directory, { recursive: true, force: true }); }
      },
    };
  } catch (original) {
    try { await rm(directory, { recursive: true, force: true }); }
    catch (cleanup) { throw new AggregateError([original, cleanup], "Recorded machine startup and cleanup failed"); }
    throw original;
  }
}
