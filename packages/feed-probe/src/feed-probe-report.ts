/** Build strict, body-free machine reports from bounded feed-probe core results. */
import { z } from "zod";
import {
  CountSchema,
  FEED_PROBE_VERSION,
  FeedProbeArticleSampleSchema,
  FeedProbePaywallEvidenceSchema,
  FeedProbeResultSchema,
  FeedProbeVerdictSchema,
  FeedProbeWarningSchema,
  HarvestDiagnosticsSchema,
  ItemHealthFailureCodeSchema,
  SlugSchema,
  UrlSchema,
} from "@idhazh/common-contracts";

export const FeedProbeReportSchema = z.strictObject({
  version: z.literal(FEED_PROBE_VERSION).default(FEED_PROBE_VERSION),
  feed_id: SlugSchema,
  feed_url: UrlSchema,
  http_status: z.int().min(100).max(599).nullable(),
  robots: z.enum(["allowed", "denied", "unknown"]).nullable(),
  timings_ms: z.strictObject({
    total: CountSchema,
    feed: CountSchema.nullable(),
    articles: CountSchema,
    extract: CountSchema,
  }),
  counts: z.strictObject({
    entries: CountSchema,
    dated_entries: CountSchema,
    sample: CountSchema,
    readable: CountSchema,
    paywall: CountSchema,
    failed_articles: CountSchema,
    max_words: CountSchema.nullable(),
  }),
  verdict: FeedProbeVerdictSchema,
  passed: z.boolean(),
  paywall_confirmed: z.boolean(),
  paywall_evidence: FeedProbePaywallEvidenceSchema,
  failure_code: ItemHealthFailureCodeSchema.nullable(),
  diagnostics: HarvestDiagnosticsSchema.nullable(),
  warnings: z.array(FeedProbeWarningSchema).max(5),
  samples: z.array(FeedProbeArticleSampleSchema).max(10),
}).meta({
  version: FEED_PROBE_VERSION,
  changelog: [
    { version: FEED_PROBE_VERSION, change: "Declare strict machine-readable feed-probe report lines." },
  ],
});
export type FeedProbeReport = z.infer<typeof FeedProbeReportSchema>;

export const FeedProbeReportSummarySchema = z.strictObject({
  version: z.literal(FEED_PROBE_VERSION).default(FEED_PROBE_VERSION),
  total: CountSchema,
  passed: CountSchema,
  failed: CountSchema,
  reports: z.array(FeedProbeReportSchema),
}).meta({
  version: FEED_PROBE_VERSION,
  changelog: [
    { version: FEED_PROBE_VERSION, change: "Declare strict feed-probe JSON summary output." },
  ],
});
export type FeedProbeReportSummary = z.infer<typeof FeedProbeReportSummarySchema>;

export function buildFeedProbeReport(
  feedId: string,
  feedUrl: string,
  result: unknown,
  totalMs: number,
): FeedProbeReport {
  const parsed = FeedProbeResultSchema.parse(result);
  const datedEntries = parsed.samples.filter(sample => sample.dated === true).length;
  const maxWords = parsed.samples.reduce<number | null>((current, sample) => {
    const words = sample.diagnostics?.quality?.word_count ?? null;
    if (words === null) return current;
    return current === null ? words : Math.max(current, words);
  }, null);
  const articleFetchMs = parsed.samples.reduce(
    (total, sample) => total + (sample.diagnostics?.fetch_ms ?? 0),
    0,
  );
  const articleExtractMs = parsed.samples.reduce(
    (total, sample) => total + (sample.diagnostics?.extract_ms ?? 0),
    0,
  );
  const feedDiagnostics = parsed.verdict === "article_fetch_failure"
    ? null
    : parsed.diagnostics;

  return FeedProbeReportSchema.parse({
    version: parsed.version,
    feed_id: feedId,
    feed_url: feedUrl,
    http_status: feedDiagnostics?.http_status ?? null,
    robots: feedDiagnostics?.robots ?? null,
    timings_ms: {
      total: Math.max(0, Math.round(totalMs)),
      feed: feedDiagnostics?.fetch_ms ?? null,
      articles: articleFetchMs,
      extract: articleExtractMs,
    },
    counts: {
      entries: parsed.sample_count,
      dated_entries: datedEntries,
      sample: parsed.sample_count,
      readable: parsed.readable_count,
      paywall: parsed.paywall_sample_count,
      failed_articles: parsed.sample_count - parsed.readable_count,
      max_words: maxWords,
    },
    verdict: parsed.verdict,
    passed: parsed.passed,
    paywall_confirmed: parsed.paywall_confirmed,
    paywall_evidence: parsed.paywall_evidence,
    failure_code: parsed.failure_code,
    diagnostics: parsed.diagnostics,
    warnings: parsed.warnings,
    samples: parsed.samples,
  });
}

export function buildFeedProbeReportSummary(reports: readonly FeedProbeReport[]): FeedProbeReportSummary {
  const passed = reports.filter(report => report.passed).length;
  return FeedProbeReportSummarySchema.parse({
    version: FEED_PROBE_VERSION,
    total: reports.length,
    passed,
    failed: reports.length - passed,
    reports: [...reports],
  });
}
