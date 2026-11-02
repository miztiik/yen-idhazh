/** Keep only configured, body-free response facts and the actual browser evidence label. */
import { HttpResponseEvidenceSchema } from "@idhazh/common-contracts";
import type { HttpResponseEvidence } from "@idhazh/common-contracts";
import type { TransportRequest } from "./transport";

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
