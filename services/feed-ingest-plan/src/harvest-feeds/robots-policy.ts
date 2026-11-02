/** Admit source requests before dispatch, checking robots only for non-browser transports. */
import robotsParser from "robots-parser";
import { FeedWebsiteGroupingConfigSchema, FetchAttemptSchema } from "@idhazh/common-contracts";
import type { FeedIngestConfig, HttpResponseEvidence } from "@idhazh/common-contracts";
import type { FetchFailure } from "./harvest-types";
import type { ExtractionControls } from "./load-harvest-inputs";
import { BodyLimitError, BrowserRequestInterruptedError, HTTP_REDIRECT_STATUSES, ResponseReadError, readBodyLimitEvidence } from "./transport";
import type { BodyLimitEvidence, HarvestTransport, TransportResponse } from "./transport";
import { classifyTransportFailure, readTransportErrorCode } from "./classify-transport-failure";
import { createPlaywrightTransport } from "./playwright-transport";
import type { BrowserRuntime } from "./browser-runtime";
import { validateTargetName } from "./safe-target";
import { diagnosticUrl } from "../logging/diagnostic-url";
import type { FetchAttempt } from "../api/operation-contracts";
import { utcTimestamp } from "./harvest-types";
import { cleanArticleUrl } from "./article-url";
import { createRequestPacing } from "./request-pacing";
import type { RequestPacing } from "./request-pacing";

export { createRequestPacing };
export type { RequestPacing };
export type FetchAttemptMeasurement = {
  attempt: FetchAttempt; occurred_at: string; outcome: "success" | "failed";
  dispatched_request_count: number; request_coverage: "complete" | "partial" | "unknown";
  final_attempted_url: string | null;
  pacing_settings: FeedIngestConfig["harvest"]["request_pacing"];
};
export type FetchResult = {
  body: string | null; http_status: number | null; failure: FetchFailure | null;
  robots: "allowed" | "denied" | "unknown" | null;
  error_code?: string | null; robots_failure?: FetchFailure | null; robots_http_status?: number | null;
  attempts?: FetchAttempt[]; body_limit?: BodyLimitEvidence | null;
  final_attempted_url?: string | null; requested_url?: string | null; failed_url?: string | null;
  response_evidence?: HttpResponseEvidence | null; robots_response_evidence?: HttpResponseEvidence | null;
  redirects?: { request_url: string | null; destination_url: string | null; http_status: number }[];
  pacing_time_ms?: number; pacing_settings?: FeedIngestConfig["harvest"]["request_pacing"];
};
type RobotResult = {
  document: ReturnType<typeof robotsParser> | null; failure: FetchFailure | null;
  http_status: number | null; response_evidence: HttpResponseEvidence | null;
  body_limit?: BodyLimitEvidence; failed_url?: string | null;
};
type Capture = {
  rows: FetchAttempt[]; sequence: number; publisher_id: string | null;
  final_attempted_url: string | null; failed_url: string | null;
  robots: FetchResult["robots"]; robot_result?: RobotResult;
  response?: TransportResponse;
  redirects: NonNullable<FetchResult["redirects"]>;
  emit?: (measurement: FetchAttemptMeasurement) => Promise<void>;
};
class PermissionError extends Error {
  constructor(readonly failure: "robots-denied" | "robots-unknown") { super(failure); }
}
export type PermittedFetcher = ReturnType<typeof createPermittedFetcher>;
export const retryableStatus = new Set([408, 425, 429, 500, 502, 503, 504]);
function decodeUnreserved(value: string): string {
  return value.replace(/%[0-9a-f]{2}/gi, token => {
    const character = String.fromCharCode(parseInt(token.slice(1), 16));
    return /[a-z0-9._~-]/i.test(character) ? character : token.toUpperCase();
  });
}
export function parseRobots(body: string, origin: string) {
  return robotsParser(`${origin}/robots.txt`, decodeUnreserved(body));
}
export function robotsPermits(document: ReturnType<typeof parseRobots>, url: string): boolean {
  return document.isAllowed(decodeUnreserved(url), "*") === true;
}
async function pause(milliseconds: number, signal: AbortSignal) {
  signal.throwIfAborted();
  await new Promise<void>((resolve, reject) => {
    const abort = () => { clearTimeout(timer); reject(signal.reason); };
    const timer = setTimeout(() => { signal.removeEventListener("abort", abort); resolve(); }, milliseconds);
    signal.addEventListener("abort", abort, { once: true });
  });
}

export function createPermittedFetcher(
  config: FeedIngestConfig["harvest"], controls: ExtractionControls,
  boundary: {
    transport?: HarvestTransport; request_pacing?: RequestPacing;
    include_private_suffixes?: boolean; browser_runtime?: BrowserRuntime;
  } = {},
  clock: () => Date = () => new Date(),
) {
  const transport = boundary.transport ?? createPlaywrightTransport(config, boundary.browser_runtime);
  const pacing = boundary.request_pacing ?? createRequestPacing(config.request_pacing,
    boundary.include_private_suffixes ?? FeedWebsiteGroupingConfigSchema.parse({}).include_private_suffixes);
  const closing = new AbortController();
  const documents = new Map<string, Promise<RobotResult>>();
  function failure(error: unknown, signal: AbortSignal) {
    return error instanceof PermissionError ? error.failure : classifyTransportFailure(error, signal);
  }
  async function save(capture: Capture, attempt: FetchAttempt, dispatched: number, partial = false) {
    capture.rows.push(attempt);
    await capture.emit?.({
      attempt, occurred_at: utcTimestamp(clock), outcome: attempt.failure === null ? "success" : "failed",
      dispatched_request_count: dispatched, request_coverage: partial ? "partial" : "complete",
      final_attempted_url: capture.final_attempted_url, pacing_settings: config.request_pacing,
    });
  }
  async function robots(url: URL, signal: AbortSignal, capture: Capture): Promise<RobotResult> {
    let pending = documents.get(url.origin);
    if (!pending) {
      pending = (async () => {
        try {
          const response = await read(`${url.origin}/robots.txt`, "robots", signal, capture);
          if (response.status >= 200 && response.status < 300) {
            if (/^\s*<(?:!doctype|html|head|body)\b/i.test(response.body)) {
              return { document: null, failure: "network" as const, http_status: response.status,
                response_evidence: response.evidence };
            }
            return { document: parseRobots(response.body, url.origin), failure: null,
              http_status: response.status, response_evidence: response.evidence };
          }
          return {
            document: response.status >= 400 && response.status < 500 && response.status !== 429
              ? parseRobots("", url.origin) : null,
            failure: response.status >= 400 && response.status < 500 && response.status !== 429 ? null : "http" as const,
            http_status: response.status, response_evidence: response.evidence,
          };
        } catch (error) {
          const limit = readBodyLimitEvidence(error);
          return { document: null, failure: failure(error, signal),
            http_status: error instanceof ResponseReadError || error instanceof BodyLimitError ? error.http_status : null,
            response_evidence: error instanceof ResponseReadError || error instanceof BodyLimitError ? error.response_evidence : null,
            failed_url: capture.rows.filter(row => row.phase === "robots" && row.failure !== null).at(-1)?.request_url ?? null,
            ...(limit ? { body_limit: limit } : {}),
          };
        }
      })();
      documents.set(url.origin, pending);
    }
    signal.throwIfAborted();
    let abort: () => void = () => {};
    const interrupted = new Promise<never>((_, reject) => {
      abort = () => reject(signal.reason);
      signal.addEventListener("abort", abort, { once: true });
    });
    try { return await Promise.race([pending, interrupted]); }
    finally { signal.removeEventListener("abort", abort); }
  }
  async function admitTarget(raw: string, signal: AbortSignal, capture: Capture) {
    const started = performance.now();
    try { return validateTargetName(raw); }
    catch (error) {
      await save(capture, FetchAttemptSchema.parse({
        phase: "validation", sequence: capture.sequence++, retry: 0,
        duration_ms: Math.round(performance.now() - started), backoff_ms: 0, retry_total_ms: 0,
        http_status: null, failure: failure(error, signal), error_code: readTransportErrorCode(error),
        request_role: null, pacing_wait_ms: 0,
      }), 0);
      throw error;
    }
  }
  async function runHttp(
    raw: string, role: "document" | "resource", kind: "robots" | "feed" | "article",
    signal: AbortSignal, capture: Capture, retry: number,
    dispatch: (signal: AbortSignal) => Promise<TransportResponse>, retryTotalMs: number,
  ): Promise<TransportResponse> {
    const url = await admitTarget(raw, signal, capture);
    let permissionFailure: PermissionError | undefined;
    if (!transport.browser_managed && kind !== "robots") {
      const observed = await robots(url, signal, capture);
      const permission = observed.document === null ? "unknown"
        : robotsPermits(observed.document, url.href) ? "allowed" : "denied";
      if (capture.robots === null || capture.robots === "allowed") {
        capture.robots = permission;
        capture.robot_result = observed;
      }
      if (kind === "article" && config.article_robots_policy === "enforce" && permission !== "allowed") {
        permissionFailure = new PermissionError(permission === "denied" ? "robots-denied" : "robots-unknown");
      }
    }
    const sequence = capture.sequence++;
    let wait = 0;
    let dispatched = false;
    let response: TransportResponse | undefined;
    let error: unknown;
    const beforeQueue = performance.now();
    try {
      if (permissionFailure) throw permissionFailure;
      response = await pacing.run(url, capture.publisher_id, signal, async current => {
        current.throwIfAborted();
        dispatched = true;
        if (kind !== "robots" && role === "document") capture.final_attempted_url = diagnosticUrl(url.href) ?? null;
        return dispatch(current);
      }, milliseconds => { wait = milliseconds; });
      if (response.status >= 400 && role === "document") capture.failed_url = diagnosticUrl(url.href) ?? null;
      if (kind !== "robots" && role === "document") {
        capture.response = response;
        if (HTTP_REDIRECT_STATUSES.has(response.status) && response.location) {
          capture.redirects.push({ request_url: diagnosticUrl(url.href) ?? null,
            destination_url: diagnosticUrl(new URL(response.location, url).href) ?? null, http_status: response.status });
        }
      }
      return response;
    } catch (caught) {
      error = caught;
      if (dispatched && role === "document") capture.failed_url = diagnosticUrl(url.href) ?? null;
      throw caught;
    } finally {
      const cause = error === undefined ? response && response.status >= 400 ? "http" : null : failure(error, signal);
      const evidence = response?.evidence
        ?? (error instanceof ResponseReadError || error instanceof BodyLimitError ? error.response_evidence : null);
      await save(capture, FetchAttemptSchema.parse({
        phase: kind === "robots" ? "robots" : "target", sequence, retry,
        request_role: dispatched || error instanceof PermissionError ? role : null,
        request_url: dispatched ? diagnosticUrl(url.href) ?? null : null,
        request_profile: dispatched ? "chromium" : null, response_evidence: evidence,
        duration_ms: Math.max(0, Math.round(performance.now() - beforeQueue - wait)),
        pacing_wait_ms: wait, backoff_ms: 0, retry_total_ms: retryTotalMs,
        http_status: response?.status ?? (error instanceof ResponseReadError || error instanceof BodyLimitError ? error.http_status : null),
        failure: cause, error_code: error === undefined ? null : readTransportErrorCode(error),
      }), dispatched ? 1 : 0, dispatched && (signal.aborted || error instanceof BrowserRequestInterruptedError
        || (error instanceof ResponseReadError && error.cause instanceof BrowserRequestInterruptedError)));
    }
  }
  async function read(raw: string, kind: "robots" | "feed" | "article", signal: AbortSignal, capture: Capture): Promise<TransportResponse> {
    let last: TransportResponse | undefined;
    const started = performance.now();
    for (let retry = 0; retry <= controls.max_retries; retry++) {
      let target = raw;
      const visited = new Set<string>();
      try {
        for (;;) {
          signal.throwIfAborted();
          if (visited.has(target)) throw new RedirectLoopError();
          visited.add(target);
          const input = {
            url: await admitTarget(target, signal, capture), profile: { browser: "chromium" as const, headers: config.request_headers },
            diagnostics: config.response_diagnostics, signal, timeout_ms: config.fetch_timeout_ms,
            max_body_bytes: controls.max_body_bytes, kind,
          };
          last = transport.browser_managed
            ? await transport.request({ ...input,
              gate: (url, role, dispatch) => runHttp(url, role, kind, signal, capture, retry, dispatch,
                retry === 0 ? 0 : Math.round(performance.now() - started)) })
            : await runHttp(target, "document", kind, signal, capture, retry,
              async current => {
                const controller = new AbortController();
                const timer = setTimeout(() => controller.abort(new DOMException("Source HTTP deadline exceeded", "TimeoutError")), config.fetch_timeout_ms);
                try { return await transport.request({ ...input, signal: AbortSignal.any([current, controller.signal]) }); }
                finally { clearTimeout(timer); }
              }, retry === 0 ? 0 : Math.round(performance.now() - started));
          if (!transport.browser_managed && HTTP_REDIRECT_STATUSES.has(last.status) && last.location) {
            target = new URL(last.location, target).href;
            continue;
          }
          break;
        }
        if (!retryableStatus.has(last.status) || retry === controls.max_retries) return last;
      } catch (error) {
        if (error instanceof RedirectLoopError) throw error;
        const cause = failure(error, signal);
        if (!["network", "dns", "timeout"].includes(cause) || retry === controls.max_retries || signal.aborted) throw error;
      }
      const backoff = controls.backoff_initial_seconds * 1000 * controls.backoff_multiplier ** retry;
      const before = performance.now();
      try { await pause(backoff, signal); }
      finally {
        const previous = capture.rows.filter(row => row.phase === (kind === "robots" ? "robots" : "target")
          && row.request_role === "document").at(-1);
        if (previous) previous.backoff_ms = Math.round(performance.now() - before);
      }
    }
    if (!last) throw new Error("Source retry loop completed without a response");
    return last;
  }
  async function fetch(
    raw: string, emit?: Capture["emit"], kind: "feed" | "article" = "article",
    externalSignal?: AbortSignal, publisherId: string | null = null,
  ): Promise<FetchResult> {
    const signal = AbortSignal.any([closing.signal, pacing.signal, ...(externalSignal ? [externalSignal] : [])]);
    const capture: Capture = { rows: [], sequence: 0, publisher_id: publisherId, final_attempted_url: null,
      failed_url: null, robots: null, redirects: [], ...(emit ? { emit } : {}) };
    let response: TransportResponse | undefined;
    let error: unknown;
    try {
      const target = kind === "article" ? cleanArticleUrl(raw, config) : raw;
      response = await read(target, kind, signal, capture);
    } catch (caught) { error = caught; }
    capture.rows.sort((a, b) => a.sequence - b.sequence);
    const cause = error instanceof RedirectLoopError ? "redirect-loop" : error === undefined
      ? response && response.status >= 200 && response.status < 300 ? null : "http" : failure(error, signal);
    const observed = response ?? capture.response;
    const robot = capture.robot_result;
    return {
      body: cause === null && response ? response.body : null,
      http_status: error instanceof ResponseReadError || error instanceof BodyLimitError ? error.http_status : observed?.status ?? null,
      failure: cause, robots: capture.robots, robots_failure: robot?.failure ?? null,
      robots_http_status: robot?.http_status ?? null, robots_response_evidence: robot?.response_evidence ?? null,
      response_evidence: error instanceof ResponseReadError || error instanceof BodyLimitError ? error.response_evidence : observed?.evidence ?? null,
      body_limit: readBodyLimitEvidence(error) ?? robot?.body_limit ?? null,
      error_code: error === undefined ? null : readTransportErrorCode(error),
      requested_url: diagnosticUrl(raw) ?? null, final_attempted_url: capture.final_attempted_url,
      failed_url: cause === null ? null : cause === "robots-unknown" ? robot?.failed_url ?? null : capture.failed_url,
      redirects: capture.redirects, attempts: capture.rows,
      pacing_time_ms: capture.rows.reduce((total, row) => total + (row.pacing_wait_ms ?? 0), 0),
      pacing_settings: config.request_pacing,
    };
  }
  return {
    fetch,
    async close() {
      closing.abort(new DOMException("Source fetcher is closing", "AbortError"));
      const results = await Promise.allSettled([
        transport.close?.(), boundary.request_pacing === undefined ? pacing.close() : Promise.resolve(),
      ]);
      const failures = results.flatMap(result => result.status === "rejected" ? [result.reason] : []);
      if (failures.length) throw new AggregateError(failures, "Source fetcher cleanup failed");
    },
  };
}
class RedirectLoopError extends Error {}
