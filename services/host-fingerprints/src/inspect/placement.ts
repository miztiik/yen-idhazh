/** What placement did the host metadata endpoint report within the read deadline? */
import { z } from "zod";
import type { ServiceConfig } from "../config";
import { unavailable } from "./bounded-input";
import type { Inspection } from "./bounded-input";

const PlacementSchema = z.object({
  vmSize: z.string().nullish(), location: z.string().nullish(),
  zone: z.string().nullish(), platformFaultDomain: z.union([z.string(), z.number().finite()]).nullish(),
});
export function parsePlacement(input: unknown) {
  const parsed = PlacementSchema.safeParse(input);
  if (!parsed.success) return null;
  return {
    vm_size: parsed.data.vmSize || null, vm_location: parsed.data.location || null,
    vm_zone: parsed.data.zone || null,
    vm_fault_domain: parsed.data.platformFaultDomain === undefined || parsed.data.platformFaultDomain === null ?
      null : String(parsed.data.platformFaultDomain),
  };
}
export async function collectPlacement(config: ServiceConfig, context: Inspection) {
  let input = context.metadata;
  if (input === undefined) {
    if (config.metadata_url === null) return unavailable(context, "placement", "configured_off");
    try {
      const response = await fetch(config.metadata_url, {
        headers: { Metadata: "true" }, redirect: "error",
        signal: AbortSignal.timeout(config.metadata_timeout_ms),
      });
      if (!response.ok || !response.body) {
        unavailable(context, "placement", `metadata_http_${response.status}`);
        await response.body?.cancel();
        return null;
      }
      const reader = response.body.getReader();
      const chunks: Uint8Array[] = [];
      let length = 0;
      try {
        while (true) {
          const next = await reader.read();
          if (next.done) break;
          length += next.value.length;
          if (length > config.max_input_bytes) {
            unavailable(context, "placement", "metadata_too_large");
            await reader.cancel();
            return null;
          }
          chunks.push(next.value);
        }
      } finally {
        reader.releaseLock();
      }
      input = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    } catch (error) {
      if (!(error instanceof TypeError || error instanceof SyntaxError ||
          error instanceof DOMException || (error instanceof Error && "code" in error))) throw error;
      unavailable(context, "placement", "metadata_unavailable");
      return null;
    }
  }
  const placement = parsePlacement(input);
  if (!placement) unavailable(context, "placement", "metadata_invalid");
  return placement;
}
