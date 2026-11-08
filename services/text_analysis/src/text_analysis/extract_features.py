"""How are selected features extracted independently while preserving siblings?"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spacy.tokens import Doc, Span

from text_analysis.declare_api_contracts import (
    AnalysisCommand,
    DocumentMetricsData,
    EntitiesData,
    EntityMention,
    ErrorDetail,
    EvidenceSpan,
    FeatureData,
    FeatureResult,
    LinguisticTokensData,
    NounPhrasesData,
    RelationsData,
    SentencesData,
    SentenceSpan,
    TokenRecord,
)
from text_analysis.declare_service_settings import FeatureName
from text_analysis.extract_relations import extract_relations
from text_analysis.manage_models import LoadedModel


class FeatureUnavailableError(RuntimeError):
    """Report a selected capability the loaded model cannot provide."""


def _sentence_context(doc: Doc) -> tuple[tuple[Span, ...], dict[int, int]]:
    sentences = tuple(doc.sents)
    indexes = {
        token.i: sentence_index
        for sentence_index, sentence in enumerate(sentences)
        for token in sentence
    }
    return sentences, indexes


def _span(
    source: str,
    start_char: int,
    end_char: int,
    sentence_index: int,
) -> EvidenceSpan:
    return EvidenceSpan(
        text=source[start_char:end_char],
        start_char=start_char,
        end_char=end_char,
        sentence_index=sentence_index,
    )


def extract_feature_results(
    doc: Doc,
    command: AnalysisCommand,
    loaded: LoadedModel,
) -> tuple[FeatureResult, ...]:
    """Extract each requested feature in order and isolate post-processing failures."""
    source = command.text
    cache: dict[FeatureName, FeatureData | BaseException] = {}
    sentences_cache: tuple[tuple[Span, ...], dict[int, int]] | None = None

    def sentences() -> tuple[tuple[Span, ...], dict[int, int]]:
        nonlocal sentences_cache
        if sentences_cache is None:
            sentences_cache = _sentence_context(doc)
        return sentences_cache

    def entities() -> EntitiesData:
        sentence_list, sentence_indexes = sentences()
        del sentence_list
        return EntitiesData(
            mentions=tuple(
                EntityMention(
                    text=source[entity.start_char:entity.end_char],
                    start_char=entity.start_char,
                    end_char=entity.end_char,
                    sentence_index=sentence_indexes[entity.start],
                    label=entity.label_,
                )
                for entity in doc.ents
            )
        )

    def sentence_spans() -> SentencesData:
        sentence_list, _indexes = sentences()
        return SentencesData(
            sentences=tuple(
                SentenceSpan(
                    text=source[sentence.start_char:sentence.end_char],
                    start_char=sentence.start_char,
                    end_char=sentence.end_char,
                    sentence_index=index,
                )
                for index, sentence in enumerate(sentence_list)
            )
        )

    def relations() -> RelationsData:
        return RelationsData(
            relations=extract_relations(doc, source, loaded.relation_policy)
        )

    def noun_phrases() -> NounPhrasesData:
        _sentence_list, sentence_indexes = sentences()
        try:
            chunks = tuple(doc.noun_chunks)
        except (NotImplementedError, ValueError):
            raise FeatureUnavailableError from None
        return NounPhrasesData(
            phrases=tuple(
                _span(
                    source,
                    chunk.start_char,
                    chunk.end_char,
                    sentence_indexes[chunk.start],
                )
                for chunk in chunks
            )
        )

    def linguistic_tokens() -> LinguisticTokensData:
        _sentence_list, sentence_indexes = sentences()
        return LinguisticTokensData(
            tokens=tuple(
                TokenRecord(
                    text=source[token.idx:token.idx + len(token)],
                    start_char=token.idx,
                    end_char=token.idx + len(token),
                    sentence_index=sentence_indexes[token.i],
                    lemma=token.lemma_ or None,
                    part_of_speech=token.pos_ or None,
                    dependency=token.dep_ or None,
                    head_index=token.head.i if token.dep_ else None,
                    morphology=str(token.morph) or None,
                )
                for token in doc
            )
        )

    def document_metrics() -> DocumentMetricsData:
        sentence_list, _sentence_indexes = sentences()
        relation_count: int | None = None
        if "relations" in command.features:
            try:
                relation_value = calculate("relations")
            except Exception:
                relation_value = None
            if isinstance(relation_value, RelationsData):
                relation_count = len(relation_value.relations)
        return DocumentMetricsData(
            codepoint_count=len(source),
            utf8_byte_count=len(source.encode("utf-8")),
            token_count=len(doc),
            sentence_count=len(sentence_list),
            entity_count=len(doc.ents),
            relation_count=relation_count,
        )

    extractors: dict[FeatureName, Callable[[], FeatureData]] = {
        "entities": entities,
        "sentences": sentence_spans,
        "relations": relations,
        "noun_phrases": noun_phrases,
        "linguistic_tokens": linguistic_tokens,
        "document_metrics": document_metrics,
    }

    def calculate(feature: FeatureName) -> FeatureData:
        cached = cache.get(feature)
        if isinstance(cached, BaseException):
            raise cached
        if cached is not None:
            return cached
        if feature in loaded.unavailable_features:
            failure = FeatureUnavailableError()
            cache[feature] = failure
            raise failure
        try:
            value = extractors[feature]()
        except Exception as error:
            cache[feature] = error
            raise
        cache[feature] = value
        return value

    results: list[FeatureResult] = []
    for feature in command.features:
        try:
            results.append(
                FeatureResult(
                    feature=feature,
                    status="complete",
                    data=calculate(feature),
                    error=None,
                )
            )
        except FeatureUnavailableError:
            results.append(
                FeatureResult(
                    feature=feature,
                    status="failed",
                    data=None,
                    error=ErrorDetail.from_code(
                        "FEATURE_UNAVAILABLE",
                        feature=feature,
                    ),
                )
            )
        except Exception:
            results.append(
                FeatureResult(
                    feature=feature,
                    status="failed",
                    data=None,
                    error=ErrorDetail.from_code(
                        "FEATURE_FAILED",
                        feature=feature,
                    ),
                )
            )
    return tuple(results)
