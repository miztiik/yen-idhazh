/** Which bounded operator request may run the separately controlled cache latency curve? */
import { z } from "zod";
import type { CacheProbeController } from "../cache-probe/cache-controller";
import { readCommandBody } from "./command-body";

const CacheLatencyRequestSchema = z.strictObject({});
export async function postCacheLatency(
  request: Request, controller: CacheProbeController, maxBytes: number, bodyTimeoutMs: number,
): Promise<Response> {
  CacheLatencyRequestSchema.parse(await readCommandBody(request, maxBytes, bodyTimeoutMs));
  return Response.json(await controller.measureLatency(request.signal), { headers: { "Cache-Control": "no-store" } });
}
