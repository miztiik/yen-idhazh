/** What signed substance score follows from retained paragraphs and observed headline flags? */
import nlp from "compromise";
import { FeedSubstancePolicySchema } from "@idhazh/common-contracts";
import type { FeedIngestConfig } from "@idhazh/common-contracts";
import { measureSubstantiveParagraphs } from "./measure-substantive-paragraphs";
import { countTermLetters, normalizeArticleTerms, readArticleTerms } from "./normalize-article-terms";

export function createSubstanceScorer(settings: FeedIngestConfig["curate_articles"]["substance"]) {
  const policy = FeedSubstancePolicySchema.parse(settings);
  const headline = policy.headline;
  const punctuationPatterns = headline.punctuation_patterns.map(pattern => new RegExp(pattern, "u"));
  const stopWords = new Set(headline.stop_words);
  return (title: string, articleText: string) => {
    const evidence = measureSubstantiveParagraphs(articleText, policy);
    const words = evidence.substance_word_count;
    const full = policy.length_scores.full;
    const length_score = words < policy.word_count_ramp_end
      ? full * (words / policy.word_count_ramp_end)
      : words <= policy.word_count_sweet_spot_max ? full
      : words <= policy.word_count_plateau_start
        ? full + (policy.long_form_floor_score - full) * (words - policy.word_count_sweet_spot_max)
          / (policy.word_count_plateau_start - policy.word_count_sweet_spot_max)
        : policy.long_form_floor_score;
    const density = evidence.sentence_count === 0 ? 0
      : (evidence.name_count + evidence.number_count) / evidence.sentence_count;
    const density_score = policy.entity_density_weight * Math.min(1, Math.max(0, density / policy.entity_density_full_credit));
    const original = nlp(title);
    original.acronyms();
    const output: unknown = original.json();
    const letterTerms = readArticleTerms(output).filter(term => countTermLetters(term.text) >= headline.shouting_min_letters);
    const uppercaseTerms = letterTerms.filter(term => !term.tags.includes("Acronym") &&
      term.text === term.text.toUpperCase() && term.text !== term.text.toLowerCase());
    const shouting = letterTerms.length > 0 && uppercaseTerms.length >= headline.shouting_min_words &&
      uppercaseTerms.length / letterTerms.length >= headline.shouting_min_uppercase_fraction;
    const punctuation = punctuationPatterns.some(pattern => pattern.test(title));
    const keywords = [...normalizeArticleTerms(title)].filter(term =>
      countTermLetters(term) >= headline.keyword_min_letters && !stopWords.has(term));
    const opening = normalizeArticleTerms(evidence.opening_text);
    const opening_mismatch = keywords.length > 0 && opening.size > 0 && !keywords.some(term => opening.has(term));
    const headline_deduction = Math.min(policy.headline_hype_penalty,
      headline.shouting_weight * Number(shouting) + headline.punctuation_weight * Number(punctuation) +
      headline.opening_mismatch_weight * Number(opening_mismatch));
    const substance_score = length_score + density_score - headline_deduction;
    if (!Number.isFinite(substance_score)) throw new Error("substance_score must be finite");
    return {
      substance_word_count: words, substance_score, length_score, density_score, headline_deduction,
      shouting, punctuation, opening_mismatch,
    };
  };
}
