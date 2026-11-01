/** Verify safe header configuration and unavailable native response readings. */
import { expect, test } from "bun:test";
import { HttpResponseEvidenceSchema, ResponseDiagnosticsConfigSchema } from "../src";

test("response evidence distinguishes missing readings from measured zero", () => {
  const evidence = { content_type: null, decoded_bytes: null, declared_content_length: null,
    selected_headers: {}, headers_truncated: [], request_profile: "firefox" };
  expect(HttpResponseEvidenceSchema.parse(evidence).decoded_bytes).toBeNull();
  expect(HttpResponseEvidenceSchema.parse({ ...evidence, decoded_bytes: 0 }).decoded_bytes).toBe(0);
  for (const patch of [
    { decoded_bytes: -1 }, { decoded_bytes: 1.5 }, { declared_content_length: -1 },
    { selected_headers: { "set-cookie": "private" } }, { headers_truncated: ["content-type"] },
    { transport: "impit" }, { body: "private" }, { request_profile: "unsupported" },
  ]) expect(HttpResponseEvidenceSchema.safeParse({ ...evidence, ...patch }).success).toBe(false);
});

test("diagnostic settings reject credentials, unsafe names and repeated headers", () => {
  const settings = { header_names: ["content-type", "content-length", "retry-after"], max_header_value_chars: 256 };
  expect(ResponseDiagnosticsConfigSchema.parse(settings)).toEqual(settings);
  for (const name of ["authorization", "cookie", "set-cookie", "x-api-key", "x-token", "location", "Content-Type"]) {
    expect(ResponseDiagnosticsConfigSchema.safeParse({ ...settings, header_names: [name] }).success).toBe(false);
  }
  expect(ResponseDiagnosticsConfigSchema.safeParse({ ...settings, header_names: ["retry-after", "retry-after"] }).success).toBe(false);
  expect(ResponseDiagnosticsConfigSchema.safeParse({ ...settings, max_header_value_chars: 0 }).success).toBe(false);
});
