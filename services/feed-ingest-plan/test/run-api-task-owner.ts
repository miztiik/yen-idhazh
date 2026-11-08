/** How does owned IPC dispatch against the same native application served by a real Bun child? */
import { z } from "zod";
import { runHttpChild } from "@idhazh/serve-pipeline-apis/child";
import { createApiApp, serveApiApp } from "@idhazh/serve-pipeline-apis/app";
import type { ApiApplication } from "@idhazh/serve-pipeline-apis/app";
import { apiOrigin } from "@idhazh/serve-pipeline-apis/settings";
import { createMachineApp, loadMachineApiInputs } from "@idhazh/host-probes/machine-app";
import { MachineApiStartupSchema, readMachineApiIdentity } from "@idhazh/host-probes/machine-startup";
import { captureMachineApiFailure } from "../../host-probes/src/api/capture-machine-api-failure";
import { PlannerReadySchema } from "../src/config/planner-startup";
import { createFeedApiApp } from "../scripts/create-feed-api-app";
import { FeedApiStartupSchema, readFeedApiIdentity } from "../scripts/read-feed-api-startup";
import { restoreRecordedPlannerStartup } from "./planner-server-recording";

export const NativeRequestSchema = z.strictObject({
  request_id: z.uuid(), path: z.string().startsWith("/api/"), method: z.enum(["GET", "POST"]),
  headers: z.record(z.string(), z.string()), body: z.unknown().optional(),
});
export const NativeReplySchema = z.discriminatedUnion("kind", [
  z.strictObject({
    kind: z.literal("response"), request_id: z.uuid(), status: z.int(),
    text: z.string(),
  }),
  z.strictObject({ kind: z.literal("failed"), request_id: z.uuid(), code: z.literal("NATIVE_DISPATCH_FAILED") }),
]);
export type NativeReply = z.infer<typeof NativeReplySchema>;

async function runNativeOwner() {
  let application: ApiApplication | undefined;
  let origin: string | undefined;
  const pending = new Set<Promise<void>>();
  const dispatch = async (raw: unknown) => {
    const input = NativeRequestSchema.parse(raw);
    try {
      if (application === undefined || origin === undefined) throw new Error("Native application is not ready");
      const response = await application.fetch(new Request(new URL(input.path, origin), {
        method: input.method, headers: input.headers,
        ...(input.body === undefined ? {} : { body: JSON.stringify(input.body) }),
      }), { stage_origin: origin });
      if (process.send === undefined) throw new Error("Owned IPC is unavailable");
      process.send(NativeReplySchema.parse({
        kind: "response", request_id: input.request_id, status: response.status, text: await response.text(),
      }));
    } catch (error) {
      console.error(JSON.stringify({ event: "native_dispatch_failed", code: "NATIVE_DISPATCH_FAILED" }));
      if (process.send === undefined) throw error;
      process.send(NativeReplySchema.parse({ kind: "failed", request_id: input.request_id, code: "NATIVE_DISPATCH_FAILED" }));
    }
  };
  const receive = (raw: unknown) => {
    const operation = dispatch(raw);
    pending.add(operation);
    void operation.finally(() => pending.delete(operation)).catch(() => {
      console.error(JSON.stringify({ event: "native_ipc_invalid", code: "NATIVE_IPC_INVALID" }));
      process.exitCode = 2;
    });
  };
  process.on("message", receive);
  try {
    await runHttpChild("TYPESCRIPT_API", captureMachineApiFailure(), raw => {
      const startup = z.union([FeedApiStartupSchema, MachineApiStartupSchema]).parse(raw);
      if (startup.group === "delivery") throw new Error("The ownership journey covers planning and machine");
      return {
        shutdownTimeoutMs: startup.server.supervision.shutdown_timeout_ms,
        start: async signal => {
          const identity = startup.group === "planning"
            ? readFeedApiIdentity(startup, process.pid) : readMachineApiIdentity(startup, process.pid);
          if (startup.group === "planning") {
            const restored = await restoreRecordedPlannerStartup(startup.planner);
            application = createFeedApiApp({
              identity, planner: {
                ...restored, runtime: { ...restored.runtime, signal },
                identity: PlannerReadySchema.parse({
                  event: "planner_ready", nonce: startup.planner.nonce, pid: process.pid,
                  port: startup.server.port, runtime: startup.planner.runtime,
                }),
              },
            });
          } else {
            const inputs = await loadMachineApiInputs(process.cwd(), startup.state_root);
            application = createApiApp({ identity, create: () => createMachineApp(inputs) });
          }
          signal.throwIfAborted();
          const server = await serveApiApp(startup.server, application);
          origin = apiOrigin({ hostname: startup.server.hostname, port: server.port! });
          return { server, ready: { ...identity, port: server.port } };
        },
      };
    });
  } finally {
    await Promise.all(pending);
    process.off("message", receive);
    process.disconnect?.();
  }
}

if (import.meta.main) await runNativeOwner();
