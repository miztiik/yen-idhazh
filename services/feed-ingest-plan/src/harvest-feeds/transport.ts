/** Read one validated target with pinned DNS, manual redirects and a bounded body. */
import type { LookupFunction } from "node:net";
// Bun's bare undici shim has no dispatcher lifecycle or pinned connector.
import { Agent, fetch } from "undici/index.js";
import type { ResolvedAddress } from "./safe-target";

export class BodyLimitError extends Error {
  constructor(readonly http_status: number) { super("response exceeds extract.max_body_bytes"); }
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

export const networkTransport: HarvestTransport = {
  async request({ url, addresses, user_agent, max_body_bytes, signal }) {
    const dispatcher = createPinnedDispatcher(addresses);
    try {
      const response = await fetch(url, {
        dispatcher, redirect: "manual", signal,
        headers: { "user-agent": user_agent },
      });
      const reader = response.body?.getReader();
      const chunks: Uint8Array[] = [];
      let bytes = 0;
      try {
        if (reader) {
          for (;;) {
            const chunk = await reader.read();
            if (chunk.done) break;
            bytes += chunk.value.byteLength;
            if (bytes > max_body_bytes) throw new BodyLimitError(response.status);
            chunks.push(chunk.value);
          }
        }
      } finally {
        await reader?.cancel();
      }
      return {
        status: response.status,
        body: Buffer.concat(chunks, bytes).toString("utf8"),
        location: response.headers.get("location"),
      };
    } finally {
      await dispatcher.close();
    }
  },
};
