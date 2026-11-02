/** Which newline blocks supply retained word, sentence, name, quantity and opening evidence? */
import nlp from "compromise";
import type { FeedIngestConfig } from "@idhazh/common-contracts";
import { countWords } from "../count-article-words";

type SubstancePolicy = FeedIngestConfig["curate_articles"]["substance"];

export function measureSubstantiveParagraphs(articleText: string, policy: SubstancePolicy) {
  let substance_word_count = 0;
  let sentence_count = 0;
  let name_count = 0;
  let number_count = 0;
  let opening_text = "";
  let openingCharacters = 0;
  for (const block of articleText.split(/\n+/u)) {
    const text = block.trim();
    if (text.length === 0) continue;
    const words = countWords(text);
    const document = nlp(text);
    const sentences = document.sentences().length;
    if (words < policy.substantive_paragraph_min_words &&
        sentences < policy.substantive_paragraph_min_sentences) continue;
    substance_word_count += words;
    sentence_count += sentences;
    name_count += document.match("#ProperNoun+").length;
    number_count += document.numbers().not("#ProperNoun").length;
    if (openingCharacters < policy.headline.opening_text_max_characters) {
      const prefix = openingCharacters === 0 ? "" : "\n\n";
      for (const character of prefix + text) {
        if (openingCharacters === policy.headline.opening_text_max_characters) break;
        opening_text += character;
        openingCharacters++;
      }
    }
  }
  return { substance_word_count, sentence_count, name_count, number_count, opening_text };
}
