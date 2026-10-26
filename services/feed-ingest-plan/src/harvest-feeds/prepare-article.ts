/** Apply the same pre-download gates to a feed offer in the planner and public stage APIs. */
import { deriveCandidateId } from "@idhazh/common-contracts";
import type { DropReason, RejectionDetails } from "@idhazh/common-contracts";
import type { HarvestContext, OfferedArticle, HarvestArticleResult } from "./harvest-types";
import { HarvestArticleResultSchema, utcTimestamp } from "./harvest-types";
import type { HarvestInputs } from "./load-harvest-inputs";
import { canonicalizeUrl } from "./url-cleaner";
import { matchUrlExclusion, urlExclusionMarker } from "./url-exclusions";
import { recordRejection } from "./record-rejection";
import { calculateFreshness } from "../screen-article-candidates/freshness-decay";
import { resolvePolicy } from "../config/resolve-policy";

// These existing feed and extracted headline bounds define the input format.
const feedTitleLimit = 500;
const pageTitleLimit = 200;
export function resolveArticleTitle(feedTitle: string | null, pageTitle: string | null) {
  if (feedTitle) return [...feedTitle].slice(0, feedTitleLimit).join("").trim();
  return pageTitle && [...pageTitle].length <= pageTitleLimit ? pageTitle : null;
}
export function prepareArticle(offered: OfferedArticle, inputs: HarvestInputs, context: HarvestContext) {
  const { source, entry } = offered;
  const candidateId = deriveCandidateId(context.writer.run_id, source.source_id, entry.entry_ordinal);
  let identity: ReturnType<typeof canonicalizeUrl> | null = null;
  if (entry.link) {
    try { identity = canonicalizeUrl(entry.link); }
    catch { /* Malformed discovery addresses are never requested. */ }
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
  if (identity === null || !entry.link) return reject("MISSING_REQUIRED_FIELDS");
  const blocked = matchUrlExclusion(identity.canonical_url, inputs.config.harvest.url_exclusions);
  if (blocked !== undefined) return reject("BLOCKED_URL_MARKER", {
    matched_url_key: identity.url_key, matched_url_marker: urlExclusionMarker(blocked),
  });
  const publishedOn = context.exclusions?.published_on.get(identity.url_key);
  if (publishedOn !== undefined) return reject("ALREADY_PUBLISHED", {
    matched_url_key: identity.url_key, published_on: publishedOn, history_window_days: context.exclusions!.published_window_days,
  });
  const failureCode = context.exclusions?.settled_failure_codes.get(identity.url_key);
  if (failureCode !== undefined) return reject("SETTLED_FAILURE", { matched_url_key: identity.url_key, failure_code: failureCode });
  if (article.title) {
    const policy = resolvePolicy(inputs, context.overrides);
    const freshness = calculateFreshness(entry, undefined, observation.observed_at, context.max_future_hours, policy);
    if (freshness.timing_source === "published_at" && freshness.age_hours !== null && freshness.timing_at !== null
      && freshness.age_hours > policy.triage.max_age_hours) {
      return reject("STALE_MAX_AGE_EXCEEDED", { age_hours: freshness.age_hours, max_age_hours: policy.triage.max_age_hours },
        { ...observation, preflight_freshness: {
          timing_at: freshness.timing_at, timing_source: "published_at", age_hours: freshness.age_hours, recency_bonus: freshness.recency_bonus,
        } });
    }
  }
  return { status: "admitted" as const, candidate_id: candidateId, identity, article, observation };
}
