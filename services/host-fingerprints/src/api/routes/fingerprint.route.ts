/** Which request may collect and persist a host fingerprint? */
import { z } from "zod";
import { createChildContext, createRootContext, readTraceContext } from "@idhazh/common-contracts";
import { FingerprintRequestSchema } from "../../config";
import type { ServiceConfig, SelectedSettings } from "../../config";
import { persistFingerprint } from "../../persist-fingerprint";
import type { PersistenceOptions } from "../../persist-fingerprint";
import { FingerprintResponseSchema } from "../fingerprint-response";
import { createFingerprintCompletionEvent, createFingerprintFailureEvent } from "../create-fingerprint-event";
import type { FingerprintEventOutput } from "../create-fingerprint-event";

class FingerprintBodyLimitError extends Error {}

export async function postFingerprint(
  request: Request, config: ServiceConfig, settings: SelectedSettings, options: PersistenceOptions,
  writeEvent: FingerprintEventOutput,
): Promise<Response> {
  const parent = readTraceContext({
    traceparent: request.headers.get("traceparent") ?? undefined,
    tracestate: request.headers.get("tracestate") ?? undefined,
  });
  const context = parent === undefined ? createRootContext() : createChildContext(parent);
  let input: z.infer<typeof FingerprintRequestSchema>;
  try {
    const chunks: Uint8Array[] = [];
    let size = 0;
    if (!request.body) throw new SyntaxError("request body is required");
    const reader = request.body.getReader();
    try {
      while (true) {
        const part = await reader.read();
        if (part.done) break;
        size += part.value.length;
        if (size > config.max_input_bytes) {
          await reader.cancel();
          throw new FingerprintBodyLimitError("Request body exceeds max_input_bytes");
        }
        chunks.push(part.value);
      }
    } finally {
      reader.releaseLock();
    }
    input = FingerprintRequestSchema.parse(JSON.parse(Buffer.concat(chunks).toString("utf8")));
  } catch (error) {
    writeEvent(createFingerprintFailureEvent({ context }));
    if (error instanceof FingerprintBodyLimitError) return Response.json({ error: error.message }, { status: 413 });
    if (!(error instanceof SyntaxError || error instanceof z.ZodError)) throw error;
    return Response.json({ error: error.message }, { status: 400 });
  }
  let result: z.infer<typeof FingerprintResponseSchema>;
  try { result = FingerprintResponseSchema.parse(await persistFingerprint(input, config, settings, options)); }
  catch (error) {
    writeEvent(createFingerprintFailureEvent({ context }));
    throw error;
  }
  writeEvent(createFingerprintCompletionEvent({ context, status: result.status }));
  return Response.json(result, {
    headers: { "Cache-Control": "no-store" },
  });
}
