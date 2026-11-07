/** Prove the API word ceiling preserves the exact retained prefix and truthful measurements. */
import { expect, test } from "bun:test";
import { prepareArticleInput } from "../src/api/prepare-article-input";
import { ArticleWordLimitEvidenceSchema } from "../src/api/document-response.schema";
import { countWords } from "../src/count-article-words";
import { BodyLimitError, requestCompletion } from "../../summary-generator/src/services/request-completion.service";
import { buildModelRequest } from "../../summary-generator/src/services/model-request.service";
import type { ModelRuntime } from "../../summary-generator/src/config/load-model-runtime";

for (const words of [19999, 20000, 20001]) {
  test(`${words} extracted words obey the 20000-word API ceiling`, () => {
    const text = Array.from({ length: words }, () => "word").join(" ");
    const prepared = prepareArticleInput({ article_text: text, word_count: words }, 20000);
    const returned = Math.min(words, 20000);
    expect(prepared.article_text).toBe(Array.from({ length: returned }, () => "word").join(" "));
    expect(prepared.word_count).toBe(returned);
    expect(countWords(prepared.article_text)).toBe(returned);
    expect(prepared.word_limit).toEqual({
      max_input_words: 20000, original_word_count: words, returned_word_count: returned, truncated: words > 20000,
    });
    expect(prepared.article_text).not.toContain("Truncated");
  });
}

test("substituting the ceiling changes only the cut and its evidence", () => {
  const article = { article_text: "first\n\nsecond\tthird", word_count: 3 };
  expect(prepareArticleInput(article, 3).article_text).toBe(article.article_text);
  const shortened = prepareArticleInput(article, 2);
  expect(shortened.article_text).toBe("first\n\nsecond");
  expect(shortened.word_limit).toEqual({
    max_input_words: 2, original_word_count: 3, returned_word_count: 2, truncated: true,
  });
  expect(article.article_text).toBe("first\n\nsecond\tthird");
});

test("word cuts use every native separator without splitting multibyte text", () => {
  for (const separator of [
    "\t", "\n", "\v", "\f", "\r", "\u001c", "\u001d", "\u001e", "\u001f", " ",
    "\u0085", "\u00a0", "\u1680", "\u2000", "\u2001", "\u2002", "\u2003", "\u2004",
    "\u2005", "\u2006", "\u2007", "\u2008", "\u2009", "\u200a", "\u2028", "\u2029",
    "\u202f", "\u205f", "\u3000",
  ]) {
    const prefix = `${separator}\u0ba4\u0bae\u0bbf\u0bb4\u0bcd${separator}${separator}\u{1f600}`;
    const text = `${prefix}${separator}third${separator}`;
    expect(countWords(text)).toBe(3);
    const prepared = prepareArticleInput({ article_text: text, word_count: 3 }, 2);
    expect(prepared.article_text).toBe(prefix);
    expect(countWords(prepared.article_text)).toBe(2);
    expect(Buffer.byteLength(prepared.article_text, "utf8")).toBeGreaterThan(prepared.article_text.length);
  }
  for (const separator of ["\u200b", "\ufeff"]) {
    const text = `first${separator}second third`;
    expect(countWords(text)).toBe(2);
    expect(prepareArticleInput({ article_text: text, word_count: 2 }, 1).article_text)
      .toBe(`first${separator}second`);
  }
});

test("empty extraction and unchanged Markdown retain their actual counts and exact content", () => {
  expect(prepareArticleInput({ article_text: "", word_count: 0 }, 20000)).toEqual({
    article_text: "", word_count: 0,
    word_limit: { max_input_words: 20000, original_word_count: 0, returned_word_count: 0, truncated: false },
  });
  const text = " \n**first**\n\nsecond\tthird  ";
  expect(prepareArticleInput({ article_text: text, word_count: 3 }, 3).article_text).toBe(text);
  expect(prepareArticleInput({ article_text: text, word_count: 3 }, 2).article_text).toBe(" \n**first**\n\nsecond");
});

test("word-limit evidence refuses fabricated cuts, excess returned counts and missing fields", () => {
  const evidence = { max_input_words: 2, original_word_count: 3, returned_word_count: 2, truncated: true };
  expect(ArticleWordLimitEvidenceSchema.parse(evidence)).toEqual(evidence);
  for (const changed of [
    { ...evidence, truncated: false }, { ...evidence, returned_word_count: 3 },
    { ...evidence, original_word_count: 1 }, { ...evidence, max_input_words: 0 },
    { ...evidence, max_input_words: 1.5 }, { ...evidence, unexpected: true },
    { max_input_words: 2, original_word_count: 3, returned_word_count: 2 },
  ]) expect(ArticleWordLimitEvidenceSchema.safeParse(changed).success).toBe(false);
  expect(() => prepareArticleInput({ article_text: "one", word_count: 3 }, 2))
    .toThrow("available article word boundaries");
});

test("the word ceiling does not bypass actual native serialized-request byte rejection", async () => {
  const text = "\"".repeat(524289);
  const prepared = prepareArticleInput({ article_text: text, word_count: 1 }, 20000);
  expect(prepared.article_text).toBe(text);
  expect(prepared.word_limit.truncated).toBe(false);
  expect(Buffer.byteLength(text, "utf8")).toBeLessThan(1048576);
  const runtime: ModelRuntime = {
    base_url: "http://127.0.0.1:8080", request: { model: "recorded-word-limit-model", stream: false },
    reasoning_delimiters: null, timeout_seconds: 1, repo: "recorded-word-limit-model", file: "recorded.gguf",
  };
  const payload = buildModelRequest(runtime, "Summarize the supplied text.", prepared.article_text, { type: "json_object" });
  expect(Buffer.byteLength(JSON.stringify(payload), "utf8")).toBeGreaterThan(1048576);
  let sent = 0;
  await expect(requestCompletion(runtime, payload, {
    max_native_request_bytes: 1048576, max_native_response_bytes: 1048576,
  }, undefined, async () => {
    sent++;
    throw new Error("An oversized native request must not be dispatched.");
  })).rejects.toBeInstanceOf(BodyLimitError);
  expect(sent).toBe(0);
});
