/** Exercise the real request gate against generated loopback documents. */
const assert = require("node:assert/strict");
const { createServer } = require("node:http");
const { once } = require("node:events");
const { pathToFileURL } = require("node:url");
const { readFile } = require("node:fs/promises");
const { resolve } = require("node:path");
const { gzipSync, brotliCompressSync, deflateSync } = require("node:zlib");
const { parseHTML } = require("linkedom");

(async () => {
  const boundary = await import(pathToFileURL(process.argv[2]).href);
  const { createBrowserRuntime } = boundary;
  const transportMode = process.argv[3] === "transport";
  const root = resolve(__dirname, "../../..");
  const recordedArticle = await readFile(resolve(root, "tests/fixtures/feed-ingest-plan/harvest-article.html"), "utf8");
  const { document } = parseHTML(recordedArticle);
  for (const element of document.querySelectorAll("script,link,img,iframe")) element.remove();
  const articleFixture = document.toString();
  const feedFixture = await readFile(resolve(root, "tests/fixtures/feed-ingest-plan/harvest-rss.xml"), "utf8");
  const payload = Buffer.from("generated response ".repeat(300));
  const encoded = new Map([
    ["/gzip", gzipSync(payload)], ["/br", brotliCompressSync(payload)], ["/deflate", deflateSync(payload)],
  ]);
  const dispatched = [];
  const admitted = [];
  const targetTypes = [];
  const errors = [];
  let crossOrigin;
  let unsafeOrigin;
  const crossDispatched = [];
  let unsafeDispatches = 0;
  const source = createServer((request, response) => {
    const path = new URL(request.url, "http://loopback.invalid").pathname;
    dispatched.push(path);
    if (path === "/robots.txt") response.end("User-agent: *\nAllow: /\nDisallow: /robots-refused-asset\n");
    else if (path === "/feed.xml" || path === "/download.xml") {
      if (!request.headers.cookie?.includes("source_session=ok")) {
        response.writeHead(200, { "content-type": "text/html" });
        response.end("<script>document.cookie='source_session=ok; path=/'; location.reload();</script>");
      } else {
        response.writeHead(200, { "content-type": "application/rss+xml", "content-disposition": "attachment; filename=feed.xml" });
        response.end(feedFixture);
      }
    } else if (path === "/article") {
      assert(request.headers.cookie?.includes("source_session=ok"), "Execution lost its temporary cookie");
      response.writeHead(200, { "content-type": "text/html" });
      response.end("<article></article><script>fetch('/article-content?token=keep').then(r=>r.text()).then(t=>document.body.innerHTML=t)</script>");
    } else if (path === "/article-content") {
      assert(request.url.endsWith("?token=keep"), "Browser resource parameters were removed");
      response.writeHead(200, { "content-type": "text/html" }).end(articleFixture);
    } else if (path === "/challenge") {
      response.writeHead(200, { "content-type": "text/html", "cf-mitigated": "challenge" });
      response.end("<form id=challenge-form>Checking access</form>");
    } else if (path === "/selector-challenge") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end("<form id=challenge-running>Checking access</form>");
    } else if (path === "/empty-article") {
      response.writeHead(200, { "content-type": "text/html" }).end("<article></article>");
    } else if (path === "/no-content" || path === "/reset-content") {
      response.writeHead(path === "/no-content" ? 204 : 205).end();
    } else if (path === "/bad-encoding") {
      response.writeHead(403, { "content-type": "text/plain", "content-encoding": "gzip" }).end("not a gzip response");
    } else if (path === "/latin1") {
      response.writeHead(200, { "content-type": "text/plain; charset=iso-8859-1" }).end(Buffer.from([65, 233, 66]));
    } else if (path === "/choices" || path === "/missing-location") {
      response.writeHead(path === "/choices" ? 300 : 302, { "content-type": "text/plain" }).end("Original response");
    } else if (path === "/dedicated-worker") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(`<article></article><script>
        const worker = new Worker('/worker.js');
        worker.onmessage = () => document.querySelector('article').textContent='Worker completed real local requests.';
        </script>`);
    } else if (path === "/oversized-dom") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end("<article></article><script>document.querySelector('article').textContent='generated '.repeat(3000)</script>");
    } else if (path === "/truncated") {
      response.writeHead(403, { "content-type": "text/plain", "content-length": "5000" });
      response.write("prefix");
      setTimeout(() => response.destroy(), 100);
    } else if (path === "/stalled") {
      response.writeHead(403, { "content-type": "text/plain",
        "set-cookie": ["fixture_a=a; Path=/", "fixture_b=b; Path=/"] });
      response.write(Buffer.alloc(16384, 65));
      source.emit("fixture-stalled");
    } else if (path === "/cookie-state") {
      response.end(request.headers.cookie ?? "");
    } else if (path === "/unsafe-redirect") {
      response.writeHead(302, { location: `${unsafeOrigin}/blocked` }).end();
    } else if (path === "/unsafe-resource") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(`<article></article><script>fetch('${unsafeOrigin}/blocked')</script>`);
    } else if (path === "/popup") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(`<article></article><script>window.open('${unsafeOrigin}/popup');
        document.querySelector('article').textContent='Popup-free generated article.';</script>`);
    } else if (path === "/shared-worker") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end("<article></article><script>new SharedWorker('/shared-worker.js')</script>");
    } else if (path === "/shared-worker.js") {
      response.writeHead(200, { "content-type": "text/javascript" });
      response.end(`fetch('${unsafeOrigin}/shared-worker-data');`);
    } else if (path === "/cross-frame") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(`<article></article><iframe src="${crossOrigin}/frame"></iframe><script>
        addEventListener('message', () => document.querySelector('article').textContent='Frame finished local work.');
        </script>`);
    } else if (encoded.has(path)) {
      const body = encoded.get(path);
      response.writeHead(403, { "content-type": "text/plain", "content-encoding": path.slice(1),
        "content-length": String(body.length), "retry-after": "1".repeat(300) });
      response.end(body);
    } else if (path === "/optional-resource") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(`<article></article><script>fetch('/asset-refused').then(() => document.querySelector('article').textContent='Actual short article prose.')</script>`);
    } else if (path === "/robots-enforced") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(`<article></article><script>fetch('/robots-refused-asset')
        .catch(() => document.querySelector('article').textContent='Article remains available without the refused resource.')</script>`);
    } else if (path === "/asset-refused") {
      response.writeHead(403, { "content-type": "text/plain" }).end("Optional asset refused");
    } else if (path === "/cross-origin") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(`<article></article><script>
        fetch('${crossOrigin}/cors', {method:'PUT',headers:{'x-fixture':'generated'},body:'local'})
        .then(() => document.querySelector('article').textContent='Cross-origin generated article prose.');
        </script>`);
    } else if (path === "/redirect") {
      response.writeHead(302, { location: "/page" }).end();
    } else if (path === "/redirect-loop-a" || path === "/redirect-loop-b") {
      response.writeHead(302, { location: path.endsWith("a") ? "/redirect-loop-b" : "/redirect-loop-a" }).end();
    } else if (path === "/worker.js") {
      response.writeHead(200, { "content-type": "text/javascript" });
      response.end("Promise.all([fetch('/worker-data'), fetch('/blocked').catch(() => {})]).then(() => postMessage('done'))");
    } else if (path === "/page") {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(`<article>Local generated article.</article>
        <iframe src="/frame"></iframe><script>
        const worker = new Worker('/worker.js');
        worker.onmessage = () => document.body.dataset.worker = 'done';
        fetch('/blocked').catch(() => document.body.dataset.blocked = 'done');
        </script>`);
    } else response.end("generated local resource");
  });
  source.listen(0, "127.0.0.1");
  await once(source, "listening");
  const origin = `http://127.0.0.1:${source.address().port}`;
  const cross = createServer((request, response) => {
    const path = new URL(request.url, "http://loopback.invalid").pathname;
    crossDispatched.push({ path, method: request.method });
    response.setHeader("Access-Control-Allow-Origin", origin);
    response.setHeader("Access-Control-Allow-Methods", "PUT,OPTIONS");
    response.setHeader("Access-Control-Allow-Headers", "x-fixture");
    if (path === "/robots.txt") response.end("User-agent: *\nAllow: /\n");
    else if (path === "/frame") {
      response.writeHead(200, { "content-type": "text/html" }).end(
        `<script>fetch('/frame-data').then(() => parent.postMessage('done','${origin}'))</script>`);
    }
    else response.writeHead(request.method === "OPTIONS" ? 204 : 200).end();
  });
  cross.listen(0, "127.0.0.1");
  await once(cross, "listening");
  crossOrigin = `http://localhost:${cross.address().port}`;
  const unsafe = createServer((_request, response) => { unsafeDispatches++; response.end("Never dispatched"); });
  unsafe.listen(0, "127.0.0.1");
  await once(unsafe, "listening");
  unsafeOrigin = `http://127.0.0.1:${unsafe.address().port}`;
  globalThis.__fixtureOrigins = new Set([origin, crossOrigin]);
  if (transportMode) {
    const configured = JSON.parse(await readFile(resolve(root, "config/feed-ingest-plan.json"), "utf8"));
    const extraction = JSON.parse(await readFile(resolve(root, "config/idhazh.json"), "utf8")).extract;
    const settings = boundary.FeedIngestConfigSchema.parse(configured);
    const controls = boundary.ExtractionControlsSchema.parse({
      ...extraction, max_retries: 0,
      semantic_fallback: settings.harvest.semantic_fallback,
      press_release_filter: settings.content_filters.press_release,
    });
    const harvest = { ...settings.harvest, fetch_timeout_ms: 1000,
      browser: { ...settings.harvest.browser, document_timeout_ms: 2000 },
      request_pacing: { ...settings.harvest.request_pacing, enabled: false } };
    const shared = createBrowserRuntime(harvest.browser);
    function measuredFetcher(extractionControls, harvestConfig = harvest) {
      const actual = boundary.createPermittedFetcher(harvestConfig, extractionControls, { browser_runtime: shared });
      return {
        close: actual.close,
        async fetch(url, emit, ...rest) {
          const beforeSource = dispatched.length;
          const beforeCross = crossDispatched.length;
          const before = dispatched.length + crossDispatched.length + unsafeDispatches;
          const measurements = [];
          const result = await actual.fetch(url, async measurement => {
            measurements.push(measurement);
            await emit?.(measurement);
          }, ...rest);
          measurements.sort((a, b) => a.attempt.sequence - b.attempt.sequence);
          assert.deepEqual(measurements.map(row => row.attempt), result.attempts);
          assert.deepEqual(result.attempts.map(row => row.sequence), result.attempts.map((_, index) => index));
          const observed = dispatched.length + crossDispatched.length + unsafeDispatches - before;
          const reported = measurements.reduce((total, row) => total + row.dispatched_request_count, 0);
          if (measurements.every(row => row.request_coverage === "complete")) assert.equal(reported, observed,
            JSON.stringify({ url, source: dispatched.slice(beforeSource),
              cross: crossDispatched.slice(beforeCross), attempts: result.attempts }));
          else assert(reported >= observed);
          return result;
        },
      };
    }
    const fetcher = measuredFetcher(controls);
    try {
      const feed = await fetcher.fetch(`${origin}/feed.xml`, undefined, "feed");
      assert.equal(feed.failure, null, JSON.stringify(feed));
      assert.equal(feed.body, feedFixture);
      assert.equal(feed.response_evidence.content_type, "application/rss+xml");
      assert.equal(feed.attempts.filter(row => row.phase === "robots").length, 1);
      const article = await fetcher.fetch(`${origin}/article?identity=removed`);
      assert.equal(article.failure, null, JSON.stringify(article));
      assert(article.body.includes("article"));
      assert.equal(article.response_evidence.request_profile, "chromium");
      assert.equal(article.attempts.filter(row => row.phase === "robots").length, 0);
      const optional = await fetcher.fetch(`${origin}/optional-resource`);
      assert.equal(optional.failure, null, JSON.stringify(optional));
      assert.equal(optional.http_status, 200);
      assert.equal(optional.final_attempted_url, `${origin}/optional-resource`);
      assert(optional.attempts.some(row => row.request_role === "resource" && row.http_status === 403));
      const enforcing = measuredFetcher(controls, { ...harvest, article_robots_policy: "enforce" });
      try {
        const allowed = await enforcing.fetch(`${origin}/robots-enforced`);
        assert.equal(allowed.failure, null, JSON.stringify(allowed));
        assert(allowed.body.includes("Article remains available"));
        assert(!dispatched.includes("/robots-refused-asset"));
        assert(allowed.attempts.some(row => row.request_role === "resource"
          && row.failure === "robots-denied" && row.request_url === null));
      } finally { await enforcing.close(); }
      const preflight = await fetcher.fetch(`${origin}/cross-origin`);
      assert.equal(preflight.failure, null, JSON.stringify(preflight));
      const actual = crossDispatched.filter(request => request.path === "/cors");
      assert.equal(actual.length, 2);
      assert.equal(preflight.attempts.filter(row => row.request_url === `${crossOrigin}/cors`).length, actual.length);
      const framed = await fetcher.fetch(`${origin}/cross-frame`);
      assert.equal(framed.failure, null, JSON.stringify(framed));
      for (const path of ["/frame", "/frame-data"]) {
        assert(crossDispatched.some(row => row.path === path));
        assert(framed.attempts.some(row => row.request_url === `${crossOrigin}${path}` && row.request_role === "resource"));
      }
      for (const path of ["/unsafe-redirect", "/unsafe-resource"]) {
        const refused = await fetcher.fetch(`${origin}${path}`);
        assert.equal(refused.failure, "unsafe-target", JSON.stringify(refused));
        assert.equal(unsafeDispatches, 0);
      }
      const popup = await fetcher.fetch(`${origin}/popup`);
      assert.equal(popup.failure, null, JSON.stringify(popup));
      assert.equal(unsafeDispatches, 0);
      const unsupported = await fetcher.fetch(`${origin}/shared-worker`);
      assert.equal(unsupported.failure, null, JSON.stringify(unsupported));
      assert(unsupported.body.includes("<article></article>"), "Disabled SharedWorker unexpectedly produced article content");
      assert.equal(unsafeDispatches, 0);
      assert(!dispatched.includes("/shared-worker.js"), "SharedWorker script left before request admission");
      const challenge = await fetcher.fetch(`${origin}/challenge`, undefined, "feed");
      assert.equal(challenge.failure, "challenge-unresolved", JSON.stringify(challenge));
      assert.equal(challenge.http_status, 200);
      const selector = await fetcher.fetch(`${origin}/selector-challenge`, undefined, "feed");
      assert.equal(selector.failure, "challenge-unresolved", JSON.stringify(selector));
      assert.equal(selector.http_status, 200);
      const empty = await fetcher.fetch(`${origin}/empty-article`);
      assert.equal(empty.failure, null, JSON.stringify(empty));
      assert(empty.body.includes("<article></article>"));
      for (const [path, status] of [["/no-content", 204], ["/reset-content", 205]]) {
        const noContent = await fetcher.fetch(`${origin}${path}`, undefined, "feed");
        assert.equal(noContent.failure, null, JSON.stringify(noContent));
        assert.equal(noContent.http_status, status);
        assert.equal(noContent.body, "");
      }
      const loop = await fetcher.fetch(`${origin}/redirect-loop-a`, undefined, "feed");
      assert.equal(loop.failure, "redirect-loop", JSON.stringify(loop));
      assert.equal(loop.error_code, "ERR_TOO_MANY_REDIRECTS");
      for (const [path, status] of [["/choices", 300], ["/missing-location", 302]]) {
        const notRedirected = await fetcher.fetch(`${origin}${path}`, undefined, "feed");
        assert.equal(notRedirected.failure, "http", JSON.stringify(notRedirected));
        assert.equal(notRedirected.http_status, status);
        assert.equal(notRedirected.response_evidence.decoded_bytes, Buffer.byteLength("Original response"));
      }
      const badEncoding = await fetcher.fetch(`${origin}/bad-encoding`, undefined, "feed");
      assert.equal(badEncoding.failure, "network", JSON.stringify(badEncoding));
      assert.equal(badEncoding.http_status, 403);
      assert.equal(badEncoding.body, null);
      const worker = await fetcher.fetch(`${origin}/dedicated-worker`);
      assert.equal(worker.failure, null, JSON.stringify(worker));
      assert(worker.body.includes("Worker completed real local requests."));
      for (const path of ["/worker.js", "/worker-data", "/blocked"]) {
        assert(worker.attempts.some(row => row.request_url === `${origin}${path}` && row.request_role === "resource"));
      }
      for (const path of ["/truncated", "/stalled"]) {
        const failed = await fetcher.fetch(`${origin}${path}`, undefined, "feed");
        assert.equal(failed.body, null);
        assert(["network", "timeout"].includes(failed.failure), JSON.stringify(failed));
        assert.equal(failed.http_status, 403);
        assert.equal(failed.attempts.filter(row => row.request_url === `${origin}${path}`).length, 1);
      }
      const cancelled = new AbortController();
      const started = once(source, "fixture-stalled");
      const interrupted = fetcher.fetch(`${origin}/stalled`, undefined, "feed", cancelled.signal);
      await started;
      cancelled.abort(new DOMException("Generated cancellation", "AbortError"));
      const cancellation = await interrupted;
      assert.equal(cancellation.failure, "timeout", JSON.stringify(cancellation));
      const closingFetcher = measuredFetcher(controls);
      try {
        await closingFetcher.fetch(`${origin}/cookie-state`, undefined, "feed");
        const started = once(source, "fixture-stalled");
        let settled = false;
        const pending = closingFetcher.fetch(`${origin}/stalled`, undefined, "feed")
          .then(result => { settled = true; return result; });
        await started;
        await closingFetcher.close();
        assert(settled, "Transport disposal returned before its request and observations settled");
        assert.equal((await pending).failure, "timeout");
      } finally { await closingFetcher.close(); }
      const limited = measuredFetcher({ ...controls, max_body_bytes: 1000 });
      try {
        const isolated = await limited.fetch(`${origin}/cookie-state`, undefined, "feed");
        assert.equal(isolated.failure, null, JSON.stringify(isolated));
        assert.equal(isolated.body, "");
        const retained = await fetcher.fetch(`${origin}/cookie-state`, undefined, "feed");
        assert(retained.body.includes("source_session=ok"));
        for (const path of encoded.keys()) {
          const refused = await limited.fetch(`${origin}${path}`, undefined, "feed");
          assert.equal(refused.failure, "body-too-large", JSON.stringify(refused));
          assert.equal(refused.http_status, 403);
          assert.equal(refused.body_limit.limit_stage, "completed-response");
          assert.equal(refused.body_limit.observed_at_least_bytes, payload.length);
        }
        const dom = await limited.fetch(`${origin}/oversized-dom`);
        assert.equal(dom.failure, "body-too-large", JSON.stringify(dom));
        assert.equal(dom.body_limit.limit_stage, "parser-input");
        assert(dom.response_evidence.decoded_bytes < 1000);
      } finally { await limited.close(); }
      const byteLimited = measuredFetcher({ ...controls, max_body_bytes: 4 });
      try {
        const expanded = await byteLimited.fetch(`${origin}/latin1`, undefined, "feed");
        assert.equal(expanded.failure, "body-too-large", JSON.stringify(expanded));
        assert.equal(expanded.response_evidence.decoded_bytes, 3);
        assert.equal(expanded.body_limit.limit_stage, "parser-input");
        assert.equal(expanded.body_limit.observed_at_least_bytes, 5);
      } finally { await byteLimited.close(); }
      await fetcher.close();
      await shared.close();
      await Promise.all([source, cross, unsafe].map(server => new Promise((resolve, reject) => {
        server.close(error => error ? reject(error) : resolve());
      })));
      assert(!dispatched.includes("/shared-worker.js"), "SharedWorker script arrived after refusal or cleanup");
      assert.equal(unsafeDispatches, 0);
      console.log(JSON.stringify({ feed: feed.body, article: article.body,
        unsupported_article: unsupported.body, dispatched, passed: true }));
    } finally {
      await fetcher.close(); await shared.close();
      for (const server of [source, cross, unsafe]) {
        if (server.listening) { server.closeAllConnections(); server.close(); }
      }
    }
    return;
  }
  const runtime = createBrowserRuntime({
    headless: true, document_timeout_ms: 10000,
    challenge_selectors: ["#challenge-form", "#challenge-running", "#cf-challenge-running"],
  });
  try {
    const execution = await runtime.context({
      fail(error) { errors.push(error); console.error(error); },
      async attach(session, target) {
        targetTypes.push(target.type);
        session.on("Fetch.requestPaused", event => {
          (async () => {
            const url = new URL(event.request.url);
            admitted.push(url.pathname);
            if (url.origin !== origin || url.pathname === "/blocked") {
              await session.send("Fetch.failRequest", { requestId: event.requestId, errorReason: "BlockedByClient" });
            } else await session.send("Fetch.continueRequest", { requestId: event.requestId });
          })().catch(error => errors.push(error));
        });
        await session.send("Fetch.enable", { patterns: [{ urlPattern: "*", requestStage: "Request" }] });
      },
    }, {});
    try {
      const page = await execution.page();
      await page.goto(`${origin}/redirect`, { waitUntil: "load", timeout: 10000 });
      await page.locator("body[data-worker=done][data-blocked=done]").waitFor({ timeout: 10000 });
      assert.deepEqual(errors, []);
      assert(!dispatched.includes("/blocked"));
      for (const path of ["/redirect", "/page", "/worker.js", "/worker-data", "/frame"]) {
        assert(admitted.includes(path), `Not admitted: ${path}`);
        assert(dispatched.includes(path), `Not dispatched: ${path}`);
      }
      const sandbox = [];
      if (process.platform === "linux") {
        const session = await page.context().browser().newBrowserCDPSession();
        try {
          const { processInfo } = await session.send("SystemInfo.getProcessInfo");
          const browser = processInfo.find(process => process.type === "browser");
          assert(browser, "Browser process is unavailable for sandbox verification");
          const browserStatus = await readFile(`/proc/${browser.id}/status`, "utf8");
          const renderers = processInfo.filter(process => process.type === "renderer");
          assert(renderers.length > 0, "No live renderer exists for sandbox verification");
          const field = (status, name) => {
            const value = status.match(new RegExp(`^${name}:\\s*(.+)$`, "m"))?.[1];
            assert(value, `Kernel sandbox field is unavailable: ${name}`);
            return value.trim();
          };
          for (const renderer of renderers) {
            const status = await readFile(`/proc/${renderer.id}/status`, "utf8");
            assert.equal(field(status, "Seccomp"), "2", "Renderer Seccomp filter is not active");
            assert.equal(field(status, "NoNewPrivs"), "1", "Renderer can gain new privileges");
            assert(Number(field(status, "Seccomp_filters")) > Number(field(browserStatus, "Seccomp_filters")),
              "Renderer has no additional sandbox filter beyond the browser process");
            assert(field(status, "NSpid").split(/\s+/).length > field(browserStatus, "NSpid").split(/\s+/).length,
              "Renderer has no separate process-ID namespace");
            sandbox.push({ seccomp: field(status, "Seccomp"), no_new_privileges: field(status, "NoNewPrivs"),
              filter_count: Number(field(status, "Seccomp_filters")),
              browser_filter_count: Number(field(browserStatus, "Seccomp_filters")),
              pid_namespace_depth: field(status, "NSpid").split(/\s+/).length,
              browser_pid_namespace_depth: field(browserStatus, "NSpid").split(/\s+/).length });
          }
        } finally { await session.detach(); }
      }
      console.log(JSON.stringify({ passed: true, admitted, dispatched, targetTypes, sandbox }));
    } finally { await execution.close(); }
  } finally {
    await runtime.close(); source.closeAllConnections(); source.close(); cross.closeAllConnections(); cross.close();
    unsafe.closeAllConnections(); unsafe.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
