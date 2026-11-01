/** Hold independent domain and publisher queues through each request and its cooldown. */
import Bottleneck from "bottleneck";
import { getDomain } from "tldts";
import type { RequestPacingSettings } from "@idhazh/common-contracts";

type WaitRecorder = (milliseconds: number) => void;

export function sourceDomainKey(url: URL, includePrivateSuffixes: boolean): string {
  const hostname = url.hostname.toLowerCase().replace(/\.$/, "");
  return getDomain(hostname, { allowPrivateDomains: includePrivateSuffixes }) ?? hostname;
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
  const shutdown = new AbortController();
  let closed = false;
  let closing: Promise<void> | undefined;

  function reportWait(started: number, record: WaitRecorder, reported: { value: boolean }) {
    if (reported.value) return;
    reported.value = true;
    record(Math.max(0, Math.round(performance.now() - started)));
  }

  function waitBeforeDispatch<T>(
    pending: Promise<T>, signal: AbortSignal, dispatched: () => boolean,
  ): Promise<T> {
    if (signal.aborted && !dispatched()) return Promise.reject(signal.reason);
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
    });
  }

  async function run<T>(
    url: URL,
    publisherId: string | null,
    signal: AbortSignal,
    dispatch: (signal: AbortSignal) => Promise<T>,
    recordWait: WaitRecorder,
  ): Promise<T> {
    if (closed) throw shutdown.signal.reason;
    const requestSignal = AbortSignal.any([signal, shutdown.signal]);
    requestSignal.throwIfAborted();
    if (!settings.enabled) {
      recordWait(0);
      return dispatch(requestSignal);
    }

    const started = performance.now();
    const reported = { value: false };
    let dispatched = false;
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
    const onAbort = () => {
      if (dispatched) return;
      reportWait(started, recordWait, reported);
      settle({ error: requestSignal.reason });
    };
    requestSignal.addEventListener("abort", onAbort, { once: true });

    const execute = async () => {
      if (requestSignal.aborted) throw requestSignal.reason;
      reportWait(started, recordWait, reported);
      dispatched = true;
      let value: T;
      try {
        value = await dispatch(requestSignal);
        settle({ value });
      } catch (error) {
        settle({ error });
        await cooldown();
        throw error;
      }
      await cooldown();
      return value;
    };
    const cooldown = async () => {
      const waits = [
        samplePacingDelay(settings.domain_delay_ms, settings.jitter_ms, random),
        ...(publisherId === null ? [] : [
          samplePacingDelay(settings.publisher_delay_ms, settings.jitter_ms, random),
        ]),
      ];
      await Promise.all(waits.map(milliseconds => wait(milliseconds, requestSignal)));
    };
    const wait = (milliseconds: number, signal: AbortSignal) => {
      if (milliseconds === 0) return Promise.resolve();
      signal.throwIfAborted();
      return new Promise<void>((resolve, reject) => {
        let timer: ReturnType<typeof setTimeout>;
        const abort = () => {
          clearTimeout(timer);
          signal.removeEventListener("abort", abort);
          reject(signal.reason);
        };
        timer = setTimeout(() => {
          signal.removeEventListener("abort", abort);
          resolve();
        }, milliseconds);
        signal.addEventListener("abort", abort, { once: true });
      });
    };

    const domainLimiter = domainGroup.key(sourceDomainKey(url, includePrivateSuffixes));
    const publisherLimiter = publisherId === null ? null : publisherGroup.key(publisherId);
    const scheduled = domainLimiter.schedule(async () => {
      if (requestSignal.aborted) throw requestSignal.reason;
      if (publisherLimiter === null) return execute();
      return waitBeforeDispatch(
        publisherLimiter.schedule(execute), requestSignal, () => dispatched,
      );
    });
    scheduled.then(
      value => settle({ value }),
      error => settle({ error }),
    );
    try { return await result; }
    finally { requestSignal.removeEventListener("abort", onAbort); }
  }

  async function close() {
    closing ??= (async () => {
      closed = true;
      shutdown.abort(new DOMException("request pacing is closing", "AbortError"));
      const groups = [domainGroup, publisherGroup] as const;
      const limiters = groups.flatMap(group => group.limiters()
        .map(limiter => ({ group, ...limiter })));
      const failures: unknown[] = [];
      const stopped = await Promise.allSettled(limiters.map(({ limiter }) => limiter.stop({
        dropWaitingJobs: true, dropErrorMessage: "Request pacing closed",
      })));
      for (const result of stopped) if (result.status === "rejected") failures.push(result.reason);
      for (const { group, key } of limiters) group.deleteKey(key);
      const disconnected = await Promise.allSettled(groups.map(group => group.disconnect()));
      for (const result of disconnected) if (result.status === "rejected") failures.push(result.reason);
      if (failures.length) throw new AggregateError(failures, "Request pacing cleanup failed");
    })();
    return closing;
  }

  return { run, close, signal: shutdown.signal };
}

export type RequestPacing = ReturnType<typeof createRequestPacing>;
