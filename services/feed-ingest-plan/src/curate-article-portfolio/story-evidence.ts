/** Which available story facts agree without claiming an embedding comparison? */
import type { PortfolioArticle } from "./portfolio-input";
import { compareHeadlineFigures } from "./headline-figures";
export type StoryComparison = Readonly<{
  left: string; right: string;
  method: "canonical-url" | "recorded-event-cluster" | "figure-clash" | "unavailable";
  matcher_version: string | null; matches: boolean | null;
  semantic_similarity: null; reason: string;
}>;

export function compareStory(left: PortfolioArticle, right: PortfolioArticle): StoryComparison {
  const a = left.candidate;
  const b = right.candidate;
  const identity = { left: a.candidate_id, right: b.candidate_id, semantic_similarity: null };
  if (a.url_key === b.url_key) {
    return { ...identity, method: "canonical-url", matcher_version: "canonical-url-sha256", matches: true, reason: "same canonical identity" };
  }
  const figures = compareHeadlineFigures(a.title, b.title);
  if (figures.clash) {
    return { ...identity, method: "figure-clash", matcher_version: "story-key-ascii-numbers-v1", matches: false, reason: "same headline words disagree about a figure" };
  }
  const publisher = left.evidence.publisher?.value;
  const otherPublisher = right.evidence.publisher?.value;
  if (publisher === undefined || otherPublisher === undefined || publisher === otherPublisher) {
    return { ...identity, method: "unavailable", matcher_version: null, matches: null, reason: "distinct recorded mastheads unavailable" };
  }
  if (a.labels.event_cluster_id !== null && a.labels.event_cluster_id === b.labels.event_cluster_id
    && a.labels.origin === b.labels.origin && a.labels.matcher_version === b.labels.matcher_version) {
    // A figure veto cannot be checked on an unsupported headline, so keep it apart.
    if (!figures.available) {
      return { ...identity, method: "unavailable", matcher_version: null, matches: null, reason: "headline figure comparison unavailable" };
    }
    return { ...identity, method: "recorded-event-cluster", matcher_version: a.labels.matcher_version, matches: true, reason: "same validated occurrence; no conflicting headline figures" };
  }
  return { ...identity, method: "unavailable", matcher_version: null, matches: null, reason: "no semantic vectors or shared recorded occurrence" };
}
