/** Which committed listener serves the pipeline APIs? */
import { join } from "node:path";
import { z } from "zod";

export const SupervisionSettingsSchema = z.strictObject({
  readiness_timeout_ms: z.int().positive(),
  shutdown_timeout_ms: z.int().positive(),
  forced_exit_timeout_ms: z.int().positive(),
});
export type SupervisionSettings = z.infer<typeof SupervisionSettingsSchema>;

export const HonoServerSettingsSchema = z.strictObject({
  hostname: z.enum(["127.0.0.1", "::1"]),
  port: z.int().positive().max(65535),
  idle_timeout_seconds: z.int().positive().max(255),
  supervision: SupervisionSettingsSchema,
});
export type HonoServerSettings = z.infer<typeof HonoServerSettingsSchema>;

export async function loadHonoSettings(root: string): Promise<HonoServerSettings> {
  return HonoServerSettingsSchema.parse(await Bun.file(join(root, "config", "hono-server.json")).json());
}

export function apiOrigin(settings: Pick<HonoServerSettings, "hostname" | "port">): string {
  return `http://${settings.hostname === "::1" ? "[::1]" : settings.hostname}:${settings.port}`;
}
