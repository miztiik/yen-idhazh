/** Apply the same pre-download gates to a feed offer in the planner and public stage APIs. */
import { deriveCandidateId } from "@idhazh/common-contracts";
import type { DropReason, RejectionDetails } from "@idhazh/common-contracts";
import type { HarvestContext, OfferedArticle, HarvestArticleResult } from "./harvest-types";
import { HarvestArticleResultSchema, utcTimestamp } from "./harvest-types";
import type { HarvestInputs } from "./load-harvest-inputs";
import { deriveArticleIdentity, InvalidArticleUrlError } from "./article-identity";
import { UnsafeTargetError } from "./safe-target";
import { fetchDiagnostics } from "./fetch-diagnostics";
import { matchUrlExclusion, urlExclusionMarker } from "./url-exclusions";
import { recordRejection } from "./record-rejection";
import { calculateFreshness } from "../screen-article-candidates/freshness-decay";
import { resolvePolicy } from "../config/resolve-policy";
import { matchMediaArticle } from "./media-filter";
import { rejectArticleAge } from "../article-freshness-policy";

// These existing feed and extracted headline bounds define the input format.
const feedTitleLimit = 500;
const pageTitleLimit = 200;
export function resolveArticleTitle(feedTitle: string | null, pageTitle: string | null) {
  if (feedTitle) return [...feedTitle].slice(0, feedTitleLimit).join("").trim();
  return pageTitle && [...pageTitle].length <= pageTitleLimit ? pageTitle : null;
}
export function prepareArticle(offered: OfferedArticle, inputs: HarvestInputs, context: HarvestContext) {
  const { source, entry } = offered;
  const candidateId = deriveCandidateId(context.writer.run_id, source.feed_id, entry.entry_ordinal);
  let identity: ReturnType<typeof deriveArticleIdentity> | null = null;
  let unsafe = false;
  if (entry.link) {
    try { identity = deriveArticleIdentity(entry.link, inputs.config.harvest); }
    catch (error) {
      if (error instanceof UnsafeTargetError) unsafe = true;
      else if (!(error instanceof InvalidArticleUrlError)) throw error;
    }
  }
  const article = {
    candidate_id: candidateId, canonical_url: identity?.canonical_url ?? null, url_key: identity?.url_key ?? null,
    title: resolveArticleTitle(entry.title, null), categories: entry.categories,
  };
  const observation: HarvestArticleResult["observation"] = {
    candidate_id: candidateId, http_status: null, robots: null, fetch_failure: null, paywall: null,
    paywall_evidence: "not-observed", extraction: "not-attempted", observed_at: utcTimestamp(context.clock), diagnostics: null,
  };
  const reject = (reason: DropReason, details: Partial<RejectionDetails> = {}, measured = observation) => ({
    status: "rejected" as const,
    result: HarvestArticleResultSchema.parse({
      candidate: null, rejection: recordRejection(source, context, reason, details, article), observation: measured,
    }),
    candidate_id: candidateId, identity, article, observation,
  });
  if (unsafe) {
    const diagnostics = fetchDiagnostics({ body: null, http_status: null, failure: "unsafe-target", robots: null }, 0);
    return reject("FETCH_FAILED", { diagnostics }, { ...observation, fetch_failure: "unsafe-target", diagnostics });
  }
  if (identity === null || !entry.link) return reject("MISSING_REQUIRED_FIELDS");
  const blocked = matchUrlExclusion(identity.canonical_url, inputs.config.harvest.url_exclusions)
    ?? matchUrlExclusion(entry.link, inputs.config.harvest.url_exclusions);
  if (blocked !== undefined) return reject("BLOCKED_URL_MARKER", {
    matched_url_key: identity.url_key, matched_url_marker: urlExclusionMarker(blocked),
  });
  const publishedOn = context.exclusions?.published_on.get(identity.url_key);
  if (publishedOn !== undefined) return reject("ALREADY_PUBLISHED", {
    matched_url_key: identity.url_key, published_on: publishedOn, history_window_days: context.exclusions!.published_window_days,
  });
  const failureCode = context.exclusions?.settled_failure_codes.get(identity.url_key);
  if (failureCode !== undefined) return reject("SETTLED_FAILURE", {
    matched_url_key: identity.url_key, failure_code: failureCode,
  });
  const media = matchMediaArticle(entry.link, identity.canonical_url, entry.media_types ?? [], inputs.config);
  if (media !== null) return reject("MEDIA_CONTENT", media);
  if (article.title) {
    const policy = resolvePolicy(inputs);
    const freshness = calculateFreshness(entry, undefined, observation.observed_at, context.max_future_hours, policy);
    const ageRefusal = rejectArticleAge(inputs.config, source.tier, freshness.age_hours);
    if (freshness.timing_source === "published_at" && freshness.age_hours !== null && freshness.timing_at !== null
      && ageRefusal !== null) {
      return reject(ageRefusal.drop_reason, ageRefusal.details,
        { ...observation, preflight_freshness: {
          timing_at: freshness.timing_at, timing_source: "published_at", age_hours: freshness.age_hours, recency_bonus: freshness.recency_bonus,
        } });
    }
  }
  return { status: "admitted" as const, candidate_id: candidateId, identity, article, observation };
}
