"""How are ranked English phrases anchored to every exact original-source occurrence?"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spacy.language import Language
    from spacy.tokens import Doc

from text_analysis.declare_api_contracts import (
    EvidenceSpan,
    ImportantTermRecord,
    ImportantTermsData,
)
from text_analysis.declare_service_settings import ImportantTermsSettings

PHRASE_MATCH_ATTRIBUTE = "LOWER"


def anchor_ranked_terms(
    doc: Doc,
    nlp: Language,
    source: str,
    candidates: Iterable[tuple[str, float]],
    sentence_indexes: Mapping[int, int],
    max_results: int,
    *,
    is_duplicate: Callable[[str, str], bool] | None = None,
) -> ImportantTermsData:
    """Deduplicate token patterns, order source-backed ranks, then apply the limit."""
    if max_results == 0:
        return ImportantTermsData(terms=())
    if doc.text != source:
        raise ValueError("Important Terms require the original source document")

    from spacy.matcher import PhraseMatcher
    from spacy.tokens import Doc

    patterns: dict[tuple[int, ...], tuple[str, float, Doc]] = {}
    for phrase, score in candidates:
        if isinstance(score, bool) or not math.isfinite(score) or score < 0:
            raise ValueError("Important term ranks must be finite and nonnegative")
        pattern = nlp.make_doc(phrase)
        tokens = tuple(token for token in pattern if not token.is_space)
        key = tuple(token.lower for token in tokens)
        if not key:
            raise ValueError("Important term candidates must contain tokens")
        if len(tokens) != len(pattern):
            pattern = Doc(doc.vocab, words=[token.text for token in tokens])
        previous = patterns.get(key)
        if previous is None or score < previous[1]:
            patterns[key] = (phrase, score, pattern)

    if not patterns:
        return ImportantTermsData(terms=())

    original_indexes = tuple(token.i for token in doc if not token.is_space)
    matching_doc = Doc(doc.vocab, words=[doc[index].text for index in original_indexes])
    matcher = PhraseMatcher(doc.vocab, attr=PHRASE_MATCH_ATTRIBUTE)
    occurrences: dict[int, list[EvidenceSpan]] = {}
    for phrase, _score, pattern in patterns.values():
        matcher.add(phrase, [pattern])
        occurrences[doc.vocab.strings[phrase]] = []
    for match_id, start, end in matcher(matching_doc):
        original_start = original_indexes[start]
        span = doc[original_start:original_indexes[end - 1] + 1]
        occurrences[match_id].append(
            EvidenceSpan(
                text=source[span.start_char:span.end_char],
                start_char=span.start_char,
                end_char=span.end_char,
                sentence_index=sentence_indexes[original_start],
            )
        )
    for matches in occurrences.values():
        matches.sort(key=lambda item: (item.start_char, item.end_char))

    def rank_key(candidate: tuple[str, float, Doc]) -> tuple[float, int]:
        phrase, score, _pattern = candidate
        matches = occurrences[doc.vocab.strings[phrase]]
        return score, matches[0].start_char if matches else len(source)

    terms: list[ImportantTermRecord] = []
    selected_names: list[str] = []
    for phrase, score, _pattern in sorted(patterns.values(), key=rank_key):
        name = phrase.lower()
        if is_duplicate is not None and any(
            is_duplicate(name, previous) for previous in selected_names
        ):
            continue
        matches = occurrences[doc.vocab.strings[phrase]]
        if not matches:
            raise ValueError("A selected important term has no exact source occurrence")
        terms.append(
            ImportantTermRecord(
                text=matches[0].text,
                score=score,
                occurrences=tuple(matches),
            )
        )
        selected_names.append(name)
        if len(terms) == max_results:
            break
    return ImportantTermsData(terms=tuple(terms))


def rank_important_terms(
    doc: Doc,
    nlp: Language,
    source: str,
    sentence_indexes: Mapping[int, int],
    settings: ImportantTermsSettings,
) -> ImportantTermsData:
    """Rank with YAKE's validated English settings without another model invocation."""
    if settings.max_results == 0:
        return ImportantTermsData(terms=())

    from yake import KeywordExtractor
    from yake.data import DataCore

    ranker = KeywordExtractor(
        lan=doc.lang_,
        n=settings.max_phrase_words,
        dedup_lim=settings.deduplication_threshold,
        dedup_func=settings.deduplication_method,
        window_size=settings.window_size,
        top=settings.max_results,
        stopwords=(
            None
            if settings.stopwords is None
            else {word.casefold() for word in settings.stopwords}
        ),
    )
    # The convenience extractor swallows calculation errors; native stages do not.
    core = DataCore(
        text=source.replace("\n", " "),
        stopword_set=ranker.stopword_set,
        config={
            "n": settings.max_phrase_words,
            "windows_size": settings.window_size,
        },
    )
    core.build_single_terms_features()
    core.build_mult_terms_features()

    def is_duplicate(left: str, right: str) -> bool:
        return (
            settings.deduplication_threshold < 1
            and ranker.dedup_function(left, right) > settings.deduplication_threshold
        )

    return anchor_ranked_terms(
        doc,
        nlp,
        source,
        (
            (candidate.kw, float(candidate.h))
            for candidate in core.candidates.values()
            if candidate.is_valid()
        ),
        sentence_indexes,
        settings.max_results,
        is_duplicate=is_duplicate,
    )
