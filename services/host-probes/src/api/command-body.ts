/** Can one JSON command be read without exceeding its configured byte bound? */
export class CommandBodyError extends Error {
  constructor(readonly status: 400 | 413, message: string) { super(message); }
}

export async function readCommandBody(request: Request, maxBytes: number): Promise<unknown> {
  if (request.signal.aborted) throw new CommandBodyError(400, "Task profile request aborted");
  if (request.headers.has("Origin")) throw new CommandBodyError(400, "Task profiles accept operator requests, not browser origins");
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
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const part = await reader.read();
      if (part.done) break;
      size += part.value.byteLength;
      if (size > maxBytes) {
        await reader.cancel();
        throw new CommandBodyError(413, "Request body exceeds max_request_body_bytes");
      }
      chunks.push(part.value);
    }
  } catch (error) {
    if (request.signal.aborted) throw new CommandBodyError(400, "Task profile request aborted");
    throw error;
  } finally { reader.releaseLock(); }
  let text: string;
  try { text = new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks)); }
  catch (error) {
    if (!(error instanceof TypeError)) throw error;
    throw new CommandBodyError(400, "Request body must be UTF-8 JSON");
  }
  return JSON.parse(text);
}
