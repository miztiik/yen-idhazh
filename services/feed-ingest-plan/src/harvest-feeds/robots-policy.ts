/** Fetch a target only after this run has established its origin's robots permission. */
import robotsParser from "robots-parser";
import { HarvestDiagnosticsSchema } from "@idhazh/common-contracts";
import type { FeedIngestConfig } from "@idhazh/common-contracts";
import type { FetchFailure } from "./harvest-types";
import type { ExtractionControls } from "./load-harvest-inputs";
import { BodyLimitError, ResponseReadError, networkTransport } from "./transport";
import type { HarvestTransport, TransportResponse } from "./transport";
import { UnsafeTargetError, resolveAddresses, validateTarget } from "./safe-target";
import type { ResolveAddresses } from "./safe-target";

export type FetchResult = {
  body: string | null;
  http_status: number | null;
  failure: FetchFailure | null;
  robots: "allowed" | "denied" | "unknown" | null;
  error_code?: string | null;
  robots_failure?: FetchFailure | null;
  robots_http_status?: number | null;
};
type RawResult = { response: TransportResponse | null; failure: FetchFailure | null; http_status: number | null; error_code?: string | null };
type RobotDocument = ReturnType<typeof robotsParser> | null;
type RobotResult = { document: RobotDocument; failure: FetchFailure | null; http_status: number | null; error_code?: string | null };
export type PermittedFetcher = ReturnType<typeof createPermittedFetcher>;
export const retryableStatus = new Set([408, 425, 429, 500, 502, 503, 504]);
const redirectStatus = new Set([301, 302, 303, 307, 308]);

function decodeUnreserved(value: string): string {
  return value.replace(/%[0-9a-f]{2}/gi, token => {
    const character = String.fromCharCode(parseInt(token.slice(1), 16));
    return /[a-z0-9._~-]/i.test(character) ? character : token.toUpperCase();
  });
}

export function crawlerProduct(userAgent: string): string {
  // The configured planner identifies its product inside the standard compatible wrapper.
  const product = /compatible;\s*([a-z0-9_-]+)/i.exec(userAgent)?.[1]
    ?? /^([a-z0-9_-]+)/i.exec(userAgent)?.[1];
  if (!product || /[\r\n]/.test(userAgent)) throw new Error("harvest.user_agent must name a crawler product");
  return product;
}

export function parseRobots(body: string, origin: string) {
  return robotsParser(`${origin}/robots.txt`, decodeUnreserved(body));
}

export function robotsPermits(document: ReturnType<typeof parseRobots>, url: string, userAgent: string): boolean {
  return document.isAllowed(decodeUnreserved(url), crawlerProduct(userAgent)) === true;
}

function transportFailure(error: unknown, signal: AbortSignal): FetchFailure {
  if (signal.aborted) return "timeout";
  if (error instanceof ResponseReadError) return transportFailure(error.cause, signal);
  if (error instanceof UnsafeTargetError) return "unsafe-target";
  if (error instanceof BodyLimitError) return "body-too-large";
  const cause = error instanceof Error && error.cause instanceof Error ? error.cause : error;
  if (cause && typeof cause === "object" && "code" in cause && typeof cause.code === "string") {
    if (["ENOTFOUND", "EAI_AGAIN", "ENODATA"].includes(cause.code)) return "dns";
    if (["ETIMEDOUT", "UND_ERR_CONNECT_TIMEOUT", "UND_ERR_HEADERS_TIMEOUT", "UND_ERR_BODY_TIMEOUT"].includes(cause.code)) return "timeout";
    if (/^(UND_ERR_|E[A-Z]+|CERT_|DEPTH_|SELF_SIGNED_|UNABLE_TO_)/.test(cause.code)) return "network";
  }
  throw error;
}

function transportErrorCode(error: unknown): string | null {
  const cause = error instanceof Error && error.cause instanceof Error ? error.cause : error;
  // OS, TLS and Undici protocol codes only; exception messages can contain addresses or credentials.
  if (cause && typeof cause === "object" && "code" in cause && typeof cause.code === "string") {
    const parsed = HarvestDiagnosticsSchema.shape.error_code.safeParse(cause.code);
    if (parsed.success) return parsed.data;
  }
  return null;
}

async function pause(milliseconds: number, signal: AbortSignal): Promise<void> {
  signal.throwIfAborted();
  await new Promise<void>((resolve, reject) => {
    const abort = () => { clearTimeout(timer); reject(signal.reason); };
    const timer = setTimeout(() => { signal.removeEventListener("abort", abort); resolve(); }, milliseconds);
    signal.addEventListener("abort", abort, { once: true });
  });
}

export function createPermittedFetcher(
  config: FeedIngestConfig["harvest"], controls: ExtractionControls,
  boundary: { transport?: HarvestTransport; resolve?: ResolveAddresses } = {},
) {
  crawlerProduct(config.user_agent);
  const transport = boundary.transport ?? networkTransport;
  const resolve = boundary.resolve ?? resolveAddresses;
  const documents = new Map<string, Promise<RobotResult>>();

  async function requestOnce(raw: string, signal: AbortSignal): Promise<TransportResponse> {
    const { url, addresses } = await validateTarget(raw, resolve, signal);
    const response = await transport.request({
      url, addresses, signal, user_agent: config.user_agent, max_body_bytes: controls.max_body_bytes,
    });
    if (Buffer.byteLength(response.body, "utf8") > controls.max_body_bytes) throw new BodyLimitError(response.status);
    return response;
  }

  async function read(raw: string, signal: AbortSignal): Promise<RawResult> {
    let result: RawResult = { response: null, failure: "network", http_status: null };
    for (let attempt = 0; attempt <= controls.max_retries; attempt++) {
      try {
        const response = await requestOnce(raw, signal);
        result = { response, failure: null, http_status: response.status };
        if (!retryableStatus.has(response.status)) return result;
      } catch (error) {
        const failure = transportFailure(error, signal);
        result = {
          response: null, failure,
          http_status: error instanceof BodyLimitError || error instanceof ResponseReadError ? error.http_status : result.http_status,
          error_code: transportErrorCode(error),
        };
        if (["timeout", "unsafe-target", "body-too-large"].includes(failure)) return result;
      }
      if (attempt < controls.max_retries) {
        try {
          await pause(controls.backoff_initial_seconds * 1000 * controls.backoff_multiplier ** attempt, signal);
        } catch (error) { return { ...result, response: null, failure: transportFailure(error, signal) }; }
      }
    }
    return result;
  }

  async function readRobots(origin: string, signal: AbortSignal): Promise<RobotResult> {
    let target = `${origin}/robots.txt`;
    let observedStatus: number | null = null;
    const visited = new Set<string>();
    for (;;) {
      if (visited.has(target) || signal.aborted) return {
        document: null, failure: signal.aborted ? "timeout" : "redirect-loop", http_status: observedStatus,
      };
      visited.add(target);
      const result = await read(target, signal);
      const { response } = result;
      if (!response) return { ...result, document: null, http_status: result.http_status ?? observedStatus };
      observedStatus = response.status;
      if (redirectStatus.has(response.status) && response.location) {
        try { target = new URL(response.location, target).href; }
        catch { return { document: null, failure: "unsafe-target", http_status: response.status }; }
        continue;
      }
      if (response.status >= 200 && response.status < 300) return { document: parseRobots(response.body, origin), failure: null, http_status: response.status };
      if (response.status >= 400 && response.status < 500 && response.status !== 429) return { document: parseRobots("", origin), failure: null, http_status: response.status };
      return { document: null, failure: "http", http_status: response.status };
    }
  }

  async function fetchTarget(raw: string, signal: AbortSignal): Promise<FetchResult> {
    let target = raw;
    let observedStatus: number | null = null;
    const visited = new Set<string>();
    for (;;) {
      let url: URL;
      try { ({ url } = await validateTarget(target, resolve, signal)); }
      catch (error) {
        return { body: null, http_status: observedStatus, failure: transportFailure(error, signal), robots: null, error_code: transportErrorCode(error) };
      }
      if (visited.has(url.href)) return { body: null, http_status: observedStatus, failure: "redirect-loop", robots: null };
      visited.add(url.href);
      let document = documents.get(url.origin);
      if (!document) {
        document = readRobots(url.origin, signal);
        documents.set(url.origin, document);
      }
      const robotResult = await document;
      const rules = robotResult.document;
      const robotEvidence = {
        robots_failure: robotResult.failure, robots_http_status: robotResult.http_status,
      };
      const permission = rules === null ? "unknown" : robotsPermits(rules, url.href, config.user_agent) ? "allowed" : "denied";
      if (permission !== "allowed") {
        return {
          body: null, http_status: observedStatus, failure: permission === "denied" ? "robots-denied" : "robots-unknown",
          robots: permission, ...robotEvidence, error_code: robotResult.error_code ?? null,
        };
      }
      const result = await read(url.href, signal);
      if (!result.response) return {
        body: null, http_status: result.http_status ?? observedStatus, failure: result.failure, robots: permission,
        ...robotEvidence, error_code: result.error_code ?? null,
      };
      const { response } = result;
      observedStatus = response.status;
      if (redirectStatus.has(response.status) && response.location) {
        try { target = new URL(response.location, url).href; }
        catch { return { body: null, http_status: response.status, failure: "unsafe-target", robots: permission }; }
        continue;
      }
      return {
        body: response.status >= 200 && response.status < 300 ? response.body : null,
        http_status: response.status,
        failure: response.status >= 200 && response.status < 300 ? null : "http",
        robots: permission,
        ...robotEvidence,
      };
    }
  }
  async function fetch(raw: string): Promise<FetchResult> {
    const controller = new AbortController();
    // Keep the deadline active even while DNS or a recorded I/O boundary is pending.
    const timer = setTimeout(() => controller.abort(new DOMException("harvest deadline exceeded", "TimeoutError")), config.fetch_timeout_ms);
    try { return await fetchTarget(raw, controller.signal); }
    finally { clearTimeout(timer); }
  }
  return { fetch };
}
