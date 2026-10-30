/** Exercise recorded robots, address, sanitization and request-failure boundaries. */
import { expect, test } from "bun:test";
import { FeedUrlExclusionSchema } from "@idhazh/common-contracts";
import { sanitizeText, SANITIZER_VERSION } from "../src/harvest-feeds/sanitize-text";
import { isPublicAddress, validateTargetName } from "../src/harvest-feeds/safe-target";
import { createPermittedFetcher, crawlerProduct, parseRobots, robotsPermits } from "../src/harvest-feeds/robots-policy";
import { mapPool } from "../src/harvest-feeds/harvest-pool";
import { matchUrlExclusion } from "../src/harvest-feeds/url-exclusions";
import { fetchDiagnostics } from "../src/harvest-feeds/fetch-diagnostics";
import { RecordedTransport, context, inputs, readHeaderRecovery, readRecordings, readSafety, source } from "./harvest-recordings";
import { harvestFeeds } from "../src/harvest-feeds/harvest-pool";
import { recordHarvestObservations } from "./observation-recordings";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { z } from "zod";
import { deriveArticleIdentity } from "../src/harvest-feeds/article-identity";
import { matchMediaArticle, matchMediaOffer } from "../src/harvest-feeds/media-filter";
import { harvestArticle } from "../src/harvest-feeds/harvest-article";
import { sourceSnapshot } from "../src/harvest-feeds/load-harvest-inputs";

test("recorded sanitizer vectors match sanitizer-3, keep prose and are idempotent", async () => {
  const fixture = await readSafety();
  expect(SANITIZER_VERSION).toBe(fixture.sanitizer_version);
  for (const vector of fixture.sanitizer) {
    expect(sanitizeText(vector.input)).toBe(vector.expected);
    expect(sanitizeText(sanitizeText(vector.input))).toBe(vector.expected);
  }
});

test("literal, encoded and named unsafe addresses fail before transport", async () => {
  const safety = await readSafety();
  for (const url of safety.unsafe_targets) expect(() => validateTargetName(url), url).toThrow();
  expect(isPublicAddress("93.184.216.34")).toBe(true);
  expect(isPublicAddress("2606:4700:4700::1111")).toBe(true);
  const loaded = await inputs([source()], { harvest: { article_robots_policy: "enforce" } });
  const unsafeTransport = new RecordedTransport(await readRecordings());
  const fetcher = createPermittedFetcher(loaded.config.harvest, loaded.extraction,
    { transport: unsafeTransport, resolve: unsafeTransport.resolve });
  for (const target of [...safety.unsafe_targets, "https://inward.example/feed.xml", "https://mixed.example/feed.xml"]) {
    expect((await fetcher.fetch(target)).failure).toBe("unsafe-target");
  }
  expect(unsafeTransport.requests).toEqual([]);
  const fixture = z.object({
    allowed: z.array(z.object({ offered: z.string(), target: z.string(), canonical_url: z.string() })),
    refused: z.array(z.object({
      offered: z.string(), failure: z.enum(["unsafe-target", "robots-denied", "robots-unknown"]),
      requests: z.array(z.string()),
    })),
    media: z.array(z.object({ offered: z.string(), canonical_url: z.string(), excluded: z.boolean() })),
  }).parse(await Bun.file(new URL(
    "../../../tests/fixtures/feed-ingest-plan/harvest-url-cleanup.json", import.meta.url,
  )).json());
  for (const vector of fixture.allowed) {
    const transport = new RecordedTransport(await readRecordings());
    const identity = deriveArticleIdentity(vector.offered, loaded.config.harvest);
    const result = await createPermittedFetcher(loaded.config.harvest, loaded.extraction,
      { transport, resolve: transport.resolve }).fetch(vector.offered);
    expect(result.failure, vector.offered).toBeNull();
    expect(transport.requests.at(-1)?.url.href).toBe(vector.target);
    expect(identity.canonical_url).toBe(vector.canonical_url);
    expect(deriveArticleIdentity(vector.offered, loaded.config.harvest)).toEqual(identity);
    expect(transport.requests.some(request => request.url.hostname === "www.google.com")).toBe(false);
  }
  for (const vector of fixture.refused) {
    const transport = new RecordedTransport(await readRecordings());
    const result = await createPermittedFetcher(loaded.config.harvest, loaded.extraction,
      { transport, resolve: transport.resolve }).fetch(vector.offered);
    expect(result.failure, vector.offered).toBe(vector.failure);
    expect(transport.requests.map(request => request.url.href)).toEqual(vector.requests);
  }
  for (const vector of fixture.media) {
    const transport = new RecordedTransport(await readRecordings());
    const identity = deriveArticleIdentity(vector.offered, loaded.config.harvest);
    expect(identity.canonical_url).toBe(vector.canonical_url);
    const matched = matchMediaArticle(vector.offered, identity.canonical_url, [], loaded.config);
    expect(matched !== null).toBe(vector.excluded);
    const article = await harvestArticle({
      source: sourceSnapshot(loaded, loaded.sources[0]!),
      entry: { entry_ordinal: 0, title: null, link: vector.offered, categories: [], author: null, published_at: null },
    }, loaded, createPermittedFetcher(loaded.config.harvest, loaded.extraction, { transport, resolve: transport.resolve }), context());
    if (vector.excluded) {
      expect(article.rejection).toMatchObject({
        drop_reason: "MEDIA_CONTENT", canonical_url: vector.canonical_url, url_key: identity.url_key, title: null,
      });
      expect(transport.requests).toEqual([]);
    } else {
      expect(article.candidate).toMatchObject({ canonical_url: vector.canonical_url, url_key: identity.url_key });
      expect(transport.requests.at(-1)?.url.href).toBe("https://news.example/second");
    }
  }
  const vector = fixture.allowed[0]!;
  const recordings = await readRecordings();
  recordings.responses[vector.offered] = [{ status: 200, fixture: "article" }];
  const transport = new RecordedTransport(recordings);
  expect((await createPermittedFetcher({ ...loaded.config.harvest, tidy_urls: false }, loaded.extraction,
    { transport, resolve: transport.resolve }).fetch(vector.offered)).failure).toBeNull();
  expect(transport.requests.at(-1)?.url.href).toBe("https://news.example/second");
});

test("recorded robots rules and structured URL exclusions bind configured policy", async () => {
  const loaded = await inputs();
  const agent = loaded.config.harvest.user_agent;
  const fixture = await readSafety();
  expect(loaded.config.harvest.url_exclusions).toEqual(fixture.url_exclusions);
  for (const rule of fixture.url_exclusions) expect(FeedUrlExclusionSchema.safeParse(rule).success).toBe(true);
  for (const rule of fixture.invalid_url_exclusions) expect(FeedUrlExclusionSchema.safeParse(rule).success).toBe(false);
  for (const vector of fixture.url_exclusion_cases) {
    const matched = matchUrlExclusion(vector.url, vector.rules ?? fixture.url_exclusions);
    expect(matched !== undefined, vector.name).toBe(vector.expected);
    if (matched !== undefined) expect(vector.rules ?? fixture.url_exclusions).toContainEqual(matched);
  }
  const media = loaded.config.content_filters.media;
  for (const rule of media.url_rules) {
    for (const url of [
      `https://${rule.host}${rule.path_prefix}`,
      `https://child.${rule.host}${rule.path_prefix === "/" ? "/story" : `${rule.path_prefix}/story`}`,
    ]) expect(matchMediaOffer(url, [], media)?.media_match).toBe("url");
    for (const url of [
      `https://${rule.host}.news.example${rule.path_prefix}`,
      `https://news.example/${rule.host}${rule.path_prefix}?next=https://${rule.host}${rule.path_prefix}`,
    ]) expect(matchMediaOffer(url, [], media)).toBeNull();
    if (rule.path_prefix !== "/") {
      expect(matchMediaOffer(`https://${rule.host}${rule.path_prefix}ing`, [], media)).toBeNull();
    }
  }
  expect(matchMediaOffer("https://news.example/story", [" AuDiO/mpeg "], media))
    .toMatchObject({ media_match: "enclosure", matched_media_type_prefix: "audio/" });
  expect(matchMediaOffer("https://news.example/story", ["image/jpeg"], media)).toBeNull();
  expect(matchMediaOffer("https://news.example/story", ["audio/mpeg"], { ...media, enabled: false })).toBeNull();
  expect(matchMediaOffer("https://news.example/story", ["audio/mpeg"], { ...media, enclosure_type_prefixes: ["video/"] })).toBeNull();
  expect(matchMediaOffer("https://news.example/story", [], {
    ...media, url_rules: [{ host: "news.example", path_prefix: "/story", include_subdomains: false }],
  })?.media_match).toBe("url");
  for (const recording of fixture.robots) {
    const document = parseRobots(recording.body, "https://news.example");
    for (const path of recording.allowed) expect(robotsPermits(document, `https://news.example${path}`, agent), `${recording.name} ${path}`).toBe(true);
    for (const path of recording.denied) expect(robotsPermits(document, `https://news.example${path}`, agent), `${recording.name} ${path}`).toBe(false);
  }
});

test("denied or unknown permission never requests the target; robots cache is per normalized origin and run", async () => {
  const loaded = await inputs([], { harvest: { article_robots_policy: "enforce" } });
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
  const loaded = await inputs([], { harvest: { article_robots_policy: "enforce" } });
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
  const loaded = await inputs([source()], {
    harvest: { article_robots_policy: "enforce" },
    extraction: { max_retries: 1, backoff_initial_seconds: 0.01 },
  });
  const transport = new RecordedTransport(await readRecordings());
  const fetcher = createPermittedFetcher(loaded.config.harvest, loaded.extraction, { transport, resolve: transport.resolve });
  expect(fetchDiagnostics(await fetcher.fetch("https://news.example/not-found"), 0)).toMatchObject({
    http_status: 404, fetch_failure: "http", failure_code: "http_client_error",
  });
  expect((await fetcher.fetch("https://news.example/retry")).http_status).toBe(200);
  expect(transport.requests.filter(request => request.url.pathname === "/not-found")).toHaveLength(1);
  expect(transport.requests.filter(request => request.url.pathname === "/retry")).toHaveLength(2);
  for (const interruption of ["FEED_FETCH_COMPLETED", "ARTICLE_HARVEST_COMPLETED"] as const) {
    const directory = await mkdtemp(join(tmpdir(), "interrupted-fetch-facts-"));
    try {
      const interruptedContext = context();
      const facts = recordHarvestObservations(interruptedContext);
      const interruptedTransport = new RecordedTransport(await readRecordings());
      // A failing progress consumer cannot erase work already streamed to the counter boundary.
      interruptedContext.progress = event => {
        if (event === interruption) throw new Error("progress destination interrupted");
      };
      await expect(harvestFeeds(await inputs(), interruptedContext, {
        transport: interruptedTransport, resolve: interruptedTransport.resolve,
      })).rejects.toThrow("completed work is retained");
      expect(interruptedTransport.requests.length).toBeGreaterThanOrEqual(2);
      expect(facts.filter(row => row.operation === "attempt")
        .reduce((count, row) => count + row.dispatched_request_count!, 0)).toBe(interruptedTransport.requests.length);
      expect(facts.find(row => row.request_phase === "target")).toMatchObject({
        outcome: "success", http_status: 200, dispatched_request_count: 1, occurred_at: "2026-10-21T23:59:59Z",
      });
      expect(facts.find(row => row.operation === "fetch")).toMatchObject({
        outcome: "success", attribution: null, failure_code: null,
      });
      expect(facts.every(row => !("event_id" in row) && !("article_text" in row))).toBe(true);
    } finally { await rm(directory, { recursive: true, force: true }); }
  }
  expect(fetchDiagnostics(await fetcher.fetch("https://missing.example/story"), 0)).toMatchObject({
    fetch_failure: "dns", error_code: "ENOTFOUND", failure_code: "network_error",
  });
  expect(fetchDiagnostics(await fetcher.fetch("https://news.example/network-error"), 0)).toMatchObject({
    fetch_failure: "network", error_code: "ECONNRESET", failure_code: "network_error",
  });
  expect(fetchDiagnostics(await fetcher.fetch("https://news.example/error"), 0)).toMatchObject({
    http_status: 503, failure_code: "http_server_error",
  });
  const replay = await readRecordings();
  const success = replay.responses["https://news.example/second"]![0]!;
  replay.responses["https://news.example/timeout"] = [{ error: "timeout" }, success];
  replay.responses["https://news.example/network-error"] = [{ error: "ECONNRESET" }, success];
  const retryTransport = new RecordedTransport(replay);
  const retryFetcher = createPermittedFetcher(
    loaded.config.harvest, loaded.extraction,
    { transport: retryTransport, resolve: retryTransport.resolve },
  );
  const recovered = await retryFetcher.fetch("https://news.example/timeout");
  expect(recovered.http_status).toBe(200);
  expect(recovered.attempts!.filter(attempt => attempt.phase === "target").map(attempt => ({
    retry: attempt.retry, failure: attempt.failure,
  }))).toEqual([{ retry: 0, failure: "timeout" }, { retry: 1, failure: null }]);
  const targetAttempts = recovered.attempts!.filter(attempt => attempt.phase === "target");
  expect(targetAttempts[0]!.backoff_ms).toBeGreaterThan(0);
  expect(targetAttempts[0]!.retry_total_ms).toBe(0);
  const waited = targetAttempts[0]!.backoff_ms;
  if (waited === null) throw new Error("Current fetch must measure its actual backoff");
  expect(targetAttempts[1]!.retry_total_ms).toBeGreaterThanOrEqual(
    targetAttempts[0]!.duration_ms + waited - 1,
  );
  expect(targetAttempts[1]!.backoff_ms).toBe(0);
  expect((await retryFetcher.fetch("https://news.example/network-error")).http_status).toBe(200);
  let resolutions = 0;
  const dnsRetry = createPermittedFetcher(loaded.config.harvest, loaded.extraction, {
    transport: retryTransport,
    resolve: async hostname => {
      if (resolutions++ === 0) throw Object.assign(new Error("recorded transient DNS"), { code: "EAI_AGAIN" });
      return retryTransport.resolve(hostname);
    },
  });
  const dnsRecovered = await dnsRetry.fetch("https://news.example/second");
  expect(dnsRecovered.http_status).toBe(200);
  expect(dnsRecovered.attempts!.slice(0, 2).map(attempt => ({
    phase: attempt.phase, retry: attempt.retry, failure: attempt.failure,
  }))).toEqual([
    { phase: "validation", retry: 0, failure: "dns" },
    { phase: "validation", retry: 1, failure: null },
  ]);
  const timeoutTransport = new RecordedTransport(await readRecordings());
  const exhausted = await createPermittedFetcher(
    { ...loaded.config.harvest, fetch_timeout_ms: 30,
      request_headers: { ...loaded.config.harvest.request_headers, secondary: null } }, loaded.extraction,
    { transport: timeoutTransport, resolve: timeoutTransport.resolve },
  ).fetch("https://news.example/timeout");
  expect(exhausted.failure).toBe("timeout");
  expect(timeoutTransport.requests.filter(request => request.url.pathname === "/timeout").length).toBeLessThanOrEqual(2);
  expect(exhausted.attempts!.every((attempt, index) => attempt.sequence === index && attempt.duration_ms >= 0)).toBe(true);
  // Replay the existing rate-limit protocol recording as the target response too.
  const safety = await readSafety();
  const limited = safety.robots_responses.find(response => response.status === 429);
  if (!limited) throw new Error("Expected the recorded rate-limit response");
  transport.recordings.responses["https://news.example/error"] = [limited];
  expect(fetchDiagnostics(await fetcher.fetch("https://news.example/error"), 0)).toMatchObject({
    http_status: 429, failure_code: "http_rate_limited",
  });
  const fixture = await readHeaderRecovery();
  const profileInputs = await inputs([], { harvest: { article_robots_policy: "enforce" } });
  const target = "https://news.example/second";
  const timeoutRecordings = await readRecordings();
  timeoutRecordings.responses[target] = fixture.primary_timeouts;
  const recoveredTimeoutTransport = new RecordedTransport(timeoutRecordings);
  const recoveredTimeout = await createPermittedFetcher(
    loaded.config.harvest, loaded.extraction,
    { transport: recoveredTimeoutTransport, resolve: recoveredTimeoutTransport.resolve },
  ).fetch(target);
  expect(recoveredTimeout.failure).toBeNull();
  expect(recoveredTimeout.body).toBe(timeoutRecordings.bodies.article);
  expect(recoveredTimeout.attempts?.filter(attempt => attempt.phase === "target").map(attempt => ({
    retry: attempt.retry, failure: attempt.failure,
  }))).toEqual([{ retry: 0, failure: "timeout" }, { retry: 1, failure: "timeout" }, { retry: 0, failure: null }]);
  const timeoutRequests = recoveredTimeoutTransport.requests.filter(request => request.url.href === target);
  expect(timeoutRequests).toHaveLength(3);
  expect(timeoutRequests[0]?.user_agent).toBe(timeoutRequests[1]?.user_agent);
  expect(timeoutRequests[1]?.user_agent).not.toBe(timeoutRequests[2]?.user_agent);
  for (const vector of fixture.recoveries) {
    const recordings = await readRecordings();
    recordings.responses[target] = vector.responses;
    const transport = new RecordedTransport(recordings);
    const result = await createPermittedFetcher(profileInputs.config.harvest, profileInputs.extraction,
      { transport, resolve: transport.resolve }).fetch(target);
    expect(result.failure, vector.name).toBeNull();
    expect(result.body).toBe(recordings.bodies.article);
    const requests = transport.requests.filter(request => request.url.href === target);
    for (const [index, profile] of [
      profileInputs.config.harvest.request_headers.primary, profileInputs.config.harvest.request_headers.secondary,
    ].entries()) {
      if (profile === null) throw new Error("Recorded recovery requires the configured secondary profile");
      const userAgent = `${profileInputs.config.harvest.user_agent} ${profile["user-agent"]}`;
      expect(requests[index]?.headers).toEqual({ ...profile, "user-agent": userAgent });
      expect(requests[index]?.user_agent).toBe(userAgent);
      expect(crawlerProduct(userAgent)).toBe(crawlerProduct(profileInputs.config.harvest.user_agent));
    }
    expect(requests[0]?.user_agent).not.toBe(requests[1]?.user_agent);
    expect(transport.requests.filter(request => request.url.pathname === "/robots.txt").map(request => request.headers))
      .toEqual([{ "user-agent": profileInputs.config.harvest.user_agent }]);
    expect(result.attempts?.filter(attempt => attempt.phase === "target").map(attempt => attempt.retry)).toEqual([0, 0]);
  }
  for (const vector of fixture.permanent_failures) {
    const recordings = await readRecordings();
    recordings.responses[target] = vector.responses;
    const transport = new RecordedTransport(recordings);
    const result = await createPermittedFetcher(profileInputs.config.harvest, profileInputs.extraction,
      { transport, resolve: transport.resolve }).fetch(target);
    expect(result.failure, vector.name).toBe("http");
    expect(transport.requests.filter(request => request.url.href === target)).toHaveLength(1);
  }
  const recordings = await readRecordings();
  recordings.responses[target] = [{ status: 200, body: fixture.short_content }, { status: 403, body: "" }];
  const retainedTransport = new RecordedTransport(recordings);
  const retained = await createPermittedFetcher(profileInputs.config.harvest, profileInputs.extraction,
    { transport: retainedTransport, resolve: retainedTransport.resolve }).fetch(target);
  expect(retained).toMatchObject({ body: fixture.short_content, http_status: 200, failure: null });
  const redirectRecordings = await readRecordings();
  redirectRecordings.responses[target] = [{ status: 200, body: fixture.short_content }, fixture.short_redirect];
  const redirectTransport = new RecordedTransport(redirectRecordings);
  const redirectCounts: number[] = [];
  const redirected = await createPermittedFetcher(profileInputs.config.harvest, profileInputs.extraction,
    { transport: redirectTransport, resolve: redirectTransport.resolve }).fetch(target,
    async measurement => { redirectCounts.push(measurement.dispatched_request_count); });
  expect(redirected).toMatchObject({ body: fixture.short_content, http_status: 200, failure: null });
  expect(redirected.attempts?.filter(attempt => attempt.phase === "target").map(attempt => attempt.http_status))
    .toEqual([200, 302, 404]);
  expect(redirectCounts.reduce((sum, count) => sum + count, 0)).toBe(redirectTransport.requests.length);
  redirectRecordings.responses["https://news.example/not-found"] = [{ error: "ECONNRESET" }];
  const failedRedirectTransport = new RecordedTransport(redirectRecordings);
  const failedRedirect = await createPermittedFetcher(profileInputs.config.harvest, profileInputs.extraction,
    { transport: failedRedirectTransport, resolve: failedRedirectTransport.resolve }).fetch(target);
  expect(failedRedirect).toMatchObject({ body: fixture.short_content, http_status: 200, failure: null });
  for (const [location, failure] of [
    ["http://127.0.0.1/secret", "unsafe-target"],
    ["https://denied.example/story", "robots-denied"],
    ["https://unknown.example/story", "robots-unknown"],
  ] as const) {
    redirectRecordings.responses[target] = [
      { status: 200, body: fixture.short_content }, { status: 302, body: "", location },
    ];
    const refusedTransport = new RecordedTransport(redirectRecordings);
    const refused = await createPermittedFetcher(profileInputs.config.harvest, profileInputs.extraction,
      { transport: refusedTransport, resolve: refusedTransport.resolve }).fetch(target);
    expect(refused).toMatchObject({ body: null, failure });
    expect(refusedTransport.requests.some(request => request.url.href === location)).toBe(false);
  }
  const noRecovery = new RecordedTransport(recordings);
  const disabled = await createPermittedFetcher({
    ...profileInputs.config.harvest, request_headers: { ...profileInputs.config.harvest.request_headers, secondary: null },
  }, profileInputs.extraction, { transport: noRecovery, resolve: noRecovery.resolve }).fetch(target);
  expect(disabled.body).toBe(fixture.short_content);
  expect(noRecovery.requests.filter(request => request.url.href === target)).toHaveLength(1);
  const threshold = new RecordedTransport(recordings);
  await createPermittedFetcher({
    ...profileInputs.config.harvest,
    request_headers: { ...profileInputs.config.harvest.request_headers, recovery_min_body_bytes: 0 },
  }, profileInputs.extraction, { transport: threshold, resolve: threshold.resolve }).fetch(target);
  expect(threshold.requests.filter(request => request.url.href === target)).toHaveLength(1);
  const feedTransport = new RecordedTransport(recordings);
  const shortFeed = await createPermittedFetcher(profileInputs.config.harvest, profileInputs.extraction,
    { transport: feedTransport, resolve: feedTransport.resolve }).fetch(target, undefined, "feed");
  expect(shortFeed).toMatchObject({ body: fixture.short_content, http_status: 200, failure: null });
  expect(feedTransport.requests.filter(request => request.url.href === target)).toHaveLength(1);
  const retryRecordings = await readRecordings();
  retryRecordings.responses[target] = [
    { status: 503, body: "" }, { status: 503, body: "" }, { status: 200, fixture: "article" },
  ];
  const retried = new RecordedTransport(retryRecordings);
  const profileRecovered = await createPermittedFetcher(profileInputs.config.harvest, { ...profileInputs.extraction, max_retries: 1 },
    { transport: retried, resolve: retried.resolve }).fetch(target);
  expect(profileRecovered.failure).toBeNull();
  expect(profileRecovered.attempts?.filter(attempt => attempt.phase === "target").map(attempt => attempt.retry)).toEqual([0, 1, 0]);
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
  const completed: number[] = [];
  await expect(mapPool([0, 1, 2], 2, async value => {
    if (value === 0) throw new Error("recorded pool failure");
    await Bun.sleep(1);
    completed.push(value);
    return value;
  })).rejects.toThrow("completed work is retained");
  expect(completed).toEqual([1, 2]);
});

test("recorded robots HTTP and transport outcomes apply the absence-versus-unknown rule", async () => {
  const safety = await readSafety();
  const loaded = await inputs([], { harvest: { fetch_timeout_ms: 50, article_robots_policy: "enforce" } });
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
  const loaded = await inputs([], { harvest: { fetch_timeout_ms: 50, article_robots_policy: "enforce" } });
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
