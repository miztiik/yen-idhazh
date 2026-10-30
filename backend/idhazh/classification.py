"""Assign article labels from configured, locally encoded comparison groups."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import TypeAdapter, ValidationError

from idhazh import embed, tag
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import Slug
from idhazh.contracts.knobs.classification_encoding import (
    MODEL_METADATA_FILENAME,
    ClassificationEncodingConfig,
    ComparisonGroup,
)
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.contracts.watchlist import Watchlist

LOG = logging.getLogger("idhazh")
_SLUG = TypeAdapter(Slug)
_ENCODER_RUNTIME_FAILURES: tuple[type[Exception], ...] = (
    ImportError, OSError, RuntimeError, MemoryError
)


@dataclass(frozen=True, slots=True)
class Target:
    id: str
    text: str
    evidence_phrases: tuple[str, ...]
    vector: tuple[float, ...] | None = None


@dataclass(frozen=True, slots=True)
class Group:
    config: ComparisonGroup
    targets: tuple[Target, ...]


@dataclass(frozen=True, slots=True)
class ClassificationContext:
    groups: tuple[Group, ...]
    session: Any | None
    tokenizer: Any | None
    dimensions: int | None
    taxonomy: Taxonomy
    watchlist: Watchlist
    runtime_failures: tuple[type[Exception], ...] = _ENCODER_RUNTIME_FAILURES


def load_context(
    *,
    config: ClassificationEncodingConfig | None,
    repo_root: Path,
    config_dir: Path,
    taxonomy: Taxonomy,
    watchlist: Watchlist,
) -> ClassificationContext:
    """Validate configured sources and prepare target vectors once for this run."""
    if config is None:
        raise ValueError(
            "config/idhazh.json is refused: classification_encoding is required by "
            "the article-classification stage"
        )

    source_cache: dict[str, Mapping[str, Any]] = {}
    groups = tuple(
        Group(
            config=group,
            targets=_targets_for_group(
                group,
                source_cache=source_cache,
                config_dir=config_dir,
            ),
        )
        for group in config.comparison_groups
    )
    asset_root = _asset_path(
        repo_root, config.asset_directory, "asset_directory", file_required=False
    )
    for relative, expected in config.model_digests.items():
        path = _asset_path(asset_root, relative, f"model_digests[{relative}]")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(
                f"config/idhazh.json classification_encoding.model_digests[{relative}] "
                f"does not match {config.asset_directory}/{relative}"
            )
    model_config_path = _asset_path(
        asset_root, MODEL_METADATA_FILENAME, "model config"
    )
    try:
        model_metadata = json.loads(model_config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(
            "classification_encoding model config.json is missing or invalid"
        ) from error
    if not isinstance(model_metadata, dict):
        raise ValueError("classification_encoding model config.json must be an object")
    model_capacity = model_metadata.get("max_position_embeddings")
    if type(model_capacity) is not int or model_capacity < 1:
        raise ValueError(
            "classification_encoding model config.json.max_position_embeddings "
            "must be a positive integer"
        )
    if config.max_tokens > model_capacity:
        raise ValueError(
            "config/idhazh.json classification_encoding.max_tokens exceeds "
            "config.json.max_position_embeddings"
        )
    model_width = model_metadata.get("hidden_size")
    if type(model_width) is not int or model_width < 1:
        raise ValueError(
            "classification_encoding model config.json.hidden_size must be a positive integer"
        )
    if config.dimensions != model_width:
        raise ValueError(
            "config/idhazh.json classification_encoding.dimensions is "
            f"{config.dimensions}, but config.json.hidden_size is {model_width}"
        )

    model_path = _asset_path(asset_root, config.model_file, "model_file")
    tokenizer_path = _asset_path(asset_root, config.tokenizer_file, "tokenizer_file")
    runtime_failures = _ENCODER_RUNTIME_FAILURES
    try:
        runtime_failures = _encoder_failure_types()
        session = embed.build_encoder_session(model_path)
        tokenizer = embed.build_tokenizer_file(tokenizer_path, max_tokens=config.max_tokens)
        outputs = session.get_outputs()
    except runtime_failures as error:
        return _phrase_fallback(
            groups, config.dimensions, taxonomy, watchlist, "loading", error
        )
    if not outputs or not outputs[0].shape:
        raise ValueError(
            "classification encoder output metadata does not declare a vector width"
        )
    output_width = outputs[0].shape[-1]
    if isinstance(output_width, int) and output_width != config.dimensions:
        raise ValueError(
            "config/idhazh.json classification_encoding.dimensions is "
            f"{config.dimensions}, but the configured model emits {output_width}"
        )
    if not isinstance(output_width, int):
        try:
            probe = embed.encode_texts(session, tokenizer, ["classification"])[0]
        except runtime_failures as error:
            return _phrase_fallback(
                groups, config.dimensions, taxonomy, watchlist, "checking model width", error
            )
        if len(probe) != config.dimensions:
            raise ValueError(
                "config/idhazh.json classification_encoding.dimensions is "
                f"{config.dimensions}, but the configured model emits {len(probe)}"
            )

    texts = [target.text for group in groups for target in group.targets]
    try:
        vectors = embed.encode_texts(session, tokenizer, texts)
    except runtime_failures as error:
        return _phrase_fallback(
            groups, config.dimensions, taxonomy, watchlist, "preparing targets", error
        )
    if len(vectors) != len(texts) or any(
        len(vector) != config.dimensions for vector in vectors
    ):
        raise ValueError(
            "classification encoder target vectors do not match "
            "classification_encoding.dimensions"
        )

    vector_iter = iter(vectors)
    encoded_groups = tuple(
        Group(
            config=group.config,
            targets=tuple(
                Target(
                    id=target.id,
                    text=target.text,
                    evidence_phrases=target.evidence_phrases,
                    vector=tuple(next(vector_iter)),
                )
                for target in group.targets
            ),
        )
        for group in groups
    )
    return ClassificationContext(
        encoded_groups, session, tokenizer, config.dimensions, taxonomy, watchlist,
        runtime_failures,
    )


def _phrase_fallback(
    groups: tuple[Group, ...],
    dimensions: int,
    taxonomy: Taxonomy,
    watchlist: Watchlist,
    stage: str,
    error: Exception,
) -> ClassificationContext:
    LOG.warning(
        "classification encoder failed while %s; phrase tags will be used for this work run: %s",
        stage,
        _failure_reason(error),
    )
    return ClassificationContext(groups, None, None, dimensions, taxonomy, watchlist)


def _encoder_failure_types() -> tuple[type[Exception], ...]:
    return (*_ENCODER_RUNTIME_FAILURES, *_onnx_runtime_failures())


def _failure_reason(error: Exception) -> str:
    detail = str(error).splitlines()[0] if str(error) else "no error detail"
    detail = re.sub(r"(?i)\b[A-Z]:\\[^,;\r\n]+|\\\\[^,;\r\n]+", "<local path>", detail)
    detail = re.sub(r"(?<![\w.])/(?:[^,;\r\n]+)", "<local path>", detail)
    return f"{type(error).__name__}: {detail}"


def _onnx_runtime_failures() -> tuple[type[Exception], ...]:
    try:
        import onnxruntime.capi.onnxruntime_pybind11_state as state
    except ImportError:
        return ()
    names = (
        "DeviceReset",
        "EPFail",
        "EngineError",
        "Fail",
        "ModelLoadCanceled",
        "ModelRequiresCompilation",
        "RuntimeException",
    )
    return tuple(
        error_type
        for name in names
        if isinstance((error_type := getattr(state, name, None)), type)
        and issubclass(error_type, Exception)
    )


def assign(article: Article, context: ClassificationContext) -> Article:
    """Compare sanitized article text against all groups, then assign known fields."""
    if article.status is not ArticleStatus.OK:
        return article
    if context.session is None or context.tokenizer is None:
        return tag.tagged(article, taxonomy=context.taxonomy, watchlist=context.watchlist)

    text = f"{article.title or ''}. {article.text or ''}"
    try:
        vector = embed.encode_texts(context.session, context.tokenizer, [text])[0]
    except context.runtime_failures as error:
        LOG.warning(
            "classification encoder failed for article %s; phrase tags are used: %s",
            article.item_id,
            _failure_reason(error),
        )
        return tag.tagged(article, taxonomy=context.taxonomy, watchlist=context.watchlist)
    if context.dimensions is None:
        raise ValueError("classification context has no declared dimensions")
    if len(vector) != context.dimensions:
        raise ValueError(
            "classification encoder returned an unexpected article vector width: "
            f"expected {context.dimensions}, got {len(vector)}"
        )

    comparisons: dict[str, dict[str, float]] = {}
    for group in context.groups:
        comparisons[group.config.id] = {
            target.id: _cosine(vector, target.vector)
            for target in group.targets
            if target.vector is not None
        }

    updates: dict[str, object] = {}
    for group in context.groups:
        destination = group.config.destination
        scores = comparisons[group.config.id]
        if destination == "desk":
            chosen = _unambiguous_desks(group.config, scores)
            if chosen:
                updates["desk"] = chosen[0]
            if len(chosen) > 1:
                updates["secondary_desk"] = chosen[1]
        elif destination in {"lenses", "events"}:
            floor = _required_similarity(group.config)
            updates[destination] = sorted(
                identity for identity, score in scores.items() if score >= floor
            )
        elif destination == "entities":
            updates[destination] = _named_entities(group, scores, text)

    return article.model_copy(update=updates)


def _targets_for_group(
    group: ComparisonGroup,
    *,
    source_cache: dict[str, Mapping[str, Any]],
    config_dir: Path,
) -> tuple[Target, ...]:
    source = source_cache.get(group.source)
    if source is None:
        path = _source_path(config_dir, group.source)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(
                f"{group.source} is refused by classification group {group.id}"
            ) from error
        if not isinstance(value, dict):
            raise ValueError(f"{group.source} must contain a JSON object")
        source = value
        source_cache[group.source] = source

    entries = source.get(group.entries_key)
    if not isinstance(entries, list):
        raise ValueError(
            f"{group.source}.{group.entries_key} is not a list for classification group "
            f"{group.id}"
        )
    targets: list[Target] = []
    seen: set[str] = set()
    required_fields = {group.id_field, *group.text_fields, *group.match}
    for index, entry in enumerate(entries):
        prefix = f"{group.source}.{group.entries_key}[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{prefix} must be an object")
        missing = sorted(required_fields - entry.keys())
        if missing:
            raise ValueError(
                f"{prefix} is missing configured classification fields: {', '.join(missing)}"
            )
        identity = entry[group.id_field]
        if not isinstance(identity, str) or not identity:
            raise ValueError(f"{prefix}.{group.id_field} must be a non-empty string")
        try:
            _SLUG.validate_python(identity)
        except ValidationError as error:
            raise ValueError(f"{prefix}.{group.id_field} is not a valid id") from error
        if identity in seen:
            raise ValueError(f"{prefix}.{group.id_field} duplicates id {identity}")
        seen.add(identity)

        values: list[str] = []
        for field in group.text_fields:
            field_value = entry[field]
            if isinstance(field_value, str):
                values.append(field_value)
            elif isinstance(field_value, list) and all(
                isinstance(value, str) for value in field_value
            ):
                values.extend(field_value)
            else:
                raise ValueError(f"{prefix}.{field} must be a string or a list of strings")
        for field in group.match:
            if not isinstance(entry[field], str):
                raise ValueError(f"{prefix}.{field} must be a string for exact matching")
        if not all(entry[field] == expected for field, expected in group.match.items()):
            continue
        text = ". ".join(value for value in values if value.strip())
        if not text:
            raise ValueError(f"{prefix} has no selected classification text")
        targets.append(
            Target(
                id=identity,
                text=text,
                evidence_phrases=tuple(value for value in values if value.strip()),
            )
        )
    if not targets:
        raise ValueError(f"{group.source} selects no entries for classification group {group.id}")
    return tuple(targets)


def _source_path(config_dir: Path, relative: str) -> Path:
    return _asset_path(config_dir.parent, relative, "comparison group source")


def _asset_path(
    base: Path, relative: str, field: str, *, file_required: bool = True
) -> Path:
    portable = PurePosixPath(relative)
    if portable.is_absolute() or not portable.parts or ".." in portable.parts:
        raise ValueError(f"classification_encoding.{field} must be a safe relative path")
    root = base.resolve()
    path = root.joinpath(*portable.parts)
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"classification_encoding.{field} file is missing: {relative}") from error
    expected_type = resolved.is_file() if file_required else resolved.is_dir()
    if not resolved.is_relative_to(root) or not expected_type:
        kind = "file" if file_required else "directory"
        raise ValueError(f"classification_encoding.{field} is not a {kind} under its root")
    return resolved


def _cosine(left: list[float], right: tuple[float, ...] | None) -> float:
    if right is None or len(left) != len(right):
        raise ValueError("classification vectors have different dimensions")
    return sum(a * b for a, b in zip(left, right, strict=True))


def _required_similarity(config: ComparisonGroup) -> float:
    if config.minimum_similarity is None:
        raise ValueError(f"classification group {config.id} has no similarity threshold")
    return config.minimum_similarity


def _unambiguous_desks(config: ComparisonGroup, scores: dict[str, float]) -> tuple[str, ...]:
    floor = _required_similarity(config)
    candidates = sorted(
        ((score, identity) for identity, score in scores.items() if score >= floor),
        key=lambda item: (-item[0], item[1]),
    )
    if not candidates:
        return ()
    margin = config.ambiguity_margin
    if margin is None:
        raise ValueError(f"classification group {config.id} has no ambiguity margin")
    if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < margin:
        return ()
    if len(candidates) == 1:
        return (candidates[0][1],)
    if len(candidates) > 2 and candidates[1][0] - candidates[2][0] < margin:
        return (candidates[0][1],)
    return tuple(identity for _, identity in candidates[:2])


def _named_entities(group: Group, scores: dict[str, float], text: str) -> list[str]:
    floor = _required_similarity(group.config)
    margin = group.config.ambiguity_margin
    if margin is None:
        raise ValueError(f"classification group {group.config.id} has no ambiguity margin")
    haystack = tag.normalise(text)
    phrase_owners: dict[str, set[str]] = defaultdict(set)
    for target in group.targets:
        for phrase in target.evidence_phrases:
            normalised = tag.normalise(phrase)
            if normalised != " " and normalised in haystack:
                phrase_owners[normalised].add(target.id)

    matched: set[str] = set()
    for owners in phrase_owners.values():
        candidates = sorted(
            ((scores[identity], identity) for identity in owners if scores[identity] >= floor),
            key=lambda item: (-item[0], item[1]),
        )
        if not candidates:
            continue
        if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < margin:
            continue
        matched.add(candidates[0][1])
    return sorted(matched)
