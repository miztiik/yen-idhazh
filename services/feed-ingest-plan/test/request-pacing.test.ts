/** Do domain and publisher queues retain independent settlement and cooldown rules? */
import { expect, test } from "bun:test";
import {
  createRequestPacing,
  samplePacingDelay,
  sourceDomainKey,
} from "../src/harvest-feeds/request-pacing";

type Settings = Parameters<typeof createRequestPacing>[0];
type DispatchRecord = { url: string; started: number; settled: number };

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
    expect(waits).toEqual([0]);
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
    await Promise.all([pacing.close(), pacing.close()]);
    await expect(queued).rejects.toMatchObject({ name: "AbortError" });
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
