/** Which explicit API group and private controls belong to one owned child? */
import { z } from "zod";
import { PlannerStartupFailureSchema, PlannerStartupSchema } from "@idhazh/feed-ingest-plan/startup";
import { SafePersistHttpStartupSchema } from "@idhazh/feed-ingest-plan/delivery-contracts";
import { HonoServerSettingsSchema } from "./load-settings";
import { ApiGroupSchema, ServerRunSchema } from "./server-evidence";

const PrivatePathSchema = z.string().min(1).refine(
  value => !value.startsWith("/") && !value.includes("\\") && !value.includes(":"),
  "Private output must be relative to the checkout with POSIX separators",
);
const common = {
  server: HonoServerSettingsSchema,
  run: ServerRunSchema,
  directory: PrivatePathSchema,
};
export const ApiStartupSchema = z.discriminatedUnion("group", [
  z.strictObject({ ...common, group: z.literal("planning"), planner: PlannerStartupSchema }),
  z.strictObject({ ...common, group: z.literal("delivery"), delivery: SafePersistHttpStartupSchema }),
  z.strictObject({
    ...common, group: z.literal("machine"), nonce: z.uuid(), state_root: PrivatePathSchema,
    supervision: PlannerStartupSchema.shape.settings.shape.supervision,
  }),
]);
export type ApiStartup = z.infer<typeof ApiStartupSchema>;
export const ApiStartupFailureSchema = PlannerStartupFailureSchema.extend({
  event: z.literal("typescript_api_startup_failed"),
});
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

export function startupNonce(startup: ApiStartup): string {
  return startup.group === "planning" ? startup.planner.nonce
    : startup.group === "delivery" ? startup.delivery.nonce : startup.nonce;
}
export function enabledModules(group: ApiStartup["group"]): ApiReady["modules"] {
  return group === "planning" ? ["planning", "machine"] : [group];
}
export function startupSupervision(startup: ApiStartup) {
  return startup.group === "planning" ? startup.planner.settings.supervision
    : startup.group === "delivery" ? startup.delivery.settings.supervision : startup.supervision;
}

// This fixed route identifies the shared listener, not any one module's health.
export const API_HEALTH_PATH = "/health";
