/** Which validated public library terms can headline comparison consume? */
import nlp from "compromise";
import { z } from "zod";

const ArticleTermSchema = z.object({
  text: z.string(),
  normal: z.string(),
  tags: z.array(z.string()),
});
const ArticleDocumentSchema = z.array(z.object({ terms: z.array(ArticleTermSchema) }));

export function readArticleTerms(value: unknown) {
  return ArticleDocumentSchema.parse(value).flatMap(entry => entry.terms);
}

export function normalizeArticleTerms(text: string): Set<string> {
  const document = nlp(text.toLowerCase());
  document.nouns().toSingular();
  document.verbs().toInfinitive();
  const output: unknown = document.json();
  return new Set(readArticleTerms(output).map(term => term.normal).filter(term => term.length > 0));
}

export function countTermLetters(text: string): number {
  return (text.match(/\p{L}/gu) ?? []).length;
}
