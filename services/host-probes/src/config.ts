/** Which validated controls govern one host sampling service? */
import { z } from "zod";
import { constants as bufferConstants } from "node:buffer";

// Bun timers use a signed 32-bit millisecond delay; larger values overflow.
const MAX_TIMER_DELAY_MS = 2 ** 31 - 1;

export const ProbeConfigSchema = z.object({
  sample_interval_ms: z.number().int().positive().max(MAX_TIMER_DELAY_MS),
  listen_host: z.string().trim().min(1),
  listen_port: z.number().int().min(1).max(65535),
  max_proc_bytes: z.number().int().positive().max(bufferConstants.MAX_LENGTH - 1),
}).strict();

export type ProbeConfig = z.infer<typeof ProbeConfigSchema>;

export async function loadConfig(
  path: string | URL = new URL("../../../config/host-probes.json", import.meta.url),
): Promise<ProbeConfig> {
  let input: unknown;
  try {
    input = await Bun.file(path).json();
  } catch (error) {
    throw new Error("Cannot read config/host-probes.json as JSON", { cause: error });
  }
  return ProbeConfigSchema.parse(input);
}
