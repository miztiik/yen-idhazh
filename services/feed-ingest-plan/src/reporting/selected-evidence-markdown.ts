/** Which measured counts and score components explain the saved chosen population? */
import { SelectedArticleRowSchema } from "@idhazh/common-contracts";
import { escapeMarkdown } from "./markdown-format";

export function renderSelectedEvidence(input: unknown, run: { run_id: string; attempt: number; selected_count: number }) {
  const rows = input === undefined ? undefined : SelectedArticleRowSchema.array().parse(input);
  if (rows !== undefined && (rows.length !== run.selected_count
    || rows.some(row => row.run_id !== run.run_id || row.attempt !== run.attempt))) {
    throw new Error("Selected report evidence must match the complete execution");
  }
  return [
    "<details>", "<summary>Selected article evidence</summary>", "",
    "## Table J - Selected article evidence", "",
    "| Id | Rank | Feed | Full-body words | Retained words | Feed weight | Substance points | Base points | Chosen points | Age basis |",
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ...(rows ?? []).toSorted((left, right) => left.editorial_rank - right.editorial_rank).map((row, index) => {
      const substance = row.ratings.adjustments.find(term => term.term === "substance_quality_score")!;
      return `| J${index + 1} | ${[
        row.editorial_rank, row.feed_id, row.word_count, row.substance_word_count, row.weight,
        substance.value, row.ratings.base_article_score, row.ratings.marginal_score, row.timing_basis,
      ].map(value => escapeMarkdown(String(value))).join(" | ")} |`;
    }),
    ...(rows === undefined ? ["", "Selected metadata was not recorded; measured counts and scores are unavailable."]
      : rows.length === 0 ? ["", "The saved selection contains zero articles."] : []),
    "", "Full-body words measure original sanitized text. Retained words measure the scored paragraphs; zero is a measured value.",
    "Feed weight expresses configured source authority. Substance points measure article shape, not factual accuracy.",
    "Unknown age remains eligible with null timing and zero recency. Diversity changes order, never capacity.",
    "", "</details>",
  ].join("\n");
}
