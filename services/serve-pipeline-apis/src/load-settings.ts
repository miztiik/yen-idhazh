/** Which committed listener serves the pipeline APIs? */
import { join } from "node:path";
import { z } from "zod";
import { ApiGroupSchema } from "./declare-api-identity";
import type { ApiGroup } from "./declare-api-identity";

export const HONO_SETTINGS_VERSION = "2026-11-07";
export const ListenerAddressSchema = z.strictObject({
  hostname: z.enum(["127.0.0.1", "::1"]),
  port: z.int().positive().max(65535),
});

export const SupervisionSettingsSchema = z.strictObject({
  readiness_timeout_ms: z.int().positive(),
  shutdown_timeout_ms: z.int().positive(),
  forced_exit_timeout_ms: z.int().positive(),
});
export type SupervisionSettings = z.infer<typeof SupervisionSettingsSchema>;

export const HonoServerSettingsSchema = z.strictObject({
  ...ListenerAddressSchema.shape,
  idle_timeout_seconds: z.int().positive().max(255),
  supervision: SupervisionSettingsSchema,
});
export type HonoServerSettings = z.infer<typeof HonoServerSettingsSchema>;

export const HonoServerConfigSchema = z.strictObject({
  version: z.literal(HONO_SETTINGS_VERSION),
  listeners: z.record(ApiGroupSchema, ListenerAddressSchema),
  idle_timeout_seconds: HonoServerSettingsSchema.shape.idle_timeout_seconds,
  supervision: SupervisionSettingsSchema,
}).superRefine((value, context) => {
  const addresses = new Set<string>();
  for (const group of ApiGroupSchema.options) {
    const address = apiOrigin(value.listeners[group]);
    if (addresses.has(address)) context.addIssue({
      code: "custom", path: ["listeners", group, "port"],
      message: "API server groups require distinct listener addresses",
    });
    addresses.add(address);
  }
}).meta({
  version: HONO_SETTINGS_VERSION,
  readCompatibility: "current_only; committed listener maps replace the shared address",
  changelog: [{ version: HONO_SETTINGS_VERSION, change: "Select explicit listeners for independent native API servers." }],
});

export function selectHonoSettings(input: unknown, group: ApiGroup): HonoServerSettings {
  const selected = ApiGroupSchema.parse(group);
  const config = HonoServerConfigSchema.parse(input);
  return HonoServerSettingsSchema.parse({
    ...config.listeners[selected], idle_timeout_seconds: config.idle_timeout_seconds,
    supervision: config.supervision,
  });
}

export async function loadHonoSettings(root: string, group: ApiGroup): Promise<HonoServerSettings> {
  return selectHonoSettings(await Bun.file(join(root, "config", "hono-server.json")).json(), group);
}

export function apiOrigin(settings: Pick<HonoServerSettings, "hostname" | "port">): string {
  return `http://${settings.hostname === "::1" ? "[::1]" : settings.hostname}:${settings.port}`;
}
