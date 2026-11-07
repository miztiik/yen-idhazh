/** Which common private controls and readiness identity belong to one owned listener? */
import { z } from "zod";
import { HonoServerSettingsSchema } from "./load-settings";
import { ApiGroupSchema, ServerRunSchema } from "./server-evidence";

export const PrivatePathSchema = z.string().min(1).refine(
  value => !value.startsWith("/") && !value.includes("\\") && !value.includes(":"),
  "Private output must be relative to the checkout with POSIX separators",
);
export const ApiHostStartupSchema = z.object({
  server: HonoServerSettingsSchema,
  run: ServerRunSchema,
  directory: PrivatePathSchema,
});
export type ApiHostStartup = z.infer<typeof ApiHostStartupSchema>;
export const ApiReadySchema = z.strictObject({
  event: z.literal("typescript_api_ready"),
  nonce: z.uuid(),
  pid: z.int().positive(),
  port: z.int().positive().max(65535),
  group: ApiGroupSchema,
  modules: z.array(z.enum(["planning", "machine", "delivery"])).min(1),
  enabled: z.boolean(),
});
export type ApiReady = z.infer<typeof ApiReadySchema>;

export function enabledModules(group: ApiReady["group"]): ApiReady["modules"] {
  return group === "planning" ? ["planning", "machine"] : [group];
}

// This fixed route identifies the shared listener, not any one module's health.
export const API_HEALTH_PATH = "/api/2026-11-05/get-api-health";
