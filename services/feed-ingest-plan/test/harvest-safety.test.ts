/** Exercise recorded address, sanitization and target-request failure boundaries. */
import { expect, test } from "bun:test";
import { createCandidateId, FeedUrlExclusionSchema } from "@idhazh/common-contracts";
import { sanitizeText, SANITIZER_VERSION } from "../src/harvest-feeds/sanitize-text";
import { isPublicAddress, validateTargetName } from "../src/harvest-feeds/safe-target";
import { createSourceFetcher } from "../src/harvest-feeds/fetch-source";
import { mapPool } from "../src/harvest-feeds/harvest-pool";
import { matchUrlExclusion } from "../src/harvest-feeds/url-exclusions";
import { fetchDiagnostics } from "../src/harvest-feeds/fetch-diagnostics";
import { RecordedTransport, context, inputs, readHeaderRecovery, readRecordings, readSafety, readUrlProtocol, source } from "./harvest-recordings";
import { harvestFeeds } from "../src/harvest-feeds/harvest-pool";
import { recordHarvestObservations } from "./observation-recordings";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { deriveArticleIdentity } from "../src/harvest-feeds/article-identity";
import { deriveFeedIdentity } from "../src/harvest-feeds/feed-identity";
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
  const loaded = await inputs([source()]);
  const unsafeTransport = new RecordedTransport(await readRecordings());
  const fetcher = createSourceFetcher(loaded.config.harvest, loaded.extraction,
    { transport: unsafeTransport });
  for (const target of safety.unsafe_targets) {
    expect((await fetcher.fetch(target)).failure).toBe("unsafe-target");
  }
  expect(unsafeTransport.requests).toEqual([]);
  const fixture = await readUrlProtocol();
  for (const kind of ["article", "feed"] as const) for (const vector of fixture.allowed) {
    const transport = new RecordedTransport(await readRecordings());
    const derive = kind === "article" ? deriveArticleIdentity : deriveFeedIdentity;
    const identity = derive(vector.offered);
    const fetcher = createSourceFetcher(loaded.config.harvest, loaded.extraction, { transport });
    try {
      const result = await fetcher.fetch(vector.offered, undefined, kind);
      expect(result.failure, vector.offered).toBeNull();
      expect(transport.requests[0]?.url.href).toBe(identity.canonical_url);
      expect(transport.requests.at(-1)?.url.href).toBe(vector.target);
      expect(identity.canonical_url).toBe(vector.canonical_url);
      expect(derive(vector.offered)).toEqual(identity);
      expect(transport.requests.some(request => request.url.hostname === "127.0.0.1")).toBe(false);
    } finally { await fetcher.close(); }
  }
  for (const vector of fixture.refused) {
    const transport = new RecordedTransport(await readRecordings());
    const identity = deriveArticleIdentity(vector.offered);
    const fetcher = createSourceFetcher(loaded.config.harvest, loaded.extraction, { transport });
    try {
      const result = await harvestArticle({
        candidate_id: createCandidateId(),
        source: sourceSnapshot(loaded.sources[0]!),
        entry: { entry_ordinal: 0, title: "Refused target", link: vector.offered, categories: [], author: null, published_at: null },
      }, loaded, fetcher, context());
      expect(result.rejection).toMatchObject({
        drop_reason: "FETCH_FAILED", canonical_url: identity.canonical_url, url_key: identity.url_key,
      });
      expect(result.observation.fetch_failure, vector.offered).toBe(vector.failure);
      expect(transport.requests.map(request => request.url.href)).toEqual(vector.requests);
    } finally { await fetcher.close(); }
  }
  for (const vector of fixture.media) {
    const transport = new RecordedTransport(await readRecordings());
    const identity = deriveArticleIdentity(vector.offered);
    expect(identity.canonical_url).toBe(vector.canonical_url);
    const matched = matchMediaArticle(vector.offered, identity.canonical_url, [], loaded.config);
    expect(matched !== null).toBe(vector.excluded);
    const article = await harvestArticle({
      candidate_id: createCandidateId(),
      source: sourceSnapshot(loaded.sources[0]!),
      entry: { entry_ordinal: 0, title: null, link: vector.offered, categories: [], author: null, published_at: null },
    }, loaded, createSourceFetcher(loaded.config.harvest, loaded.extraction, { transport }), context());
    if (vector.excluded) {
      expect(article.rejection).toMatchObject({
        drop_reason: "MEDIA_CONTENT", canonical_url: vector.canonical_url, url_key: identity.url_key, title: null,
      });
      expect(transport.requests).toEqual([]);
    } else {
      expect(article.candidate).toMatchObject({ canonical_url: vector.canonical_url, url_key: identity.url_key });
      expect(transport.requests.at(-1)?.url.href).toBe(vector.canonical_url);
    }
  }
});

test("malformed article inputs have no invented address or hash and make no request", async () => {
  const loaded = await inputs();
  const transport = new RecordedTransport(await readRecordings());
  const fetcher = createSourceFetcher(loaded.config.harvest, loaded.extraction, { transport });
  try {
    for (const link of ["not-a-url", "https://[invalid-host/"]) {
      const candidate_id = createCandidateId();
      const result = await harvestArticle({
        candidate_id,
        source: sourceSnapshot(loaded.sources[0]!),
        entry: { entry_ordinal: 0, title: "Malformed address", link, categories: [], author: null, published_at: null },
      }, loaded, fetcher, context());
      expect(result.rejection).toMatchObject({
        drop_reason: "MISSING_REQUIRED_FIELDS", candidate_id, canonical_url: null, url_key: null,
      });
      expect(result.observation.candidate_id).toBe(candidate_id);
    }
    expect(transport.requests).toEqual([]);
  } finally { await fetcher.close(); }
});

test("structured URL and media exclusions bind configured policy", async () => {
  const loaded = await inputs();
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
  expect(matchMediaOffer(
    "https://businesstoday.in/technology/news/story/iphone-air-2-apple-may-finally-address-one-of-the-biggest-concerns-with-its-slim-iphone-564691-2026-10-30",
    [], media,
  )).toBeNull();
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
});

test("feed and article redirects dispatch only validated target hops", async () => {
  const loaded = await inputs([]);
  for (const kind of ["feed", "article"] as const) {
    const transport = new RecordedTransport(await readRecordings());
    const fetcher = createSourceFetcher(loaded.config.harvest, loaded.extraction, { transport });
    try {
      expect(await fetcher.fetch("https://news.example/unsafe-redirect", undefined, kind))
        .toMatchObject({ failure: "unsafe-target", http_status: 302 });
      expect(await fetcher.fetch("https://news.example/cross-origin-redirect", undefined, kind))
        .toMatchObject({ failure: null, http_status: 200 });
      expect((await fetcher.fetch("https://news.example/safe-redirect", undefined, kind)).http_status).toBe(200);
      expect(await fetcher.fetch("https://news.example/loop", undefined, kind))
        .toMatchObject({ failure: "redirect-loop", http_status: 302 });
      expect(transport.requests.map(request => request.url.href)).toEqual([
        "https://news.example/unsafe-redirect",
        "https://news.example/cross-origin-redirect", "https://atom.example/entry",
        "https://news.example/safe-redirect", "https://news.example/second", "https://news.example/loop",
      ]);
    } finally { await fetcher.close(); }
  }
});

test("permanent statuses do not retry; transient statuses use existing retry controls", async () => {
  const loaded = await inputs([source()], {
    extraction: { max_retries: 1, backoff_initial_seconds: 0.01 },
  });
  const transport = new RecordedTransport(await readRecordings());
  const fetcher = createSourceFetcher(loaded.config.harvest, loaded.extraction, { transport });
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
        transport: interruptedTransport,
      })).rejects.toThrow("completed work is retained");
      expect(interruptedTransport.requests.length).toBeGreaterThanOrEqual(interruption === "FEED_FETCH_COMPLETED" ? 1 : 2);
      expect(facts.filter(row => row.operation === "attempt")
        .reduce((count, row) => count + row.dispatched_request_count!, 0)).toBe(interruptedTransport.requests.length);
      expect(facts.find(row => row.request_phase === "target")).toMatchObject({
        outcome: "success", http_status: 200, dispatched_request_count: 1, occurred_at: "2026-10-21T23:59:59Z",
      });
      expect(facts.find(row => row.operation === "fetch")).toMatchObject({
        outcome: "success", attribution: null, failure_code: null,
      });
      expect(facts.every(row => !("article_text" in row))).toBe(true);
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
  const retryFetcher = createSourceFetcher(
    loaded.config.harvest, loaded.extraction,
    { transport: retryTransport },
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
  const timeoutTransport = new RecordedTransport(await readRecordings());
  const exhausted = await createSourceFetcher(
    { ...loaded.config.harvest, fetch_timeout_ms: 30,
      request_headers: { ...loaded.config.harvest.request_headers, secondary: null } }, loaded.extraction,
    { transport: timeoutTransport },
  ).fetch("https://news.example/timeout");
  expect(exhausted.failure).toBe("timeout");
  expect(timeoutTransport.requests.filter(request => request.url.pathname === "/timeout").length).toBeLessThanOrEqual(2);
  expect(exhausted.attempts!.every((attempt, index) => attempt.sequence === index && attempt.duration_ms >= 0)).toBe(true);
  const safety = await readSafety();
  const limited = safety.rate_limit_response;
  transport.recordings.responses["https://news.example/error"] = [limited];
  expect(fetchDiagnostics(await fetcher.fetch("https://news.example/error"), 0)).toMatchObject({
    http_status: 429, failure_code: "http_rate_limited",
  });
  const fixture = await readHeaderRecovery();
  const profileInputs = await inputs([]);
  const target = "https://news.example/second";
  const timeoutRecordings = await readRecordings();
  timeoutRecordings.responses[target] = fixture.primary_timeouts;
  const recoveredTimeoutTransport = new RecordedTransport(timeoutRecordings);
  const recoveredTimeout = await createSourceFetcher(
    loaded.config.harvest, loaded.extraction,
    { transport: recoveredTimeoutTransport },
  ).fetch(target);
  expect(recoveredTimeout.failure).toBeNull();
  expect(recoveredTimeout.body).toBe(timeoutRecordings.bodies.article);
  expect(recoveredTimeout.attempts?.filter(attempt => attempt.phase === "target").map(attempt => ({
    retry: attempt.retry, failure: attempt.failure,
  }))).toEqual([{ retry: 0, failure: "timeout" }, { retry: 1, failure: "timeout" }, { retry: 0, failure: null }]);
  const timeoutRequests = recoveredTimeoutTransport.requests.filter(request => request.url.href === target);
  expect(timeoutRequests).toHaveLength(3);
  expect(timeoutRequests[0]?.profile).toEqual(timeoutRequests[1]?.profile);
  expect(timeoutRequests[1]?.profile).not.toEqual(timeoutRequests[2]?.profile);
  for (const vector of fixture.recoveries) {
    const recordings = await readRecordings();
    recordings.responses[target] = vector.responses;
    const transport = new RecordedTransport(recordings);
    const result = await createSourceFetcher(profileInputs.config.harvest, profileInputs.extraction,
      { transport }).fetch(target);
    expect(result.failure, vector.name).toBeNull();
    expect(result.body).toBe(recordings.bodies.article);
    const requests = transport.requests.filter(request => request.url.href === target);
    for (const [index, profile] of [
      profileInputs.config.harvest.request_headers.primary, profileInputs.config.harvest.request_headers.secondary,
    ].entries()) {
      if (profile === null) throw new Error("Recorded recovery requires the configured secondary profile");
      expect(requests[index]?.profile).toEqual(profile);
    }
    expect(requests[0]?.profile.browser).not.toBe(requests[1]?.profile.browser);
    expect(transport.requests.map(request => request.url.href)).toEqual([target, target]);
    expect(result.attempts?.filter(attempt => attempt.phase === "target").map(attempt => attempt.retry)).toEqual([0, 0]);
  }
  for (const vector of fixture.permanent_failures) {
    const recordings = await readRecordings();
    recordings.responses[target] = vector.responses;
    const transport = new RecordedTransport(recordings);
    const result = await createSourceFetcher(profileInputs.config.harvest, profileInputs.extraction,
      { transport }).fetch(target);
    expect(result.failure, vector.name).toBe("http");
    expect(transport.requests.filter(request => request.url.href === target)).toHaveLength(1);
  }
  const recordings = await readRecordings();
  recordings.responses[target] = [{ status: 200, body: fixture.short_content }, { status: 403, body: "" }];
  const retainedTransport = new RecordedTransport(recordings);
  const retained = await createSourceFetcher(profileInputs.config.harvest, profileInputs.extraction,
    { transport: retainedTransport }).fetch(target);
  expect(retained).toMatchObject({ body: fixture.short_content, http_status: 200, failure: null });
  expect(retained.response_evidence).toMatchObject({
    decoded_bytes: Buffer.byteLength(fixture.short_content), request_profile: "firefox",
  });
  expect(retained.attempts?.filter(attempt => attempt.phase === "target").map(attempt =>
    [attempt.http_status, attempt.request_profile])).toEqual([[200, "firefox"], [403, "chrome"]]);
  const redirectRecordings = await readRecordings();
  redirectRecordings.responses[target] = [{ status: 200, body: fixture.short_content }, fixture.short_redirect];
  const redirectTransport = new RecordedTransport(redirectRecordings);
  const redirectCounts: number[] = [];
  const redirected = await createSourceFetcher(profileInputs.config.harvest, profileInputs.extraction,
    { transport: redirectTransport }).fetch(target,
    async measurement => { redirectCounts.push(measurement.dispatched_request_count); });
  expect(redirected).toMatchObject({ body: fixture.short_content, http_status: 200, failure: null });
  expect(redirected.response_evidence).toMatchObject({
    decoded_bytes: Buffer.byteLength(fixture.short_content), request_profile: "firefox",
  });
  expect(redirected.attempts?.filter(attempt => attempt.phase === "target").map(attempt => attempt.http_status))
    .toEqual([200, 302, 404]);
  expect(redirectCounts.reduce((sum, count) => sum + count, 0)).toBe(redirectTransport.requests.length);
  redirectRecordings.responses["https://news.example/not-found"] = [{ error: "ECONNRESET" }];
  const failedRedirectTransport = new RecordedTransport(redirectRecordings);
  const failedRedirect = await createSourceFetcher(profileInputs.config.harvest, profileInputs.extraction,
    { transport: failedRedirectTransport }).fetch(target);
  expect(failedRedirect).toMatchObject({ body: fixture.short_content, http_status: 200, failure: null });
  expect(failedRedirect.response_evidence?.request_profile).toBe("firefox");
  expect(failedRedirect.failed_url).toBeNull();
  for (const [location, failure] of [
    ["http://127.0.0.1/secret", "unsafe-target"],
    ["https://local.internal/story", "unsafe-target"],
  ] as const) {
    redirectRecordings.responses[target] = [
      { status: 200, body: fixture.short_content }, { status: 302, body: "", location },
    ];
    const refusedTransport = new RecordedTransport(redirectRecordings);
    const refused = await createSourceFetcher(profileInputs.config.harvest, profileInputs.extraction,
      { transport: refusedTransport }).fetch(target);
    expect(refused).toMatchObject({ body: null, failure });
    expect(refusedTransport.requests.some(request => request.url.href === location)).toBe(false);
  }
  const noRecovery = new RecordedTransport(recordings);
  const disabled = await createSourceFetcher({
    ...profileInputs.config.harvest, request_headers: { ...profileInputs.config.harvest.request_headers, secondary: null },
  }, profileInputs.extraction, { transport: noRecovery }).fetch(target);
  expect(disabled.body).toBe(fixture.short_content);
  expect(noRecovery.requests.filter(request => request.url.href === target)).toHaveLength(1);
  const threshold = new RecordedTransport(recordings);
  await createSourceFetcher({
    ...profileInputs.config.harvest,
    request_headers: { ...profileInputs.config.harvest.request_headers, recovery_min_body_bytes: 0 },
  }, profileInputs.extraction, { transport: threshold }).fetch(target);
  expect(threshold.requests.filter(request => request.url.href === target)).toHaveLength(1);
  const feedTransport = new RecordedTransport(recordings);
  const shortFeed = await createSourceFetcher(profileInputs.config.harvest, profileInputs.extraction,
    { transport: feedTransport }).fetch(target, undefined, "feed");
  expect(shortFeed).toMatchObject({ body: fixture.short_content, http_status: 200, failure: null });
  expect(feedTransport.requests.filter(request => request.url.href === target)).toHaveLength(1);
  const retryRecordings = await readRecordings();
  retryRecordings.responses[target] = [
    { status: 503, body: "" }, { status: 503, body: "" }, { status: 200, fixture: "article" },
  ];
  const retried = new RecordedTransport(retryRecordings);
  const profileRecovered = await createSourceFetcher(profileInputs.config.harvest, { ...profileInputs.extraction, max_retries: 1 },
    { transport: retried }).fetch(target);
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

test("DNS and TLS failures retain only recognized target codes", async () => {
  const safety = await readSafety();
  const loaded = await inputs([]);
  for (const recording of safety.target_errors) {
    const recordings = await readRecordings();
    const target = "https://news.example/second";
    recordings.responses[target] = [recording];
    const transport = new RecordedTransport(recordings);
    const fetcher = createSourceFetcher({
      ...loaded.config.harvest,
      request_headers: { ...loaded.config.harvest.request_headers, secondary: null },
    }, loaded.extraction, { transport });
    try {
      const result = await fetcher.fetch(target);
      expect(fetchDiagnostics(result, 0), recording.error).toMatchObject({
        http_status: null, fetch_failure: recording.failure, failure_code: "network_error",
        error_code: recording.error_code,
      });
      expect(result.attempts!.find(attempt => attempt.phase === "target")).toMatchObject({
        failure: recording.failure, error_code: recording.error_code,
      });
      expect(transport.requests.map(request => request.url.href)).toEqual([target]);
    } finally { await fetcher.close(); }
  }
});

test("external cancellation during a target request prevents another attempt", async () => {
  const loaded = await inputs([], { extraction: { max_retries: 1 } });
  const transport = new RecordedTransport(await readRecordings());
  const fetcher = createSourceFetcher(loaded.config.harvest, loaded.extraction, { transport });
  const controller = new AbortController();
  transport.on_request = () => controller.abort(new DOMException("recorded external cancellation", "AbortError"));
  try {
    const result = await fetcher.fetch("https://news.example/timeout", undefined, "article", controller.signal);
    expect(result).toMatchObject({ body: null, failure: "timeout" });
    expect(transport.requests.map(request => request.url.href)).toEqual(["https://news.example/timeout"]);
  } finally { await fetcher.close(); }
});

test("existing byte controls reject a complete oversized recorded body without losing observed status", async () => {
  const loaded = await inputs([], { extraction: { max_body_bytes: 1024 } });
  const transport = new RecordedTransport(await readRecordings());
  const fetcher = createSourceFetcher(loaded.config.harvest, loaded.extraction, { transport });
  const result = await fetcher.fetch("https://news.example/second");
  expect(result).toMatchObject({ body: null, failure: "body-too-large", http_status: 200 });
  expect(fetchDiagnostics(result, 0).body_limit).toEqual({
    configured_limit_bytes: 1024,
    observed_at_least_bytes: Buffer.byteLength((await readRecordings()).bodies.article),
  });
  expect(transport.requests.every(request => request.max_body_bytes === 1024)).toBe(true);
});
