/** Read one source response with native fingerprints, manual redirects and decoded limits. */
import { Impit } from "impit";
import { HttpResponseEvidenceSchema } from "@idhazh/common-contracts";
import type { HttpResponseEvidence } from "@idhazh/common-contracts";
import { BodyLimitError, ResponseReadError } from "./transport";
import type { HarvestTransport, TransportRequest } from "./transport";

export function responseEvidence(
  headers: Headers, input: TransportRequest, decoded_bytes: number | null,
): HttpResponseEvidence {
  const selected_headers: Record<string, string> = {};
  const headers_truncated: string[] = [];
  const { header_names, max_header_value_chars } = input.diagnostics;
  const clean = (value: string) => value.replace(/[^\x20-\x7e]/g, " ").slice(0, max_header_value_chars);
  for (const name of header_names) {
    const value = headers.get(name);
    if (value === null) continue;
    selected_headers[name] = clean(value);
    if (value.length > max_header_value_chars) headers_truncated.push(name);
  }
  const length = headers.get("content-length");
  const declared = length !== null && /^\d+$/.test(length) ? Number(length) : null;
  const contentType = headers.get("content-type");
  return HttpResponseEvidenceSchema.parse({
    content_type: contentType === null ? null : clean(contentType), decoded_bytes,
    declared_content_length: declared !== null && Number.isSafeInteger(declared) ? declared : null,
    selected_headers, headers_truncated, request_profile: input.profile.browser,
  });
}

export function createImpitTransport(): HarvestTransport {
  const clients = new Map<string, Impit>();
  return {
    async request(input) {
      input.signal.throwIfAborted();
      const key = JSON.stringify(input.profile);
      let client = clients.get(key);
      if (client === undefined) {
        client = new Impit({ browser: input.profile.browser, headers: input.profile.headers, followRedirects: false });
        clients.set(key, client);
      }
      const controller = new AbortController();
      const abort = () => controller.abort(input.signal.reason);
      try {
        const response = await client.fetch(input.url, {
          signal: controller.signal, redirect: "manual", timeout: input.timeout_ms,
        });
        let evidence = responseEvidence(response.headers, input, null);
        const reader = response.body.getReader();
        const chunks: Uint8Array[] = [];
        let bytes = 0;
        try {
          if (input.signal.aborted) {
            try { await reader.cancel(); }
            catch (cleanup) {
              throw new AggregateError([input.signal.reason, cleanup], "Cancellation cleanup failed", { cause: input.signal.reason });
            }
            input.signal.throwIfAborted();
          }
          input.signal.addEventListener("abort", abort, { once: true });
          if (input.signal.aborted) abort();
          for (;;) {
            input.signal.throwIfAborted();
            const chunk = await reader.read();
            if (chunk.done) break;
            bytes += chunk.value.byteLength;
            evidence = { ...evidence, decoded_bytes: bytes };
            if (bytes > input.max_body_bytes) {
              const limit = new BodyLimitError(response.status, input.max_body_bytes, bytes, evidence);
              try { await reader.cancel(); }
              catch (cleanup) { throw new AggregateError([limit, cleanup], "Body limit cleanup failed", { cause: limit }); }
              throw limit;
            }
            chunks.push(chunk.value);
          }
          evidence = { ...evidence, decoded_bytes: bytes };
          return { status: response.status, body: Buffer.concat(chunks, bytes).toString("utf8"),
            location: response.headers.get("location"), evidence };
        } catch (error) {
          throw new ResponseReadError(response.status, evidence, error);
        } finally {
          input.signal.removeEventListener("abort", abort);
          reader.releaseLock();
        }
      } finally { controller.abort(); }
    },
  };
}
