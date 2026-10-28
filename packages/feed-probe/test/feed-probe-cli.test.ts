import { unlink } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "bun:test";
import {
  FEED_PROBE_SAMPLE_DEFAULT,
  FEED_PROBE_VERSION,
  FeedProbeResultSchema,
} from "@idhazh/common-contracts";
import type {
  HarvestTransport,
  TransportResponse,
} from "@idhazh/feed-ingest-plan/transport";
import type { ResolveAddresses } from "@idhazh/feed-ingest-plan/safe-target";
import { probeFeed } from "../src/feed-probe";
import { runFeedProbeCli } from "../src/cli";
import { parseFeedProbeCliArguments } from "../src/cli-options";
import {
  FeedProbeReportSchema,
  buildFeedProbeReport,
} from "../src/feed-probe-report";
import {
  normalizeFeedUrl,
  resolveFeedProbeTargets,
} from "../src/source-selection";
import {
  defaultTraceRelativePath,
  resolveSafeArtifactPath,
} from "../src/cli-artifacts";

const repositoryRoot = fileURLToPath(new URL("../../..", import.meta.url));

async function fixtureText(relativeName: string): Promise<string> {
  return Bun.file(new URL(`./fixtures/${relativeName}`, import.meta.url)).text();
}

async function existingFeedFixture(relativeName: string): Promise<string> {
  return Bun.file(new URL(`../../../tests/fixtures/feed-probe/${relativeName}`, import.meta.url)).text();
}

async function sourceCatalog(): Promise<unknown> {
  return JSON.parse(await fixtureText("sources.json"));
}

type RecordedRoute = {
  status: number;
  body: string;
  location?: string | null;
};

class RecordedFeedTransport implements HarvestTransport {
  constructor(private readonly routes: ReadonlyMap<string, RecordedRoute>) {}

  async request(input: {
    url: URL;
    addresses: readonly { address: string; family: 4 | 6 }[];
    user_agent: string;
    headers: Readonly<Record<string, string>>;
    max_body_bytes: number;
    signal: AbortSignal;
  }): Promise<TransportResponse> {
    const route = this.routes.get(input.url.href) ?? { status: 404, body: "" };
    return {
      status: route.status,
      body: route.body,
      location: route.location ?? null,
    };
  }
}

const resolveFixtureAddress: ResolveAddresses = async () => [
  { address: "8.8.8.8", family: 4 },
];

async function recordedBoundary(routes: Record<string, RecordedRoute>) {
  return {
    transport: new RecordedFeedTransport(new Map(Object.entries(routes))),
    resolve: resolveFixtureAddress,
  };
}

async function removeNamedFile(relativePath: string): Promise<void> {
  try {
    await unlink(join(repositoryRoot, relativePath));
  } catch (error) {
    if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error;
  }
}

test("CLI arguments apply defaults and bounded article counts", () => {
  const parsed = parseFeedProbeCliArguments([
    "--articles", "4",
    "--report", "backend/var/probes/report.jsonl",
    "--trace", "backend/var/probes/trace.jsonl",
    "--log-level", "debug",
    "--json-lines",
    "https://fixture.test/feed.xml",
  ]);
  expect(parsed.kind).toBe("options");
  if (parsed.kind !== "options") return;
  expect(parsed.options.articles).toBe(4);
  expect(parsed.options.report).toBe("backend/var/probes/report.jsonl");
  expect(parsed.options.trace).toBe("backend/var/probes/trace.jsonl");
  expect(parsed.options.logLevel).toBe("DEBUG");
  expect(parsed.options.jsonLines).toBe(true);
  expect(parsed.options.urls).toEqual(["https://fixture.test/feed.xml"]);

  const defaults = parseFeedProbeCliArguments(["https://fixture.test/feed.xml"]);
  expect(defaults.kind).toBe("options");
  if (defaults.kind === "options") {
    expect(defaults.options.articles).toBe(FEED_PROBE_SAMPLE_DEFAULT);
  }
  expect(parseFeedProbeCliArguments(["--articles", "11", "https://fixture.test/feed.xml"]).kind).toBe("error");
});

test("strict machine report uses the core version and no article text", () => {
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
  const report = buildFeedProbeReport(
    "fixture-feed",
    "https://fixture.test/feed.xml",
    result,
    12,
  );
  expect(FeedProbeReportSchema.safeParse(report).success).toBe(true);
  expect(report.version).toBe(FEED_PROBE_VERSION);
  expect(JSON.stringify(report)).not.toContain("<html");
  expect(JSON.stringify(report)).not.toContain("article_text");
});

test("URL mode rejects normalized catalog duplicates before probing", async () => {
  let probeCalls = 0;
  const stdout: string[] = [];
  const stderr: string[] = [];
  const exit = await runFeedProbeCli(
    ["https://www.fixture.test/feed.xml/"],
    {
      repoRoot: repositoryRoot,
      loadSourceCatalog: sourceCatalog,
      probe: async () => {
        probeCalls += 1;
        throw new Error("network transport must not run");
      },
      stdout: line => stdout.push(line),
      stderr: line => stderr.push(line),
    },
  );
  expect(exit).toBe(2);
  expect(probeCalls).toBe(0);
  expect(stderr.join("\n")).toContain("Duplicate catalog target");
});

test("source selection filters feeds by vertical and ID", async () => {
  const parsed = parseFeedProbeCliArguments([
    "--from-config", "feeds",
    "--vertical", "ai",
    "--id", "alpha-ai",
  ]);
  expect(parsed.kind).toBe("options");
  if (parsed.kind !== "options") return;
  const targets = await resolveFeedProbeTargets(parsed.options, sourceCatalog);
  expect(targets).toEqual([{
    feed_id: "alpha-ai",
    url: "https://fixture.test/feed.xml",
    status: "active",
    vertical: "ai",
  }]);

  const retired = parseFeedProbeCliArguments(["--from-config", "retired", "--id", "legacy-india"]);
  expect(retired.kind).toBe("options");
  if (retired.kind !== "options") return;
  const retiredTargets = await resolveFeedProbeTargets(retired.options, sourceCatalog);
  expect(retiredTargets[0]?.feed_id).toBe("legacy-india");

  const noTargets = parseFeedProbeCliArguments([]);
  expect(noTargets.kind).toBe("options");
  if (noTargets.kind !== "options") return;
  await expect(resolveFeedProbeTargets(noTargets.options, sourceCatalog))
    .rejects.toThrow("No feed targets were provided");
});

test("normalized URL duplicate detection is stable", () => {
  expect(normalizeFeedUrl("https://www.example.com/feed.xml/"))
    .toBe("https://example.com/feed.xml");
  expect(normalizeFeedUrl("https://example.com/feed.xml?b=2&a=1"))
    .toBe("https://example.com/feed.xml?a=1&b=2");
});

test("safe report and trace paths stay relative and inside the repository", () => {
  const trace = resolveSafeArtifactPath(
    repositoryRoot,
    "backend/var/probes/cli-test.jsonl",
    new Date("2026-10-28T22:00:00Z"),
  );
  expect(trace.relative).toBe("backend/var/probes/cli-test.jsonl");
  expect(defaultTraceRelativePath(new Date("2026-10-28T22:00:00Z")))
    .toBe("backend/var/probes/2026-10-28T22-00-00Z.jsonl");
  expect(() => resolveSafeArtifactPath(repositoryRoot, "../outside.jsonl"))
    .toThrow("relative POSIX");
  expect(() => resolveSafeArtifactPath(repositoryRoot, "frontend/public/report.jsonl"))
    .toThrow("Artifact path would write");
  expect(() => resolveSafeArtifactPath(repositoryRoot, "backend/var/probes/report.txt"))
    .toThrow(".jsonl");
});

test("real core pass and report exit zero with recorded transport", async () => {
  const feed = await existingFeedFixture("feed.xml");
  const article = await existingFeedFixture("readable-article.html");
  const boundary = await recordedBoundary({
    "https://pass-fixture.test/robots.txt": { status: 404, body: "" },
    "https://pass-fixture.test/feed.xml": { status: 200, body: feed },
    "https://fixture.test/robots.txt": { status: 404, body: "" },
    "https://fixture.test/article-one": { status: 200, body: article },
    "https://fixture.test/article-two": { status: 200, body: article },
    "https://fixture.test/article-three": { status: 200, body: article },
  });
  const traceRelative = "backend/var/probes/cli-pass-test.jsonl";
  const reportRelative = "backend/var/probes/cli-pass-test-report.jsonl";

  try {
    const stdout: string[] = [];
    const stderr: string[] = [];
    const exit = await runFeedProbeCli(
      [
        "--articles", "3",
        "--trace", traceRelative,
        "--report", reportRelative,
        "--json",
        "https://pass-fixture.test/feed.xml",
      ],
      {
        repoRoot: repositoryRoot,
        loadSourceCatalog: sourceCatalog,
        probe: async request => probeFeed(request, { boundary }),
        stdout: line => stdout.push(line),
        stderr: line => stderr.push(line),
      },
    );
    expect(exit).toBe(0);
    expect(stderr.join("\n")).toContain("failed/total: 0/1");
    expect(stdout).toHaveLength(1);
    const summary = JSON.parse(stdout[0]!);
    expect(summary.total).toBe(1);
    expect(summary.passed).toBe(1);
    expect(summary.failed).toBe(0);

    const reportText = await Bun.file(join(repositoryRoot, reportRelative)).text();
    const lines = reportText.trim().split("\n");
    expect(lines.length).toBe(1);
    const report = JSON.parse(lines[0]!);
    expect(FeedProbeReportSchema.safeParse(report).success).toBe(true);
    expect(report.passed).toBe(true);
    expect(reportText).not.toContain("<html");
    expect(reportText).not.toContain("A readable fixture article");
  } finally {
    await removeNamedFile(traceRelative);
    await removeNamedFile(reportRelative);
  }
});

test("real core feed failure returns exit one with a body-free trace", async () => {
  const boundary = await recordedBoundary({
    "https://fail-fixture.test/robots.txt": { status: 404, body: "" },
    "https://fail-fixture.test/feed.xml": { status: 404, body: "" },
  });
  const traceRelative = "backend/var/probes/cli-fail-test.jsonl";

  try {
    const stderr: string[] = [];
    const exit = await runFeedProbeCli(
      ["--articles", "1", "--trace", traceRelative, "https://fail-fixture.test/feed.xml"],
      {
        repoRoot: repositoryRoot,
        loadSourceCatalog: sourceCatalog,
        probe: async request => probeFeed(request, { boundary }),
        stdout: () => {},
        stderr: line => stderr.push(line),
      },
    );
    expect(exit).toBe(1);
    expect(stderr.join("\n")).toContain("failed/total: 1/1");
    const traceText = await Bun.file(join(repositoryRoot, traceRelative)).text();
    const report = JSON.parse(traceText.trim());
    expect(FeedProbeReportSchema.safeParse(report).success).toBe(true);
    expect(report.passed).toBe(false);
    expect(report.verdict).toBe("feed_failure");
    expect(traceText).not.toContain("<html");
    expect(traceText).not.toContain("article_text");
  } finally {
    await removeNamedFile(traceRelative);
  }
});
