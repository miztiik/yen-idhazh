"""How does one executor process own and replace exactly one lazy spaCy model?"""

from __future__ import annotations

import gc
import importlib.metadata
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spacy.language import Language

from text_analysis.declare_api_contracts import ModelIdentity
from text_analysis.declare_service_settings import (
    ALL_FEATURES,
    EnabledLanguage,
    FeatureName,
    ModelProfile,
    RelationPolicy,
    ServiceSettings,
)


class ModelUnavailableError(RuntimeError):
    """Hide package and model loader diagnostics behind one safe API outcome."""


@dataclass(frozen=True, slots=True)
class LoadedModel:
    """Retain one process-local model and its verified feature capabilities."""

    nlp: Language
    identity: ModelIdentity
    unavailable_features: frozenset[FeatureName]
    relation_policy: RelationPolicy


_MODEL_SLOT: tuple[tuple[EnabledLanguage, ModelProfile], LoadedModel] | None = None


def _installed_version(package: str) -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        raise ModelUnavailableError from None


def verify_spacy_runtime(settings: ServiceSettings) -> None:
    """Verify the configured spaCy distribution without importing model weights."""
    if _installed_version("spacy") != settings.spacy_version:
        raise ModelUnavailableError


def _unavailable_features(
    nlp: Language,
    supported: tuple[FeatureName, ...],
    relation_policy: RelationPolicy,
) -> frozenset[FeatureName]:
    unavailable = set(ALL_FEATURES) - set(supported)
    pipes = set(nlp.pipe_names)
    has_sentences = bool(pipes & {"parser", "senter", "sentencizer"})
    has_entities = "ner" in pipes
    has_parser = "parser" in pipes
    parser_labels = set(nlp.get_pipe("parser").labels) if has_parser else set()
    entity_labels = set(nlp.get_pipe("ner").labels) if has_entities else set()

    if not has_entities:
        unavailable.add("entities")
    if nlp.lang != "en" or not has_entities or not has_sentences:
        unavailable.add("named_entities")
    if nlp.lang != "en" or not has_sentences:
        unavailable.add("important_terms")
    if not has_sentences:
        unavailable.add("sentences")
    if not has_parser:
        unavailable.add("noun_phrases")
    if not has_sentences or not has_entities:
        unavailable.add("document_metrics")

    relation_dependencies = (
        set(relation_policy.actor_dependencies)
        | set(relation_policy.object_dependencies)
        | {
            relation_policy.agent_dependency,
            relation_policy.agent_object_dependency,
            relation_policy.conjunction_dependency,
        }
    )
    relation_entities = set(relation_policy.time_entity_labels) | set(
        relation_policy.place_entity_labels
    )
    if (
        not has_parser
        or not has_entities
        or not parser_labels.intersection(relation_dependencies)
        or not entity_labels.intersection(relation_entities)
    ):
        unavailable.add("relations")
    return frozenset(unavailable)


def load_selected_model(
    settings: ServiceSettings,
    language: EnabledLanguage,
    profile: ModelProfile,
) -> tuple[LoadedModel, float]:
    """Load or reuse the selected model and report only actual load time."""
    global _MODEL_SLOT

    key = (language, profile)
    if _MODEL_SLOT is not None and _MODEL_SLOT[0] == key:
        return _MODEL_SLOT[1], 0.0
    if _MODEL_SLOT is not None:
        previous = _MODEL_SLOT[1]
        _MODEL_SLOT = None
        del previous
        gc.collect()

    selected_language = settings.languages.select(language)
    selected_model = selected_language.profiles.get(profile)
    if selected_model is None:
        raise ModelUnavailableError
    verify_spacy_runtime(settings)
    if _installed_version(selected_model.package) != selected_model.version:
        raise ModelUnavailableError

    started_at = time.monotonic()
    try:
        import spacy

        nlp = spacy.load(selected_model.package)
    except Exception as error:
        raise ModelUnavailableError from error
    model_load_ms = (time.monotonic() - started_at) * 1000
    model_version = str(nlp.meta.get("version", ""))
    if (
        nlp.lang != language
        or model_version != selected_model.version
        or _installed_version("spacy") != settings.spacy_version
    ):
        raise ModelUnavailableError

    relation_policy = settings.relation_rules.resolve(language)
    loaded = LoadedModel(
        nlp=nlp,
        identity=ModelIdentity(
            profile=profile,
            package=selected_model.package,
            model_version=model_version,
            spacy_version=settings.spacy_version,
        ),
        unavailable_features=_unavailable_features(
            nlp,
            selected_language.supported_features,
            relation_policy,
        ),
        relation_policy=relation_policy,
    )
    _MODEL_SLOT = (key, loaded)
    return loaded, model_load_ms
