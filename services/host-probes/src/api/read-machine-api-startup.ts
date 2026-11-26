/** Which private controls start a machine-only child without any feed configuration? */
import { z } from "zod";
import { ApiHostStartupSchema, ApiReadySchema, enabledModules, PrivatePathSchema } from "@idhazh/serve-pipeline-apis/startup";
import { TaskPerformanceExecutionSchema } from "../config";

export const MachineApiStartupSchema = z.strictObject({
  ...ApiHostStartupSchema.shape,
  group: z.literal("machine"), nonce: z.uuid(), state_root: PrivatePathSchema,
  registry_path: PrivatePathSchema.optional(),
  task_performance: TaskPerformanceExecutionSchema.optional(),
  task_profile_memory_enabled: z.boolean().optional(),
}).refine(value => value.task_profile_memory_enabled === undefined || value.task_performance !== undefined, {
  path: ["task_profile_memory_enabled"], message: "A memory selection requires a task recording execution",
}).meta({
  version: "2026-11-26",
  readCompatibility: "An omitted registry uses the committed registry; omitted task execution leaves legacy probes unchanged.",
  changelog: [
    { version: "2026-11-26", change: "Admit a recording execution, accounting days and the job's memory selection." },
    { version: "2026-11-07", change: "Capture the caller's selected registry without feed configuration." },
  ],
});
export type MachineApiStartup = z.infer<typeof MachineApiStartupSchema>;
export const MachineApiStartupFailureSchema = z.strictObject({
  event: z.literal("typescript_api_startup_failed"),
  code: z.string().regex(/^[A-Z][A-Z0-9_]*$/), message: z.string().min(1),
  failure: z.null().default(null),
});

export function readMachineApiIdentity(startup: MachineApiStartup, pid: number) {
  return ApiReadySchema.parse({
    event: "typescript_api_ready", nonce: startup.nonce, pid, port: startup.server.port,
    group: startup.group, modules: enabledModules(startup.group), enabled: true,
  });
}
