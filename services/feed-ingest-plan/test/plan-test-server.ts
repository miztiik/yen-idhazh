/** Send operator test requests through a real ephemeral loopback listener. */
import { createPlanApp } from "../src/api/server";
import type { PlanInputs } from "../src/load-plan-inputs";
import type { PlanRuntime } from "../src/run-feed-plan";

export function createPlanTestServer(inputs: PlanInputs, runtime: PlanRuntime) {
  const app = createPlanApp(inputs, runtime);
  const server = Bun.serve({
    hostname: "127.0.0.1", port: 0, idleTimeout: 0,
    fetch(request, server) {
      return app.fetch(request, { beginPlanning: () => server.timeout(request, 0),
        stage_origin: `http://127.0.0.1:${server.port}` });
    },
  });
  return {
    request(path: string, init?: RequestInit) {
      return fetch(new URL(path, `http://127.0.0.1:${server.port}`), init);
    },
    async close() { try { await server.stop(true); } finally { await app.close(); } },
  };
}
