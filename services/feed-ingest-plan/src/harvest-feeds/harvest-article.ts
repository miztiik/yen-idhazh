/** Turn one original feed entry into a validated candidate or one terminal rejection. */
import { FeedIngestCandidateSchema } from "@idhazh/common-contracts";
import type { HarvestDiagnostics } from "@idhazh/common-contracts";
import type { HarvestContext, OfferedArticle, HarvestArticleResult } from "./harvest-types";
import { HarvestArticleResultSchema } from "./harvest-types";
import type { HarvestInputs } from "./load-harvest-inputs";
import type { PermittedFetcher } from "./robots-policy";
import { extractArticle } from "./dom-extractor";
import { fetchRejection, recordRejection } from "./record-rejection";
import { fetchDiagnostics } from "./fetch-diagnostics";
import { parseDocument } from "./parse-document";
import { documentWork, describeArticleParse } from "./document-work";
import { prepareArticle, resolveArticleTitle } from "./prepare-article";

export async function harvestArticle(
  offered: OfferedArticle, inputs: HarvestInputs, fetcher: PermittedFetcher, context: HarvestContext,
): Promise<HarvestArticleResult> {
  const { source, entry } = offered;
  const prepared = prepareArticle(offered, inputs, context);
  const { candidate_id, identity, article, observation } = prepared;
  const eventIdentity = {
    run_id: context.writer.run_id, correlation_id: context.correlation_id,
    article_id: identity?.url_key ?? null, source_id: source.source_id,
  };
  const work = documentWork(context, eventIdentity, candidate_id, {
    document_kind: "article", source_id: source.source_id, publisher_id: source.publisher_id,
    candidate_id, observed_run_id: context.writer.run_id, observed_attempt: context.writer.attempt,
  });
  if (prepared.status === "rejected") {
    await work.skip();
    return prepared.result;
  }
  if (identity === null || entry.link === null) throw new Error("Admitted article lacks its validated discovery address");
  const fetchStarted = performance.now();
  const { fetched, observation: fetchedEvent } = await work.fetch(fetcher, entry.link);
  let diagnostics = fetchDiagnostics(fetched, Math.round(performance.now() - fetchStarted));
  const fetched_at = fetchedEvent.occurred_at;
  const fetchedObservation = {
    ...observation, http_status: fetched.http_status, robots: fetched.robots,
    fetch_failure: fetched.failure, observed_at: fetched_at,
    diagnostics,
  };
  if (fetched.body === null) {
    await work.skipParse(fetchedEvent.event_id);
    const failure = fetchRejection(fetched, inputs.config.harvest.fetch_timeout_ms, diagnostics);
    return HarvestArticleResultSchema.parse({
      candidate: null,
      rejection: recordRejection(source, context, failure.reason, failure.details, article),
      observation: fetchedObservation,
    });
  }
  let extracted: ReturnType<typeof extractArticle>;
  const extractStarted = performance.now();
  const body = fetched.body;
  const link = entry.link;
  const parsed = await work.parse(
    () => parseDocument("article", body, link, inputs.extraction, source.form, context.parser_pool, context.parser_options), fetchedEvent.event_id, describeArticleParse,
  );
  if (parsed.parsed === null) {
    diagnostics = {
      ...diagnostics, extract_ms: Math.round(performance.now() - extractStarted),
      extraction_failure: parsed.failure === "malformed-feed" ? null : parsed.failure,
      failure_code: "unknown", stopped_stage: "extract", detail: parsed.failure,
    };
    return HarvestArticleResultSchema.parse({
      candidate: null,
      rejection: recordRejection(source, context, "EXTRACT_FAILED", {
        http_status: fetched.http_status, diagnostics,
      }, article),
      observation: { ...fetchedObservation, extraction: "failed", diagnostics },
    });
  }
  extracted = parsed.parsed;
  const extract_ms = Math.round(performance.now() - extractStarted);
  article.title = resolveArticleTitle(article.title, extracted.page_title);
  const extraction = extracted.article_text ? "success" : "empty";
  const extraction_failure = !extracted.article_text ? "empty-content" : !article.title ? "missing-title" : null;
  diagnostics = {
    ...diagnostics, extract_ms,
    extraction_failure, failure_code: extraction_failure === "empty-content" ? "no_text"
      : extraction_failure === "missing-title" ? "no_title" : extracted.quality?.failure_code ?? null,
    stopped_stage: extraction_failure === null ? null : "extract", detail: extraction_failure,
    warnings: extracted.warnings,
    quality: extracted.quality,
  } satisfies HarvestDiagnostics;
  if (diagnostics.warnings.length) context.progress?.("ARTICLE_EXTRACTION_WARNING", {
    source_id: source.source_id, candidate_id, diagnostics,
  });
  const completeObservation = {
    ...fetchedObservation, paywall: extracted.paywall, paywall_evidence: extracted.paywall_evidence, extraction,
    diagnostics,
  };
  if (extracted.quality?.rejected) {
    diagnostics = {
      ...diagnostics, extraction_failure: null, stopped_stage: "extract", detail: extracted.quality.failure_code,
      failure_code: extracted.quality.failure_code,
    };
    return HarvestArticleResultSchema.parse({
      candidate: null,
      rejection: recordRejection(source, context, "EXTRACT_FAILED", { http_status: fetched.http_status, diagnostics }, article),
      observation: { ...completeObservation, diagnostics },
    });
  }
  if (!article.title || !extracted.article_text) {
    return HarvestArticleResultSchema.parse({
      candidate: null, rejection: recordRejection(source, context, extracted.article_text ? "MISSING_REQUIRED_FIELDS" : "EXTRACT_EMPTY", {
        http_status: fetched.http_status, diagnostics,
      }, article),
      observation: completeObservation,
    });
  }
  return HarvestArticleResultSchema.parse({
    candidate: FeedIngestCandidateSchema.parse({
      date: fetched_at.slice(0, 10), fetched_at,
      correlation_id: context.correlation_id, run_id: context.writer.run_id,
      candidate_id, entry_ordinal: entry.entry_ordinal,
      source_id: source.source_id, source, ...identity,
      title: article.title, categories: article.categories,
      article_text: extracted.article_text, word_count: extracted.word_count,
      author: extracted.author ?? entry.author, published_at: entry.published_at,
    }),
    rejection: null, observation: completeObservation,
  });
}
