/** How does the versioned HTTP endpoint expose one transient host sample? */
import type { ProbeConfig } from "../config";
import { sampleHost } from "../probe/sample-host";
import type { ProbeContext } from "../probe/proc-reader";

// The calendar-versioned route is an API protocol identifier.
export const SAMPLE_PATH = "/api/2026-10-20/sample";
// Bun's zero disables its idle timer; only the configured sampling delay applies.
const DISABLED_IDLE_TIMEOUT = 0;

export function createSampleHandler(config: ProbeConfig, context: ProbeContext = {}) {
  return async (request: Request): Promise<Response> => {
    if (new URL(request.url).pathname !== SAMPLE_PATH) {
      return Response.json({ error: "Not found" }, { status: 404 });
    }
    if (request.method !== "GET") {
      return Response.json({ error: "Method not allowed" }, { status: 405, headers: { Allow: "GET" } });
    }
    return Response.json(await sampleHost(config, context), { headers: { "Cache-Control": "no-store" } });
  };
}

export function serveSamples(config: ProbeConfig) {
  return Bun.serve({
    hostname: config.listen_host,
    port: config.listen_port,
    idleTimeout: DISABLED_IDLE_TIMEOUT,
    fetch: createSampleHandler(config),
    error(error) {
      console.error(JSON.stringify({ error: error.message }));
      return Response.json({ error: "Host sampling failed" }, { status: 500 });
    },
  });
}
