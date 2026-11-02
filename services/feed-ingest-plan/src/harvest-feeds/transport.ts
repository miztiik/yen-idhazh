/** Which source request and response facts cross the harvest boundary? */
import type { FeedIngestConfig, HttpResponseEvidence } from "@idhazh/common-contracts";

export const HTTP_REDIRECT_STATUSES: ReadonlySet<number> = new Set([301, 302, 303, 307, 308]);

export class BodyLimitError extends Error {
  constructor(
    readonly http_status: number,
    readonly configured_limit_bytes: number,
    readonly observed_at_least_bytes: number,
    readonly response_evidence: HttpResponseEvidence,
    readonly limit_stage: "decoded-stream" | "completed-response" | "parser-input" = "decoded-stream",
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
  final_url?: string;
};
export class ChallengeUnresolvedError extends ResponseReadError {}
export class BrowserNetworkError extends Error {
  constructor(message: string, readonly code: string | null = null) { super(message); }
}
export class BrowserRequestInterruptedError extends BrowserNetworkError {}
export type BodyLimitEvidence = Pick<BodyLimitError, "configured_limit_bytes" | "observed_at_least_bytes" | "limit_stage">;
export function readBodyLimitEvidence(error: unknown): BodyLimitEvidence | undefined {
  const readCause = error instanceof ResponseReadError ? error.cause : error;
  const primary = readCause instanceof AggregateError ? readCause.cause : readCause;
  if (!(primary instanceof BodyLimitError)) return undefined;
  return {
    configured_limit_bytes: primary.configured_limit_bytes,
    observed_at_least_bytes: primary.observed_at_least_bytes,
    limit_stage: primary.limit_stage,
  };
}
export type TransportRequest = {
  url: URL;
  profile: { browser: "firefox" | "chrome" | "chromium"; headers: FeedIngestConfig["harvest"]["request_headers"] };
  diagnostics: FeedIngestConfig["harvest"]["response_diagnostics"];
  max_body_bytes: number;
  timeout_ms: number;
  signal: AbortSignal;
  kind?: "robots" | "feed" | "article";
  gate?: (
    url: string, role: "document" | "resource",
    dispatch: (signal: AbortSignal) => Promise<TransportResponse>,
  ) => Promise<TransportResponse>;
};
export interface HarvestTransport {
  readonly browser_managed?: boolean;
  request(input: TransportRequest): Promise<TransportResponse>;
  close?(): Promise<void>;
}
