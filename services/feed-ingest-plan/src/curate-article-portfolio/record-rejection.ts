/** Which existing terminal rejection row explains one curation loss? */
import { CandidateRejectionRecordSchema } from "@idhazh/common-contracts";
import type { DropReason, RejectionDetails } from "@idhazh/common-contracts";
import type { PortfolioArticle } from "./portfolio-input";

export function recordRejection(
  article: PortfolioArticle, observedAt: string, reason: DropReason,
  details: Partial<RejectionDetails>,
) {
  const candidate = article.candidate;
  return CandidateRejectionRecordSchema.parse({
    date: observedAt.slice(0, 10),
    correlation_id: candidate.correlation_id,
    source_id: candidate.source_id, feed_url: candidate.source.feed_url, subject: "article",
    candidate_id: candidate.candidate_id, url_key: candidate.url_key,
    canonical_url: candidate.canonical_url, title: candidate.title, categories: candidate.categories,
    stage: "curate-article-portfolio", drop_reason: reason,
    details: { ...details, diagnostics: article.observation?.diagnostics ?? null }, rejected_at: observedAt,
  });
}
