/** Probe feed and article access without reading or writing source or item state. */
import {
  FeedIngestConfigSchema,
  HarvestDiagnosticsSchema,
  ItemHealthFailureCodeSchema,
  FeedProbeRequestSchema,
  FeedProbeResultSchema,
} from "@idhazh/common-contracts";
import type {
  FeedIngestConfig,
  FeedProbeArticleSample,
  FeedProbeResult,
  FeedProbeWarning,
  HarvestDiagnostics,
  ItemHealthFailureCode,
} from "@idhazh/common-contracts";
import { ArticleExtractionError } from "@idhazh/feed-ingest-plan/dom-extractor";
import { fetchDiagnostics } from "@idhazh/feed-ingest-plan/fetch-diagnostics";
import { ExtractionControlsSchema } from "@idhazh/feed-ingest-plan/extraction-controls";
import type { ExtractionControls } from "@idhazh/feed-ingest-plan/extraction-controls";
import { parseDocument } from "@idhazh/feed-ingest-plan/parse-document";
import { FeedParseError, parseFeed } from "@idhazh/feed-ingest-plan/parse-feed";
import { createPermittedFetcher } from "@idhazh/feed-ingest-plan/robots-policy";
import type { FetchResult } from "@idhazh/feed-ingest-plan/robots-policy";
import type { HarvestTransport } from "@idhazh/feed-ingest-plan/transport";
import type { ResolveAddresses } from "@idhazh/feed-ingest-plan/safe-target";

export type FeedProbeOptions = {
  signal?: AbortSignal;
  harvest?: FeedIngestConfig["harvest"];
  extraction?: ExtractionControls;
  transport?: HarvestTransport;
  resolve?: ResolveAddresses;
  boundary?: {
    transport?: HarvestTransport;
    resolve?: ResolveAddresses;
  };
};

type FeedProbeSettings = {
  harvest: FeedIngestConfig["harvest"];
  extraction: ExtractionControls;
};

async function loadSettings(options: FeedProbeOptions): Promise<FeedProbeSettings> {
  let planning: FeedIngestConfig | null = null;
  if (options.harvest === undefined || options.extraction === undefined) {
    const planningRaw = await Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json();
    planning = FeedIngestConfigSchema.parse(planningRaw);
  }
  const harvest = options.harvest === undefined
    ? planning!.harvest
    : FeedIngestConfigSchema.shape.harvest.parse(options.harvest);
  let extraction: ExtractionControls;
  if (options.extraction !== undefined) {
    extraction = ExtractionControlsSchema.parse(options.extraction);
  } else {
    const extractionRaw = await Bun.file(new URL("../../../config/idhazh.json", import.meta.url)).json() as {
      extract?: unknown;
    };
    if (!extractionRaw.extract || typeof extractionRaw.extract !== "object" || Array.isArray(extractionRaw.extract)) {
      throw new Error("Production extraction config must define an extract object");
    }
    extraction = ExtractionControlsSchema.parse({
      ...(extractionRaw.extract as Record<string, unknown>),
      semantic_fallback: planning!.harvest.semantic_fallback,
      press_release_filter: planning!.content_filters.press_release,
    });
  }
  return { harvest, extraction };
}

function timeoutDiagnostics(): HarvestDiagnostics {
  return HarvestDiagnosticsSchema.parse({
    http_status: null,
    robots: null,
    fetch_failure: "timeout",
    robots_failure: null,
    robots_http_status: null,
    error_code: null,
    failure_code: "network_error",
    stopped_stage: "fetch",
    detail: "timeout",
    fetch_ms: null,
    extract_ms: null,
    warnings: [],
    quality: null,
  });
}

function parserFailureDiagnostics(result: FetchResult, fetchMs: number): HarvestDiagnostics {
  return HarvestDiagnosticsSchema.parse({
    ...fetchDiagnostics(result, fetchMs),
    stopped_stage: "parse",
    failure_code: "unknown",
    detail: "malformed-feed",
  });
}

function emptyFeedDiagnostics(result: FetchResult, fetchMs: number): HarvestDiagnostics {
  return HarvestDiagnosticsSchema.parse({
    ...fetchDiagnostics(result, fetchMs),
    stopped_stage: "parse",
    failure_code: "unknown",
    detail: "empty-feed",
  });
}

function itemFailureCode(diagnostics: HarvestDiagnostics | null): ItemHealthFailureCode {
  const value = diagnostics?.failure_code ?? null;
  const parsed = ItemHealthFailureCodeSchema.safeParse(value);
  return parsed.success && parsed.data !== "not_attempted" ? parsed.data : "unknown";
}

function bodyFreeResult(
  verdict: FeedProbeResult["verdict"],
  samples: readonly FeedProbeArticleSample[],
  diagnostics: HarvestDiagnostics | null,
  warnings: readonly FeedProbeWarning[],
  confirmation: { paywall_confirmed: boolean; paywall_evidence: FeedProbeResult["paywall_evidence"]; },
): FeedProbeResult {
  const readableCount = samples.filter(sample => sample.readable).length;
  const paywallSampleCount = samples.filter(sample => sample.paywall === true).length;
  const passed = readableCount > 0;
  let failureCode: FeedProbeResult["failure_code"] = null;
  if (verdict === "paywall_confirmed" || verdict === "paywall_not_confirmed") {
    failureCode = "paywalled";
  } else if (!passed && verdict === "article_fetch_failure" && samples.length) {
    const sampled = samples.find(sample => sample.diagnostics !== null)?.diagnostics ?? null;
    failureCode = itemFailureCode(sampled);
  } else if (!passed && verdict === "feed_failure") {
    failureCode = itemFailureCode(diagnostics);
  }
  return FeedProbeResultSchema.parse({
    verdict,
    passed,
    paywall_confirmed: confirmation.paywall_confirmed,
    sample_count: samples.length,
    readable_count: readableCount,
    paywall_sample_count: paywallSampleCount,
    paywall_evidence: confirmation.paywall_evidence,
    failure_code: failureCode,
    diagnostics,
    warnings: [...warnings],
    samples: [...samples],
  });
}

function timedOutResult(): FeedProbeResult {
  const diagnostics = timeoutDiagnostics();
  return bodyFreeResult("feed_failure", [], diagnostics, [], {
    paywall_confirmed: false,
    paywall_evidence: "not-observed",
  });
}

function sampleWithFetchFailure(
  dated: boolean,
  fetched: FetchResult,
  fetchMs: number,
): FeedProbeArticleSample {
  return {
    readable: false,
    dated,
    paywall: null,
    paywall_evidence: "not-observed",
    diagnostics: fetchDiagnostics(fetched, fetchMs),
  };
}

export async function probeFeed(
  request: unknown,
  signalOrOptions: AbortSignal | FeedProbeOptions = {},
): Promise<FeedProbeResult> {
  const parsed = FeedProbeRequestSchema.parse(request);
  const options = signalOrOptions instanceof AbortSignal ? { signal: signalOrOptions } : signalOrOptions;
  const operationSignal = options.signal;
  if (operationSignal?.aborted) return timedOutResult();

  const settings = await loadSettings(options);
  const boundary = {
    ...(options.boundary ?? {}),
    ...(options.transport === undefined ? {} : { transport: options.transport }),
    ...(options.resolve === undefined ? {} : { resolve: options.resolve }),
  };
  const fetcher = createPermittedFetcher(
    settings.harvest,
    settings.extraction,
    boundary,
  );
  const feedStarted = performance.now();
  const feedFetched = await fetcher.fetch(parsed.feed_url, undefined, "feed", operationSignal);
  const feedFetchMs = Math.round(performance.now() - feedStarted);
  if (feedFetched.body === null) {
    const diagnostics = fetchDiagnostics(feedFetched, feedFetchMs);
    return bodyFreeResult("feed_failure", [], diagnostics, [], {
      paywall_confirmed: false,
      paywall_evidence: "not-observed",
    });
  }

  let entries: Awaited<ReturnType<typeof parseFeed>>;
  try {
    entries = await parseFeed(feedFetched.body);
  } catch (error) {
    if (error instanceof FeedParseError) {
      const diagnostics = parserFailureDiagnostics(feedFetched, feedFetchMs);
      return bodyFreeResult("feed_failure", [], diagnostics, [], {
        paywall_confirmed: false,
        paywall_evidence: "not-observed",
      });
    }
    throw error;
  }
  const candidates = entries.filter(entry => entry.link !== null).slice(0, parsed.sample_count);
  if (!candidates.length) {
    const diagnostics = emptyFeedDiagnostics(feedFetched, feedFetchMs);
    return bodyFreeResult("feed_failure", [], diagnostics, [], {
      paywall_confirmed: false,
      paywall_evidence: "not-observed",
    });
  }

  const samples: FeedProbeArticleSample[] = [];
  const warnings = new Set<FeedProbeWarning>();
  let operationAborted = false;
  for (const entry of candidates) {
    if (operationSignal?.aborted) {
      operationAborted = true;
      break;
    }
    const dated = entry.published_at !== null;
    const link = entry.link!;
    const articleStarted = performance.now();
    const fetched = await fetcher.fetch(link, undefined, "article", operationSignal);
    const fetchMs = Math.round(performance.now() - articleStarted);
    if (fetched.body === null) {
      samples.push(sampleWithFetchFailure(dated, fetched, fetchMs));
      if (operationSignal?.aborted) {
        operationAborted = true;
        break;
      }
      continue;
    }

    const extractionStarted = performance.now();
    try {
      const extracted = await parseDocument(
        "article",
        fetched.body,
        link,
        settings.extraction,
        undefined,
        operationSignal === undefined ? {} : { signal: operationSignal },
      );
      const extractMs = Math.round(performance.now() - extractionStarted);
      let extractionFailure: HarvestDiagnostics["extraction_failure"] = null;
      let stoppedStage: HarvestDiagnostics["stopped_stage"] = null;
      let detail: HarvestDiagnostics["detail"] = null;
      let failureCode: HarvestDiagnostics["failure_code"] = null;
      if (!extracted.article_text.trim()) {
        extractionFailure = "empty-content";
        stoppedStage = "extract";
        detail = "empty-content";
        failureCode = "no_text";
      } else if (extracted.quality?.rejected && extracted.quality.failure_code !== null) {
        stoppedStage = "extract";
        detail = extracted.quality.failure_code;
        failureCode = extracted.quality.failure_code;
      }
      const diagnostics = HarvestDiagnosticsSchema.parse({
        ...fetchDiagnostics(fetched, fetchMs),
        extract_ms: extractMs,
        extraction_failure: extractionFailure,
        failure_code: failureCode,
        stopped_stage: stoppedStage,
        detail,
        warnings: extracted.warnings,
        quality: extracted.quality,
      });
      const readable = extracted.paywall !== true
        && extracted.article_text.trim().length > 0
        && extracted.quality?.rejected !== true;
      samples.push({
        readable,
        dated,
        paywall: extracted.paywall,
        paywall_evidence: extracted.paywall_evidence,
        diagnostics,
      });
      for (const warning of extracted.warnings) warnings.add(warning);
    } catch (error) {
      if (operationSignal?.aborted) {
        operationAborted = true;
        break;
      }
      const extractMs = Math.round(performance.now() - extractionStarted);
      const extractionFailure = error instanceof ArticleExtractionError ? error.reason : null;
      const diagnostics = HarvestDiagnosticsSchema.parse({
        ...fetchDiagnostics(fetched, fetchMs),
        extract_ms: extractMs,
        extraction_failure: extractionFailure,
        failure_code: "unknown",
        stopped_stage: "extract",
        detail: extractionFailure,
        warnings: [],
        quality: null,
      });
      samples.push({
        readable: false,
        dated,
        paywall: null,
        paywall_evidence: "not-observed",
        diagnostics,
      });
    }
  }

  if (operationAborted) {
    return bodyFreeResult("article_fetch_failure", samples, timeoutDiagnostics(), [...warnings], {
      paywall_confirmed: false,
      paywall_evidence: "not-observed",
    });
  }

  const evidenceCounts = new Map<"json-ld" | "configured-marker", number>();
  for (const sample of samples) {
    if (sample.paywall !== true) continue;
    if (sample.paywall_evidence !== "json-ld" && sample.paywall_evidence !== "configured-marker") continue;
    evidenceCounts.set(sample.paywall_evidence, (evidenceCounts.get(sample.paywall_evidence) ?? 0) + 1);
  }
  const confirmedEvidence = [...evidenceCounts.entries()].find(([, count]) => count >= 2)?.[0] ?? null;
  const paywallConfirmed = confirmedEvidence !== null;
  const evidence = confirmedEvidence
    ?? samples.find(sample => sample.paywall === true)?.paywall_evidence
    ?? "not-observed";
  const readableCount = samples.filter(sample => sample.readable).length;
  let verdict: FeedProbeResult["verdict"];
  if (readableCount > 0) verdict = "pass";
  else if (paywallConfirmed) verdict = "paywall_confirmed";
  else if (samples.some(sample => sample.paywall === true)) verdict = "paywall_not_confirmed";
  else verdict = "article_fetch_failure";

  if (readableCount > 0 && samples.length > 0 && samples.every(sample => sample.dated === false)) {
    warnings.add("no_dated_entries");
  }
  const aggregateDiagnostics = verdict === "article_fetch_failure"
    ? samples.find(sample => sample.diagnostics !== null)?.diagnostics ?? null
    : null;
  return bodyFreeResult(verdict, samples, aggregateDiagnostics, [...warnings], {
    paywall_confirmed: paywallConfirmed,
    paywall_evidence: evidence,
  });
}

export const feedProbe = probeFeed;
