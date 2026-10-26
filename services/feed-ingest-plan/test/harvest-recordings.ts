/** Replay only the named offline feed, article, address and protocol recordings. */
import { z } from "zod";
import { loadHarvestInputs } from "../src/harvest-feeds/load-harvest-inputs";
import type { ConfiguredSource } from "../src/harvest-feeds/load-harvest-inputs";
import type { HarvestContext, RejectionDestination } from "../src/harvest-feeds/harvest-types";
import type { HarvestTransport, TransportRequest, TransportResponse } from "../src/harvest-feeds/transport";
import type { ResolveAddresses } from "../src/harvest-feeds/safe-target";

const root = new URL("../../../", import.meta.url);
const fixtures = new URL("tests/fixtures/feed-ingest-plan/", root);
const AddressSchema = z.object({ address: z.string(), family: z.union([z.literal(4), z.literal(6)]) });
const ResponseSchema = z.object({
  status: z.int().optional(), body: z.string().optional(), fixture: z.enum(["rss", "atom", "article"]).optional(),
  location: z.string().optional(), error: z.string().optional(),
});
const RecordingsSchema = z.object({
  addresses: z.record(z.string(), z.array(AddressSchema)),
  responses: z.record(z.string(), z.array(ResponseSchema).min(1)),
});
export type RecordedResponse = z.infer<typeof ResponseSchema>;

export async function readRecordings() {
  const [raw, rss, atom, article] = await Promise.all([
    Bun.file(new URL("harvest-responses.json", fixtures)).json(),
    Bun.file(new URL("harvest-rss.xml", fixtures)).text(),
    Bun.file(new URL("harvest-atom.xml", fixtures)).text(),
    Bun.file(new URL("harvest-article.html", fixtures)).text(),
  ]);
  return { ...RecordingsSchema.parse(raw), bodies: { rss, atom, article } };
}
export type Recordings = Awaited<ReturnType<typeof readRecordings>>;

export class RecordedTransport implements HarvestTransport {
  readonly requests: TransportRequest[] = [];
  active = 0;
  peak = 0;
  on_request?: (request: TransportRequest) => void;
  private readonly positions = new Map<string, number>();
  constructor(readonly recordings: Recordings) {}

  readonly resolve: ResolveAddresses = async hostname => {
    const addresses = this.recordings.addresses[hostname];
    if (!addresses) throw Object.assign(new Error("recorded DNS has no address"), { code: "ENOTFOUND" });
    return addresses;
  };

  async request(input: TransportRequest): Promise<TransportResponse> {
    input.signal.throwIfAborted();
    const url = input.url.href;
    const responses = this.recordings.responses[url];
    if (!responses) throw new Error(`No recorded response for ${url}; network is not permitted`);
    this.requests.push(input);
    this.on_request?.(input);
    const index = this.positions.get(url) ?? 0;
    this.positions.set(url, index + 1);
    const response = responses[Math.min(index, responses.length - 1)];
    if (!response) throw new Error("recording contains no response");
    this.peak = Math.max(this.peak, ++this.active);
    try {
      await Bun.sleep(1);
      if (response.error === "timeout") {
        await new Promise<never>((_, reject) => {
          if (input.signal.aborted) reject(input.signal.reason);
          else input.signal.addEventListener("abort", () => reject(input.signal.reason), { once: true });
        });
      }
      if (response.error) throw Object.assign(new Error("recorded transport failure"), { code: response.error });
      if (response.status === undefined) throw new Error("recording is missing its observed status");
      const body = response.fixture ? this.recordings.bodies[response.fixture] : response.body;
      if (body === undefined) throw new Error("recording is missing its observed body");
      return { status: response.status, body, location: response.location ?? null };
    } finally { this.active--; }
  }
}

export function source(patch: Partial<ConfiguredSource> = {}): ConfiguredSource {
  return {
    id: "recorded-news", url: "https://news.example/feed.xml", title: "Configured science news",
    kind: "reporting", tier: 2, form: "article",
    weight: 0.8, status: "active", retired_on: null, added_on: null,
    retirement_reason: null, publisher_id: null, ...patch,
  };
}

export async function inputs(sources: unknown[] = [source()], overrides: {
  harvest?: Record<string, unknown>; extraction?: Record<string, unknown>;
  lenses?: unknown; entities?: unknown; salience?: unknown; publishers?: unknown;
} = {}) {
  const [config, taxonomy, extraction] = await Promise.all([
    Bun.file(new URL("config/feed-ingest-plan.json", root)).json(),
    Bun.file(new URL("config/taxonomy.json", root)).json(),
    Bun.file(new URL("config/idhazh.json", root)).json(),
  ]);
  return loadHarvestInputs({
    config: { ...config, harvest: { ...config.harvest, concurrency: 2, fetch_timeout_ms: 200, ...overrides.harvest } },
    taxonomy: { ...taxonomy, ...(overrides.lenses === undefined ? {} : { lenses: overrides.lenses }) },
    sources: {
      feeds: sources,
      ...(overrides.salience === undefined ? {} : { salience: overrides.salience }),
      ...(overrides.publishers === undefined ? {} : { publishers: overrides.publishers }),
    },
    extraction: {
      ...extraction,
      extract: { ...extraction.extract, max_retries: 0, backoff_initial_seconds: 0, ...overrides.extraction },
    },
  });
}

export function context(log: HarvestContext["log"] = () => {}): HarvestContext {
  return {
    max_future_hours: 6,
    writer: {
      run_id: "2026-10-21-700", attempt: 2, job: null, pipeline_name: "feed-ingest-plan",
      task_name: "harvest-feeds", shard: 0, producer: "tests.harvest", git_sha: "a".repeat(40),
    },
    correlation_id: "recorded-harvest-700",
    clock: () => new Date("2026-10-21T23:59:59.000Z"), log,
    observation_clock: () => new Date("2026-10-21T23:59:59.000Z"),
  };
}

export function destination(outputRoot: string): RejectionDestination {
  return {
    outputRoot,
    registryEntry: {
      name: "rejections", family: "feed-ingest-plan", grain: "raw-and-compact",
      lifecycle_status: "active", prefix: ["feed-ingest-plan", "rejections"],
    },
    ledgerSettings: { format: "parquet", compression_raw: "snappy", compression_compact: "zstd" },
  };
}

export async function readSafety() {
  return z.object({
    sanitizer_version: z.string(),
    sanitizer: z.array(z.object({ input: z.string(), expected: z.string() })),
    unsafe_targets: z.array(z.string()),
    url_exclusions: z.array(z.object({
      host: z.string(), path_prefix: z.string(), include_subdomains: z.boolean(),
    })),
    url_exclusion_cases: z.array(z.object({
      name: z.string(), url: z.string(),
      rules: z.array(z.object({ host: z.string(), path_prefix: z.string(), include_subdomains: z.boolean() })).optional(),
      expected: z.boolean(),
    })),
    invalid_url_exclusions: z.array(z.unknown()),
    robots: z.array(z.object({
      name: z.string(), body: z.string(), allowed: z.array(z.string()), denied: z.array(z.string()),
    })),
    robots_responses: z.array(ResponseSchema.extend({
      expected: z.enum(["robots-denied", "robots-unknown"]).nullable(),
    })),
  }).parse(await Bun.file(new URL("harvest-safety.json", fixtures)).json());
}
