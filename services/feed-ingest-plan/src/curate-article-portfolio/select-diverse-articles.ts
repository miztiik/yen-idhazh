/** Which unique URLs win each complete numerical diversity sweep? */
import { FeedDiversityPolicySchema } from "@idhazh/common-contracts";
import type { DropReason, NumericalSelectionInput, NumericalSelectionOutput } from "@idhazh/common-contracts";
import type { z } from "zod";

export type FeedDiversityPolicy = z.infer<typeof FeedDiversityPolicySchema>;
export type ChosenDiverseArticle = Pick<NumericalSelectionOutput,
  "domain_diversity_penalty" | "feed_diversity_penalty" | "novelty_bonus"> & {
  record: NumericalSelectionInput;
  score: number;
};
export type DiverseArticleLoss = {
  record: NumericalSelectionInput;
  reason: Extract<DropReason,
    "REJECTED_DUPLICATE_CANONICAL_CARRIER" | "REJECTED_GLOBAL_CAPACITY_REACHED">;
};

export function selectDiverseArticles(
  records: readonly NumericalSelectionInput[],
  limit: number,
  diversity: FeedDiversityPolicy,
): { chosen: ChosenDiverseArticle[]; losses: DiverseArticleLoss[] } {
  if (!Number.isSafeInteger(limit) || limit < 0) {
    throw new Error("selection limit must be a nonnegative safe integer");
  }
  const policy = FeedDiversityPolicySchema.parse(diversity);
  const chosen: ChosenDiverseArticle[] = [];
  const chosenIds = new Set<string>();
  const chosenUrls = new Set<string>();
  const feedCounts = new Map<string, number>();
  const websiteCounts = new Map<string, number>();

  while (chosen.length < limit) {
    let best: ChosenDiverseArticle | null = null;
    for (const record of records) {
      if (chosenUrls.has(record.url_key)) continue;
      const websiteCount = websiteCounts.get(record.website_group) ?? 0;
      const feedCount = feedCounts.get(record.feed_id) ?? 0;
      const domainPenalty = policy.lambda_domain * (websiteCount ** 2);
      const feedPenalty = policy.lambda_feed * (feedCount ** 2);
      const bonus = feedCount === 0 ? policy.novelty_bonus : 0;
      const score = ((record.base_score - domainPenalty) - feedPenalty) + bonus;
      if (!Number.isFinite(score)) {
        throw new Error(`non-finite marginal score for candidate_id ${record.candidate_id}`);
      }
      if (best === null || score > best.score
        || (score === best.score && record.candidate_id < best.record.candidate_id)) {
        best = {
          record, score,
          domain_diversity_penalty: -domainPenalty,
          feed_diversity_penalty: -feedPenalty,
          novelty_bonus: bonus,
        };
      }
    }
    if (best === null) break;
    chosen.push(best);
    chosenIds.add(best.record.candidate_id);
    chosenUrls.add(best.record.url_key);
    feedCounts.set(best.record.feed_id, (feedCounts.get(best.record.feed_id) ?? 0) + 1);
    websiteCounts.set(best.record.website_group, (websiteCounts.get(best.record.website_group) ?? 0) + 1);
  }

  const losses: DiverseArticleLoss[] = [];
  for (const record of records) {
    if (chosenIds.has(record.candidate_id)) continue;
    losses.push({
      record,
      reason: chosenUrls.has(record.url_key)
        ? "REJECTED_DUPLICATE_CANONICAL_CARRIER"
        : "REJECTED_GLOBAL_CAPACITY_REACHED",
    });
  }
  return { chosen, losses };
}
