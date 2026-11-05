/** Translate selected article identities at the API boundary without copying native validation rules. */
import { z } from "zod";
import { SelectedArticleRowSchema } from "@idhazh/common-contracts";
import type { SelectedArticleRow } from "@idhazh/common-contracts";

const { url_key: articleId, ...metadata } = SelectedArticleRowSchema.shape;
export const SelectedArticleResponseSchema = z.strictObject({
  ...metadata, article_id: articleId,
}).superRefine(({ article_id, ...row }, ctx) => {
  const native = SelectedArticleRowSchema.safeParse({ ...row, url_key: article_id });
  if (!native.success) {
    for (const issue of native.error.issues) {
      ctx.addIssue({ ...issue, path: issue.path[0] === "url_key"
        ? ["article_id", ...issue.path.slice(1)] : issue.path });
    }
  }
});
export type SelectedArticleResponse = z.infer<typeof SelectedArticleResponseSchema>;

export function projectSelectedArticle(row: SelectedArticleRow): SelectedArticleResponse {
  const { url_key, ...metadata } = SelectedArticleRowSchema.parse(row);
  return SelectedArticleResponseSchema.parse({ ...metadata, article_id: url_key });
}

export function restoreSelectedArticle(row: SelectedArticleResponse): SelectedArticleRow {
  const { article_id, ...metadata } = SelectedArticleResponseSchema.parse(row);
  return SelectedArticleRowSchema.parse({ ...metadata, url_key: article_id });
}
