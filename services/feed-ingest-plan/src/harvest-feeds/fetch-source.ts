/** Fetch safe feed and article targets with bounded retries, redirects and native profiles. */
import { FeedWebsiteGroupingConfigSchema, FetchAttemptSchema } from "@idhazh/common-contracts";
import type { FeedIngestConfig, HttpResponseEvidence, SourceCooldownEvidence } from "@idhazh/common-contracts";
import type { FetchFailure } from "./harvest-types";
import type { ExtractionControls } from "./load-harvest-inputs";
import { BodyLimitError, ResponseReadError, readBodyLimitEvidence } from "./transport";
import { classifyTransportFailure, readTransportErrorCode } from "./classify-transport-failure";
import { createImpitTransport } from "./impit-transport";
import type { BodyLimitEvidence, HarvestTransport, TransportRequest, TransportResponse } from "./transport";
import { validateTargetName } from "./safe-target";
import { diagnosticUrl } from "../logging/diagnostic-url";
import type { FetchAttempt } from "../api/operation-contracts";
import { utcTimestamp } from "./harvest-types";
import { normalizeResourceUrl } from "./normalize-resource-url";
import { createRequestPacing, DispatchDeadlineError } from "./request-pacing";
import type { RequestPacing } from "./request-pacing";

export type FetchAttemptMeasurement = {
  attempt: FetchAttempt; occurred_at: string; outcome: "success" | "failed";
  dispatched_request_count: number; request_coverage: "complete";
  destination_domain: string | null;
  final_attempted_url: string | null;
  pacing_settings: FeedIngestConfig["harvest"]["request_pacing"];
  source_cooldown?: SourceCooldownEvidence;
};
type AttemptCapture = {
  rows: FetchAttempt[]; final_attempted_url: string | null; publisher_id: string | null;
  deadline: number;
  emit?: (measurement: FetchAttemptMeasurement) => Promise<void>;
};
type BeginAttempt = (signal: AbortSignal) => Pick<TransportRequest, "signal" | "timeout_ms">;

export type FetchResult = {
  body: string | null;
  http_status: number | null;
  failure: FetchFailure | null;
  error_code?: string | null;
  attempts?: FetchAttempt[];
  body_limit?: BodyLimitEvidence | null;
  final_attempted_url?: string | null;
  requested_url?: string | null;
  failed_url?: string | null;
  response_evidence?: HttpResponseEvidence | null;
  redirects?: { request_url: string | null; destination_url: string | null; http_status: number }[];
  pacing_time_ms?: number;
  pacing_settings?: FeedIngestConfig["harvest"]["request_pacing"];
};
type RawResult = {
  response: TransportResponse | null; failure: FetchFailure | null; http_status: number | null;
  error_code?: string | null; body_limit?: BodyLimitEvidence;
  response_evidence?: HttpResponseEvidence | null;
  failed_url?: string | null;
};
type TargetResult = RawResult & { retained_response?: TransportResponse };
export type SourceFetcher = ReturnType<typeof createSourceFetcher>;
export const retryableStatus = new Set([408, 425, 429, 500, 502, 503, 504]);
const redirectStatus = new Set([301, 302, 303, 307, 308]);

async function pause(milliseconds: number, signal: AbortSignal): Promise<void> {
  signal.throwIfAborted();
  await new Promise<void>((resolve, reject) => {
    const abort = () => { clearTimeout(timer); reject(signal.reason); };
    const timer = setTimeout(() => { signal.removeEventListener("abort", abort); resolve(); }, milliseconds);
    signal.addEventListener("abort", abort, { once: true });
  });
}

export function createSourceFetcher(
  config: FeedIngestConfig["harvest"], controls: ExtractionControls,
  boundary: {
    transport?: HarvestTransport;
    request_pacing?: RequestPacing;
    include_private_suffixes?: boolean;
  } = {},
  clock: () => Date = () => new Date(),
) {
  const transport = boundary.transport ?? createImpitTransport();
  const ownsPacing = boundary.request_pacing === undefined;
  const pacing = boundary.request_pacing ?? createRequestPacing(
    config.request_pacing,
    boundary.include_private_suffixes
      ?? FeedWebsiteGroupingConfigSchema.parse({}).include_private_suffixes,
  );
  const backoffs = Array.from({ length: Math.max(1, controls.max_retries) }, (_, retry) =>
    controls.backoff_initial_seconds * 1000 * controls.backoff_multiplier ** retry);
  const retryWait = backoffs.slice(0, controls.max_retries).reduce((total, delay) => total + delay, 0);
  const profileCount = config.request_headers.secondary === null ? 1 : 2;
  const allowance = (config.fetch_timeout_ms * (controls.max_retries + 1) + retryWait) * profileCount;
  async function requestOnce(
    raw: string, profile: FeedIngestConfig["harvest"]["request_headers"]["primary"], signal: AbortSignal,
    capture: AttemptCapture, dispatched: () => void, beginAttempt: BeginAttempt,
    recordPacingWait: (milliseconds: number) => void, recordCooldown: (evidence: SourceCooldownEvidence) => void,
  ): Promise<TransportResponse> {
    const url = validateTargetName(raw);
    signal.throwIfAborted();
    return pacing.run(url, capture.publisher_id, signal, async (requestSignal, observeResponse) => {
      const timing = beginAttempt(requestSignal);
      dispatched();
      let limited = false;
      const observeRateLimit = (status: number, retryAfter: string | null) => {
        if (limited || status !== 429) return;
        limited = true;
        observeResponse(status, retryAfter);
      };
      try {
        const response = await transport.request({
          url, profile, diagnostics: config.response_diagnostics, ...timing,
          max_body_bytes: controls.max_body_bytes,
          observe_headers: observeRateLimit,
        });
        if (response.status === 429) observeRateLimit(429, null);
        else observeResponse(response.status, null);
        return response;
      } catch (error) {
        if (error instanceof BodyLimitError || error instanceof ResponseReadError) observeRateLimit(error.http_status, null);
        throw error;
      }
    }, recordPacingWait, { concurrency: config.concurrency, deadline: capture.deadline, backoffs, recordCooldown });
  }

  async function retry<T>(
    signal: AbortSignal, phase: FetchAttempt["phase"], attempts: AttemptCapture,
    execute: (
      signal: AbortSignal, dispatched: () => void,
      beginAttempt: BeginAttempt,
      recordPacingWait: (milliseconds: number) => void,
      recordCooldown: (evidence: SourceCooldownEvidence) => void,
    ) => Promise<T>,
    status: (value: T) => number | null,
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
    const expired = () => result.http_status === 429 ? result : { ...result, value: null, failure: "timeout" as const };
    for (let attempt = 0; attempt <= controls.max_retries; attempt++) {
      if (signal.aborted || performance.now() >= attempts.deadline) return expired();
      const previous = result;
      const controller = new AbortController();
      let timer: ReturnType<typeof setTimeout> | undefined;
      let attemptSignal = signal;
      const beginAttempt = (current: AbortSignal) => {
        current.throwIfAborted();
        const timeout_ms = Math.min(config.fetch_timeout_ms, Math.ceil(attempts.deadline - performance.now()));
        if (timeout_ms <= 0) throw new DispatchDeadlineError();
        timer = setTimeout(() => controller.abort(new DOMException("attempt deadline exceeded", "TimeoutError")), timeout_ms);
        attemptSignal = AbortSignal.any([current, controller.signal]);
        return { signal: attemptSignal, timeout_ms };
      };
      const started = performance.now();
      let pacing_wait_ms = 0;
      let dispatched_request_count = 0;
      let dispatchedAt: string | null = null;
      let sourceCooldown: SourceCooldownEvidence | undefined;
      let failed = true;
      let classified = false;
      let evidence: FetchAttempt;
      try {
        if (request === undefined) beginAttempt(signal);
        const value = await execute(signal, () => {
          dispatched_request_count++;
          dispatchedAt = utcTimestamp(clock);
        }, beginAttempt,
          milliseconds => { pacing_wait_ms = milliseconds; },
          cooldown => { sourceCooldown = cooldown; });
        const http_status = status(value);
        result = { value, failure: http_status !== null && http_status >= 400 ? "http" : null, http_status, error_code: null,
          response_evidence: request?.evidence(value) ?? null };
        failed = result.failure !== null;
        classified = true;
      } catch (error) {
        const bodyLimit = readBodyLimitEvidence(error);
        result = {
          value: null, failure: error instanceof DispatchDeadlineError ? "timeout" : classifyTransportFailure(error, attemptSignal),
          http_status: error instanceof BodyLimitError || error instanceof ResponseReadError ? error.http_status : null,
          error_code: readTransportErrorCode(error),
          response_evidence: error instanceof ResponseReadError || error instanceof BodyLimitError ? error.response_evidence : null,
          ...(bodyLimit === undefined ? {} : { body_limit: bodyLimit }),
        };
        classified = true;
      } finally {
        if (timer !== undefined) clearTimeout(timer);
        evidence = FetchAttemptSchema.parse({
          phase, sequence: attempts.rows.length, retry: attempt,
          duration_ms: Math.max(0, Math.round(performance.now() - started - pacing_wait_ms)),
          backoff_ms: 0, retry_total_ms: attempt === 0 ? 0 : Math.round(started - loopStarted),
          http_status: classified ? result.http_status : null, failure: classified ? result.failure : null,
          error_code: classified ? result.error_code : null,
          request_url: dispatched_request_count > 0 && request ? diagnosticUrl(request.url) ?? null : null,
          request_profile: dispatched_request_count > 0 && request ? request.profile.browser : null,
          response_evidence: classified ? result.response_evidence ?? null : null,
          pacing_wait_ms,
        });
        attempts.rows.push(evidence);
        await attempts.emit?.({
          attempt: evidence, occurred_at: dispatchedAt ?? utcTimestamp(clock), outcome: failed ? "failed" : "success",
          dispatched_request_count, request_coverage: "complete",
          destination_domain: (dispatched_request_count > 0 || sourceCooldown !== undefined) && request !== undefined
            ? new URL(request.url).hostname.replace(/^\[|\]$|\.$/g, "") : null,
          final_attempted_url: attempts.final_attempted_url,
          pacing_settings: config.request_pacing,
          ...(sourceCooldown === undefined ? {} : { source_cooldown: sourceCooldown }),
        });
      }
      if (request !== undefined && dispatched_request_count === 0 && result.failure === "timeout") {
        return previous.http_status === 429 ? previous : result;
      }
      if (result.value !== null && (result.http_status === null || !retryableStatus.has(result.http_status))) return result;
      if (result.failure !== null && !["dns", "network", "timeout", "http"].includes(result.failure)) return result;
      if (signal.aborted) return expired();
      if (attempt < controls.max_retries && !(config.request_pacing.enabled && result.http_status === 429)) {
        const waiting = performance.now();
        try {
          await pause(backoffs[attempt]!, signal);
        } catch (error) {
          if (signal.aborted) return expired();
          throw error;
        }
        finally { evidence.backoff_ms = Math.round(performance.now() - waiting); }
      }
    }
    return result;
  }

  async function read(
    raw: string, signal: AbortSignal, attempts: AttemptCapture,
    profile: FeedIngestConfig["harvest"]["request_headers"]["primary"] = config.request_headers.primary,
    onDispatched?: () => void,
  ): Promise<RawResult> {
    const first = attempts.rows.length;
    const result = await retry(signal, "target", attempts,
      (current, dispatched, beginAttempt, recordPacingWait, recordCooldown) => requestOnce(raw, profile, current,
        attempts, () => {
        dispatched();
        onDispatched?.();
      }, beginAttempt, recordPacingWait, recordCooldown),
      value => value.status, { url: raw, profile, evidence: value => value.evidence });
    const failed = result.http_status === 429
      ? attempts.rows.slice(first).findLast(attempt => attempt.http_status === 429)
      : attempts.rows.at(-1);
    return {
      response: result.value, failure: result.failure, http_status: result.http_status,
      error_code: result.error_code,
      response_evidence: result.response_evidence ?? null,
      failed_url: result.failure === null ? null : failed?.request_url ?? null,
      ...(result.body_limit === undefined ? {} : { body_limit: result.body_limit }),
    };
  }

  async function readTarget(
    raw: string, signal: AbortSignal, attempts: AttemptCapture, kind: "feed" | "article",
    onDispatched: () => void,
  ): Promise<TargetResult> {
    const profiles = config.request_headers;
    const primary = await read(raw, signal, attempts, profiles.primary, onDispatched);
    const lastAttempt = attempts.rows.at(-1);
    if (primary.http_status === 429 || lastAttempt?.phase !== "target" || lastAttempt.request_profile === null) return primary;
    const success = (result: RawResult) => result.response !== null && result.failure === null
      && result.response.status >= 200 && result.response.status < 300;
    const bytes = (result: RawResult) => Buffer.byteLength(result.response?.body.trim() ?? "", "utf8");
    const recoverable = success(primary) ? kind === "article" && bytes(primary) < profiles.recovery_min_body_bytes
      : primary.failure === "network" || primary.failure === "timeout"
        || (primary.failure === "http" && primary.http_status !== null
          && profiles.recoverable_http_statuses.includes(primary.http_status));
    if (profiles.secondary === null || !recoverable || signal.aborted) return primary;
    const secondary = await read(raw, signal, attempts, profiles.secondary, onDispatched);
    if (secondary.failure === "unsafe-target") return secondary;
    // A failed recovery must not replace real, short content with a failed download.
    if (success(primary) && (!success(secondary) || bytes(secondary) <= bytes(primary))
      && !(secondary.response?.location && redirectStatus.has(secondary.response.status))) return primary;
    return success(primary) && primary.response !== null
      ? { ...secondary, retained_response: primary.response } : secondary;
  }

  async function fetchTarget(
    raw: string, signal: AbortSignal, attempts: AttemptCapture, kind: "feed" | "article",
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
    const preserveResponse = (result: FetchResult): FetchResult => retained !== null && result.failure !== null
      && ["http", "dns", "network", "timeout", "redirect-loop"].includes(result.failure) ? retained : result;
    const visited = new Set<string>();
    for (;;) {
      let url: URL;
      // URL validation has no source dispatch and no DNS lookup.
      const started = performance.now();
      try {
        url = validateTargetName(normalizeResourceUrl(target));
        target = url.href;
      }
      catch (error) {
        const failure = classifyTransportFailure(error, signal);
        const attempt = FetchAttemptSchema.parse({
          phase: "validation", sequence: attempts.rows.length, retry: 0,
          duration_ms: Math.round(performance.now() - started), backoff_ms: 0, retry_total_ms: 0,
          http_status: null, failure, error_code: readTransportErrorCode(error), pacing_wait_ms: 0,
        });
        attempts.rows.push(attempt);
        await attempts.emit?.({
          attempt, occurred_at: utcTimestamp(clock), outcome: "failed",
          dispatched_request_count: 0, request_coverage: "complete",
          destination_domain: null,
          final_attempted_url: attempts.final_attempted_url,
          pacing_settings: config.request_pacing,
        });
        return withAttemptedUrl({ body: null, http_status: observedStatus, failure, error_code: attempt.error_code });
      }
      const validated = await retry(signal, "validation", attempts, async current => {
        current.throwIfAborted();
        return validateTargetName(target);
      }, () => null);
      if (!validated.value) return withAttemptedUrl(preserveResponse({
        body: null, http_status: observedStatus, failure: validated.failure, error_code: validated.error_code,
      }));
      if (visited.has(url.href)) return withAttemptedUrl(preserveResponse({
        body: null, http_status: observedStatus, failure: "redirect-loop",
      }));
      visited.add(url.href);
      const result = await readTarget(url.href, signal, attempts, kind, () => {
        finalAttemptedUrl = url.href;
        attempts.final_attempted_url = diagnosticUrl(url.href) ?? null;
      });
      if (result.retained_response !== undefined) retained ??= {
        body: result.retained_response.body, http_status: result.retained_response.status,
        failure: null, response_evidence: result.retained_response.evidence,
      };
      if (!result.response) return withAttemptedUrl(preserveResponse({
        body: null, http_status: result.http_status ?? observedStatus, failure: result.failure,
        error_code: result.error_code ?? null,
        response_evidence: result.response_evidence ?? null,
        failed_url: result.failed_url ?? null,
        ...(result.body_limit === undefined ? {} : { body_limit: result.body_limit }),
      }));
      const { response } = result;
      observedStatus = response.status;
      observedEvidence = response.evidence;
      if (redirectStatus.has(response.status) && response.location) {
        try { target = new URL(response.location, url).href; }
        catch { return withAttemptedUrl({ body: null, http_status: response.status, failure: "unsafe-target" }); }
        redirects.push({ request_url: diagnosticUrl(url.href) ?? null,
          destination_url: diagnosticUrl(target) ?? null, http_status: response.status });
        continue;
      }
      return withAttemptedUrl(preserveResponse({
        body: response.status >= 200 && response.status < 300 ? response.body : null,
        http_status: response.status,
        failure: response.status >= 200 && response.status < 300 ? null : "http",
        response_evidence: response.evidence,
        failed_url: result.failure === null ? null : result.failed_url ?? null,
      }));
    }
  }
  async function fetch(
    raw: string, emit?: AttemptCapture["emit"], kind: "feed" | "article" = "article",
    externalSignal?: AbortSignal, publisherId: string | null = null,
  ): Promise<FetchResult> {
    const controller = new AbortController();
    const operationSignal = externalSignal === undefined
      ? AbortSignal.any([controller.signal, pacing.signal])
      : AbortSignal.any([controller.signal, externalSignal, pacing.signal]);
    // All target profiles and redirect hops share this bounded operation deadline.
    const attempts: AttemptCapture = {
      rows: [], final_attempted_url: null, publisher_id: publisherId,
      deadline: performance.now() + allowance,
      ...(emit === undefined ? {} : { emit }),
    };
    const timer = setTimeout(() => controller.abort(new DOMException("harvest deadline exceeded", "TimeoutError")), allowance);
    try {
      const result = await fetchTarget(raw, operationSignal, attempts, kind);
      return {
        ...result, attempts: attempts.rows,
        pacing_time_ms: attempts.rows.reduce((total, attempt) => total + (attempt.pacing_wait_ms ?? 0), 0),
        pacing_settings: config.request_pacing,
      };
    }
    finally { clearTimeout(timer); }
  }

  return {
    fetch,
    close: () => ownsPacing ? pacing.close() : Promise.resolve(),
  };
}
