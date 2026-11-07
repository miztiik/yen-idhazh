/** Prove real offline extraction, fetch-to-parse links and JSDOM closure without scripts or resources. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { JSDOM, VirtualConsole } from "jsdom";
import { createRootContext } from "@idhazh/common-contracts/create-operation-context";
import { readTraceContext } from "@idhazh/common-contracts/propagate-trace-context";
import { extractContentFromUrl, parseExtractedDocument } from "../extract-content.js";
import { loadAnalysisConfig } from "../load-analysis-config.js";
import { PipelineEventBus } from "../publish-events.js";
import { SUMMARY_GENERATOR_TESTS_EVENT_SOURCE } from "../declare-event-source.js";
import { repositoryRoot, withConfig } from "../../../../services/summary-generator/test/model-recordings.js";

const sourceHtml = readFileSync(path.join(repositoryRoot, "tests/fixtures/feed-probe/readable-article.html"), "utf8");
const fixtureDocument = new JSDOM(sourceHtml);
const sourceTitle = fixtureDocument.window.document.title;
const sourceParagraph = fixtureDocument.window.document.querySelector("article p")?.textContent;
assert.ok(sourceParagraph);
fixtureDocument.window.close();
const resourceHtml = `<script>document.body.insertAdjacentHTML('beforeend', '<p id="script-effect">Injected script content</p>')</script>
<script src="/unrequested-script.js"></script><link rel="stylesheet" href="/unrequested-style.css">
<img src="/unrequested-image.png"><iframe src="/unrequested-frame.html"></iframe>`;

test("the real source parser produces substantive text with one main-document fetch and linked callbacks", () =>
  withConfig(async root => {
    const parent = createRootContext();
    const bus = new PipelineEventBus(SUMMARY_GENERATOR_TESTS_EVENT_SOURCE, path.join(root, "source-events.jsonl"));
    const url = "https://source.example/article";
    const requested: Request[] = [];
    const result = await extractContentFromUrl(url, parent, progress => {
      assert.equal(progress.context.traceId, parent.traceId);
      bus.emitEvent(progress.type, progress.data, progress.context);
    }, async request => {
      requested.push(request);
      return new Response(sourceHtml + resourceHtml, { headers: { "Content-Type": "text/html" } });
    }, loadAnalysisConfig(root));
    assert.equal(result.title, sourceTitle);
    assert.ok(result.content.length > loadAnalysisConfig(root).min_content_characters);
    assert.ok(result.content.includes(sourceParagraph));
    assert.equal(result.content.includes("Injected script content"), false);
    assert.deepEqual(requested.map(request => request.url), [url]);
    assert.equal(requested[0].headers.has("traceparent"), false);
    assert.equal(requested[0].headers.has("tracestate"), false);
    const [started, fetched, parsed] = bus.getEventHistory();
    assert.equal(started.type, "URL_HTTP_FETCH_STARTED");
    assert.equal(fetched.type, "URL_HTTP_FETCH_COMPLETED");
    assert.equal(parsed.type, "URL_DEFUDDLE_EXTRACTED");
    assert.equal(started.traceparent, fetched.traceparent);
    assert.notEqual(parsed.traceparent, fetched.traceparent);
    const fetchContext = readTraceContext({ traceparent: fetched.traceparent });
    assert.deepEqual(result.context.links, [{ traceId: fetchContext?.traceId, spanId: fetchContext?.spanId }]);
    assert.equal(parsed.traceparent,
      `00-${result.context.traceId}-${result.context.spanId}-00`);
  }));

test("JSDOM runs no scripts, loads no resource documents and closes after successful parsing", () =>
  withConfig(async root => {
    const diagnostics: unknown[] = [];
    const virtualConsole = new VirtualConsole();
    virtualConsole.on("jsdomError", value => { diagnostics.push(value); });
    const dom = new JSDOM(sourceHtml + resourceHtml, { url: "https://source.example/article", virtualConsole });
    const document = dom.window.document;
    const frame = document.querySelector("iframe");
    assert.ok(frame);
    assert.equal(frame.contentDocument?.documentElement ?? null, null);
    const result = await parseExtractedDocument(dom, "https://source.example/article",
      createRootContext(), undefined, loadAnalysisConfig(root));
    assert.ok(result.content.length > 0);
    assert.equal(document.querySelector("#script-effect"), null);
    assert.deepEqual(diagnostics, []);
    assert.equal(dom.window.document, undefined);
  }));

test("failed parsing also closes its window and source failure retains supplied fetch context", () =>
  withConfig(async root => {
    const config = loadAnalysisConfig(root);
    const dom = new JSDOM("<title>Too short</title><p>short</p>", { url: "https://source.example/short" });
    await assert.rejects(() => parseExtractedDocument(dom, "https://source.example/short",
      createRootContext(), undefined, { ...config, min_content_characters: sourceHtml.length }), /substantive/);
    assert.equal(dom.window.document, undefined);
    const parent = createRootContext();
    const bus = new PipelineEventBus(SUMMARY_GENERATOR_TESTS_EVENT_SOURCE, path.join(root, "failed-source-events.jsonl"));
    let cancelled = false;
    const body = new ReadableStream<Uint8Array>({ cancel() { cancelled = true; } });
    await assert.rejects(() => extractContentFromUrl("https://source.example/failure", parent, progress => {
      assert.equal(progress.context.parentSpanId, parent.spanId);
      bus.emitEvent(progress.type, progress.data, progress.context);
    }, async request => {
      assert.equal(request.headers.has("traceparent"), false);
      return new Response(body, { status: 503 });
    }, config), /HTTP 503/);
    assert.equal(bus.getEventHistory().length, 1);
    assert.equal(cancelled, true);
  }));
