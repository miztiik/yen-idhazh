/** Start the native machine application under its shared private-pipe lifetime. */
import { runHttpChild } from "@idhazh/serve-pipeline-apis/child";
import { createApiApp, serveApiApp } from "@idhazh/serve-pipeline-apis/app";
import { createMachineApp, loadMachineApiInputs } from "./create-machine-app";
import { captureMachineApiFailure, MachineApiError } from "./capture-machine-api-failure";
import { MachineApiStartupSchema, readMachineApiIdentity } from "./read-machine-api-startup";

export function runMachineApiServer() {
  return runHttpChild("TYPESCRIPT_API", captureMachineApiFailure(), message => {
    const startup = MachineApiStartupSchema.parse(message);
    return {
      shutdownTimeoutMs: startup.server.supervision.shutdown_timeout_ms,
      start: async signal => {
        const inputs = await loadMachineApiInputs(process.cwd(), startup.state_root);
        const identity = readMachineApiIdentity(startup, process.pid);
        signal.throwIfAborted();
        try {
          const server = await serveApiApp(startup.server, createApiApp({
            identity, create: () => createMachineApp(inputs),
          }));
          return { server, ready: { ...identity, port: server.port } };
        } catch (error) {
          throw new MachineApiError("TYPESCRIPT_API_BIND_FAILED", "Pipeline API loopback listener could not start", error);
        }
      },
    };
  });
}

if (import.meta.main) {
  try { await runMachineApiServer(); }
  catch { process.exitCode = 2; }
}
