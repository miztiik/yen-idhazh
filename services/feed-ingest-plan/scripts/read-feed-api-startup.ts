/** Which native planning or delivery controls may cross the owned feed child pipe? */
import { z } from "zod";
import { ApiHostStartupSchema, ApiReadySchema, enabledModules } from "@idhazh/serve-pipeline-apis/startup";
import { PlannerStartupFailureSchema, PlannerStartupSchema } from "../src/config/planner-startup";
import { SafePersistHttpStartupSchema } from "./feed-ingest-plan-delivery-result";

export const FeedApiStartupSchema = z.discriminatedUnion("group", [
  z.strictObject({ ...ApiHostStartupSchema.shape, group: z.literal("planning"), planner: PlannerStartupSchema }),
  z.strictObject({ ...ApiHostStartupSchema.shape, group: z.literal("delivery"), delivery: SafePersistHttpStartupSchema }),
]);
export type FeedApiStartup = z.infer<typeof FeedApiStartupSchema>;
export const FeedApiStartupFailureSchema = PlannerStartupFailureSchema.extend({
  event: z.literal("typescript_api_startup_failed"),
});
export function readFeedApiIdentity(startup: FeedApiStartup, pid: number) {
  return ApiReadySchema.parse({
    event: "typescript_api_ready",
    nonce: startup.group === "planning" ? startup.planner.nonce : startup.delivery.nonce,
    pid, port: startup.server.port, group: startup.group, modules: enabledModules(startup.group),
    enabled: startup.group !== "planning" || startup.planner.settings.enabled,
  });
}
