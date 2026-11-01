import { expect, test } from "bun:test";
import {
  FEED_PROBE_SAMPLE_DEFAULT,
  FEED_PROBE_SAMPLE_MAX,
  FeedProbeRequestSchema,
  FeedProbeResultSchema,
  FeedIngestConfigSchema,
} from "@idhazh/common-contracts";
import type {
  HarvestTransport,
  TransportResponse,
  TransportRequest,
} from "@idhazh/feed-ingest-plan/transport";
import { HttpResponseEvidenceSchema } from "@idhazh/common-contracts";
import { probeFeed as runProbeFeed } from "../src/feed-probe";
import type { FeedProbeOptions } from "../src/feed-probe";

type RecordedRoute = {
  status: number;
  body: string;
  location?: string | null;
};

class RecordedFeedTransport implements HarvestTransport {
  constructor(private readonly routes: ReadonlyMap<string, RecordedRoute>) {}

  async request(input: TransportRequest): Promise<TransportResponse> {
    const route = this.routes.get(input.url.href) ?? { status: 404, body: "" };
    return {
      status: route.status,
      body: route.body,
      location: route.location ?? null,
      evidence: HttpResponseEvidenceSchema.parse({
        content_type: null, decoded_bytes: Buffer.byteLength(route.body), declared_content_length: null,
        selected_headers: {}, headers_truncated: [], request_profile: input.profile.browser,
      }),
    };
  }
}

async function fixture(name: string): Promise<string> {
  return Bun.file(new URL(`../../../tests/fixtures/feed-probe/${name}`, import.meta.url)).text();
}

async function boundary(routes: Record<string, RecordedRoute>) {
  return {
    transport: new RecordedFeedTransport(new Map(Object.entries(routes))),
  };
}

async function probeFeed(request: unknown, options: FeedProbeOptions = {}) {
  const config = FeedIngestConfigSchema.parse(await Bun.file(new URL(
    "../../../config/feed-ingest-plan.json", import.meta.url,
  )).json());
  const harvest = options.harvest ?? config.harvest;
  return runProbeFeed(request, {
    ...options,
    harvest: { ...harvest, request_pacing: { ...harvest.request_pacing, enabled: false } },
  });
}

function robotsRoute(): Record<string, RecordedRoute> {
  return {
    "https://fixture.test/robots.txt": { status: 404, body: "" },
  };
}

test("strict request and result contracts apply the sample default and maximum", () => {
  const request = FeedProbeRequestSchema.parse({ feed_url: "https://fixture.test/feed.xml" });
  expect(request.sample_count).toBe(FEED_PROBE_SAMPLE_DEFAULT);
  expect(FeedProbeRequestSchema.safeParse({
    feed_url: "https://fixture.test/feed.xml",
    sample_count: FEED_PROBE_SAMPLE_MAX + 1,
  }).success).toBe(false);
  expect(FeedProbeRequestSchema.safeParse({
    feed_url: "https://fixture.test/feed.xml",
    sample_count: 3,
    extra: true,
  }).success).toBe(false);

  const result = FeedProbeResultSchema.parse({
    verdict: "pass",
    passed: true,
    paywall_confirmed: false,
    sample_count: 1,
    readable_count: 1,
    paywall_sample_count: 0,
    paywall_evidence: "none",
    failure_code: null,
    diagnostics: null,
    warnings: [],
    samples: [{
      readable: true,
      dated: true,
      paywall: false,
      paywall_evidence: "none",
      diagnostics: null,
    }],
  });
  expect(result.version).toBe("2026-10-28");
  expect(FeedProbeResultSchema.safeParse({ ...result, extra: true }).success).toBe(false);
});

test("one readable fixture article passes through production parsing and extraction", async () => {
  const feed = await fixture("feed.xml");
  const article = await fixture("readable-article.html");
  const transport = await boundary({
    ...robotsRoute(),
    "https://fixture.test/feed.xml": { status: 200, body: feed },
    "https://fixture.test/article-one": { status: 200, body: article },
    "https://fixture.test/article-two": { status: 200, body: article },
    "https://fixture.test/article-three": { status: 200, body: article },
  });

  const result = await probeFeed(
    { feed_url: "https://fixture.test/feed.xml", sample_count: 3 },
    { boundary: transport },
  );

  expect(result.verdict).toBe("pass");
  expect(result.passed).toBe(true);
  expect(result.readable_count).toBeGreaterThanOrEqual(1);
  expect(result.paywall_confirmed).toBe(false);
});

test("HTTP feed failure does not pass", async () => {
  const transport = await boundary({
    ...robotsRoute(),
    "https://fixture.test/feed.xml": { status: 404, body: "" },
  });
  const result = await probeFeed(
    { feed_url: "https://fixture.test/feed.xml" },
    { boundary: transport },
  );

  expect(result.verdict).toBe("feed_failure");
  expect(result.passed).toBe(false);
  expect(result.failure_code).toBe("http_client_error");
});

test("observed article and feed robots warnings do not hide readable content", async () => {
  const feed = await fixture("one-paywall-feed.xml");
  const article = await fixture("readable-article.html");
  const config = FeedIngestConfigSchema.parse(await Bun.file(new URL(
    "../../../config/feed-ingest-plan.json", import.meta.url,
  )).json());
  const harvest = { ...config.harvest, article_robots_policy: "observe" as const };
  for (const allowedFeed of [true, false]) {
    const transport = await boundary({
      "https://fixture.test/robots.txt": {
        status: 200, body: `User-agent: *\nDisallow: /\n${allowedFeed ? "Allow: /feed.xml\n" : ""}`,
      },
      "https://fixture.test/feed.xml": { status: 200, body: feed },
      "https://fixture.test/paywall-one": { status: 200, body: article },
    });
    const result = await probeFeed(
      { feed_url: "https://fixture.test/feed.xml", sample_count: 1 }, { harvest, boundary: transport },
    );
    expect(result.passed).toBe(true);
    expect(result.samples[0]?.diagnostics).toMatchObject({
      robots: "denied", robots_http_status: 200, fetch_failure: null, http_status: 200,
    });
  }
  const unavailable = await boundary({
    ...robotsRoute(),
    "https://fixture.test/feed.xml": {
      status: 200, body: feed.replace("https://fixture.test/paywall-one", "https://article-fixture.test/paywall-one"),
    },
    "https://article-fixture.test/robots.txt": { status: 503, body: "" },
    "https://article-fixture.test/paywall-one": { status: 200, body: article },
  });
  const result = await probeFeed(
    { feed_url: "https://fixture.test/feed.xml", sample_count: 1 }, { harvest, boundary: unavailable },
  );
  expect(result.passed).toBe(true);
  expect(result.samples[0]?.diagnostics).toMatchObject({
    robots: "unknown", robots_http_status: 503, robots_failure: "http", fetch_failure: null, http_status: 200,
  });
});

test("HTTP article failure does not pass", async () => {
  const feed = await fixture("one-paywall-feed.xml");
  const transport = await boundary({
    ...robotsRoute(),
    "https://fixture.test/feed.xml": { status: 200, body: feed },
    "https://fixture.test/paywall-one": { status: 404, body: "" },
  });

  const result = await probeFeed(
    { feed_url: "https://fixture.test/feed.xml", sample_count: 1 },
    { boundary: transport },
  );

  expect(result.verdict).toBe("article_fetch_failure");
  expect(result.passed).toBe(false);
  expect(result.failure_code).toBe("http_client_error");
  expect(result.samples[0]?.paywall_evidence).toBe("not-observed");
});

test("a pre-aborted operation is refused before transport", async () => {
  const transport = await boundary(robotsRoute());
  const controller = new AbortController();
  controller.abort();

  const result = await probeFeed(
    { feed_url: "https://fixture.test/feed.xml" },
    { signal: controller.signal, boundary: transport },
  );

  expect(result.verdict).toBe("feed_failure");
  expect(result.passed).toBe(false);
  expect(result.diagnostics?.fetch_failure).toBe("timeout");
});

test("one paywall sample does not confirm paywall", async () => {
  const feed = await fixture("one-paywall-feed.xml");
  const article = await fixture("paywall-jsonld.html");
  const transport = await boundary({
    ...robotsRoute(),
    "https://fixture.test/feed.xml": { status: 200, body: feed },
    "https://fixture.test/paywall-one": { status: 200, body: article },
  });

  const result = await probeFeed(
    { feed_url: "https://fixture.test/feed.xml", sample_count: 1 },
    { boundary: transport },
  );

  expect(result.verdict).toBe("paywall_not_confirmed");
  expect(result.passed).toBe(false);
  expect(result.paywall_confirmed).toBe(false);
  expect(result.paywall_sample_count).toBe(1);
  expect(result.samples[0]?.paywall_evidence).toBe("json-ld");
});

test("two matching paywall samples confirm paywall", async () => {
  const feed = await fixture("two-paywall-feed.xml");
  const article = await fixture("paywall-marker.html");
  const transport = await boundary({
    ...robotsRoute(),
    "https://fixture.test/feed.xml": { status: 200, body: feed },
    "https://fixture.test/paywall-one": { status: 200, body: article },
    "https://fixture.test/paywall-two": { status: 200, body: article },
  });

  const result = await probeFeed(
    { feed_url: "https://fixture.test/feed.xml", sample_count: 2 },
    { boundary: transport },
  );

  expect(result.verdict).toBe("paywall_confirmed");
  expect(result.passed).toBe(false);
  expect(result.paywall_confirmed).toBe(true);
  expect(result.paywall_sample_count).toBe(2);
  expect(result.paywall_evidence).toBe("configured-marker");
});

test("mixed paywall and readable samples pass but do not confirm paywall", async () => {
  const feed = await fixture("mixed-feed.xml");
  const paywall = await fixture("paywall-jsonld.html");
  const readable = await fixture("readable-article.html");
  const transport = await boundary({
    ...robotsRoute(),
    "https://fixture.test/feed.xml": { status: 200, body: feed },
    "https://fixture.test/paywall-one": { status: 200, body: paywall },
    "https://fixture.test/article-one": { status: 200, body: readable },
  });

  const result = await probeFeed(
    { feed_url: "https://fixture.test/feed.xml", sample_count: 2 },
    { boundary: transport },
  );

  expect(result.passed).toBe(true);
  expect(result.verdict).toBe("pass");
  expect(result.paywall_confirmed).toBe(false);
});

test("malformed feed is refused cleanly", async () => {
  const feed = await fixture("malformed-feed.xml");
  const transport = await boundary({
    ...robotsRoute(),
    "https://fixture.test/feed.xml": { status: 200, body: feed },
  });

  const result = await probeFeed(
    { feed_url: "https://fixture.test/feed.xml" },
    { boundary: transport },
  );

  expect(result.verdict).toBe("feed_failure");
  expect(result.passed).toBe(false);
  const detail = result.diagnostics?.detail;
  expect(detail === "malformed-feed" || detail === "empty-feed").toBe(true);
});

test("malformed article metadata remains a warning and does not fail a readable article", async () => {
  const feed = await fixture("undated-feed.xml");
  const article = await fixture("malformed-jsonld-article.html");
  const transport = await boundary({
    ...robotsRoute(),
    "https://fixture.test/feed.xml": { status: 200, body: feed },
    "https://fixture.test/article-one": { status: 200, body: article },
  });

  const result = await probeFeed(
    { feed_url: "https://fixture.test/feed.xml", sample_count: 1 },
    { boundary: transport },
  );

  expect(result.passed).toBe(true);
  expect(result.warnings).toContain("malformed-json-ld");
  expect(result.warnings).toContain("no_dated_entries");
});
