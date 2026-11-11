"""Which native phrase-ranking rules keep scores, limits and source evidence truthful?"""

import unittest

import spacy
from spacy.language import Language
from spacy.tokens import Doc
from text_analysis.declare_service_settings import ImportantTermsSettings
from text_analysis.rank_important_terms import anchor_ranked_terms, rank_important_terms
from yake import KeywordExtractor
from yake.data import DataCore


def _document(source: str) -> tuple[Language, Doc, dict[int, int]]:
    nlp = spacy.blank("en")
    nlp.add_pipe("sentencizer")
    doc = nlp(source)
    indexes = {
        token.i: index
        for index, sentence in enumerate(doc.sents)
        for token in sentence
    }
    return nlp, doc, indexes


class ImportantTermsTests(unittest.TestCase):
    def test_similarity_selection_stops_at_limit_with_real_scores_and_occurrences(self) -> None:
        source = (
            "Alpine bridge canyon desert forest garden. "
            "Alpine bridge canyon desert forest garden."
        )
        nlp, doc, indexes = _document(source)
        settings = ImportantTermsSettings(max_results=2, max_phrase_words=1)
        ranker = KeywordExtractor(
            lan="en",
            n=settings.max_phrase_words,
            dedup_lim=settings.deduplication_threshold,
            dedup_func=settings.deduplication_method,
            window_size=settings.window_size,
            top=settings.max_results,
        )
        core = DataCore(
            text=source,
            stopword_set=ranker.stopword_set,
            config={"n": settings.max_phrase_words, "windows_size": settings.window_size},
        )
        core.build_single_terms_features()
        core.build_mult_terms_features()
        candidates = tuple(
            (candidate.unique_kw, float(candidate.h))
            for candidate in core.candidates.values()
            if candidate.is_valid()
        )
        self.assertGreater(len(candidates), settings.max_results)
        result = anchor_ranked_terms(
            doc,
            nlp,
            source,
            reversed(candidates),
            indexes,
            settings.max_results,
            is_duplicate=lambda left, right: (
                ranker.dedup_function(left, right) > settings.deduplication_threshold
            ),
        )
        stats = ranker.get_cache_stats()
        expected_comparisons = settings.max_results * (settings.max_results - 1) // 2
        self.assertEqual(stats["hits"] + stats["misses"], expected_comparisons)
        self.assertEqual(len(result.terms), settings.max_results)
        self.assertEqual(
            rank_important_terms(doc, nlp, source, indexes, settings), result
        )
        expected = sorted(
            candidates, key=lambda candidate: (candidate[1], source.lower().index(candidate[0]))
        )[:settings.max_results]
        self.assertEqual(
            [(item.text.lower(), item.score) for item in result.terms], expected
        )
        self.assertTrue(all(len(item.occurrences) == 2 for item in result.terms))
        for term in result.terms:
            for occurrence in term.occurrences:
                self.assertEqual(
                    source[occurrence.start_char:occurrence.end_char], occurrence.text
                )

    def test_real_yake_ranking_returns_exact_unicode_occurrences_within_limit(self) -> None:
        source = (
            "\U0001f4f0 River mapping improves flood planning. "
            "River mapping improves flood planning."
        )
        nlp, doc, indexes = _document(source)
        settings = ImportantTermsSettings(max_results=4)
        result = rank_important_terms(doc, nlp, source, indexes, settings)
        self.assertGreater(len(result.terms), 0)
        self.assertLessEqual(len(result.terms), settings.max_results)
        self.assertEqual(
            [item.score for item in result.terms],
            sorted(item.score for item in result.terms),
        )
        for term in result.terms:
            self.assertTrue(term.occurrences)
            self.assertEqual(term.text, term.occurrences[0].text)
            for occurrence in term.occurrences:
                self.assertEqual(
                    source[occurrence.start_char:occurrence.end_char],
                    occurrence.text,
                )

    def test_matching_deduplicates_before_limit_and_breaks_score_ties_by_source(self) -> None:
        source = "\U0001f4f0 RIVER  mapping. River\nmapping. Lake survey."
        nlp, doc, indexes = _document(source)
        result = anchor_ranked_terms(
            doc,
            nlp,
            source,
            (
                ("lake survey", 0.2),
                ("river mapping", 0.2),
                ("RIVER MAPPING", 0.3),
                ("mapping", 0.4),
            ),
            indexes,
            3,
        )
        self.assertEqual(
            [(item.text, item.score) for item in result.terms],
            [("RIVER  mapping", 0.2), ("Lake survey", 0.2), ("mapping", 0.4)],
        )
        self.assertEqual(
            [item.text for item in result.terms[0].occurrences],
            ["RIVER  mapping", "River\nmapping"],
        )
        self.assertEqual(
            [item.start_char for item in result.terms[0].occurrences],
            [source.index("RIVER"), source.index("River")],
        )

    def test_zero_limit_and_no_candidates_complete_with_empty_terms(self) -> None:
        source = "The and or."
        nlp, doc, indexes = _document(source)
        self.assertEqual(
            rank_important_terms(
                doc, nlp, source, indexes, ImportantTermsSettings(max_results=0)
            ).terms,
            (),
        )
        self.assertEqual(
            rank_important_terms(doc, nlp, source, indexes, ImportantTermsSettings()).terms,
            (),
        )

    def test_selected_unanchored_candidate_fails_without_first_substring_repair(self) -> None:
        source = "River blue mapping."
        nlp, doc, indexes = _document(source)
        with self.assertRaises(ValueError):
            anchor_ranked_terms(
                doc, nlp, source, (("river mapping", 0.1),), indexes, 1
            )
        result = anchor_ranked_terms(
            doc,
            nlp,
            source,
            (("river", 0.1), ("missing phrase", 0.2)),
            indexes,
            1,
        )
        self.assertEqual([item.text for item in result.terms], ["River"])

    def test_yake_options_change_real_phrase_candidates(self) -> None:
        source = "River mapping improves flood planning. River mapping helps coastal towns."
        nlp, doc, indexes = _document(source)
        for method in ("seqm", "jaro", "levs"):
            with self.subTest(method=method):
                settings = ImportantTermsSettings(
                    max_results=2,
                    max_phrase_words=1,
                    deduplication_threshold=0.5,
                    deduplication_method=method,
                    window_size=2,
                    stopwords=("river", "mapping"),
                )
                result = rank_important_terms(doc, nlp, source, indexes, settings)
                self.assertEqual(len(result.terms), settings.max_results)
                self.assertTrue(all(" " not in item.text for item in result.terms))
                self.assertTrue(
                    all(item.text.casefold() not in settings.stopwords for item in result.terms)
                )


if __name__ == "__main__":
    unittest.main()
