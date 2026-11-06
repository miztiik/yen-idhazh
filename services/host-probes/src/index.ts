/** Which host probe operation did the operator request? */
import { createRootContext } from "@idhazh/common-contracts";
import type { OperationMetadata } from "@idhazh/common-contracts";
import { loadConfig } from "./config";
import { serveSamples } from "./api/server";
import { sampleHost } from "./probe/sample-host";
import { createProbeCompletionEvent, createProbeFailureEvent } from "./api/create-probe-event";
export { createSampleHandler } from "./api/server";
export { loadConfig } from "./config";

async function main(context: OperationMetadata): Promise<void> {
  const args = Bun.argv.slice(2);
  if (args.length !== 1 || (args[0] !== "--sample" && args[0] !== "--serve")) {
    throw new Error("Usage: bun run src/index.ts --sample|--serve");
  }
  const config = await loadConfig();
  if (args[0] === "--sample") {
    const result = await sampleHost(config);
    console.error(JSON.stringify(createProbeCompletionEvent({ context, operation: "sample", outcome: "handled" })));
    console.log(JSON.stringify(result));
  } else {
    const server = serveSamples(config, { lifetimeContext: context });
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
