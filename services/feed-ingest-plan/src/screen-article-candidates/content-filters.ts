/** Which configured post-extraction heuristic is the first to exclude this measured article? */
import type {
  ArticleContentEvidence, CandidateRejectionRecord, FeedIngestConfig, RejectionDetails,
} from "@idhazh/common-contracts";

export function excludeArticleContent(
  evidence: ArticleContentEvidence | undefined, words: number, config: FeedIngestConfig["content_filters"],
): (Pick<CandidateRejectionRecord, "drop_reason"> & { details: Partial<RejectionDetails> }) | null {
  if (evidence === undefined) return null;
  const press = config.press_release;
  if (evidence.press_release_marker_index !== null && evidence.press_release_marker_index >= press.markers.length) {
    throw new Error("content_evidence.press_release_marker_index does not name a configured marker");
  }
  if (press.enabled && evidence.press_release_marker_index !== null) return {
    drop_reason: "PRESS_RELEASE", details: { content_evidence: evidence, sample_chars_limit: press.sample_chars },
  };
  const links = config.link_heavy;
  if (links.enabled && (evidence.link_density > links.max_link_density
    || (evidence.list_items > links.max_list_items && words < links.list_word_limit))) return {
    drop_reason: "LINK_HEAVY", details: {
      content_evidence: evidence, max_link_density: links.max_link_density,
      max_list_items: links.max_list_items, list_word_limit: links.list_word_limit, words_found: words,
    },
  };
  return null;
}
