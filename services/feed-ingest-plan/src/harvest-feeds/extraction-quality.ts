/** Measure the native article-shape rules without inventing a worker token reading. */
import type { ExtractionQuality } from "@idhazh/common-contracts";
import type { ExtractionControls } from "./extraction-controls";
import { EXTRACTOR_VERSION, SANITIZER_FINGERPRINT } from "./extraction-provenance";

export function countWords(text: string): number {
  return text.split(/[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/u)
    .filter(Boolean).length;
}

function proseWords(text: string): number {
  return text.match(/[A-Za-z0-9][A-Za-z0-9'.,-]*/g)?.length ?? 0;
}

export function measureExtractionQuality(
  text: string, corroborated: number | null, config: ExtractionControls,
): ExtractionQuality {
  const words = countWords(text);
  const lines = text.split(/\r\n|[\n\r\v\f\u001c-\u001e\u0085\u2028\u2029]/u).map(line => line.trim()).filter(Boolean);
  const sentences = text.split(/(?<=[.!?])\s+/u).filter(sentence => proseWords(sentence) >= config.prose_sentence_words_min).length;
  const not_prose = sentences < config.prose_sentence_min || (lines.length >= config.prose_line_count_min
    && lines.filter(line => proseWords(line) >= config.prose_sentence_words_min).length / lines.length < config.prose_line_ratio_min);
  const contaminated = corroborated === null ? null : words / corroborated > config.corroboration_ratio_max;
  const too_short = words < config.min_source_words;
  // Python receives no sibling-host lines either; absence of that reading is not a clean verdict.
  const failure_code = contaminated ? "contaminated" : not_prose ? "not_prose" : too_short ? "too_short" : null;
  const rejected = failure_code === "contaminated" ? config.reject_contaminated
    : failure_code === "not_prose" ? config.reject_not_prose
    : failure_code === "too_short" ? config.reject_too_short : false;
  return {
    source_word_count: words, word_count: words, corroborated_word_count: corroborated,
    token_count: null, truncated: null, truncated_at_tokens: null, truncation_cap_tokens: config.truncation_cap_tokens,
    too_short, not_prose, boilerplate: null, contaminated, failure_code, rejected,
    extractor_version: EXTRACTOR_VERSION, sanitizer_version: SANITIZER_FINGERPRINT,
  };
}
