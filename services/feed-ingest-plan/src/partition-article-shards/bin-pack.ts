/** Which least-loaded worker receives each article in decreasing estimated work order? */
import type { PartitionArticle } from "./partition-input";

export function assignBinPack(articles: readonly PartitionArticle[], count: number): Map<string, number> {
  const loads = Array<number>(count).fill(0);
  const assignments = new Map<string, number>();
  const ordered = [...articles].sort((left, right) =>
    right.selection.estimated_work - left.selection.estimated_work
    || left.selection.editorial_rank - right.selection.editorial_rank
    || left.selection.candidate_id.localeCompare(right.selection.candidate_id, "en"),
  );
  for (const article of ordered) {
    let worker = 0;
    for (let index = 1; index < count; index++) {
      if (loads[index]! < loads[worker]!) worker = index;
    }
    loads[worker] = loads[worker]! + article.selection.estimated_work;
    if (!Number.isFinite(loads[worker])) throw new Error("Estimated worker work exceeds the numeric range");
    assignments.set(article.selection.candidate_id, worker);
  }
  return assignments;
}
