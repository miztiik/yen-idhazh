"""Assign article labels from configured, locally encoded comparison groups."""

from __future__ import annotations

import hashlib
import json
import logging
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
    ClassificationEncodingConfig,
    ComparisonGroup,
)
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.contracts.watchlist import Watchlist

LOG = logging.getLogger("idhazh")
_SLUG = TypeAdapter(Slug)


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
    model_path = _asset_path(asset_root, config.model_file, "model_file")
    tokenizer_path = _asset_path(asset_root, config.tokenizer_file, "tokenizer_file")

    session = embed.build_encoder_session(model_path)
    tokenizer = embed.build_tokenizer_file(tokenizer_path, max_tokens=config.max_tokens)
    probe_text = " ".join(["classification"] * (config.max_tokens * 4))
    if len(tokenizer.encode(probe_text).ids) != config.max_tokens:
        raise ValueError(
            "config/idhazh.json classification_encoding.max_tokens exceeds the "
            "configured tokenizer capacity"
        )
    try:
        probe = embed.encode_texts(session, tokenizer, [probe_text])[0]
    except Exception as error:
        raise ValueError(
            "config/idhazh.json classification_encoding.max_tokens is not supported "
            "by the configured model"
        ) from error
    if len(probe) != config.dimensions:
        raise ValueError(
            "config/idhazh.json classification_encoding.dimensions is "
            f"{config.dimensions}, but the configured model emits {len(probe)}"
        )

    texts = [target.text for group in groups for target in group.targets]
    try:
        vectors = embed.encode_texts(session, tokenizer, texts)
    except Exception as error:
        LOG.warning(
            "classification encoder failed while preparing targets; phrase tags will "
            "be used for this work run: %s",
            type(error).__name__,
        )
        return ClassificationContext(groups, None, None, config.dimensions, taxonomy, watchlist)
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
        encoded_groups, session, tokenizer, config.dimensions, taxonomy, watchlist
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
    except Exception as error:
        LOG.warning(
            "classification encoder failed for article %s; phrase tags are used: %s",
            article.item_id,
            type(error).__name__,
        )
        return tag.tagged(article, taxonomy=context.taxonomy, watchlist=context.watchlist)
    if context.dimensions is None:
        raise ValueError("classification context has no declared dimensions")
    if len(vector) != context.dimensions:
        LOG.warning(
            "classification encoder returned an unexpected width for article %s; "
            "phrase tags are used",
            article.item_id,
        )
        return tag.tagged(article, taxonomy=context.taxonomy, watchlist=context.watchlist)

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
            chosen = _unambiguous_best(group.config, scores)
            if chosen is not None:
                updates["desk"] = chosen
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


def _unambiguous_best(config: ComparisonGroup, scores: dict[str, float]) -> str | None:
    floor = _required_similarity(config)
    candidates = sorted(
        ((score, identity) for identity, score in scores.items() if score >= floor),
        key=lambda item: (-item[0], item[1]),
    )
    if not candidates:
        return None
    margin = config.ambiguity_margin
    if margin is None:
        raise ValueError(f"classification group {config.id} has no ambiguity margin")
    if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < margin:
        return None
    return candidates[0][1]


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
