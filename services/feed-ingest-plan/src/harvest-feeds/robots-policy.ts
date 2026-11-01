/** Fetch safe targets while retaining robots evidence and honoring article enforcement. */
import robotsParser from "robots-parser";
import { FetchAttemptSchema } from "@idhazh/common-contracts";
import type { FeedIngestConfig, HttpResponseEvidence } from "@idhazh/common-contracts";
import type { FetchFailure } from "./harvest-types";
import type { ExtractionControls } from "./load-harvest-inputs";
import { BodyLimitError, ResponseReadError, readBodyLimitEvidence } from "./transport";
import { classifyTransportFailure, readTransportErrorCode } from "./classify-transport-failure";
import { createImpitTransport } from "./impit-transport";
import type { BodyLimitEvidence, HarvestTransport, TransportResponse } from "./transport";
import { validateTargetName } from "./safe-target";
import { diagnosticUrl } from "../logging/diagnostic-url";
import type { FetchAttempt } from "../api/operation-contracts";
import { utcTimestamp } from "./harvest-types";
import { cleanArticleUrl } from "./article-url";

export type FetchAttemptMeasurement = {
  attempt: FetchAttempt; occurred_at: string; outcome: "success" | "failed";
  dispatched_request_count: number; request_coverage: "complete";
  final_attempted_url: string | null;
};
type AttemptCapture = {
  rows: FetchAttempt[]; final_attempted_url: string | null;
  emit?: (measurement: FetchAttemptMeasurement) => Promise<void>;
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
  body_limit?: BodyLimitEvidence | null;
  final_attempted_url?: string | null;
  requested_url?: string | null;
  failed_url?: string | null;
  response_evidence?: HttpResponseEvidence | null;
  robots_response_evidence?: HttpResponseEvidence | null;
  redirects?: { request_url: string | null; destination_url: string | null; http_status: number }[];
};
type RawResult = {
  response: TransportResponse | null; failure: FetchFailure | null; http_status: number | null;
  error_code?: string | null; body_limit?: BodyLimitEvidence;
  response_evidence?: HttpResponseEvidence | null;
  failed_url?: string | null;
};
type TargetResult = RawResult & { retained_response?: TransportResponse };
type RobotDocument = ReturnType<typeof robotsParser> | null;
type RobotResult = {
  document: RobotDocument; failure: FetchFailure | null; http_status: number | null;
  error_code?: string | null; body_limit?: BodyLimitEvidence;
  response_evidence?: HttpResponseEvidence | null;
  failed_url?: string | null;
};
export type PermittedFetcher = ReturnType<typeof createPermittedFetcher>;
export const retryableStatus = new Set([408, 425, 429, 500, 502, 503, 504]);
const redirectStatus = new Set([301, 302, 303, 307, 308]);

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
  boundary: { transport?: HarvestTransport } = {},
  clock: () => Date = () => new Date(),
) {
  const transport = boundary.transport ?? createImpitTransport();
  const documents = new Map<string, Promise<RobotResult>>();

  async function requestOnce(
    raw: string, profile: FeedIngestConfig["harvest"]["request_headers"]["primary"], signal: AbortSignal, dispatched: () => void,
  ): Promise<TransportResponse> {
    const url = validateTargetName(raw);
    signal.throwIfAborted();
    dispatched();
    return transport.request({
      url, profile, diagnostics: config.response_diagnostics, signal,
      max_body_bytes: controls.max_body_bytes, timeout_ms: config.fetch_timeout_ms,
    });
  }

  async function retry<T>(
    signal: AbortSignal, phase: FetchAttempt["phase"], attempts: AttemptCapture,
    execute: (signal: AbortSignal, dispatched: () => void) => Promise<T>, status: (value: T) => number | null,
    request?: { url: string; profile: FeedIngestConfig["harvest"]["request_headers"]["primary"];
      evidence: (value: T) => HttpResponseEvidence },
  ): Promise<{
    value: T | null; failure: FetchFailure | null; http_status: number | null;
    error_code: string | null; body_limit?: BodyLimitEvidence; response_evidence?: HttpResponseEvidence | null;
  }> {
    const loopStarted = performance.now();
    let result: {
      value: T | null; failure: FetchFailure | null; http_status: number | null;
      error_code: string | null; body_limit?: BodyLimitEvidence; response_evidence?: HttpResponseEvidence | null;
    } = {
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
        result = { value, failure: http_status !== null && http_status >= 400 ? "http" : null, http_status, error_code: null,
          response_evidence: request?.evidence(value) ?? null };
        failed = result.failure !== null;
        classified = true;
      } catch (error) {
        const bodyLimit = readBodyLimitEvidence(error);
        result = {
          value: null, failure: classifyTransportFailure(error, attemptSignal),
          http_status: error instanceof BodyLimitError || error instanceof ResponseReadError ? error.http_status : null,
          error_code: readTransportErrorCode(error),
          response_evidence: error instanceof ResponseReadError || error instanceof BodyLimitError ? error.response_evidence : null,
          ...(bodyLimit === undefined ? {} : { body_limit: bodyLimit }),
        };
        classified = true;
      } finally {
        clearTimeout(timer);
        evidence = FetchAttemptSchema.parse({
          phase, sequence: attempts.rows.length, retry: attempt, duration_ms: Math.round(performance.now() - started),
          backoff_ms: 0, retry_total_ms: attempt === 0 ? 0 : Math.round(started - loopStarted),
          http_status: classified ? result.http_status : null, failure: classified ? result.failure : null,
          error_code: classified ? result.error_code : null,
          request_url: dispatched_request_count > 0 && request ? diagnosticUrl(request.url) ?? null : null,
          request_profile: dispatched_request_count > 0 && request ? request.profile.browser : null,
          response_evidence: classified ? result.response_evidence ?? null : null,
        });
        attempts.rows.push(evidence);
        await attempts.emit?.({
          attempt: evidence, occurred_at: utcTimestamp(clock), outcome: failed ? "failed" : "success",
          dispatched_request_count, request_coverage: "complete",
          final_attempted_url: attempts.final_attempted_url,
        });
      }
      if (result.value !== null && (result.http_status === null || !retryableStatus.has(result.http_status))) return result;
      if (result.failure !== null && !["dns", "network", "timeout", "http"].includes(result.failure)) return result;
      if (signal.aborted) return { ...result, value: null, failure: "timeout" };
      if (attempt < controls.max_retries) {
        const waiting = performance.now();
        try {
          await pause(controls.backoff_initial_seconds * 1000 * controls.backoff_multiplier ** attempt, signal);
        } catch (error) { return { ...result, value: null, failure: classifyTransportFailure(error, signal) }; }
        finally { evidence.backoff_ms = Math.round(performance.now() - waiting); }
      }
    }
    return result;
  }

  async function read(
    raw: string, signal: AbortSignal, phase: "robots" | "target", attempts: AttemptCapture,
    profile: FeedIngestConfig["harvest"]["request_headers"]["primary"] = config.request_headers.primary,
    onDispatched?: () => void,
  ): Promise<RawResult> {
    const result = await retry(signal, phase, attempts,
      (current, dispatched) => requestOnce(raw, profile, current, () => {
        dispatched();
        onDispatched?.();
      }), value => value.status, { url: raw, profile, evidence: value => value.evidence });
    return {
      response: result.value, failure: result.failure, http_status: result.http_status,
      error_code: result.error_code,
      response_evidence: result.response_evidence ?? null,
      failed_url: result.failure === null ? null : attempts.rows.at(-1)?.request_url ?? null,
      ...(result.body_limit === undefined ? {} : { body_limit: result.body_limit }),
    };
  }

  async function readTarget(
    raw: string, signal: AbortSignal, attempts: AttemptCapture, kind: "feed" | "article",
    onDispatched: () => void,
  ): Promise<TargetResult> {
    const profiles = config.request_headers;
    const primary = await read(raw, signal, "target", attempts, profiles.primary, onDispatched);
    const success = (result: RawResult) => result.response !== null && result.failure === null
      && result.response.status >= 200 && result.response.status < 300;
    const bytes = (result: RawResult) => Buffer.byteLength(result.response?.body.trim() ?? "", "utf8");
    const recoverable = success(primary) ? kind === "article" && bytes(primary) < profiles.recovery_min_body_bytes
      : primary.failure === "network" || primary.failure === "timeout"
        || (primary.failure === "http" && primary.http_status !== null
          && profiles.recoverable_http_statuses.includes(primary.http_status));
    if (profiles.secondary === null || !recoverable || signal.aborted) return primary;
    const secondary = await read(raw, signal, "target", attempts, profiles.secondary, onDispatched);
    if (secondary.failure === "unsafe-target") return secondary;
    // A failed recovery must not replace real, short content with a failed download.
    if (success(primary) && (!success(secondary) || bytes(secondary) <= bytes(primary))
      && !(secondary.response?.location && redirectStatus.has(secondary.response.status))) return primary;
    return success(primary) && primary.response !== null
      ? { ...secondary, retained_response: primary.response } : secondary;
  }

  async function readRobots(origin: string, signal: AbortSignal, attempts: AttemptCapture): Promise<RobotResult> {
    let target = `${origin}/robots.txt`;
    let observedStatus: number | null = null;
    let observedEvidence: HttpResponseEvidence | null = null;
    const visited = new Set<string>();
    for (;;) {
      if (visited.has(target) || signal.aborted) return {
        document: null, failure: signal.aborted ? "timeout" : "redirect-loop", http_status: observedStatus,
        response_evidence: observedEvidence, failed_url: null,
      };
      visited.add(target);
      const result = await read(target, signal, "robots", attempts);
      const { response } = result;
      if (!response) return { ...result, document: null, http_status: result.http_status ?? observedStatus,
        response_evidence: result.response_evidence ?? observedEvidence };
      observedStatus = response.status;
      observedEvidence = response.evidence;
      if (redirectStatus.has(response.status) && response.location) {
        try { target = new URL(response.location, target).href; }
        catch { return { document: null, failure: "unsafe-target", http_status: response.status,
          response_evidence: response.evidence, failed_url: null }; }
        continue;
      }
      if (response.status >= 200 && response.status < 300) return { document: parseRobots(response.body, origin), failure: null, http_status: response.status, response_evidence: response.evidence };
      if (response.status >= 400 && response.status < 500 && response.status !== 429) return { document: parseRobots("", origin), failure: null, http_status: response.status, response_evidence: response.evidence };
      return { document: null, failure: "http", http_status: response.status, response_evidence: response.evidence,
        failed_url: result.failed_url ?? null };
    }
  }

  async function fetchTarget(
    raw: string, signal: AbortSignal, attempts: AttemptCapture, kind: "feed" | "article",
    robotsSignal: AbortSignal, suspendDeadline: () => void, resumeDeadline: () => void,
    robotsAllowance: number,
  ): Promise<FetchResult> {
    let target = raw;
    let observedStatus: number | null = null;
    let observedEvidence: HttpResponseEvidence | null = null;
    let finalAttemptedUrl: string | null = null;
    const redirects: NonNullable<FetchResult["redirects"]> = [];
    const withAttemptedUrl = (result: Omit<FetchResult, "final_attempted_url">): FetchResult => ({
      ...result, requested_url: diagnosticUrl(raw) ?? null,
      final_attempted_url: finalAttemptedUrl === null ? null : diagnosticUrl(finalAttemptedUrl) ?? null,
      response_evidence: result.response_evidence ?? observedEvidence,
      failed_url: result.failed_url ?? null,
      redirects,
    });
    let retained: FetchResult | null = null;
    let evidence: Pick<FetchResult, "robots" | "robots_failure" | "robots_http_status" | "body_limit" | "robots_response_evidence"> = { robots: null };
    const preserveResponse = (result: FetchResult): FetchResult => retained !== null && result.failure !== null
      && ["http", "dns", "network", "timeout", "redirect-loop"].includes(result.failure) ? retained : result;
    const visited = new Set<string>();
    for (;;) {
      let url: URL;
      // URL validation has no source dispatch and no DNS lookup.
      const started = performance.now();
      try {
        url = kind === "article" ? validateTargetName(cleanArticleUrl(target, config)) : validateTargetName(target);
        target = url.href;
      }
      catch (error) {
        const failure = classifyTransportFailure(error, signal);
        const attempt = FetchAttemptSchema.parse({
          phase: "validation", sequence: attempts.rows.length, retry: 0,
          duration_ms: Math.round(performance.now() - started), backoff_ms: 0, retry_total_ms: 0,
          http_status: null, failure, error_code: readTransportErrorCode(error),
        });
        attempts.rows.push(attempt);
        await attempts.emit?.({
          attempt, occurred_at: utcTimestamp(clock), outcome: "failed",
          dispatched_request_count: 0, request_coverage: "complete",
          final_attempted_url: attempts.final_attempted_url,
        });
        return withAttemptedUrl({ body: null, http_status: observedStatus, failure, ...evidence, error_code: attempt.error_code });
      }
      const validated = await retry(signal, "validation", attempts, async current => {
        current.throwIfAborted();
        return validateTargetName(target);
      }, () => null);
      if (!validated.value) return withAttemptedUrl(preserveResponse({
        body: null, http_status: observedStatus, failure: validated.failure, ...evidence, error_code: validated.error_code,
      }));
      if (visited.has(url.href)) return withAttemptedUrl(preserveResponse({
        body: null, http_status: observedStatus, failure: "redirect-loop", ...evidence,
      }));
      visited.add(url.href);
      suspendDeadline();
      let robotResult: RobotResult;
      try {
        let document = documents.get(url.origin);
        const ownsRequest = document === undefined;
        if (!document) {
          const controller = new AbortController();
          const timer = setTimeout(() => controller.abort(new DOMException("robots deadline exceeded", "TimeoutError")), robotsAllowance);
          document = readRobots(url.origin, AbortSignal.any([robotsSignal, controller.signal]), attempts)
            .finally(() => clearTimeout(timer));
          documents.set(url.origin, document);
        }
        robotResult = ownsRequest ? await document : await waitForRobots(document, robotsSignal);
      } catch (error) {
        if (!robotsSignal.aborted) throw error;
        return withAttemptedUrl({ body: null, http_status: observedStatus, failure: "timeout", ...evidence });
      } finally { resumeDeadline(); }
      const rules = robotResult.document;
      const robotEvidence = {
        robots_failure: robotResult.failure, robots_http_status: robotResult.http_status,
        robots_response_evidence: robotResult.response_evidence ?? null,
        ...(robotResult.body_limit === undefined ? {} : { body_limit: robotResult.body_limit }),
      };
      const permission = rules === null ? "unknown"
        : robotsPermits(rules, url.href) ? "allowed" : "denied";
      if (evidence.robots === null || evidence.robots === "allowed") {
        evidence = { robots: permission, ...robotEvidence };
      }
      if (permission !== "allowed" && kind === "article" && config.article_robots_policy === "enforce") {
        return withAttemptedUrl({
          body: null, http_status: observedStatus, failure: permission === "denied" ? "robots-denied" : "robots-unknown",
          robots: permission, ...robotEvidence, error_code: robotResult.error_code ?? null,
          failed_url: permission === "unknown" ? robotResult.failed_url ?? null : null,
        });
      }
      const result = await readTarget(url.href, signal, attempts, kind, () => {
        finalAttemptedUrl = url.href;
        attempts.final_attempted_url = diagnosticUrl(url.href) ?? null;
      });
      if (result.retained_response !== undefined) retained ??= {
        body: result.retained_response.body, http_status: result.retained_response.status,
        failure: null, ...evidence, response_evidence: result.retained_response.evidence,
      };
      if (!result.response) return withAttemptedUrl(preserveResponse({
        body: null, http_status: result.http_status ?? observedStatus, failure: result.failure,
        ...evidence, error_code: result.error_code ?? null,
        response_evidence: result.response_evidence ?? null,
        failed_url: result.failed_url ?? null,
        ...(result.body_limit === undefined ? {} : { body_limit: result.body_limit }),
      }));
      const { response } = result;
      observedStatus = response.status;
      observedEvidence = response.evidence;
      if (redirectStatus.has(response.status) && response.location) {
        try { target = new URL(response.location, url).href; }
        catch { return withAttemptedUrl({ body: null, http_status: response.status, failure: "unsafe-target", ...evidence }); }
        redirects.push({ request_url: diagnosticUrl(url.href) ?? null,
          destination_url: diagnosticUrl(target) ?? null, http_status: response.status });
        continue;
      }
      return withAttemptedUrl(preserveResponse({
        body: response.status >= 200 && response.status < 300 ? response.body : null,
        http_status: response.status,
        failure: response.status >= 200 && response.status < 300 ? null : "http",
        ...evidence,
        response_evidence: response.evidence,
        failed_url: result.failure === null ? null : result.failed_url ?? null,
      }));
    }
  }
  async function fetch(
    raw: string, emit?: AttemptCapture["emit"], kind: "feed" | "article" = "article",
    externalSignal?: AbortSignal,
  ): Promise<FetchResult> {
    const controller = new AbortController();
    const operationSignal = externalSignal === undefined
      ? controller.signal
      : AbortSignal.any([controller.signal, externalSignal]);
    const attempts: AttemptCapture = { rows: [], final_attempted_url: null, ...(emit === undefined ? {} : { emit }) };
    // Robots uses one retry allowance; target profiles share their own allowance across hops.
    const backoff = Array.from({ length: controls.max_retries }, (_, retry) =>
      controls.backoff_initial_seconds * 1000 * controls.backoff_multiplier ** retry).reduce((sum, value) => sum + value, 0);
    const profileCount = [config.request_headers.primary, config.request_headers.secondary].filter(profile => profile !== null).length;
    const robotsAllowance = config.fetch_timeout_ms * (controls.max_retries + 1) + backoff;
    let remaining = robotsAllowance * profileCount;
    let started = performance.now();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const resumeDeadline = () => {
      started = performance.now();
      timer = setTimeout(() => controller.abort(new DOMException("harvest deadline exceeded", "TimeoutError")), Math.max(0, remaining));
    };
    const suspendDeadline = () => { clearTimeout(timer); remaining -= performance.now() - started; };
    resumeDeadline();
    try { return { ...await fetchTarget(raw, operationSignal, attempts, kind,
      externalSignal ?? new AbortController().signal, suspendDeadline, resumeDeadline, robotsAllowance), attempts: attempts.rows }; }
    finally { clearTimeout(timer); }
  }

  async function waitForRobots(document: Promise<RobotResult>, signal: AbortSignal): Promise<RobotResult> {
    signal.throwIfAborted();
    let abort: () => void = () => {};
    const cancelled = new Promise<never>((_, reject) => {
      abort = () => reject(signal.reason);
      signal.addEventListener("abort", abort, { once: true });
    });
    try { return await Promise.race([document, cancelled]); }
    finally { signal.removeEventListener("abort", abort); }
  }
  return { fetch };
}
