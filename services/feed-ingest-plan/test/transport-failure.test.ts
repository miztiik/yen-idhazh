/** Preserve measured cutoff facts when a later cancellation or cleanup also fails. */
import { expect, test } from "bun:test";
import { BodyLimitError, ResponseReadError, readBodyLimitEvidence } from "../src/harvest-feeds/transport";
import { classifyTransportFailure, readTransportErrorCode } from "../src/harvest-feeds/classify-transport-failure";
import { HttpResponseEvidenceSchema } from "@idhazh/common-contracts";
import { ConnectError, ConnectTimeout } from "impit";

test("a proven cutoff wins over later cancellation and retains combined cleanup evidence", () => {
  const evidence = HttpResponseEvidenceSchema.parse({
    content_type: "text/html", decoded_bytes: 101, declared_content_length: null,
    selected_headers: {}, headers_truncated: [], request_profile: "firefox",
  });
  const primary = new BodyLimitError(403, 100, 101, evidence);
  const cleanup = Object.assign(new Error("OS cleanup failure"), { code: "ECANCELED" });
  const combined = new AggregateError([primary, cleanup], "Body limit cleanup failed", { cause: primary });
  const wrapped = new ResponseReadError(403, evidence, combined);
  for (const error of [primary, combined, new ResponseReadError(403, evidence, primary), wrapped]) {
    expect(classifyTransportFailure(error, AbortSignal.abort())).toBe("body-too-large");
    expect(readBodyLimitEvidence(error)).toEqual({ configured_limit_bytes: 100, observed_at_least_bytes: 101 });
  }
  expect(wrapped.cause).toBe(combined);
  expect(combined.errors).toEqual([primary, cleanup]);
  expect(readTransportErrorCode(wrapped)).toBe("ECANCELED");
});

test("native exception types classify failures without inventing message-derived DNS detail", () => {
  const signal = new AbortController().signal;
  const network = new ConnectError("DNS detail ENOTFOUND in a message is not an available code");
  expect(classifyTransportFailure(network, signal)).toBe("network");
  expect(readTransportErrorCode(network)).toBeNull();
  expect(classifyTransportFailure(new ConnectTimeout("native connect timeout"), signal)).toBe("timeout");
  expect(readBodyLimitEvidence(network)).toBeUndefined();
  const unknown = new Error("unrecognized local failure");
  expect(() => classifyTransportFailure(unknown, signal)).toThrow(unknown);
});

test("response disposal keeps native timeout and its separate cleanup failure", () => {
  const evidence = HttpResponseEvidenceSchema.parse({
    content_type: "text/html", decoded_bytes: 0, declared_content_length: null,
    selected_headers: {}, headers_truncated: [], request_profile: "firefox",
  });
  const primary = new ConnectTimeout("native timeout");
  const cleanup = Object.assign(new Error("OS cleanup failure"), { code: "ECANCELED" });
  const combined = new AggregateError([primary, cleanup], "Response cleanup failed", { cause: primary });
  const wrapped = new ResponseReadError(403, evidence, combined);
  expect(classifyTransportFailure(wrapped, new AbortController().signal)).toBe("timeout");
  expect(readTransportErrorCode(wrapped)).toBe("ECANCELED");
  expect(combined.errors).toEqual([primary, cleanup]);
});
