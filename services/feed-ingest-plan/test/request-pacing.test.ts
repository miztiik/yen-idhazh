/** Do domain and publisher queues retain independent settlement and cooldown rules? */
import { expect, test } from "bun:test";
import {
  createRequestPacing,
  samplePacingDelay,
  sourceDomainKey,
} from "../src/harvest-feeds/request-pacing";
import { createSourceFetcher } from "@idhazh/feed-ingest-plan/fetch-source";
import { fetchDiagnostics } from "../src/harvest-feeds/fetch-diagnostics";
import { readRetryAfter } from "../src/harvest-feeds/read-retry-after";
import { RecordedTransport, inputs, readRecordings } from "./harvest-recordings";

type Settings = Parameters<typeof createRequestPacing>[0];
type DispatchRecord = { url: string; started: number; settled: number };

test("source retries retain pacing evidence and dispatch only target requests on each fetch", async () => {
  const loaded = await inputs([], { harvest: { fetch_timeout_ms: 1000 }, extraction: { max_retries: 1 } });
  const recordings = await readRecordings();
  const target = "https://news.example/second";
  recordings.responses[target] = [{ status: 503, body: "" }, { status: 200, fixture: "article" }];
  const transport = new RecordedTransport(recordings);
  const config = {
    ...loaded.config.harvest,
    request_headers: { ...loaded.config.harvest.request_headers, secondary: null },
    request_pacing: { ...loaded.config.harvest.request_pacing, ...settings() },
  };
  const fetcher = createSourceFetcher(config, loaded.extraction, { transport });
  try {
    const fetched = await fetcher.fetch(target, undefined, "article", undefined, "publisher-a");
    const dispatched = fetched.attempts!.filter(attempt => attempt.phase === "target");
    expect(dispatched.map(attempt => attempt.failure)).toEqual(["http", null]);
    expect(dispatched.every(attempt => attempt.pacing_wait_ms !== null)).toBe(true);
    expect(fetched.pacing_time_ms).toBe(fetched.attempts!.reduce((sum, attempt) => sum + (attempt.pacing_wait_ms ?? 0), 0));
    expect(fetchDiagnostics(fetched, 0)).toMatchObject({
      pacing_time_ms: fetched.pacing_time_ms, pacing_settings: config.request_pacing,
    });
    expect((await fetcher.fetch(target)).failure).toBeNull();
    expect(transport.requests.map(request => request.url.href)).toEqual([target, target, target]);
  } finally { await fetcher.close(); }
});

function deferred<T = void>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
}

function settings(patch: Partial<Settings> = {}): Settings {
  return {
    enabled: true, domain_delay_ms: 0, publisher_delay_ms: 0, jitter_ms: 0, ...patch,
  };
}

test("429 reserves both source keys but releases the shared dispatch slot", async () => {
  const limited = "https://news.example.com/feed";
  const sharedDomain = "https://other.example.com/article";
  const sharedPublisher = "https://news.example.org/article";
  const independent = "https://other.example.net/article";
  const loaded = await inputs([], {
    harvest: { concurrency: 1, fetch_timeout_ms: 1800, request_pacing: settings() },
    extraction: { max_retries: 1, backoff_initial_seconds: 0.01 },
  });
  const recordings = await readRecordings();
  for (const url of [sharedDomain, sharedPublisher, independent]) recordings.responses[url] = [{ status: 200, fixture: "article" }];
  recordings.responses[limited] = [
    { status: 429, body: "", headers: { "retry-after": "1" } }, { status: 200, body: "ok" },
  ];
  const transport = new RecordedTransport(recordings);
  const fetcher = createSourceFetcher(loaded.config.harvest, loaded.extraction, { transport });
  const observed = deferred();
  const dispatchTimes = new Map<string, number>();
  const dispatched: number[] = [];
  const cancelledCounts: number[] = [];
  transport.on_request = request => {
    if (!dispatchTimes.has(request.url.href)) dispatchTimes.set(request.url.href, performance.now());
  };
  let restricted = 0;
  const first = fetcher.fetch(limited, async measurement => {
    dispatched.push(measurement.dispatched_request_count);
    if (measurement.attempt.http_status === 429) {
      restricted = performance.now();
      observed.resolve();
    }
  }, "feed", undefined, "limited");
  try {
    await Promise.race([observed.promise, first.then(() => { throw new Error("No 429 was observed"); })]);
    const controller = new AbortController();
    const cancelled = fetcher.fetch(sharedDomain, async measurement => {
      cancelledCounts.push(measurement.dispatched_request_count);
    }, "article", controller.signal);
    const sameDomain = fetcher.fetch(sharedDomain, undefined, "article", undefined, "different");
    const samePublisher = fetcher.fetch(sharedPublisher, undefined, "article", undefined, "limited");
    expect(await fetcher.fetch(independent)).toMatchObject({ http_status: 200, failure: null });
    controller.abort();
    expect(await cancelled).toMatchObject({ http_status: null, failure: "timeout", final_attempted_url: null });
    expect(cancelledCounts).toEqual([0, 0]);
    expect(transport.requests.map(request => request.url.href)).toEqual([limited, independent]);
    expect((await Promise.all([sameDomain, samePublisher, first])).map(result => result.http_status)).toEqual([200, 200, 200]);
    for (const url of [sharedDomain, sharedPublisher]) {
      expect(dispatchTimes.get(url)!, url).toBeGreaterThanOrEqual(restricted + 975);
    }
    expect(dispatched).toEqual([0, 1, 1]);
    expect(transport.requests).toHaveLength(5);
    expect(transport.peak).toBe(1);
  } finally { await fetcher.close(); }
});

test("Retry-After accepts seconds and HTTP dates, not numbers or dates outside the wire protocol", () => {
  const now = Date.parse("Sun, 06 Nov 1994 08:49:35 GMT") + 500;
  expect(readRetryAfter(" 003 ", now)).toEqual({ basis: "retry-after-seconds", delay_ms: 3000 });
  for (const date of ["Sun, 06 Nov 1994 08:49:37 GMT", "Sunday, 06-Nov-94 08:49:37 GMT", "Sun Nov  6 08:49:37 1994"]) {
    expect(readRetryAfter(date, now)).toEqual({ basis: "retry-after-date", delay_ms: 1500 });
  }
  expect(readRetryAfter("Sun, 06 Nov 1994 08:49:35 GMT", now)).toEqual({ basis: "retry-after-date", delay_ms: 0 });
  for (const bad of ["", "1.5", "-1", "1, 2", "2026-11-28", "Sun, 31 Nov 2026 12:00:00 GMT"]) {
    expect(readRetryAfter(bad, now)).toEqual({ basis: "invalid-retry-after" });
  }
  expect(readRetryAfter(null, now)).toEqual({ basis: "missing-retry-after" });
});

test("missing and malformed headers grow one bounded source backoff and success resets it", async () => {
  const target = "https://news.example.com/feed";
  const loaded = await inputs([], {
    harvest: { fetch_timeout_ms: 1200, request_pacing: settings({ domain_delay_ms: 35 }) },
    extraction: { max_retries: 2, backoff_initial_seconds: 0.1, backoff_multiplier: 2 },
  });
  const recordings = await readRecordings();
  const limited = { status: 429, body: "" };
  const success = { status: 200, body: "ok" };
  recordings.responses[target] = [
    limited, { ...limited, headers: { "retry-after": "not a date" } }, limited, success, limited, success,
  ];
  const transport = new RecordedTransport(recordings);
  const fetcher = createSourceFetcher(loaded.config.harvest, loaded.extraction, { transport });
  const starts: number[] = [];
  transport.on_request = () => starts.push(performance.now());
  const decisions: { basis: string; remaining_ms: number }[] = [];
  const capture: NonNullable<Parameters<typeof fetcher.fetch>[1]> = async attempt => {
    if (attempt.source_cooldown !== undefined) decisions.push(attempt.source_cooldown);
  };
  try {
    expect(await fetcher.fetch(target, capture, "feed")).toMatchObject({ http_status: 429, failure: "http" });
    expect(await fetcher.fetch(target, capture, "feed")).toMatchObject({ http_status: 200, failure: null });
    expect(await fetcher.fetch(target, capture, "feed")).toMatchObject({ http_status: 200, failure: null });
    expect(decisions).toEqual([
      { basis: "missing-retry-after", remaining_ms: 100 },
      { basis: "invalid-retry-after", remaining_ms: 200 },
      { basis: "missing-retry-after", remaining_ms: 200 },
      { basis: "missing-retry-after", remaining_ms: 100 },
    ]);
    expect(starts).toHaveLength(6);
    for (const [index, delay] of [[0, 100], [1, 200], [2, 200], [4, 100]] as const) {
      expect(starts[index + 1]! - starts[index]!).toBeGreaterThanOrEqual(delay);
    }
  } finally { await fetcher.close(); }
});

function recordingDispatch(
  records: DispatchRecord[],
  active: { value: number; peak: number },
  responseDelay = 5,
  onStarted?: () => void,
) {
  return async (url: string, publisherId: string | null, pacing: ReturnType<typeof createRequestPacing>,
    signal = new AbortController().signal, waits: number[] = []) => pacing.run(
    new URL(url), publisherId, signal,
    async current => {
      current.throwIfAborted();
      active.value++;
      active.peak = Math.max(active.peak, active.value);
      const record = { url, started: performance.now(), settled: 0 };
      records.push(record);
      onStarted?.();
      try {
        await Bun.sleep(responseDelay);
        current.throwIfAborted();
        record.settled = performance.now();
        return "recorded response";
      } finally { active.value--; }
    },
    milliseconds => waits.push(milliseconds),
  );
}

test("same registrable domain waits through response settlement and domain cooldown", async () => {
  const pacing = createRequestPacing(settings({ domain_delay_ms: 35 }), true, () => 0);
  const records: DispatchRecord[] = [];
  const active = { value: 0, peak: 0 };
  const firstStarted = deferred<void>();
  const dispatch = recordingDispatch(records, active, 5, () => firstStarted.resolve());
  try {
    const first = dispatch("https://a.example.com/feed", "publisher-a", pacing);
    await firstStarted.promise;
    const second = dispatch("https://b.example.com/feed", "publisher-b", pacing);
    expect(await first).toBe("recorded response");
    expect(await second).toBe("recorded response");
    expect(records).toHaveLength(2);
    expect(records[1]!.started - records[0]!.settled).toBeGreaterThanOrEqual(28);
    expect(active.peak).toBe(1);
  } finally { await pacing.close(); }
});

test("one publisher shares cooldown across independent registrable domains", async () => {
  const pacing = createRequestPacing(settings({ publisher_delay_ms: 35 }), true, () => 0);
  const records: DispatchRecord[] = [];
  const active = { value: 0, peak: 0 };
  const firstStarted = deferred<void>();
  const dispatch = recordingDispatch(records, active, 5, () => firstStarted.resolve());
  try {
    const first = dispatch("https://news.example.com/feed", "publisher-shared", pacing);
    await firstStarted.promise;
    const second = dispatch("https://news.example.org/feed", "publisher-shared", pacing);
    expect(await Promise.all([first, second])).toEqual(["recorded response", "recorded response"]);
    expect(records[1]!.started - records[0]!.settled).toBeGreaterThanOrEqual(28);
    expect(active.peak).toBe(1);
  } finally { await pacing.close(); }
});

test("unrelated domains and publishers progress concurrently without a null publisher key", async () => {
  const pacing = createRequestPacing(settings(), true, () => 0);
  const records: DispatchRecord[] = [];
  const active = { value: 0, peak: 0 };
  const started = deferred<void>();
  const release = deferred<void>();
  let startCount = 0;
  const dispatch = (url: string, publisherId: string | null) => pacing.run(
    new URL(url), publisherId, new AbortController().signal,
    async () => {
      active.value++;
      active.peak = Math.max(active.peak, active.value);
      const record = { url, started: performance.now(), settled: 0 };
      records.push(record);
      startCount++;
      if (startCount === 3) started.resolve();
      try {
        await release.promise;
        record.settled = performance.now();
        return "recorded response";
      } finally { active.value--; }
    },
    () => {},
  );
  try {
    const pending = Promise.all([
      dispatch("https://one.example.com/feed", "publisher-one"),
      dispatch("https://two.example.org/feed", "publisher-two"),
      dispatch("https://three.example.net/feed", null),
    ]);
    await started.promise;
    expect(active.peak).toBe(3);
    release.resolve();
    const results = await pending;
    expect(results).toEqual(["recorded response", "recorded response", "recorded response"]);
  } finally { await pacing.close(); }
});

test("jitter samples are independent, and private suffix policy sets domain keys", async () => {
  const samples = [0.25, 0.75];
  expect(samplePacingDelay(100, 40, () => samples.shift()!)).toBe(110);
  expect(samplePacingDelay(100, 40, () => samples.shift()!)).toBe(130);
  expect(samplePacingDelay(100, 0, () => { throw new Error("zero jitter must not sample"); })).toBe(100);
  expect(sourceDomainKey(new URL("https://one.github.io"), true)).toBe("one.github.io");
  expect(sourceDomainKey(new URL("https://two.github.io"), true)).toBe("two.github.io");
  expect(sourceDomainKey(new URL("https://one.github.io"), false)).toBe("github.io");
  expect(sourceDomainKey(new URL("https://two.github.io"), false)).toBe("github.io");

  const pacing = createRequestPacing(settings({
    domain_delay_ms: 35, publisher_delay_ms: 35, jitter_ms: 40,
  }), true, () => 0.25);
  const records: DispatchRecord[] = [];
  const active = { value: 0, peak: 0 };
  const dispatch = recordingDispatch(records, active, 1);
  try {
    await dispatch("https://jitter.example/feed", "publisher-jitter", pacing);
    await dispatch("https://jitter.example/feed", "publisher-jitter", pacing);
    expect(records[1]!.started - records[0]!.settled).toBeGreaterThanOrEqual(35);
  } finally { await pacing.close(); }

  const zero = createRequestPacing(settings({ jitter_ms: 0 }), true, () => 0);
  const waits: number[] = [];
  try {
    expect(await zero.run(new URL("https://zero.example/feed"), null, new AbortController().signal,
      async () => "recorded response", milliseconds => waits.push(milliseconds))).toBe("recorded response");
    expect(waits).toHaveLength(1);
    expect(waits[0]).toBeGreaterThanOrEqual(0);
  } finally { await zero.close(); }
});

test("aborting a queued request settles it without dispatch or a stranded domain key", async () => {
  const pacing = createRequestPacing(settings(), true, () => 0);
  const records: DispatchRecord[] = [];
  const active = { value: 0, peak: 0 };
  const started = deferred<void>();
  const release = deferred<void>();
  const first = pacing.run(
    new URL("https://queue.example/feed"), "publisher-one", new AbortController().signal,
    async () => {
      active.value++;
      records.push({ url: "https://queue.example/feed", started: performance.now(), settled: 0 });
      started.resolve();
      try {
        await release.promise;
        records[0]!.settled = performance.now();
        return "recorded response";
      } finally { active.value--; }
    },
    () => {},
  );
  const controller = new AbortController();
  try {
    await started.promise;
    const queued = pacing.run(
      new URL("https://queue.example/article"), "publisher-two", controller.signal,
      async () => {
        records.push({ url: "https://queue.example/article", started: performance.now(), settled: 0 });
        return "recorded response";
      },
      () => {},
    );
    controller.abort(new DOMException("cancelled while queued", "AbortError"));
    await expect(queued).rejects.toMatchObject({ name: "AbortError" });
    release.resolve();
    expect(await first).toBe("recorded response");
    expect(records.map(record => record.url)).toEqual(["https://queue.example/feed"]);
    expect(active.value).toBe(0);

    const next = pacing.run(
      new URL("https://queue.example/next"), null, new AbortController().signal,
      async () => {
        records.push({ url: "https://queue.example/next", started: performance.now(), settled: 0 });
        return "recorded response";
      },
      () => {},
    );
    expect(await next).toBe("recorded response");
    expect(records).toHaveLength(2);
  } finally { await pacing.close(); }
});

test("cancelling a publisher wait releases its domain while the publisher remains busy", async () => {
  const pacing = createRequestPacing(settings(), true, () => 0);
  const firstStarted = deferred<void>();
  const firstRelease = deferred<void>();
  const first = pacing.run(
    new URL("https://first.example/feed"), "publisher-shared", new AbortController().signal,
    async () => {
      firstStarted.resolve();
      await firstRelease.promise;
      return "first response";
    },
    () => {},
  );
  const controller = new AbortController();
  let cancelledDispatched = false;
  try {
    await firstStarted.promise;
    const queued = pacing.run(
      new URL("https://second.example/feed"), "publisher-shared", controller.signal,
      async () => {
        cancelledDispatched = true;
        return "cancelled response";
      },
      () => {},
    );
    controller.abort(new DOMException("cancelled while waiting for publisher", "AbortError"));
    await expect(queued).rejects.toMatchObject({ name: "AbortError" });

    expect(await pacing.run(
      new URL("https://second.example/next"), "publisher-independent",
      new AbortController().signal, async () => "independent response", () => {},
    )).toBe("independent response");
    expect(cancelledDispatched).toBe(false);

    firstRelease.resolve();
    expect(await first).toBe("first response");
    expect(await pacing.run(
      new URL("https://third.example/feed"), "publisher-shared",
      new AbortController().signal, async () => "later response", () => {},
    )).toBe("later response");
  } finally {
    firstRelease.resolve();
    await Promise.allSettled([first]);
    await pacing.close();
  }
});

test("cancellation during cooldown releases the key without waiting for its full delay", async () => {
  const pacing = createRequestPacing(settings({ domain_delay_ms: 1500 }), true, () => 0);
  const records: DispatchRecord[] = [];
  const active = { value: 0, peak: 0 };
  const dispatch = recordingDispatch(records, active, 1);
  const controller = new AbortController();
  try {
    const first = dispatch("https://cooldown.example/feed", null, pacing, controller.signal);
    expect(await first).toBe("recorded response");
    const second = dispatch("https://cooldown.example/article", null, pacing);
    const cancelledAt = performance.now();
    controller.abort(new DOMException("cancelled during cooldown", "AbortError"));
    expect(await second).toBe("recorded response");
    expect(records[1]!.started - cancelledAt).toBeLessThan(1000);
  } finally { await pacing.close(); }
});

test("closing pacing aborts queued and cooldown waits and releases its keys", async () => {
  const pacing = createRequestPacing(settings({ domain_delay_ms: 60_000 }), true, () => 0);
  const records: string[] = [];
  try {
    expect(await pacing.run(new URL("https://closing.example/feed"), null,
      new AbortController().signal, async () => {
        records.push("first");
        return "recorded response";
      }, () => {})).toBe("recorded response");

    const queued = pacing.run(new URL("https://closing.example/article"), null,
      new AbortController().signal, async () => {
        records.push("queued");
        return "recorded response";
      }, () => {});
    const queuedOutcome = queued.then(
      value => ({ status: "resolved" as const, value }),
      error => ({ status: "rejected" as const, error }),
    );
    await Promise.all([pacing.close(), pacing.close()]);
    expect(await queuedOutcome).toMatchObject({
      status: "rejected", error: { name: "AbortError" },
    });
    expect(records).toEqual(["first"]);
    await expect(pacing.run(new URL("https://closing.example/next"), null,
      new AbortController().signal, async () => "unexpected", () => {}))
      .rejects.toMatchObject({ name: "AbortError" });
  } finally { await pacing.close(); }
});

test("disabled pacing dispatches immediately and records no queue wait", async () => {
  const pacing = createRequestPacing(settings({
    enabled: false, domain_delay_ms: 500, publisher_delay_ms: 500, jitter_ms: 500,
  }), true, () => 0.9);
  const waits: number[] = [];
  let dispatched = false;
  try {
    expect(await pacing.run(new URL("https://disabled.example/feed"), "publisher",
      new AbortController().signal, async () => {
        dispatched = true;
        return "recorded response";
      },
      milliseconds => waits.push(milliseconds))).toBe("recorded response");
    expect(dispatched).toBe(true);
    expect(waits).toEqual([0]);
  } finally { await pacing.close(); }
});
