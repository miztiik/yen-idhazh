/** Read one validated target with pinned DNS, manual redirects and a bounded body. */
import type { LookupFunction } from "node:net";
// The package request API avoids Bun's incomplete fetch implementation.
import { Agent, interceptors, request } from "undici/index.js";
import type { Readable } from "node:stream";
import type { ResolvedAddress } from "./safe-target";

export class BodyLimitError extends Error {
  constructor(readonly http_status: number) { super("response exceeds extract.max_body_bytes"); }
}
export class ResponseReadError extends Error {
  constructor(readonly http_status: number, cause: unknown) {
    super("response body could not be read", { cause });
  }
}
export type TransportResponse = {
  status: number;
  body: string;
  location: string | null;
};
export type TransportRequest = {
  url: URL;
  addresses: readonly ResolvedAddress[];
  user_agent: string;
  max_body_bytes: number;
  signal: AbortSignal;
};
export interface HarvestTransport {
  request(input: TransportRequest): Promise<TransportResponse>;
}

export function createPinnedDispatcher(addresses: readonly ResolvedAddress[]) {
  const first = addresses[0];
  if (!first) throw new Error("validated target has no address");
  // DNS is not consulted a second time: every possible socket address was validated.
  const lookup: LookupFunction = (_hostname, options, callback) => {
    if (options.all) callback(null, [...addresses]);
    else callback(null, first.address, first.family);
  };
  return new Agent({ connect: { lookup } });
}

export async function readResponseBody(body: Readable, status: number, limit: number): Promise<string> {
  const chunks: Uint8Array[] = [];
  let bytes = 0;
  for await (const value of body) {
    const chunk = Buffer.isBuffer(value) ? value : Buffer.from(value);
    bytes += chunk.byteLength;
    if (bytes > limit) throw new BodyLimitError(status);
    chunks.push(chunk);
  }
  return Buffer.concat(chunks, bytes).toString("utf8");
}

export const networkTransport: HarvestTransport = {
  async request({ url, addresses, user_agent, max_body_bytes, signal }) {
    const dispatcher = createPinnedDispatcher(addresses);
    try {
      const response = await request(url, {
        dispatcher: dispatcher.compose(interceptors.decompress({ skipErrorResponses: false })),
        signal,
        headers: { "user-agent": user_agent },
      });
      const location = response.headers.location;
      if (Array.isArray(location)) throw new Error("response has multiple redirect locations");
      let body: string;
      try { body = await readResponseBody(response.body, response.statusCode, max_body_bytes); }
      catch (error) { throw new ResponseReadError(response.statusCode, error); }
      return {
        status: response.statusCode,
        body,
        location: location ?? null,
      };
    } finally {
      // A per-request dispatcher has no shared work to drain on refusal or abort.
      await dispatcher.destroy();
    }
  },
};
