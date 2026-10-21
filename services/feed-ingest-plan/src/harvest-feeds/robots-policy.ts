/** Fetch a target only after this run has established its origin's robots permission. */
import robotsParser from "robots-parser";
import type { FeedIngestConfig } from "@idhazh/common-contracts";
import type { FetchFailure } from "./harvest-types";
import type { ExtractionControls } from "./load-harvest-inputs";
import { BodyLimitError, networkTransport } from "./transport";
import type { HarvestTransport, TransportResponse } from "./transport";
import { UnsafeTargetError, resolveAddresses, validateTarget } from "./safe-target";
import type { ResolveAddresses } from "./safe-target";

export type FetchResult = {
  body: string | null;
  http_status: number | null;
  failure: FetchFailure | null;
  robots: "allowed" | "denied" | "unknown" | null;
};
type RawResult = { response: TransportResponse | null; failure: FetchFailure | null };
type RobotDocument = ReturnType<typeof robotsParser> | null;
export type PermittedFetcher = ReturnType<typeof createPermittedFetcher>;
const retryableStatus = new Set([408, 425, 429, 500, 502, 503, 504]);
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
  if (error instanceof UnsafeTargetError) return "unsafe-target";
  if (error instanceof BodyLimitError) return "body-too-large";
  const cause = error instanceof Error && error.cause instanceof Error ? error.cause : error;
  if (cause && typeof cause === "object" && "code" in cause && typeof cause.code === "string") {
    if (["ENOTFOUND", "EAI_AGAIN", "ENODATA"].includes(cause.code)) return "dns";
    if (cause.code.startsWith("UND_ERR_") || /^(E[A-Z]+|ERR_TLS_|CERT_)/.test(cause.code)) return "network";
  }
  throw error;
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
  const documents = new Map<string, Promise<RobotDocument>>();

  async function requestOnce(raw: string, signal: AbortSignal): Promise<TransportResponse> {
    const { url, addresses } = await validateTarget(raw, resolve, signal);
    return transport.request({
      url, addresses, signal, user_agent: config.user_agent, max_body_bytes: controls.max_body_bytes,
    });
  }

  async function read(raw: string, signal: AbortSignal): Promise<RawResult> {
    let result: RawResult = { response: null, failure: "network" };
    for (let attempt = 0; attempt <= controls.max_retries; attempt++) {
      try {
        const response = await requestOnce(raw, signal);
        result = { response, failure: null };
        if (!retryableStatus.has(response.status)) return result;
      } catch (error) {
        const failure = transportFailure(error, signal);
        result = { response: null, failure };
        if (["timeout", "unsafe-target", "body-too-large"].includes(failure)) return result;
      }
      if (attempt < controls.max_retries) {
        try {
          await pause(controls.backoff_initial_seconds * 1000 * controls.backoff_multiplier ** attempt, signal);
        } catch (error) { return { response: null, failure: transportFailure(error, signal) }; }
      }
    }
    return result;
  }

  async function readRobots(origin: string, signal: AbortSignal): Promise<RobotDocument> {
    let target = `${origin}/robots.txt`;
    const visited = new Set<string>();
    for (;;) {
      if (visited.has(target) || signal.aborted) return null;
      visited.add(target);
      const { response } = await read(target, signal);
      if (!response) return null;
      if (redirectStatus.has(response.status) && response.location) {
        try { target = new URL(response.location, target).href; } catch { return null; }
        continue;
      }
      if (response.status >= 200 && response.status < 300) return parseRobots(response.body, origin);
      if (response.status >= 400 && response.status < 500 && response.status !== 429) return parseRobots("", origin);
      return null;
    }
  }

  async function fetchTarget(raw: string, signal: AbortSignal): Promise<FetchResult> {
    let target = raw;
    const visited = new Set<string>();
    for (;;) {
      let url: URL;
      try { ({ url } = await validateTarget(target, resolve, signal)); }
      catch (error) {
        return { body: null, http_status: null, failure: transportFailure(error, signal), robots: null };
      }
      if (visited.has(url.href)) return { body: null, http_status: null, failure: "redirect-loop", robots: null };
      visited.add(url.href);
      let document = documents.get(url.origin);
      if (!document) {
        document = readRobots(url.origin, signal);
        documents.set(url.origin, document);
      }
      const rules = await document;
      const permission = rules === null ? "unknown" : robotsPermits(rules, url.href, config.user_agent) ? "allowed" : "denied";
      if (permission !== "allowed") {
        return { body: null, http_status: null, failure: permission === "denied" ? "robots-denied" : "robots-unknown", robots: permission };
      }
      const result = await read(url.href, signal);
      if (!result.response) return { body: null, http_status: null, failure: result.failure, robots: permission };
      const { response } = result;
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
