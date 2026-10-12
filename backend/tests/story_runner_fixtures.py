"""Build bounded typed arithmetic fixtures without publishing annotation evidence."""

import json
from pathlib import Path

import numpy as np

from idhazh.contracts.encoder_reading import EncoderReading, ReadingState
from idhazh.contracts.story_candidates import VectorCache
from idhazh.contracts.story_encoder_candidate import PinnedEncoderCandidate
from idhazh.contracts.story_evaluation import StoryPolicy
from idhazh.contracts.story_source import ArchiveArticle, ArticleEvidence, SourceCheck, SourceFreeze
from idhazh.contracts.story_vectors import VectorSnapshot
from idhazh.story_dataset.encoder_candidates import register_pinned_candidate
from idhazh.story_dataset.source import article_id, load_policy
from idhazh.story_dataset.storage import digest, file_hash, now

PIN = "f" * 40


def articles() -> dict[str, ArticleEvidence]:
    result = {}
    for index in range(4):
        source = ArchiveArticle(
            domain="example.invalid",
            first_day="2026-10-11",
            item_id=f"generated-{index}",
            published_at="2026-10-11T00:00:00Z",
            time_source="generated-fixture",
            title=f"Generated article {index}",
            summary=f"Generated summary {index}; no article archive or annotation.",
            url=f"https://example.invalid/generated-{index}",
        )
        identity = article_id(source.url)
        result[identity] = ArticleEvidence(
            article_id=identity, input_sha256=digest(source), source=source
        )
    return result


def manifest() -> SourceFreeze:
    return SourceFreeze(
        source_sha256="1" * 64,
        source_bytes=1,
        articles=len(articles()),
        first_days=["2026-10-11"],
        frozen_at=now(),
        source_description="Generated bounded runner protocol fixture; no model inference.",
        regression_hashes={},
        approved_examples_sha256="2" * 64,
    )


def policy() -> StoryPolicy:
    return load_policy(Path("config") / "story-dataset.json").model_copy(
        update={"batch_size": 20, "metadata_neighbors": 1}
    )


def registered_candidate(root: Path) -> tuple[PinnedEncoderCandidate, VectorSnapshot]:
    rows = list(articles())[:2]
    reading = EncoderReading(
        slug="fixture-control",
        model_id="fixture/model",
        parameters_millions=0,
        why="Generated fixture only; no actual model provenance claim.",
        written_at=now(),
        state=ReadingState.MEASURED,
        articles_to_encode=2,
        articles_done=2,
        numbers_an_article=2,
        separation=0.5,
    )
    (root / "reading.json").write_text(
        json.dumps({"encoders": [reading.model_dump(mode="json")]}), encoding="utf-8"
    )
    (root / "input.json").write_text("{}", encoding="utf-8")
    (root / "config.json").write_text("{}", encoding="utf-8")
    np.save(root / "old.npy", np.eye(2, dtype=np.float32))
    legacy = VectorSnapshot(
        path_base="dataset-root",
        source_sha256=manifest().source_sha256,
        input_sha256=file_hash(root / "input.json"),
        input_file="input.json",
        readings_file="reading.json",
        readings_sha256=file_hash(root / "reading.json"),
        encoder_config_file="config.json",
        encoder_config_sha256=file_hash(root / "config.json"),
        max_sequence_length=256,
        article_ids=rows,
        text_sha256=[digest(i) for i in rows],
        missing_article_ids=sorted(set(articles()) - set(rows)),
        caches=[
            VectorCache(
                slug=reading.slug,
                model_id=reading.model_id,
                revision=None,
                file="old.npy",
                file_sha256=file_hash(root / "old.npy"),
                rows=2,
                dimensions=2,
                reading_sha256=digest(reading),
                input_sha256=file_hash(root / "input.json"),
                settings_sha256=digest({"prefix": "", "model_options": {}, "encode_options": {}}),
            )
        ],
    )
    metadata = root / "metadata.json"
    metadata.write_text(json.dumps({"id": reading.model_id, "sha": PIN}), encoding="utf-8")
    check = SourceCheck(
        url=f"https://huggingface.co/api/models/{reading.model_id}/revision/{PIN}?expand[]=sha",
        checked_at=now(),
        state="read",
        finding="Generated offline metadata fixture.",
        evidence_sha256=file_hash(metadata),
    )
    return register_pinned_candidate(legacy, root, reading.slug, PIN, metadata, check, root), legacy
