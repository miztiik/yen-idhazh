/** Admit target requests by domain and publisher before claiming a shared network slot. */
import { setTimeout as sleep } from "node:timers/promises";
import Bottleneck from "bottleneck";
import { getDomain } from "tldts";
import type { RequestPacingSettings, SourceCooldownEvidence } from "@idhazh/common-contracts";
import { readRetryAfter } from "./read-retry-after";
import { workPool } from "./work-pool";

type WaitRecorder = (milliseconds: number) => void;
type ObserveResponse = (status: number, retryAfter: string | null) => void;
type Admission = {
  concurrency: number;
  deadline: number;
  backoffs: readonly number[];
  recordCooldown: (evidence: SourceCooldownEvidence) => void;
};
type Reservation = {
  basis: SourceCooldownEvidence["basis"];
  until: number;
  timer?: ReturnType<typeof setTimeout>;
};
// Node timers cannot represent longer waits in a single call.
const MAX_TIMER_MS = 2 ** 31 - 1;
export class DispatchDeadlineError extends Error {
  constructor() { super("No time remains for source dispatch"); }
}

export function sourceDomainKey(url: URL, includePrivateSuffixes: boolean): string {
  const hostname = url.hostname.toLowerCase().replace(/\.$/, "");
  return getDomain(hostname, { allowPrivateDomains: includePrivateSuffixes }) ?? hostname;
}

export function sourcePacingKeys(url: URL, publisherId: string | null, includePrivateSuffixes: boolean): [string] | [string, string] {
  const domain = `domain:${sourceDomainKey(url, includePrivateSuffixes)}`;
  return publisherId === null ? [domain] : [domain, `publisher:${publisherId}`];
}

export function samplePacingDelay(baseDelayMs: number, jitterMs: number, random: () => number): number {
  return jitterMs === 0 ? baseDelayMs : baseDelayMs + Math.floor(random() * (jitterMs + 1));
}

export function createRequestPacing(
  settings: RequestPacingSettings,
  includePrivateSuffixes: boolean,
  random: () => number = Math.random,
) {
  const domainGroup = new Bottleneck.Group({ maxConcurrent: 1 });
  const publisherGroup = new Bottleneck.Group({ maxConcurrent: 1 });
  let dispatchPool: { concurrency: number; use: ReturnType<typeof workPool> } | undefined;
  const reservations = new Map<string, Reservation>();
  const streaks = new WeakMap<Bottleneck, number>();
  const shutdown = new AbortController();
  let closed = false;
  let closing: Promise<void> | undefined;

  function remember(key: string, basis: Reservation["basis"], now: number, delay: number) {
    if (closed) return;
    const until = Math.min(now + delay, Number.MAX_SAFE_INTEGER);
    const previous = reservations.get(key);
    if (until <= now || (previous !== undefined && previous.until >= until)) return;
    clearTimeout(previous?.timer);
    const reservation: Reservation = { basis, until };
    const expire = () => {
      const remaining = until - performance.now();
      if (remaining <= 0) reservations.delete(key);
      else reservation.timer = setTimeout(expire, Math.min(MAX_TIMER_MS, Math.ceil(remaining))).unref();
    };
    reservations.set(key, reservation);
    expire();
  }

  function waitBeforeDispatch<T>(
    pending: Promise<T>, signal: AbortSignal, dispatched: () => boolean,
  ): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      const onAbort = () => {
        if (dispatched()) return;
        signal.removeEventListener("abort", onAbort);
        reject(signal.reason);
      };
      signal.addEventListener("abort", onAbort, { once: true });
      pending.then(
        value => { signal.removeEventListener("abort", onAbort); resolve(value); },
        error => { signal.removeEventListener("abort", onAbort); reject(error); },
      );
      if (signal.aborted) onAbort();
    });
  }

  async function run<T>(
    url: URL,
    publisherId: string | null,
    signal: AbortSignal,
    dispatch: (signal: AbortSignal, observeResponse: ObserveResponse) => Promise<T>,
    recordWait: WaitRecorder,
    admission?: Admission,
  ): Promise<T> {
    if (closed) throw shutdown.signal.reason;
    const requestSignal = AbortSignal.any([signal, shutdown.signal]);
    requestSignal.throwIfAborted();
    if (admission !== undefined) {
      dispatchPool ??= { concurrency: admission.concurrency, use: workPool(admission.concurrency) };
      if (dispatchPool.concurrency !== admission.concurrency) {
        throw new RangeError("A shared source scheduler requires one network concurrency limit");
      }
    }
    const useNetworkSlot = dispatchPool?.use ?? (<R>(execute: () => Promise<R>) => execute());
    const deadline = admission?.deadline ?? Infinity;
    const checkDeadline = () => {
      requestSignal.throwIfAborted();
      if (performance.now() >= deadline) throw new DispatchDeadlineError();
    };
    const started = performance.now();
    let reported = false;
    const reportWait = () => {
      if (reported) return;
      reported = true;
      recordWait(!settings.enabled && admission === undefined ? 0 : Math.round(performance.now() - started));
    };
    let dispatched = false;
    const hasDispatched = () => dispatched;
    if (!settings.enabled) {
      try {
        return await waitBeforeDispatch(useNetworkSlot(async () => {
          checkDeadline();
          reportWait();
          dispatched = true;
          return dispatch(requestSignal, () => {});
        }), requestSignal, hasDispatched);
      } finally { reportWait(); }
    }

    const keys = sourcePacingKeys(url, publisherId, includePrivateSuffixes);
    function currentReservation(now = performance.now()) {
      let latest: Reservation | undefined;
      for (const key of keys) {
        const entry = reservations.get(key);
        if (entry !== undefined && entry.until > (latest?.until ?? now)) latest = entry;
      }
      return latest;
    }
    const reportCooldown = (reservation: Reservation, now = performance.now()) => admission?.recordCooldown({
      basis: reservation.basis, remaining_ms: Math.max(0, Math.round(reservation.until - now)),
    });
    let settled = false;
    let resolveResult!: (value: T) => void;
    let rejectResult!: (error: unknown) => void;
    const result = new Promise<T>((resolve, reject) => {
      resolveResult = resolve;
      rejectResult = reject;
    });
    const settle = (outcome: { value: T } | { error: unknown }) => {
      if (settled) return;
      settled = true;
      if ("error" in outcome) rejectResult(outcome.error);
      else resolveResult(outcome.value);
    };
    const failPending = (error: unknown) => {
      if (settled) return;
      if (!dispatched) {
        const reservation = currentReservation();
        if (reservation !== undefined) reportCooldown(reservation);
        reportWait();
      }
      settle({ error });
    };
    const onAbort = () => { if (!dispatched) failPending(requestSignal.reason); };
    requestSignal.addEventListener("abort", onAbort, { once: true });

    const backoffs = admission?.backoffs ?? [];
    const observeResponse = (domain: Bottleneck, publisher: Bottleneck | null): ObserveResponse => (status, raw) => {
      const limiters = publisher === null ? [domain] : [domain, publisher];
      if (status >= 200 && status < 300) for (const limiter of limiters) streaks.delete(limiter);
      if (status !== 429 || admission === undefined) return;
      const now = performance.now();
      const retryAfter = readRetryAfter(raw, Date.now());
      for (const [index, limiter] of limiters.entries()) {
        let delay: number;
        if ("delay_ms" in retryAfter) delay = retryAfter.delay_ms;
        else {
          const streak = streaks.get(limiter) ?? 0;
          delay = backoffs[streak] ?? 0;
          streaks.set(limiter, Math.min(streak + 1, Math.max(0, backoffs.length - 1)));
        }
        remember(keys[index]!, retryAfter.basis, now, delay);
      }
      const reservation = currentReservation(now);
      if (reservation === undefined) admission.recordCooldown({ basis: retryAfter.basis, remaining_ms: 0 });
      else reportCooldown(reservation, now);
    };
    const execute = async (domain: Bottleneck, publisher: Bottleneck | null) => {
      checkDeadline();
      if (currentReservation() !== undefined) return false;
      try {
        await waitBeforeDispatch(useNetworkSlot(async () => {
          checkDeadline();
          reportWait();
          dispatched = true;
          try { settle({ value: await dispatch(requestSignal, observeResponse(domain, publisher)) }); }
          catch (error) { settle({ error }); }
        }), requestSignal, hasDispatched);
      } finally {
        if (dispatched) {
          const delay = Math.max(samplePacingDelay(settings.domain_delay_ms, settings.jitter_ms, random),
            publisher === null ? 0 : samplePacingDelay(settings.publisher_delay_ms, settings.jitter_ms, random));
          if (delay > 0) await sleep(delay, undefined, { signal: requestSignal });
        }
      }
      return true;
    };

    async function schedule() {
      for (;;) {
        checkDeadline();
        const reservation = currentReservation();
        if (reservation !== undefined) {
          if (reservation.until >= deadline) throw new DispatchDeadlineError();
          await sleep(Math.min(MAX_TIMER_MS, Math.ceil(reservation.until - performance.now())), undefined, { signal: requestSignal });
          continue;
        }
        const [domainKey, publisherKey] = keys;
        const domain = domainGroup.key(domainKey);
        const publisher = publisherKey === undefined ? null : publisherGroup.key(publisherKey);
        const sent = await domain.schedule(async () => {
          checkDeadline();
          if (currentReservation() !== undefined) return false;
          if (publisher === null) return execute(domain, null);
          return waitBeforeDispatch(publisher.schedule(() => execute(domain, publisher)), requestSignal, hasDispatched);
        });
        if (sent) return;
      }
    }
    void schedule().catch(failPending);
    try { return await result; }
    finally { requestSignal.removeEventListener("abort", onAbort); }
  }

  async function close() {
    closing ??= (async () => {
      closed = true;
      shutdown.abort(new DOMException("request pacing is closing", "AbortError"));
      for (const reservation of reservations.values()) clearTimeout(reservation.timer);
      reservations.clear();
      const groups = [domainGroup, publisherGroup] as const;
      const limiters = groups.flatMap(group => group.limiters()
        .map(limiter => ({ group, ...limiter })));
      const failures: unknown[] = [];
      const stopped = await Promise.allSettled(limiters.map(({ limiter }) => limiter.stop({
        dropWaitingJobs: true, dropErrorMessage: "Request pacing closed",
      })));
      for (const result of stopped) if (result.status === "rejected") failures.push(result.reason);
      const deleted = await Promise.allSettled(limiters.map(({ group, key }) => group.deleteKey(key)));
      for (const result of deleted) if (result.status === "rejected") failures.push(result.reason);
      const disconnected = await Promise.allSettled(groups.map(group => group.disconnect()));
      for (const result of disconnected) if (result.status === "rejected") failures.push(result.reason);
      if (failures.length) throw new AggregateError(failures, "Request pacing cleanup failed");
    })();
    return closing;
  }

  return { run, close, signal: shutdown.signal };
}

export type RequestPacing = ReturnType<typeof createRequestPacing>;
