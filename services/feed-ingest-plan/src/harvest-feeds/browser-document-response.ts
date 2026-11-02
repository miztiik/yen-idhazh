/** Admit completed HTTP bodies and rendered parser input without replacing failed responses. */
import { BodyLimitError } from "./transport";
import type { TransportRequest, TransportResponse } from "./transport";
import { responseEvidence } from "./source-response-evidence";

export function completedBrowserResponse(
  input: TransportRequest, status: number, headers: Headers, body: Buffer, url: string,
): TransportResponse {
  const evidence = responseEvidence(headers, input, body.byteLength);
  if (body.byteLength > input.max_body_bytes) {
    throw new BodyLimitError(status, input.max_body_bytes, body.byteLength, evidence, "completed-response");
  }
  return { status, body: body.toString("utf8"), location: headers.get("location"), evidence, final_url: url };
}

export function admitParserInput(input: TransportRequest, response: TransportResponse, body: string): TransportResponse {
  const bytes = Buffer.byteLength(body, "utf8");
  if (bytes > input.max_body_bytes) {
    throw new BodyLimitError(response.status, input.max_body_bytes, bytes, response.evidence, "parser-input");
  }
  return { ...response, body };
}

export function inlineDocumentHeaders(
  headers: { name: string; value: string }[], kind: TransportRequest["kind"], role: "document" | "resource",
): { name: string; value: string }[] | undefined {
  if (kind === "article" || role !== "document") return undefined;
  const type = headers.find(header => header.name.toLowerCase() === "content-type")?.value ?? "";
  if (/text\/html|application\/xhtml\+xml/i.test(type)) return undefined;
  return [
    ...headers.filter(header => !["content-type", "content-disposition"].includes(header.name.toLowerCase())),
    { name: "content-type", value: "text/plain; charset=utf-8" },
  ];
}
