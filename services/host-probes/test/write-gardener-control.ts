/** Write hosted runner evidence through the native handlers without external requests. */
import { z } from "zod";
import { createFingerprintHandler, FINGERPRINT_PATH } from "@idhazh/host-fingerprints/api";
import { FingerprintRequestSchema, loadConfig, loadSettings } from "@idhazh/host-fingerprints/config";
import { FingerprintResponseSchema } from "@idhazh/host-fingerprints/response";
import {
  RECORD_TASK_PERFORMANCE_PATH, RecordTaskPerformanceRequestSchema,
} from "../src/api/record-task-performance-route";
import { createSampleHandler } from "../src/api/server";
import { loadConfig as loadProbeConfig, loadTaskPerformanceSettings } from "../src/config";

const captures = z.array(z.strictObject({
  state: z.string(), request: FingerprintRequestSchema,
  tasks: z.array(RecordTaskPerformanceRequestSchema),
})).parse(JSON.parse(await Bun.stdin.text()));
const configRoot = new URL("../../../config/", import.meta.url);
const config = await loadConfig(new URL("host-fingerprints.json", configRoot));
const settings = await loadSettings(new URL("idhazh.json", configRoot));
const probes = await loadProbeConfig();
const performance = await loadTaskPerformanceSettings();
const registryPath = new URL("ledgers.json", configRoot);
settings.observability.host_fingerprint_placement_enabled = false;
settings.observability.host_fingerprint_bandwidth_jobs = [];

function command(path: string, body: unknown): Request {
  return new Request(`http://localhost${path}`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
  });
}

for (const { state, request, tasks } of captures) {
  const handler = createFingerprintHandler(config, settings, {
    outputRoot: state, registryPath,
  });
  const reply = await handler(command(FINGERPRINT_PATH, request));
  if (!reply.ok) throw new Error(`${reply.status}: ${await reply.text()}`);
  const opening = FingerprintResponseSchema.parse(await reply.json());
  if (opening.status !== "written") throw new Error("The runner did not capture its opening");
  const { run_id, attempt, shard, git_sha, job, pipeline_name } = request.writer;
  if (job === null || pipeline_name === null) throw new Error("A hosted runner needs both identities");
  const recorder = createSampleHandler(probes, {}, undefined, undefined, {
    outputRoot: state, registryPath, settings: performance,
    execution: {
      run_id, attempt, shard, git_sha, pipeline_name, accounting_days: [request.date],
      runner_job: job,
    },
  });
  try {
    const recorded: unknown[] = [];
    for (const task of tasks) {
      const response = await recorder(command(RECORD_TASK_PERFORMANCE_PATH, {
        ...task, measurement: { ...task.measurement, host_unit_id: opening.files[0]!.unit_id },
      }));
      if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
      recorded.push(await response.json());
    }
    console.log(JSON.stringify({ opening, recorded }));
  } finally {
    await recorder.close();
  }
}
