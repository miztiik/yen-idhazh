/** Does the API rename only selected identity while retaining every native metadata rule? */
import { expect, test } from "bun:test";
import { SelectedArticleRowSchema } from "@idhazh/common-contracts";
import {
  SelectedArticleResponseSchema, projectSelectedArticle, restoreSelectedArticle,
} from "../src/api/article-identity-projection";

test("selected API rows round-trip through the sole strict native projection", async () => {
  const rows = SelectedArticleRowSchema.array().parse(await Bun.file(new URL(
    "../../../tests/fixtures/feed-ingest-plan/entry-points/selected-articles.rows.json", import.meta.url,
  )).json());
  for (const row of rows) {
    const api = projectSelectedArticle(row);
    const { url_key, ...metadata } = row;
    expect(api).toEqual({ ...metadata, article_id: url_key });
    expect(restoreSelectedArticle(api)).toEqual(row);
    expect(SelectedArticleResponseSchema.safeParse(row).success).toBe(false);
    expect(SelectedArticleRowSchema.safeParse(api).success).toBe(false);
    for (const patch of [
      { url_key }, { article_text: "Private article text" }, { article_id: "a".repeat(64) },
      { substance_word_count: row.word_count + 1 }, { editorial_rank: 0 },
      { timing_at: null, timing_basis: "published_at" }, { ratings: { ...row.ratings, base_article_score: 999 } },
    ]) expect(SelectedArticleResponseSchema.safeParse({ ...api, ...patch }).success).toBe(false);
  }
  expect(Object.keys(SelectedArticleResponseSchema.shape).sort()).toEqual(
    Object.keys(SelectedArticleRowSchema.shape).map(field => field === "url_key" ? "article_id" : field).sort(),
  );
});
