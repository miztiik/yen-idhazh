/** Keep the real recorded machine application under the production private-pipe lifetime. */
import { runHttpChild } from "@idhazh/feed-ingest-plan/http-child-lifetime";
import { ApiStartupSchema, startupNonce, startupSupervision } from "../src/api-startup";
import { serveRecordedMachine } from "./recorded-machine-api";

await runHttpChild("TYPESCRIPT_API", message => {
  const startup = ApiStartupSchema.parse(message);
  if (startup.group !== "machine") throw new Error("The recorded machine child requires its explicit group");
  return {
    shutdownTimeoutMs: startupSupervision(startup).shutdown_timeout_ms,
    start: async signal => {
      signal.throwIfAborted();
      const server = await serveRecordedMachine(process.cwd(), startup.server, startupNonce(startup));
      return { server, ready: server.identity };
    },
  };
});
