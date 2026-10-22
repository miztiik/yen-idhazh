/** Exercise recorded robots, address, sanitization and request-failure boundaries. */
import { expect, test } from "bun:test";
import { sanitizeText, SANITIZER_VERSION } from "../src/harvest-feeds/sanitize-text";
import { isPublicAddress, validateTargetName } from "../src/harvest-feeds/safe-target";
import { createPermittedFetcher, crawlerProduct, parseRobots, robotsPermits } from "../src/harvest-feeds/robots-policy";
import { mapPool } from "../src/harvest-feeds/harvest-pool";
import { fetchDiagnostics } from "../src/harvest-feeds/fetch-diagnostics";
import { RecordedTransport, inputs, readRecordings, readSafety, source } from "./harvest-recordings";

test("recorded sanitizer vectors match sanitizer-3, keep prose and are idempotent", async () => {
  const fixture = await readSafety();
  expect(SANITIZER_VERSION).toBe(fixture.sanitizer_version);
  for (const vector of fixture.sanitizer) {
    expect(sanitizeText(vector.input)).toBe(vector.expected);
    expect(sanitizeText(sanitizeText(vector.input))).toBe(vector.expected);
  }
});

test("literal, encoded and named unsafe addresses fail before transport", async () => {
  const fixture = await readSafety();
  for (const url of fixture.unsafe_targets) expect(() => validateTargetName(url), url).toThrow();
  expect(isPublicAddress("93.184.216.34")).toBe(true);
  expect(isPublicAddress("2606:4700:4700::1111")).toBe(true);
  const loaded = await inputs();
  const transport = new RecordedTransport(await readRecordings());
  const fetcher = createPermittedFetcher(loaded.config.harvest, loaded.extraction, { transport, resolve: transport.resolve });
  for (const target of [...fixture.unsafe_targets, "https://inward.example/feed.xml", "https://mixed.example/feed.xml"]) {
    expect((await fetcher.fetch(target)).failure).toBe("unsafe-target");
  }
  expect(transport.requests).toEqual([]);
});

test("recorded repeated groups, precedence, wildcard and encoded path rules bind the configured crawler", async () => {
  const fixture = await readSafety();
  const loaded = await inputs();
  const agent = loaded.config.harvest.user_agent;
  expect(crawlerProduct(agent)).toBe("YenIdhazhBot");
  for (const recording of fixture.robots) {
    const document = parseRobots(recording.body, "https://news.example");
    for (const path of recording.allowed) expect(robotsPermits(document, `https://news.example${path}`, agent), `${recording.name} ${path}`).toBe(true);
    for (const path of recording.denied) expect(robotsPermits(document, `https://news.example${path}`, agent), `${recording.name} ${path}`).toBe(false);
  }
});

test("denied or unknown permission never requests the target; robots cache is per normalized origin and run", async () => {
  const loaded = await inputs();
  const transport = new RecordedTransport(await readRecordings());
  const boundary = { transport, resolve: transport.resolve };
  const fetcher = createPermittedFetcher(loaded.config.harvest, loaded.extraction, boundary);
  const denied = fetchDiagnostics(await fetcher.fetch("https://denied.example/story"), 0);
  expect(denied).toMatchObject({
    fetch_failure: "robots-denied", failure_code: "robots_denied", robots: "denied",
    http_status: null, robots_http_status: 200, robots_failure: null,
  });
  const unknown = fetchDiagnostics(await fetcher.fetch("https://unknown.example/story"), 0);
  expect(unknown).toMatchObject({
    fetch_failure: "robots-unknown", failure_code: "robots_unreachable", robots: "unknown",
    http_status: null, robots_http_status: 503, robots_failure: "http",
  });
  expect((await fetcher.fetch("https://NEWS.EXAMPLE:443/denied")).failure).toBe("robots-denied");
  expect((await fetcher.fetch("https://news.example/denied/again")).failure).toBe("robots-denied");
  expect(transport.requests.map(request => request.url.href)).toEqual([
    "https://denied.example/robots.txt", "https://unknown.example/robots.txt", "https://news.example/robots.txt",
  ]);
  for (const request of transport.requests) expect(request.user_agent).toBe(loaded.config.harvest.user_agent);
  const nextRun = createPermittedFetcher(loaded.config.harvest, loaded.extraction, boundary);
  await nextRun.fetch("https://denied.example/story");
  expect(transport.requests.filter(request => request.url.hostname === "denied.example")).toHaveLength(2);
});

test("redirects establish safe destination and robots permission before requesting the next hop", async () => {
  const loaded = await inputs();
  const transport = new RecordedTransport(await readRecordings());
  const fetcher = createPermittedFetcher(loaded.config.harvest, loaded.extraction, { transport, resolve: transport.resolve });
  expect(await fetcher.fetch("https://news.example/unsafe-redirect")).toMatchObject({ failure: "unsafe-target", http_status: 302 });
  expect((await fetcher.fetch("https://news.example/denied-redirect")).failure).toBe("robots-denied");
  expect((await fetcher.fetch("https://news.example/safe-redirect")).http_status).toBe(200);
  expect(await fetcher.fetch("https://news.example/loop")).toMatchObject({ failure: "redirect-loop", http_status: 302 });
  expect(transport.requests.some(request => request.url.hostname === "127.0.0.1")).toBe(false);
  expect(transport.requests.some(request => request.url.href === "https://denied.example/story")).toBe(false);
});

test("permanent statuses do not retry; transient statuses use existing retry controls", async () => {
  const loaded = await inputs([source()], { extraction: { max_retries: 1 } });
  const transport = new RecordedTransport(await readRecordings());
  const fetcher = createPermittedFetcher(loaded.config.harvest, loaded.extraction, { transport, resolve: transport.resolve });
  expect(fetchDiagnostics(await fetcher.fetch("https://news.example/not-found"), 0)).toMatchObject({
    http_status: 404, fetch_failure: "http", failure_code: "http_client_error",
  });
  expect((await fetcher.fetch("https://news.example/retry")).http_status).toBe(200);
  expect(transport.requests.filter(request => request.url.pathname === "/not-found")).toHaveLength(1);
  expect(transport.requests.filter(request => request.url.pathname === "/retry")).toHaveLength(2);
  expect(fetchDiagnostics(await fetcher.fetch("https://missing.example/story"), 0)).toMatchObject({
    fetch_failure: "dns", error_code: "ENOTFOUND", failure_code: "network_error",
  });
  expect(fetchDiagnostics(await fetcher.fetch("https://news.example/network-error"), 0)).toMatchObject({
    fetch_failure: "network", error_code: "ECONNRESET", failure_code: "network_error",
  });
  expect(fetchDiagnostics(await fetcher.fetch("https://news.example/error"), 0)).toMatchObject({
    http_status: 503, failure_code: "http_server_error",
  });
  // Replay the existing rate-limit protocol recording as the target response too.
  const safety = await readSafety();
  const limited = safety.robots_responses.find(response => response.status === 429);
  if (!limited) throw new Error("Expected the recorded rate-limit response");
  transport.recordings.responses["https://news.example/error"] = [limited];
  expect(fetchDiagnostics(await fetcher.fetch("https://news.example/error"), 0)).toMatchObject({
    http_status: 429, failure_code: "http_rate_limited",
  });
});

test("pool concurrency changes with configuration and results retain offered order", async () => {
  for (const concurrency of [1, 2, 4]) {
    let active = 0, peak = 0;
    const values = [0, 1, 2, 3, 4];
    const result = await mapPool(values, concurrency, async value => {
      peak = Math.max(peak, ++active);
      await Bun.sleep(1);
      active--;
      return value;
    });
    expect(result).toEqual(values);
    expect(peak).toBe(concurrency);
  }
  await expect(mapPool([1], 0, async value => value)).rejects.toThrow();
});

test("recorded robots HTTP and transport outcomes apply the absence-versus-unknown rule", async () => {
  const safety = await readSafety();
  const loaded = await inputs([], { harvest: { fetch_timeout_ms: 50 } });
  for (const recording of safety.robots_responses) {
    const recordings = await readRecordings();
    recordings.responses["https://news.example/robots.txt"] = [recording];
    const transport = new RecordedTransport(recordings);
    const fetcher = createPermittedFetcher(loaded.config.harvest, loaded.extraction, { transport, resolve: transport.resolve });
    const result = await fetcher.fetch("https://news.example/second");
    expect(result.failure, JSON.stringify(recording)).toBe(recording.expected);
    if (result.robots === "unknown") {
      expect(result.robots_http_status).toBe(recording.status ?? null);
      expect(result.http_status).toBeNull();
      expect(result.robots_failure).not.toBeNull();
    }
    expect(transport.requests.some(request => request.url.pathname === "/second")).toBe(recording.expected === null);
  }
});

test("DNS rebinding or a pending DNS request cannot bypass safe target checks or deadline", async () => {
  const loaded = await inputs([], { harvest: { fetch_timeout_ms: 50 } });
  const transport = new RecordedTransport(await readRecordings());
  const addresses = transport.recordings.addresses["mixed.example"];
  if (!addresses?.[0] || !addresses[1]) throw new Error("recorded mixed addresses missing");
  const publicAddress = addresses[0], privateAddress = addresses[1];
  let resolutions = 0;
  const fetcher = createPermittedFetcher(loaded.config.harvest, loaded.extraction, {
    transport,
    resolve: async () => [++resolutions === 1 ? publicAddress : privateAddress],
  });
  expect((await fetcher.fetch("https://news.example/second")).failure).toBe("robots-unknown");
  expect(transport.requests).toEqual([]);
  const pending = createPermittedFetcher(loaded.config.harvest, loaded.extraction, {
    transport, resolve: () => new Promise(() => {}),
  });
  expect((await pending.fetch("https://news.example/second")).failure).toBe("timeout");
});

test("existing byte controls reject a complete oversized recorded body without losing observed status", async () => {
  const loaded = await inputs([], { extraction: { max_body_bytes: 1024 } });
  const transport = new RecordedTransport(await readRecordings());
  const fetcher = createPermittedFetcher(loaded.config.harvest, loaded.extraction, { transport, resolve: transport.resolve });
  const result = await fetcher.fetch("https://news.example/second");
  expect(result).toMatchObject({ body: null, failure: "body-too-large", http_status: 200 });
  expect(transport.requests.every(request => request.max_body_bytes === 1024)).toBe(true);
});
