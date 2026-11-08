/** Which native module and process does one owned listener actually serve? */
import { z } from "zod";

export const ApiGroupSchema = z.enum(["planning", "machine", "delivery"]);
export type ApiGroup = z.infer<typeof ApiGroupSchema>;
export const ApiReadySchema = z.strictObject({
  event: z.literal("typescript_api_ready"),
  nonce: z.uuid(),
  pid: z.int().positive(),
  port: z.int().positive().max(65535),
  group: ApiGroupSchema,
  modules: z.array(ApiGroupSchema).length(1),
  enabled: z.boolean(),
}).refine(value => value.modules[0] === value.group, {
  path: ["modules"], message: "Readiness must identify only the selected native module",
}).meta({
  version: "2026-11-07",
  readCompatibility: "current_only; private readiness identifies one native server module",
  changelog: [{ version: "2026-11-07", change: "Identify independently owned native API servers." }],
});
export type ApiReady = z.infer<typeof ApiReadySchema>;
export type ApiReadiness = { origin: string; identity: ApiReady };

export function enabledModules(group: ApiGroup): ApiReady["modules"] {
  return [ApiGroupSchema.parse(group)];
}

// This fixed route identifies the listener, not any native module's health.
export const API_HEALTH_PATH = "/api/2026-11-05/get-api-health";
