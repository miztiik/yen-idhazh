/** Can one JSON command be read without exceeding its configured byte bound? */
import type { OperationMetadata } from "@idhazh/common-contracts";
import { createProbeFailureEvent } from "./create-probe-event";
import type { ProbeEventOutput } from "./create-probe-event";

export type ProbeRequestDiagnostics = { context: OperationMetadata; writeEvent: ProbeEventOutput };

export class CommandBodyError extends Error {
  constructor(readonly status: 400 | 413, message: string) { super(message); }
}

export async function readCommandBody(
  request: Request, maxBytes: number, diagnostics: ProbeRequestDiagnostics, timeoutMs?: number,
): Promise<unknown> {
  if (request.signal.aborted) throw new CommandBodyError(400, "Host probe request aborted");
  if (request.headers.has("Origin")) throw new CommandBodyError(400, "Host probe commands accept operator requests, not browser origins");
  if (request.headers.get("Content-Type")?.split(";", 1)[0]?.trim().toLowerCase() !== "application/json") {
    throw new CommandBodyError(400, "Content-Type must be application/json");
  }
  const length = request.headers.get("Content-Length");
  if (length !== null && /^\d+$/.test(length) && Number(length) > maxBytes) {
    await request.body?.cancel();
    throw new CommandBodyError(413, "Request body exceeds max_request_body_bytes");
  }
  if (request.body === null) throw new CommandBodyError(400, "JSON request body is required");
  const reader = request.body.getReader();
  let expired = false;
  const timeout = timeoutMs === undefined ? undefined : setTimeout(() => {
    expired = true;
    void reader.cancel().catch(() => {
      diagnostics.writeEvent(createProbeFailureEvent({ context: diagnostics.context, type: "host_probe_body_cleanup_failed" }));
    });
  }, timeoutMs);
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const part = await reader.read();
      if (expired) throw new CommandBodyError(400, "Request body exceeded the configured cache lifecycle timeout");
      if (part.done) break;
      size += part.value.byteLength;
      if (size > maxBytes) {
        await reader.cancel();
        throw new CommandBodyError(413, "Request body exceeds max_request_body_bytes");
      }
      chunks.push(part.value);
    }
  } catch (error) {
    if (request.signal.aborted) throw new CommandBodyError(400, "Host probe request aborted");
    throw error;
  } finally { clearTimeout(timeout); reader.releaseLock(); }
  let text: string;
  try { text = new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks)); }
  catch (error) {
    if (!(error instanceof TypeError)) throw error;
    throw new CommandBodyError(400, "Request body must be UTF-8 JSON");
  }
  return JSON.parse(text);
}
