/** Which native source request and response facts cross the harvest boundary? */
import type { FeedIngestConfig, HttpResponseEvidence } from "@idhazh/common-contracts";

export class BodyLimitError extends Error {
  constructor(
    readonly http_status: number,
    readonly configured_limit_bytes: number,
    readonly observed_at_least_bytes: number,
    readonly response_evidence: HttpResponseEvidence,
  ) { super("response exceeds extract.max_body_bytes"); }
}
export class ResponseReadError extends Error {
  constructor(readonly http_status: number, readonly response_evidence: HttpResponseEvidence, cause: unknown) {
    super("response body could not be read", { cause });
  }
}
export type TransportResponse = {
  status: number;
  body: string;
  location: string | null;
  evidence: HttpResponseEvidence;
};
export type BodyLimitEvidence = Pick<BodyLimitError, "configured_limit_bytes" | "observed_at_least_bytes">;
export type TransportRequest = {
  url: URL;
  profile: FeedIngestConfig["harvest"]["request_headers"]["primary"];
  diagnostics: FeedIngestConfig["harvest"]["response_diagnostics"];
  max_body_bytes: number;
  signal: AbortSignal;
};
export interface HarvestTransport {
  request(input: TransportRequest): Promise<TransportResponse>;
}
