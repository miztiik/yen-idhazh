/** Exercise recorded robots, address, sanitization and request-failure boundaries. */
import { expect, test } from "bun:test";
import { sanitizeText, SANITIZER_VERSION } from "../src/harvest-feeds/sanitize-text";
import { isPublicAddress, validateTargetName } from "../src/harvest-feeds/safe-target";
import { createPermittedFetcher, crawlerProduct, parseRobots, robotsPermits } from "../src/harvest-feeds/robots-policy";
import { mapPool } from "../src/harvest-feeds/harvest-pool";
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
  expect((await fetcher.fetch("https://denied.example/story")).failure).toBe("robots-denied");
  expect((await fetcher.fetch("https://unknown.example/story")).failure).toBe("robots-unknown");
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
  expect((await fetcher.fetch("https://news.example/unsafe-redirect")).failure).toBe("unsafe-target");
  expect((await fetcher.fetch("https://news.example/denied-redirect")).failure).toBe("robots-denied");
  expect((await fetcher.fetch("https://news.example/safe-redirect")).http_status).toBe(200);
  expect((await fetcher.fetch("https://news.example/loop")).failure).toBe("redirect-loop");
  expect(transport.requests.some(request => request.url.hostname === "127.0.0.1")).toBe(false);
  expect(transport.requests.some(request => request.url.href === "https://denied.example/story")).toBe(false);
});

test("permanent statuses do not retry; transient statuses use existing retry controls", async () => {
  const loaded = await inputs([source()], { extraction: { max_retries: 1 } });
  const transport = new RecordedTransport(await readRecordings());
  const fetcher = createPermittedFetcher(loaded.config.harvest, loaded.extraction, { transport, resolve: transport.resolve });
  expect((await fetcher.fetch("https://news.example/not-found")).http_status).toBe(404);
  expect((await fetcher.fetch("https://news.example/retry")).http_status).toBe(200);
  expect(transport.requests.filter(request => request.url.pathname === "/not-found")).toHaveLength(1);
  expect(transport.requests.filter(request => request.url.pathname === "/retry")).toHaveLength(2);
  expect((await fetcher.fetch("https://missing.example/story")).failure).toBe("dns");
  expect((await fetcher.fetch("https://news.example/network-error")).failure).toBe("network");
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
