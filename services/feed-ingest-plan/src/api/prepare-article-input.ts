/** Shorten one extracted article at an exact word boundary before API candidate capture. */
import { matchArticleWords } from "../count-article-words";
import { ArticleWordLimitEvidenceSchema } from "./document-response.schema";

export function prepareArticleInput(
  article: { article_text: string; word_count: number }, maxInputWords: number,
) {
  const wordLimit = ArticleWordLimitEvidenceSchema.parse({
    max_input_words: maxInputWords,
    original_word_count: article.word_count,
    returned_word_count: Math.min(article.word_count, maxInputWords),
    truncated: article.word_count > maxInputWords,
  });
  if (!wordLimit.truncated) {
    return { article_text: article.article_text, word_count: article.word_count, word_limit: wordLimit };
  }
  let count = 0;
  for (const word of matchArticleWords(article.article_text)) {
    if (++count === maxInputWords) {
      return {
        article_text: article.article_text.slice(0, word.index + word[0].length),
        word_count: wordLimit.returned_word_count,
        word_limit: wordLimit,
      };
    }
  }
  throw new Error("The extracted word count exceeds the available article word boundaries.");
}
