/** Which private controls start a machine-only child without any feed configuration? */
import { z } from "zod";
import { ApiHostStartupSchema, ApiReadySchema, enabledModules, PrivatePathSchema } from "@idhazh/serve-pipeline-apis/startup";

export const MachineApiStartupSchema = z.strictObject({
  ...ApiHostStartupSchema.shape,
  group: z.literal("machine"), nonce: z.uuid(), state_root: PrivatePathSchema,
  registry_path: PrivatePathSchema.optional(),
}).meta({
  version: "2026-11-07",
  readCompatibility: "current_only; omitted registry uses the existing named committed registry",
  changelog: [{ version: "2026-11-07", change: "Capture the caller's selected registry without feed configuration." }],
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
