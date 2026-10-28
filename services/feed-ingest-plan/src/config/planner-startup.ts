/** Which private, transient controls can cross into a workflow's planner child? */
import { z } from "zod";
import { CommitShaSchema, PositiveCountSchema } from "@idhazh/common-contracts";
import { ServiceSettingsSchema } from "./service-settings";

// This pipe protocol is not a saved artifact or an HTTP input.
export const PlannerStartupSchema = z.strictObject({
  nonce: z.uuid(),
  settings: ServiceSettingsSchema.refine(value =>
    ["127.0.0.1", "::1"].includes(value.listener.hostname), "Workflow listener must bind loopback"),
  output_root: z.string().min(1).refine(value =>
    !value.startsWith("/") && !value.includes("\\") && !value.includes(":"),
  "Output root must be relative to the child checkout with POSIX separators"),
  runtime: z.strictObject({
    git_sha: CommitShaSchema, run_number: z.string().regex(/^[0-9]+$/),
    correlation_id: z.uuid(), attempt: PositiveCountSchema,
    captured_at: z.iso.datetime(),
  }),
});
export type PlannerStartup = z.infer<typeof PlannerStartupSchema>;
export const PlannerReadySchema = z.strictObject({
  event: z.literal("planner_ready"), nonce: z.uuid(), pid: PositiveCountSchema,
  port: PositiveCountSchema.max(65535), runtime: PlannerStartupSchema.shape.runtime,
});
export type PlannerReady = z.infer<typeof PlannerReadySchema>;
export const PlannerStartupFailureSchema = z.strictObject({
  event: z.literal("planner_startup_failed"), code: z.string().min(1), message: z.string().min(1),
});
