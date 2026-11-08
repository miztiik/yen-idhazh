/** Which common private controls and readiness identity belong to one owned listener? */
import { z } from "zod";
import { HonoServerSettingsSchema } from "./load-settings";
import { ServerRunSchema } from "./server-evidence";
export { API_HEALTH_PATH, ApiReadySchema, enabledModules } from "./declare-api-identity";
export type { ApiReady, ApiReadiness } from "./declare-api-identity";

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
