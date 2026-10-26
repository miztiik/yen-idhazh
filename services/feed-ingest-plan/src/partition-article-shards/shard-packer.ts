/** Pack the selected work into workers while preserving editorial order and article content. */
import { SelectedArticleContentSchema } from "@idhazh/common-contracts";
import type { z } from "zod";

export function partitionArticles(
  input: readonly z.infer<typeof SelectedArticleContentSchema>[],
  controls: { strategy: "bin-pack" | "round-robin" | "none"; dispatch_count: number },
) {
  const articles = input.map(article => SelectedArticleContentSchema.parse(article)).sort((a, b) => a.editorial_rank - b.editorial_rank);
  if (new Set(articles.map(article => article.url_key)).size !== articles.length
    || articles.some((article, index) => article.editorial_rank !== index + 1)) {
    throw new Error("Selected articles must have distinct URLs and consecutive editorial ranks");
  }
  const assignments = new Map<string, number>();
  const work = Array<number>(controls.dispatch_count).fill(0);
  const ordered = controls.strategy === "bin-pack" ? [...articles].sort((a, b) =>
    b.estimated_work - a.estimated_work || a.editorial_rank - b.editorial_rank || a.url_key.localeCompare(b.url_key)) : articles;
  for (const [index, article] of ordered.entries()) {
    let worker = controls.strategy === "round-robin" ? index % controls.dispatch_count : 0;
    if (controls.strategy === "bin-pack") for (let next = 1; next < controls.dispatch_count; next++) {
      if (work[next]! < work[worker]!) worker = next;
    }
    work[worker] = work[worker]! + article.estimated_work;
    if (!Number.isFinite(work[worker])) throw new Error("Worker work exceeds the numeric range");
    assignments.set(article.url_key, worker);
  }
  return {
    ...controls, work,
    articles: articles.map(article => SelectedArticleContentSchema.parse({ ...article, worker_assignment: assignments.get(article.url_key)! })),
  };
}
