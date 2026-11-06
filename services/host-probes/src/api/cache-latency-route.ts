/** Which bounded operator request may run the separately controlled cache latency curve? */
import { z } from "zod";
import type { CacheProbeController } from "../cache-probe/cache-controller";
import { readCommandBody } from "./command-body";
import type { ProbeRequestDiagnostics } from "./command-body";
import { createProbeCompletionEvent } from "./create-probe-event";

const CacheLatencyRequestSchema = z.strictObject({});
export async function postCacheLatency(
  request: Request, controller: CacheProbeController, maxBytes: number, bodyTimeoutMs: number,
  diagnostics: ProbeRequestDiagnostics,
): Promise<Response> {
  CacheLatencyRequestSchema.parse(await readCommandBody(request, maxBytes, diagnostics, bodyTimeoutMs));
  const result = await controller.measureLatency(request.signal);
  diagnostics.writeEvent(createProbeCompletionEvent({
    context: diagnostics.context, operation: "cache-latency", outcome: result.status === "disabled" ? "disabled" : "handled",
  }));
  return Response.json(result, { headers: { "Cache-Control": "no-store" } });
}
