/** Which request may collect and persist a host fingerprint? */
import { z } from "zod";
import { CaptureContextSchema } from "../../config";
import type { ServiceConfig, SelectedSettings } from "../../config";
import { persistFingerprint } from "../../persist-fingerprint";
import type { PersistenceOptions } from "../../persist-fingerprint";

export async function postFingerprint(request: Request, config: ServiceConfig, settings: SelectedSettings, options: PersistenceOptions): Promise<Response> {
  let input: unknown;
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
          return Response.json({ error: "Request body exceeds max_input_bytes" }, { status: 413 });
        }
        chunks.push(part.value);
      }
    } finally {
      reader.releaseLock();
    }
    input = CaptureContextSchema.parse(JSON.parse(Buffer.concat(chunks).toString("utf8")));
  } catch (error) {
    if (!(error instanceof SyntaxError || error instanceof z.ZodError)) throw error;
    return Response.json({ error: error.message }, { status: 400 });
  }
  return Response.json(await persistFingerprint(input, config, settings, options), {
    headers: { "Cache-Control": "no-store" },
  });
}
