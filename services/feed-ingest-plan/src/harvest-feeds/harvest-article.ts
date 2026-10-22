/** Turn one original feed entry into a validated candidate or one terminal rejection. */
import { FeedIngestCandidateSchema, deriveCandidateId } from "@idhazh/common-contracts";
import type { HarvestContext, OfferedArticle, HarvestArticleResult } from "./harvest-types";
import { HarvestArticleResultSchema, utcTimestamp } from "./harvest-types";
import type { HarvestInputs } from "./load-harvest-inputs";
import type { PermittedFetcher } from "./robots-policy";
import { ArticleExtractionError, extractArticle } from "./dom-extractor";
import { canonicalizeUrl } from "./url-cleaner";
import { fetchRejection, recordRejection } from "./record-rejection";
import { calculateFreshness } from "../screen-article-candidates/freshness-decay";
import { resolvePolicy } from "../config/resolve-policy";

// Existing discovery/extraction headline bounds, not editorial selection thresholds.
const FEED_TITLE_MAX_CHARS = 500;
const PAGE_TITLE_MAX_CHARS = 200;

export async function harvestArticle(
  offered: OfferedArticle, inputs: HarvestInputs, fetcher: PermittedFetcher, context: HarvestContext,
): Promise<HarvestArticleResult> {
  const { source, entry, policy } = offered;
  const candidate_id = deriveCandidateId(context.writer.run_id, source.source_id, entry.entry_ordinal);
  let identity: ReturnType<typeof canonicalizeUrl> | null = null;
  if (entry.link) {
    try { identity = canonicalizeUrl(entry.link); }
    catch { /* Invalid addresses are preserved as missing identity, never requested. */ }
  }
  const article = {
    candidate_id, canonical_url: identity?.canonical_url ?? null, url_key: identity?.url_key ?? null,
    title: entry.title ? [...entry.title].slice(0, FEED_TITLE_MAX_CHARS).join("").trim() : null,
    categories: entry.categories,
  };
  const observation = {
    candidate_id, http_status: null, robots: null, fetch_failure: null,
    paywall: null, paywall_evidence: "not-observed", extraction: "not-attempted",
    observed_at: utcTimestamp(context.clock),
  } satisfies HarvestArticleResult["observation"];
  if (!identity || !entry.link) {
    return HarvestArticleResultSchema.parse({
      candidate: null, rejection: recordRejection(source, context, "MISSING_REQUIRED_FIELDS", {}, article), observation,
    });
  }
  if (article.title) {
    const effectivePolicy = resolvePolicy(inputs, source.vertical, context.overrides);
    const freshness = calculateFreshness(entry, undefined, observation.observed_at, context.max_future_hours, effectivePolicy);
    if (freshness.timing_source === "published_at" && freshness.age_hours !== null
      && freshness.age_hours > effectivePolicy.triage.max_age_hours) {
      return HarvestArticleResultSchema.parse({
        candidate: null,
        rejection: recordRejection(source, context, "STALE_MAX_AGE_EXCEEDED", {
          age_hours: freshness.age_hours, max_age_hours: effectivePolicy.triage.max_age_hours,
        }, article),
        observation: { ...observation, preflight_freshness: freshness },
      });
    }
  }
  const fetched = await fetcher.fetch(entry.link);
  const fetched_at = utcTimestamp(context.clock);
  const fetchedObservation = {
    ...observation, http_status: fetched.http_status, robots: fetched.robots,
    fetch_failure: fetched.failure, observed_at: fetched_at,
  };
  if (fetched.body === null) {
    const failure = fetchRejection(fetched, inputs.config.harvest.fetch_timeout_ms);
    return HarvestArticleResultSchema.parse({
      candidate: null,
      rejection: recordRejection(source, context, article.title ? failure.reason : "MISSING_REQUIRED_FIELDS", failure.details, article),
      observation: fetchedObservation,
    });
  }
  let extracted: ReturnType<typeof extractArticle>;
  try { extracted = extractArticle(fetched.body, entry.link, inputs.extraction.paywall_markers); }
  catch (error) {
    if (!(error instanceof ArticleExtractionError)) throw error;
    return HarvestArticleResultSchema.parse({
      candidate: null,
      rejection: recordRejection(source, context, article.title ? "FETCH_FAILED" : "MISSING_REQUIRED_FIELDS", {}, article),
      observation: { ...fetchedObservation, extraction: "failed" },
    });
  }
  const pageTitle = extracted.page_title && [...extracted.page_title].length <= PAGE_TITLE_MAX_CHARS ? extracted.page_title : null;
  article.title ??= pageTitle;
  const extraction = extracted.article_text ? "success" : "empty";
  const completeObservation = {
    ...fetchedObservation, paywall: extracted.paywall, paywall_evidence: extracted.paywall_evidence, extraction,
  };
  if (!article.title || !extracted.article_text) {
    return HarvestArticleResultSchema.parse({
      candidate: null, rejection: recordRejection(source, context, "MISSING_REQUIRED_FIELDS", {}, article),
      observation: completeObservation,
    });
  }
  return HarvestArticleResultSchema.parse({
    candidate: FeedIngestCandidateSchema.parse({
      date: fetched_at.slice(0, 10), fetched_at,
      correlation_id: context.correlation_id, run_id: context.writer.run_id,
      candidate_id, entry_ordinal: entry.entry_ordinal,
      source_id: source.source_id, vertical: source.vertical, source, ...identity,
      title: article.title, categories: article.categories,
      article_text: extracted.article_text, word_count: extracted.word_count,
      author: extracted.author ?? entry.author, published_at: entry.published_at,
      labels: {
        assigned_desk: null, lenses: null, event_types: null, event_cluster_id: null,
        entities: null, origin: null, matcher_version: null,
      },
      policy,
    }),
    rejection: null, observation: completeObservation,
  });
}
