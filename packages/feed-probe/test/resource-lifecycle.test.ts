/** Does recorded probing await disposal and retain a supplied browser across CLI targets? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { unlink } from "node:fs/promises";
import { FeedIngestConfigSchema, HttpResponseEvidenceSchema } from "@idhazh/common-contracts";
import { createBrowserRuntime } from "@idhazh/feed-ingest-plan/browser-runtime";
import type { HarvestTransport, TransportRequest, TransportResponse } from "@idhazh/feed-ingest-plan/transport";
import { probeFeed } from "../src/feed-probe";
import { runFeedProbeCli } from "../src/cli";

class RecordedProbeTransport implements HarvestTransport {
  closes = 0;
  private closing: Promise<void> = Promise.resolve();
  private beginClose!: () => void;
  readonly closeStarted = new Promise<void>(resolve => { this.beginClose = resolve; });
  constructor(private readonly feed: string, private readonly article: string, private readonly feedStatus = 200) {}
  holdClose() {
    let release!: () => void;
    this.closing = new Promise<void>(resolve => { release = resolve; });
    return release;
  }
  async request(input: TransportRequest): Promise<TransportResponse> {
    input.signal.throwIfAborted();
    const robots = input.url.pathname === "/robots.txt";
    const feed = input.url.pathname.endsWith(".xml");
    const body = robots ? "" : feed ? this.feed : this.article;
    return {
      status: robots ? 404 : feed ? this.feedStatus : 200, body, location: null,
      evidence: HttpResponseEvidenceSchema.parse({
        content_type: null, decoded_bytes: Buffer.byteLength(body), declared_content_length: null,
        selected_headers: {}, headers_truncated: [], request_profile: input.profile.browser,
      }),
    };
  }
  async close() {
    this.closes++;
    this.beginClose();
    await this.closing;
  }
}

async function recordedProbe(feedStatus = 200) {
  const [config, feed, article] = await Promise.all([
    Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json(),
    Bun.file(new URL("../../../tests/fixtures/feed-probe/feed.xml", import.meta.url)).text(),
    Bun.file(new URL("../../../tests/fixtures/feed-probe/readable-article.html", import.meta.url)).text(),
  ]);
  const harvest = FeedIngestConfigSchema.parse(config).harvest;
  return {
    harvest: { ...harvest, request_pacing: { ...harvest.request_pacing, enabled: false } },
    transport: new RecordedProbeTransport(feed, article, feedStatus),
  };
}

test("recorded probe success and failure dispose transport without opening the supplied browser", async () => {
  for (const status of [200, 404]) {
    const recorded = await recordedProbe(status);
    const browser = createBrowserRuntime(recorded.harvest.browser);
    await browser.close();
    const finishClose = recorded.transport.holdClose();
    let settled = false;
    const probing = probeFeed({ feed_url: "https://fixture.test/feed.xml", sample_count: 1 }, {
      harvest: recorded.harvest, transport: recorded.transport, browser_runtime: browser,
    }).finally(() => { settled = true; });
    try {
      await recorded.transport.closeStarted;
      expect(settled).toBe(false);
      finishClose();
      const result = await probing;
      expect(result.passed).toBe(status === 200);
      expect(recorded.transport.closes).toBe(1);
    } finally { finishClose(); await probing; }
  }
});

test("CLI targets receive the same supplied runtime with real recorded probe results", async () => {
  const recorded = await recordedProbe();
  const browser = createBrowserRuntime(recorded.harvest.browser);
  await browser.close();
  const trace = `backend/var/browser-lifecycle/probe-${randomUUID()}.jsonl`;
  const received: (typeof browser | undefined)[] = [];
  const errors: string[] = [];
  try {
    const result = await runFeedProbeCli([
      "--articles", "1", "--trace", trace, "--json",
      "https://lifecycle-one.example/feed.xml", "https://lifecycle-two.example/feed.xml",
    ], {
      browser_runtime: browser,
      loadSourceCatalog: () => Bun.file(new URL("./fixtures/sources.json", import.meta.url)).json(),
      stdout: () => {}, stderr: line => { errors.push(line); },
      probe: async (request, options) => {
        received.push(options?.browser_runtime);
        return probeFeed(request, { ...options, harvest: recorded.harvest, transport: recorded.transport });
      },
    });
    expect(result, errors.join("\n")).toBe(0);
    expect(received).toEqual([browser, browser]);
    expect(recorded.transport.closes).toBe(2);
  } finally {
    await unlink(new URL(`../../../${trace}`, import.meta.url)).catch(error => {
      if (!(error && typeof error === "object" && "code" in error && error.code === "ENOENT")) throw error;
    });
  }
});
