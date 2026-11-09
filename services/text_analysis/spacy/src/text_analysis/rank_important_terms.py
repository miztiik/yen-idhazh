"""How are ranked English phrases anchored to every exact original-source occurrence?"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
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
) -> ImportantTermsData:
    """Deduplicate token patterns, order source-backed ranks, then apply the limit."""
    if max_results == 0:
        return ImportantTermsData(terms=())
    if doc.text != source:
        raise ValueError("Important Terms require the original source document")

    from spacy.matcher import PhraseMatcher

    patterns: dict[tuple[int, ...], tuple[str, float, Doc]] = {}
    for phrase, score in candidates:
        if isinstance(score, bool) or not math.isfinite(score) or score < 0:
            raise ValueError("Important term ranks must be finite and nonnegative")
        pattern = nlp.make_doc(phrase)
        key = tuple(token.lower for token in pattern)
        if not key:
            raise ValueError("Important term candidates must contain tokens")
        previous = patterns.get(key)
        if previous is None or score < previous[1]:
            patterns[key] = (phrase, score, pattern)

    if not patterns:
        return ImportantTermsData(terms=())

    # YAKE normalizes case; matching must not change the returned source spelling.
    matcher = PhraseMatcher(doc.vocab, attr=PHRASE_MATCH_ATTRIBUTE)
    occurrences: dict[int, list[EvidenceSpan]] = {}
    for phrase, _score, pattern in patterns.values():
        matcher.add(phrase, [pattern])
        occurrences[doc.vocab.strings[phrase]] = []
    for match_id, start, end in matcher(doc):
        span = doc[start:end]
        occurrences[match_id].append(
            EvidenceSpan(
                text=source[span.start_char:span.end_char],
                start_char=span.start_char,
                end_char=span.end_char,
                sentence_index=sentence_indexes[start],
            )
        )
    for matches in occurrences.values():
        matches.sort(key=lambda item: (item.start_char, item.end_char))

    def rank_key(candidate: tuple[str, float, Doc]) -> tuple[float, int]:
        phrase, score, _pattern = candidate
        matches = occurrences[doc.vocab.strings[phrase]]
        return score, matches[0].start_char if matches else len(source)

    terms: list[ImportantTermRecord] = []
    for phrase, score, _pattern in sorted(patterns.values(), key=rank_key)[:max_results]:
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
    candidates = sorted(
        (candidate for candidate in core.candidates.values() if candidate.is_valid()),
        key=lambda candidate: candidate.h,
    )
    ranked: list[tuple[str, str, float]] = []
    for candidate in candidates:
        if settings.deduplication_threshold < 1 and any(
            ranker.dedup_function(candidate.unique_kw, previous_name)
            > settings.deduplication_threshold
            for previous_name, _phrase, _score in ranked
        ):
            continue
        ranked.append((candidate.unique_kw, candidate.kw, float(candidate.h)))
    return anchor_ranked_terms(
        doc,
        nlp,
        source,
        ((phrase, score) for _name, phrase, score in ranked),
        sentence_indexes,
        settings.max_results,
    )
