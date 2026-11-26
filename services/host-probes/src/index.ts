/** Which host probe operation did the operator request? */
import { resolve } from "node:path";
import { z } from "zod";
import { createRootContext } from "@idhazh/common-contracts";
import type { OperationMetadata } from "@idhazh/common-contracts";
import { loadConfig, loadTaskPerformanceSettings, TaskPerformanceExecutionSchema } from "./config";
import { serveSamples } from "./api/server";
import { sampleHost } from "./probe/sample-host";
import { createProbeCompletionEvent, createProbeFailureEvent } from "./api/create-probe-event";
export { createSampleHandler } from "./api/server";
export { loadConfig } from "./config";
export { summarizeClosedTaskProfile } from "./task-profile/summarize-closed-profile";

const launchPath = z.string().min(1).refine(path => !path.includes("\0"));
const RecordingLaunchSchema = z.strictObject({
  execution: TaskPerformanceExecutionSchema,
  state_root: launchPath,
  registry_path: launchPath.optional(),
});

async function main(context: OperationMetadata): Promise<void> {
  const [operation, flag, launchFile, ...extra] = Bun.argv.slice(2);
  if ((operation !== "--sample" && operation !== "--serve")
    || (flag !== undefined && (operation !== "--serve" || flag !== "--recording-context" || !launchFile || extra.length))) {
    throw new Error("Usage: bun run src/index.ts --sample|--serve [--recording-context launch.json]");
  }
  const config = await loadConfig();
  if (operation === "--sample") {
    const result = await sampleHost(config);
    console.error(JSON.stringify(createProbeCompletionEvent({ context, operation: "sample", outcome: "handled" })));
    console.log(JSON.stringify(result));
  } else {
    const launch = launchFile === undefined ? undefined : RecordingLaunchSchema.parse(await Bun.file(launchFile).json());
    const recording = launch === undefined ? undefined : {
      execution: launch.execution, settings: await loadTaskPerformanceSettings(), outputRoot: resolve(launch.state_root),
      ...(launch.registry_path === undefined ? {} : { registryPath: resolve(launch.registry_path) }),
    };
    const server = serveSamples(config, { lifetimeContext: context }, recording);
    console.error(JSON.stringify({ listening: server.url.toString() }));
    const stop = () => {
      void server.stop(true).catch(() => { process.exitCode = 1; });
    };
    process.once("SIGINT", stop);
    process.once("SIGTERM", stop);
  }
}

if (import.meta.main) {
  const context = createRootContext();
  main(context).catch(() => {
    console.error(JSON.stringify(createProbeFailureEvent({ context, type: "host_probe_failed" })));
    process.exitCode = 1;
  });
}
