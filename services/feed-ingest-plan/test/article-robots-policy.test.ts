/** Does article observation retain robots evidence without replacing the actual target outcome? */
import { expect, test } from "bun:test";
import { z } from "zod";
import { FeedIngestConfigSchema } from "@idhazh/common-contracts";
import { createPermittedFetcher } from "../src/harvest-feeds/robots-policy";
import { fetchDiagnostics } from "../src/harvest-feeds/fetch-diagnostics";
import { RecordedTransport, inputs, readRecordings, readSafety } from "./harvest-recordings";
import type { RecordedResponse } from "./harvest-recordings";

const target = "https://news.example/second";
const robots = "https://news.example/robots.txt";

async function setup(options: {
  policy?: "enforce" | "observe"; retries?: number; timeout?: number;
  robots?: RecordedResponse[]; target?: RecordedResponse[];
} = {}) {
  const loaded = await inputs([], { extraction: {
    max_retries: options.retries ?? 0, backoff_initial_seconds: 0,
  } });
  const config = FeedIngestConfigSchema.parse({
    ...loaded.config,
    harvest: {
      ...loaded.config.harvest, article_robots_policy: options.policy ?? "observe",
      fetch_timeout_ms: options.timeout ?? 1000,
      request_headers: { ...loaded.config.harvest.request_headers, secondary: null },
    },
  });
  const recordings = await readRecordings();
  if (options.robots) recordings.responses[robots] = options.robots;
  if (options.target) recordings.responses[target] = options.target;
  const transport = new RecordedTransport(recordings);
  const fetcher = createPermittedFetcher(config.harvest, loaded.extraction, {
    transport, resolve: transport.resolve,
  });
  return { config, transport, fetcher };
}

async function deniedRobots() {
  const recordings = await readRecordings();
  return recordings.responses["https://denied.example/robots.txt"]!;
}

function requested(transport: RecordedTransport) {
  return transport.requests.map(request => request.url.href);
}

test("the article policy accepts only enforce or observe and missing policy enforces", async () => {
  const { config } = await setup();
  const { article_robots_policy: _policy, ...harvest } = config.harvest;
  expect(FeedIngestConfigSchema.parse({ ...config, harvest }).harvest.article_robots_policy).toBe("enforce");
  for (const policy of ["enforce", "observe"] as const) {
    expect(FeedIngestConfigSchema.parse({
      ...config, harvest: { ...harvest, article_robots_policy: policy },
    }).harvest.article_robots_policy).toBe(policy);
  }
  for (const policy of ["ignore", "", null, true]) {
    expect(FeedIngestConfigSchema.safeParse({
      ...config, harvest: { ...harvest, article_robots_policy: policy },
    }).success).toBe(false);
  }
  for (const policy of ["enforce", undefined] as const) {
    const parsed = FeedIngestConfigSchema.parse({
      ...config, harvest: { ...harvest, ...(policy === undefined ? {} : { article_robots_policy: policy }) },
    });
    const transport = new RecordedTransport(await readRecordings());
    const fetched = await createPermittedFetcher(parsed.harvest, (await inputs()).extraction, {
      transport, resolve: transport.resolve,
    }).fetch("https://denied.example/story");
    expect(fetched).toMatchObject({ failure: "robots-denied", http_status: null, robots: "denied" });
    expect(requested(transport)).toEqual(["https://denied.example/robots.txt"]);
  }
});

test("observed denial retains robots facts while 200, 403 and 429 describe the article", async () => {
  const safety = await readSafety();
  const limited = safety.robots_responses.find(response => response.status === 429)!;
  for (const response of [
    { status: 200, fixture: "article" as const }, { status: 403, body: "" }, limited,
  ]) {
    const { fetcher, transport } = await setup({ robots: await deniedRobots(), target: [response] });
    const fetched = await fetcher.fetch(target);
    expect(fetchDiagnostics(fetched, 0)).toMatchObject({
      robots: "denied", robots_http_status: 200, robots_failure: null,
      http_status: response.status, fetch_failure: response.status === 200 ? null : "http",
      failure_code: response.status === 200 ? null : response.status === 429 ? "http_rate_limited" : "http_client_error",
      error_code: null,
    });
    expect(fetched.body).toBe(response.status === 200 ? transport.recordings.bodies.article : null);
    expect(requested(transport)).toEqual([robots, target]);
    expect(fetched.attempts!.filter(attempt => attempt.phase === "target")).toHaveLength(1);
  }
});

test("unreachable or timed-out robots do not replace article success or HTTP failure", async () => {
  const recordings = await readRecordings();
  const unavailable = recordings.responses["https://unknown.example/robots.txt"]!;
  for (const robotsResponse of [unavailable, [{ error: "timeout" }], [{ error: "ECONNRESET" }]]) {
    for (const status of [200, 403]) {
      const { fetcher, transport } = await setup({
        robots: robotsResponse, target: [{ status, body: "recorded article response" }], timeout: 500,
      });
      const fetched = await fetcher.fetch(target);
      expect(fetchDiagnostics(fetched, 0)).toMatchObject({
        robots: "unknown", robots_http_status: robotsResponse[0]!.status ?? null,
        robots_failure: robotsResponse[0]!.error === "timeout" ? "timeout"
          : robotsResponse[0]!.error === "ECONNRESET" ? "network" : "http",
        http_status: status, fetch_failure: status === 200 ? null : "http", error_code: null,
      });
      expect(requested(transport)).toEqual([robots, target]);
      expect(fetched.body).toBe(status === 200 ? "recorded article response" : null);
    }
  }
});

test("a full robots timeout allowance leaves the article's full retry allowance and caches failure", async () => {
  const { fetcher, transport } = await setup({
    robots: [{ error: "timeout" }], target: [{ error: "timeout" }, { status: 200, fixture: "article" }],
    retries: 1, timeout: 500,
  });
  const fetched = await fetcher.fetch(target);
  expect(fetched).toMatchObject({
    failure: null, http_status: 200, robots: "unknown", robots_failure: "timeout",
  });
  expect(fetchDiagnostics(fetched, 0).error_code).toBeNull();
  expect(fetched.attempts!.filter(attempt => attempt.phase === "robots").map(attempt => attempt.failure))
    .toEqual(["timeout", "timeout"]);
  expect(fetched.attempts!.filter(attempt => attempt.phase === "target").map(attempt => attempt.failure))
    .toEqual(["timeout", null]);
  expect((await fetcher.fetch(target))).toMatchObject({
    failure: null, http_status: 200, robots: "unknown", robots_failure: "timeout",
  });
  expect(requested(transport)).toEqual([robots, robots, target, target, target]);
  expect(transport.requests.at(-1)!.signal.aborted).toBe(false);
});

test("denied robots cannot suppress recovered or exhausted target retries", async () => {
  const recordings = await readRecordings();
  const recovery = recordings.responses["https://news.example/retry"]!;
  const failed = recordings.responses["https://news.example/network-error"]!;
  for (const responses of [recovery, failed]) {
    const { fetcher, transport } = await setup({
      robots: await deniedRobots(), target: responses, retries: 1,
    });
    const fetched = await fetcher.fetch(target);
    const recovered = responses === recovery;
    expect(fetchDiagnostics(fetched, 0)).toMatchObject({
      robots: "denied", robots_http_status: 200, robots_failure: null,
      http_status: recovered ? 200 : null, fetch_failure: recovered ? null : "network",
      error_code: recovered ? null : "ECONNRESET",
    });
    expect(fetched.attempts!.filter(attempt => attempt.phase === "target").map(attempt => ({
      retry: attempt.retry, failure: attempt.failure, error_code: attempt.error_code,
    }))).toEqual(recovered ? [
      { retry: 0, failure: "http", error_code: null }, { retry: 1, failure: null, error_code: null },
    ] : [
      { retry: 0, failure: "network", error_code: "ECONNRESET" },
      { retry: 1, failure: "network", error_code: "ECONNRESET" },
    ]);
    expect(requested(transport)).toEqual([robots, target, target]);
  }
});

test("article DNS and TLS failures retain only recognized low-level target codes", async () => {
  const fixture = z.object({
    target_errors: z.array(z.object({
      error: z.string(), failure: z.enum(["dns", "network"]), error_code: z.string().nullable(),
    })),
  }).parse(await Bun.file(new URL(
    "../../../tests/fixtures/feed-ingest-plan/article-robots-policy.json", import.meta.url,
  )).json());
  for (const robotsResponse of [await deniedRobots(), [{ error: "ECONNRESET" }]]) {
    for (const recording of fixture.target_errors) {
      const { fetcher, transport } = await setup({ robots: robotsResponse, target: [recording] });
      const fetched = await fetcher.fetch(target);
      expect(fetchDiagnostics(fetched, 0), recording.error).toMatchObject({
        robots: robotsResponse[0]!.error ? "unknown" : "denied",
        robots_failure: robotsResponse[0]!.error ? "network" : null,
        http_status: null, fetch_failure: recording.failure, failure_code: "network_error",
        error_code: recording.error_code,
      });
      expect(fetched.attempts!.find(attempt => attempt.phase === "target")).toMatchObject({
        failure: recording.failure, error_code: recording.error_code,
      });
      expect(requested(transport)).toEqual([robots, target]);
    }
  }
});

test("feed requests and feed redirects still enforce denied or unknown robots in observe mode", async () => {
  for (const destination of ["denied.example", "unknown.example"]) {
    const direct = await setup();
    expect((await direct.fetcher.fetch(`https://${destination}/story`, undefined, "feed")).failure)
      .toBe(destination === "denied.example" ? "robots-denied" : "robots-unknown");
    expect(requested(direct.transport)).toEqual([`https://${destination}/robots.txt`]);
    const redirected = await setup({ target: [{ status: 302, body: "", location: `https://${destination}/story` }] });
    expect((await redirected.fetcher.fetch(target, undefined, "feed")).failure)
      .toBe(destination === "denied.example" ? "robots-denied" : "robots-unknown");
    expect(requested(redirected.transport)).toEqual([robots, target, `https://${destination}/robots.txt`]);
  }
});

test("safe article redirects retain the initial robots warning and the final successful response", async () => {
  const recordings = await readRecordings();
  for (const initialRobots of [
    await deniedRobots(), recordings.responses["https://unknown.example/robots.txt"]!,
  ]) {
    const destination = "https://atom.example/entry";
    const { fetcher, transport } = await setup({
      robots: initialRobots, target: [{ status: 302, body: "", location: destination }],
    });
    transport.recordings.responses["https://atom.example/robots.txt"] =
      recordings.responses[robots]!;
    const fetched = await fetcher.fetch(target);
    expect(fetchDiagnostics(fetched, 0)).toMatchObject({
      robots: initialRobots[0]!.status === 503 ? "unknown" : "denied",
      robots_http_status: initialRobots[0]!.status,
      robots_failure: initialRobots[0]!.status === 503 ? "http" : null,
      http_status: 200, fetch_failure: null, failure_code: null, error_code: null,
    });
    expect(fetched.body).toBe(transport.recordings.bodies.article);
    expect(requested(transport)).toEqual([
      robots, target, "https://atom.example/robots.txt", destination,
    ]);
    expect(fetched.attempts!.filter(attempt => attempt.phase === "target").map(attempt => attempt.http_status))
      .toEqual([302, 200]);
  }
});

test("a cancelled shared-robots waiter stops without cancelling the first caller", async () => {
  const { fetcher, transport } = await setup({ robots: [{ error: "timeout" }], timeout: 500 });
  let markStarted!: () => void;
  const started = new Promise<void>(resolve => { markStarted = resolve; });
  transport.on_request = request => {
    if (request.url.href === robots) markStarted();
  };
  let firstSettled = false;
  const first = fetcher.fetch(target).finally(() => { firstSettled = true; });
  await started;
  const controller = new AbortController();
  let cancellation: ReturnType<typeof setTimeout> | undefined;
  try {
    const second = await fetcher.fetch(target, async measurement => {
      if (measurement.attempt.phase === "validation") {
        cancellation = setTimeout(() => {
          controller.abort(new DOMException("recorded shared waiter cancellation", "AbortError"));
        }, 0);
      }
    }, "article", controller.signal);
    expect(second).toMatchObject({ body: null, failure: "timeout" });
    expect(second.attempts!.map(attempt => attempt.phase)).toEqual(["validation"]);
    expect(firstSettled).toBe(false);
    expect(transport.active).toBe(1);
    expect(requested(transport)).toEqual([robots]);
  } finally {
    clearTimeout(cancellation);
    await first;
  }
  expect(await first).toMatchObject({
    failure: null, http_status: 200, robots: "unknown", robots_failure: "timeout",
  });
  expect(requested(transport)).toEqual([robots, target]);
});

test("external cancellation during robots or article work cannot dispatch another target attempt", async () => {
  for (const phase of ["robots", "target"]) {
    const { fetcher, transport } = await setup({
      retries: 1, robots: phase === "robots" ? [{ error: "timeout" }] : await deniedRobots(),
      target: [{ error: "timeout" }],
    });
    const controller = new AbortController();
    transport.on_request = request => {
      if ((request.url.href === robots ? "robots" : "target") === phase) {
        controller.abort(new DOMException("recorded external cancellation", "AbortError"));
      }
    };
    const fetched = await fetcher.fetch(target, undefined, "article", controller.signal);
    expect(fetched).toMatchObject({ body: null, failure: "timeout" });
    expect(requested(transport)).toEqual(phase === "robots" ? [robots] : [robots, target]);
  }
});

test("observe mode never dispatches unsafe robots or article redirect destinations", async () => {
  for (const destination of ["http://127.0.0.1/secret", "https://mixed.example/story"]) {
    const unsafeRobots = await setup({ robots: [{ status: 302, body: "", location: destination }] });
    const observed = await unsafeRobots.fetcher.fetch(target);
    expect(observed).toMatchObject({
      failure: null, http_status: 200, robots: "unknown", robots_failure: "unsafe-target",
    });
    expect(requested(unsafeRobots.transport)).toEqual([robots, target]);
    const unsafeArticle = await setup({
      robots: await deniedRobots(), target: [{ status: 302, body: "", location: destination }],
    });
    expect(await unsafeArticle.fetcher.fetch(target)).toMatchObject({ failure: "unsafe-target", http_status: 302 });
    expect(requested(unsafeArticle.transport)).toEqual([robots, target]);
  }
});
