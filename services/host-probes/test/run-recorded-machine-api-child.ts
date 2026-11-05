/** Keep the real recorded machine application under the production private-pipe lifetime. */
import { runHttpChild } from "@idhazh/serve-pipeline-apis/child";
import { MachineApiStartupSchema } from "../src/api/read-machine-api-startup";
import { captureMachineApiFailure } from "../src/api/capture-machine-api-failure";
import { serveRecordedMachine } from "./serve-recorded-machine-api";

await runHttpChild("TYPESCRIPT_API", captureMachineApiFailure(), message => {
  const startup = MachineApiStartupSchema.parse(message);
  return {
    shutdownTimeoutMs: startup.supervision.shutdown_timeout_ms,
    start: async signal => {
      signal.throwIfAborted();
      const server = await serveRecordedMachine(process.cwd(), startup.server, startup.nonce);
      return { server, ready: server.identity };
    },
  };
});
