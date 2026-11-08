"""How are sentence-local action relations derived from configured dependencies?"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spacy.tokens import Doc, Span, Token

from text_analysis.declare_api_contracts import EvidenceSpan, RelationRecord
from text_analysis.declare_service_settings import RelationPolicy


def _evidence(
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


def _recursive_conjunctions(token: Token, dependency: str) -> tuple[Token, ...]:
    ordered: list[Token] = []
    pending = [token]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if current.i in seen:
            continue
        seen.add(current.i)
        ordered.append(current)
        pending.extend(
            child for child in current.children if child.dep_ == dependency
        )
    return tuple(sorted(ordered, key=lambda item: item.i))


def _subtree_evidence(
    source: str,
    token: Token,
    sentence_index: int,
) -> EvidenceSpan:
    subtree = tuple(token.subtree)
    start_char = min(item.idx for item in subtree)
    end_char = max(item.idx + len(item) for item in subtree)
    return _evidence(source, start_char, end_char, sentence_index)


def _deduplicate(spans: Iterable[EvidenceSpan]) -> tuple[EvidenceSpan, ...]:
    unique = {
        (span.start_char, span.end_char): span
        for span in spans
    }
    return tuple(
        unique[key]
        for key in sorted(unique, key=lambda item: (item[0], item[1]))
    )


def _sentence_entities(
    sentence: Span,
    source: str,
    labels: tuple[str, ...],
    sentence_index: int,
) -> tuple[EvidenceSpan, ...]:
    accepted = set(labels)
    return _deduplicate(
        _evidence(
            source,
            entity.start_char,
            entity.end_char,
            sentence_index,
        )
        for entity in sentence.ents
        if entity.label_ in accepted
    )


def extract_relations(
    doc: Doc,
    source: str,
    policy: RelationPolicy,
) -> tuple[RelationRecord, ...]:
    """Extract configured action relations without coreference or cross-sentence links."""
    sentences = tuple(doc.sents)
    sentence_indexes = {
        token.i: sentence_index
        for sentence_index, sentence in enumerate(sentences)
        for token in sentence
    }
    actions = [
        token
        for token in doc
        if token.pos_ in policy.action_pos and token.i in sentence_indexes
    ]
    relations: list[RelationRecord] = []
    actor_dependencies = set(policy.actor_dependencies)
    object_dependencies = set(policy.object_dependencies)

    for action in actions:
        sentence_index = sentence_indexes[action.i]
        sentence = sentences[sentence_index]
        actor_tokens = [
            child for child in action.children if child.dep_ in actor_dependencies
        ]
        object_tokens = [
            child for child in action.children if child.dep_ in object_dependencies
        ]
        for child in action.children:
            if child.dep_ == policy.agent_dependency:
                actor_tokens.extend(
                    grandchild
                    for grandchild in child.children
                    if grandchild.dep_ == policy.agent_object_dependency
                )

        actors = _deduplicate(
            _subtree_evidence(source, related, sentence_index)
            for token in actor_tokens
            for related in _recursive_conjunctions(
                token,
                policy.conjunction_dependency,
            )
        )
        if not actors:
            continue
        objects = _deduplicate(
            _subtree_evidence(source, related, sentence_index)
            for token in object_tokens
            for related in _recursive_conjunctions(
                token,
                policy.conjunction_dependency,
            )
        )
        relations.append(
            RelationRecord(
                sentence_index=sentence_index,
                action=_evidence(
                    source,
                    action.idx,
                    action.idx + len(action),
                    sentence_index,
                ),
                actors=actors,
                objects=objects,
                times=_sentence_entities(
                    sentence,
                    source,
                    policy.time_entity_labels,
                    sentence_index,
                ),
                places=_sentence_entities(
                    sentence,
                    source,
                    policy.place_entity_labels,
                    sentence_index,
                ),
            )
        )
    return tuple(relations)
