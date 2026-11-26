/** How do fingerprint and profiling operations share a native application and cleanup? */
import { join, resolve } from "node:path";
import { Hono } from "hono";
import { createFingerprintHandler, FINGERPRINT_PATH, HEALTH_PATH } from "@idhazh/host-fingerprints/api";
import { loadConfig as loadFingerprintConfig, loadSettings } from "@idhazh/host-fingerprints/config";
import type { ApiApplication, ApiBindings } from "@idhazh/serve-pipeline-apis/app";
import { loadConfig, loadTaskPerformanceSettings } from "../config";
import type { TaskPerformanceExecution } from "../config";
import {
  CACHE_LATENCY_PATH, createSampleHandler, RECORD_TASK_PERFORMANCE_PATH,
  SAMPLE_PATH, START_ITEM_WINDOW_PATH, START_TASK_PROFILE_PATH, STOP_ITEM_WINDOW_PATH, STOP_TASK_PROFILE_PATH,
} from "./server";

type FingerprintOptions = Parameters<typeof createFingerprintHandler>;
type ProbeOptions = Parameters<typeof createSampleHandler>;
export type MachineApiInputs = {
  fingerprint: {
    config: FingerprintOptions[0]; settings: FingerprintOptions[1]; options: FingerprintOptions[2];
    diagnostics?: FingerprintOptions[3];
  };
  probes: {
    config: ProbeOptions[0]; context?: ProbeOptions[1]; report?: ProbeOptions[2]; diagnostics?: ProbeOptions[3];
    recording?: ProbeOptions[4];
  };
};

export async function loadMachineApiInputs(
  root: string, outputRoot: string, registryPath = join(root, "config", "ledgers.json"),
  execution?: TaskPerformanceExecution, taskProfileMemoryEnabled?: boolean,
): Promise<MachineApiInputs> {
  const settingsPath = join(root, "config", "idhazh.json");
  const [config, settings, probes, recordingSettings] = await Promise.all([
    loadFingerprintConfig(join(root, "config", "host-fingerprints.json")),
    loadSettings(settingsPath),
    loadConfig(join(root, "config", "host-probes.json")),
    execution === undefined ? undefined : loadTaskPerformanceSettings(settingsPath),
  ]);
  const options = { outputRoot: resolve(root, outputRoot), registryPath };
  return {
    fingerprint: { config, settings, options },
    probes: { config: probes, ...(execution === undefined || recordingSettings === undefined ? {} : {
      recording: { ...options, execution, settings: {
        ...recordingSettings,
        observability: {
          ...recordingSettings.observability,
          memory_profiling_enabled: taskProfileMemoryEnabled ?? recordingSettings.observability.memory_profiling_enabled,
        },
      } },
    }) },
  };
}

export function createMachineApp(input: MachineApiInputs): ApiApplication {
  const app = new Hono<{ Bindings: ApiBindings }>();
  const fingerprint = createFingerprintHandler(input.fingerprint.config, input.fingerprint.settings,
    input.fingerprint.options, input.fingerprint.diagnostics);
  const probe = createSampleHandler(input.probes.config, input.probes.context, input.probes.report,
    input.probes.diagnostics, input.probes.recording);
  app.all(FINGERPRINT_PATH, c => fingerprint(c.req.raw));
  app.all(HEALTH_PATH, c => fingerprint(c.req.raw));
  for (const path of [SAMPLE_PATH, START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH, START_ITEM_WINDOW_PATH,
    STOP_ITEM_WINDOW_PATH, CACHE_LATENCY_PATH, RECORD_TASK_PERFORMANCE_PATH]) {
    app.all(path, c => probe(c.req.raw));
  }
  app.notFound(c => c.json({ code: "NOT_FOUND" }, 404));
  app.onError(error => { throw error; });
  return {
    maxRequestBodyBytes: Math.max(input.fingerprint.config.max_input_bytes, input.probes.config.max_request_body_bytes),
    fetch: (request, bindings) => app.fetch(request, bindings),
    close: () => probe.close(),
  };
}
