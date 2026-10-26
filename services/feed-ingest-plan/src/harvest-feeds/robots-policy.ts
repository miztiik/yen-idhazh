/** Fetch a target only after this run has established its origin's robots permission. */
import robotsParser from "robots-parser";
import { HarvestDiagnosticsSchema } from "@idhazh/common-contracts";
import type { FeedIngestConfig } from "@idhazh/common-contracts";
import type { FetchFailure } from "./harvest-types";
import type { ExtractionControls } from "./load-harvest-inputs";
import { BodyLimitError, ResponseReadError, networkTransport } from "./transport";
import type { HarvestTransport, TransportResponse } from "./transport";
import { UnsafeTargetError, resolveAddresses, validateTarget, validateTargetName } from "./safe-target";
import type { ResolveAddresses } from "./safe-target";
import type { FetchAttempt } from "../api/operation-contracts";
import { utcTimestamp } from "./harvest-types";
import { cleanRequestTarget } from "./request-url";

export type FetchAttemptMeasurement = {
  attempt: FetchAttempt; occurred_at: string; outcome: "success" | "failed";
  dispatched_request_count: number; request_coverage: "complete";
};
type AttemptCapture = {
  rows: FetchAttempt[]; emit?: (measurement: FetchAttemptMeasurement) => Promise<void>;
};

export type FetchResult = {
  body: string | null;
  http_status: number | null;
  failure: FetchFailure | null;
  robots: "allowed" | "denied" | "unknown" | null;
  error_code?: string | null;
  robots_failure?: FetchFailure | null;
  robots_http_status?: number | null;
  attempts?: FetchAttempt[];
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
  clock: () => Date = () => new Date(),
) {
  const product = crawlerProduct(config.user_agent);
  const transport = boundary.transport ?? networkTransport;
  const resolve = boundary.resolve ?? resolveAddresses;
  const documents = new Map<string, Promise<RobotResult>>();

  function userAgentFor(headers: Readonly<Record<string, string>>): string {
    const userAgent = headers["user-agent"] ? `${config.user_agent} ${headers["user-agent"]}` : config.user_agent;
    if (crawlerProduct(userAgent) !== product) {
      throw new Error("harvest.request_headers must preserve the configured crawler product");
    }
    return userAgent;
  }
  userAgentFor(config.request_headers.primary);
  if (config.request_headers.secondary !== null) userAgentFor(config.request_headers.secondary);

  async function requestOnce(
    raw: string, headers: Readonly<Record<string, string>>, signal: AbortSignal, dispatched: () => void,
  ): Promise<TransportResponse> {
    const { url, addresses } = await validateTarget(raw, resolve, signal);
    signal.throwIfAborted();
    const user_agent = userAgentFor(headers);
    dispatched();
    const response = await transport.request({
      url, addresses, headers: { ...headers, "user-agent": user_agent }, signal, user_agent,
      max_body_bytes: controls.max_body_bytes,
    });
    if (Buffer.byteLength(response.body, "utf8") > controls.max_body_bytes) throw new BodyLimitError(response.status);
    return response;
  }

  async function retry<T>(
    signal: AbortSignal, phase: FetchAttempt["phase"], attempts: AttemptCapture,
    execute: (signal: AbortSignal, dispatched: () => void) => Promise<T>, status: (value: T) => number | null,
  ): Promise<{ value: T | null; failure: FetchFailure | null; http_status: number | null; error_code: string | null }> {
    const loopStarted = performance.now();
    let result: { value: T | null; failure: FetchFailure | null; http_status: number | null; error_code: string | null } = {
      value: null, failure: "network", http_status: null, error_code: null,
    };
    for (let attempt = 0; attempt <= controls.max_retries; attempt++) {
      if (signal.aborted) return { ...result, value: null, failure: "timeout" };
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(new DOMException("attempt deadline exceeded", "TimeoutError")), config.fetch_timeout_ms);
      const attemptSignal = AbortSignal.any([signal, controller.signal]);
      const started = performance.now();
      let dispatched_request_count = 0;
      let failed = true;
      let classified = false;
      let evidence: FetchAttempt;
      try {
        const value = await execute(attemptSignal, () => { dispatched_request_count++; });
        const http_status = status(value);
        result = { value, failure: http_status !== null && http_status >= 400 ? "http" : null, http_status, error_code: null };
        failed = result.failure !== null;
        classified = true;
      } catch (error) {
        result = {
          value: null, failure: transportFailure(error, attemptSignal),
          http_status: error instanceof BodyLimitError || error instanceof ResponseReadError ? error.http_status : null,
          error_code: transportErrorCode(error),
        };
        classified = true;
      } finally {
        clearTimeout(timer);
        evidence = {
          phase, sequence: attempts.rows.length, retry: attempt, duration_ms: Math.round(performance.now() - started),
          backoff_ms: 0, retry_total_ms: attempt === 0 ? 0 : Math.round(started - loopStarted),
          http_status: classified ? result.http_status : null, failure: classified ? result.failure : null,
          error_code: classified ? result.error_code : null,
        };
        attempts.rows.push(evidence);
        await attempts.emit?.({
          attempt: evidence, occurred_at: utcTimestamp(clock), outcome: failed ? "failed" : "success",
          dispatched_request_count, request_coverage: "complete",
        });
      }
      if (result.value !== null && (result.http_status === null || !retryableStatus.has(result.http_status))) return result;
      if (result.failure !== null && !["dns", "network", "timeout", "http"].includes(result.failure)) return result;
      if (signal.aborted) return { ...result, value: null, failure: "timeout" };
      if (attempt < controls.max_retries) {
        const waiting = performance.now();
        try {
          await pause(controls.backoff_initial_seconds * 1000 * controls.backoff_multiplier ** attempt, signal);
        } catch (error) { return { ...result, value: null, failure: transportFailure(error, signal) }; }
        finally { evidence.backoff_ms = Math.round(performance.now() - waiting); }
      }
    }
    return result;
  }

  async function read(
    raw: string, signal: AbortSignal, phase: "robots" | "target", attempts: AttemptCapture,
    headers: Readonly<Record<string, string>> = {},
  ): Promise<RawResult> {
    const result = await retry(signal, phase, attempts,
      (current, dispatched) => requestOnce(raw, headers, current, dispatched), value => value.status);
    return { response: result.value, failure: result.failure, http_status: result.http_status, error_code: result.error_code };
  }

  async function readTarget(
    raw: string, signal: AbortSignal, attempts: AttemptCapture, kind: "feed" | "article",
  ): Promise<RawResult> {
    const profiles = config.request_headers;
    const primary = await read(raw, signal, "target", attempts, profiles.primary);
    const success = (result: RawResult) => result.response !== null && result.failure === null
      && result.response.status >= 200 && result.response.status < 300;
    const bytes = (result: RawResult) => Buffer.byteLength(result.response?.body.trim() ?? "", "utf8");
    const recoverable = success(primary) ? kind === "article" && bytes(primary) < profiles.recovery_min_body_bytes
      : primary.failure === "network" || primary.failure === "timeout"
        || (primary.failure === "http" && primary.http_status !== null
          && profiles.recoverable_http_statuses.includes(primary.http_status));
    if (profiles.secondary === null || !recoverable || signal.aborted) return primary;
    const secondary = await read(raw, signal, "target", attempts, profiles.secondary);
    // A failed recovery must not replace real, short content with a failed download.
    if (success(primary) && (!success(secondary) || bytes(secondary) <= bytes(primary))
      && !(secondary.response?.location && redirectStatus.has(secondary.response.status))) return primary;
    return secondary;
  }

  async function readRobots(origin: string, signal: AbortSignal, attempts: AttemptCapture): Promise<RobotResult> {
    let target = `${origin}/robots.txt`;
    let observedStatus: number | null = null;
    const visited = new Set<string>();
    for (;;) {
      if (visited.has(target) || signal.aborted) return {
        document: null, failure: signal.aborted ? "timeout" : "redirect-loop", http_status: observedStatus,
      };
      visited.add(target);
      const result = await read(target, signal, "robots", attempts);
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

  async function fetchTarget(
    raw: string, signal: AbortSignal, attempts: AttemptCapture, kind: "feed" | "article",
  ): Promise<FetchResult> {
    let target = raw;
    let observedStatus: number | null = null;
    const visited = new Set<string>();
    for (;;) {
      let url: URL;
      // Syntax is refused without retries; transient initial DNS failures use the same retry policy.
      const started = performance.now();
      try {
        url = config.tidy_urls ? cleanRequestTarget(target) : validateTargetName(target);
        target = url.href;
      }
      catch (error) {
        const failure = transportFailure(error, signal);
        const attempt: FetchAttempt = {
          phase: "validation", sequence: attempts.rows.length, retry: 0,
          duration_ms: Math.round(performance.now() - started), backoff_ms: 0, retry_total_ms: 0,
          http_status: null, failure, error_code: transportErrorCode(error),
        };
        attempts.rows.push(attempt);
        await attempts.emit?.({
          attempt, occurred_at: utcTimestamp(clock), outcome: "failed",
          dispatched_request_count: 0, request_coverage: "complete",
        });
        return { body: null, http_status: observedStatus, failure, robots: null };
      }
      const validated = await retry(signal, "validation", attempts, current => validateTarget(target, resolve, current), () => null);
      if (!validated.value) return {
        body: null, http_status: observedStatus, failure: validated.failure, robots: null, error_code: validated.error_code,
      };
      if (visited.has(url.href)) return { body: null, http_status: observedStatus, failure: "redirect-loop", robots: null };
      visited.add(url.href);
      let document = documents.get(url.origin);
      if (!document) {
        document = readRobots(url.origin, signal, attempts);
        documents.set(url.origin, document);
      }
      const robotResult = await document;
      const rules = robotResult.document;
      const robotEvidence = {
        robots_failure: robotResult.failure, robots_http_status: robotResult.http_status,
      };
      const permission = rules === null ? "unknown"
        : robotsPermits(rules, url.href, userAgentFor(config.request_headers.primary)) ? "allowed" : "denied";
      if (permission !== "allowed") {
        return {
          body: null, http_status: observedStatus, failure: permission === "denied" ? "robots-denied" : "robots-unknown",
          robots: permission, ...robotEvidence, error_code: robotResult.error_code ?? null,
        };
      }
      const result = await readTarget(url.href, signal, attempts, kind);
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
  async function fetch(
    raw: string, emit?: AttemptCapture["emit"], kind: "feed" | "article" = "article",
  ): Promise<FetchResult> {
    const controller = new AbortController();
    const attempts: AttemptCapture = { rows: [], ...(emit === undefined ? {} : { emit }) };
    // One operation budget includes all configured attempts and backoff, shared by DNS, robots and redirects.
    const backoff = Array.from({ length: controls.max_retries }, (_, retry) =>
      controls.backoff_initial_seconds * 1000 * controls.backoff_multiplier ** retry).reduce((sum, value) => sum + value, 0);
    const deadline = config.fetch_timeout_ms * (controls.max_retries + 1) + backoff;
    const timer = setTimeout(() => controller.abort(new DOMException("harvest deadline exceeded", "TimeoutError")), deadline);
    try { return { ...await fetchTarget(raw, controller.signal, attempts, kind), attempts: attempts.rows }; }
    finally { clearTimeout(timer); }
  }
  return { fetch };
}
