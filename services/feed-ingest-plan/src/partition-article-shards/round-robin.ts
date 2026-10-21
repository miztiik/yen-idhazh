/** Which worker receives each successive editorial rank? */
import type { PartitionArticle } from "./partition-input";

export function assignRoundRobin(articles: readonly PartitionArticle[], count: number): Map<string, number> {
  return new Map(articles.map((article, index) => [article.selection.candidate_id, index % count]));
}
