"""Does the exact approved archive still match its frozen source contract?"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from idhazh.contracts.story_evaluation import StoryPolicy
from idhazh.contracts.story_source import ArchiveArticle, ArticleEvidence, SourceFreeze
from idhazh.story_dataset.storage import Store, digest, file_hash, now, read_model, write_model

REGRESSION_FILES = (
    "corpus/encoder-comparison-1/judgments/pairs.json",
    "corpus/encoder-comparison-1/judgments/verdicts.jsonl",
    "corpus/encoder-comparison-1/pairs.json",
)


def article_id(url: str) -> str:
    return "a-" + hashlib.sha256(url.encode("utf-8")).hexdigest()


def load_articles(path: Path, expected: int) -> dict[str, ArticleEvidence]:
    rows: dict[str, ArticleEvidence] = {}
    with path.open("rb") as stream:
        for index, line in enumerate(stream, 1):
            if index > expected:
                raise ValueError("archive exceeds the approved bounded input")
            article = ArchiveArticle.model_validate_json(line)
            identity = article_id(article.url)
            if identity in rows:
                raise ValueError("archive contains a repeated URL")
            rows[identity] = ArticleEvidence(
                article_id=identity, input_sha256=digest(article), source=article
            )
    if len(rows) != expected:
        raise ValueError(f"expected {expected} unique articles, found {len(rows)}")
    return rows


def freeze(root: Path, repository: Path, policy: StoryPolicy, examples: Path) -> SourceFreeze:
    path = root / "articles.jsonl"
    if path.stat().st_size != policy.expected_bytes or file_hash(path) != policy.expected_sha256:
        raise ValueError("approved source bytes/hash mismatch; never normalize the source")
    articles = load_articles(path, policy.expected_articles)
    existing = root / "manifest.json"
    if existing.exists():
        manifest = read_model(existing, SourceFreeze)
        validate_freeze(root, repository, policy)
        store = Store(root)
        try:
            with store.transaction():
                if store.setting("source") not in (None, manifest.source_sha256):
                    raise ValueError("state belongs to a different source freeze")
                store.set_setting("source", manifest.source_sha256)
                store.set_setting("format", "story-dataset-2026-10-09")
        finally:
            store.close()
        return manifest
    manifest = SourceFreeze(
        source_sha256=file_hash(path),
        source_bytes=path.stat().st_size,
        articles=len(articles),
        first_days=sorted({row.source.first_day for row in articles.values()}),
        frozen_at=now(),
        source_description="Owner-approved exact 45-day archive, Aug 21-Oct 5 2026; local only.",
        regression_hashes={name: file_hash(repository / name) for name in REGRESSION_FILES},
        approved_examples_sha256=file_hash(examples),
    )
    write_model(existing, manifest)
    store = Store(root)
    try:
        with store.transaction():
            store.set_setting("source", manifest.source_sha256)
            store.set_setting("format", "story-dataset-2026-10-09")
    finally:
        store.close()
    return manifest


def validate_freeze(
    root: Path, repository: Path, policy: StoryPolicy
) -> tuple[SourceFreeze, dict[str, ArticleEvidence]]:
    manifest = read_model(root / "manifest.json", SourceFreeze)
    path = root / manifest.source_file
    if (
        manifest.source_sha256 != policy.expected_sha256
        or manifest.source_bytes != policy.expected_bytes
        or manifest.articles != policy.expected_articles
        or path.stat().st_size != manifest.source_bytes
        or file_hash(path) != manifest.source_sha256
    ):
        raise ValueError("source freeze does not match the approved input")
    for name, expected in manifest.regression_hashes.items():
        if name not in REGRESSION_FILES or file_hash(repository / name) != expected:
            raise ValueError(f"immutable regression changed: {name}")
    examples = root / "approved-examples.json"
    if examples.exists() and file_hash(examples) != manifest.approved_examples_sha256:
        raise ValueError("approved example evidence changed")
    return manifest, load_articles(path, manifest.articles)


def load_policy(path: Path) -> StoryPolicy:
    return StoryPolicy.model_validate(json.loads(path.read_bytes()))
