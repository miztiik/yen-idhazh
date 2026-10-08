"""Every encoder the comparison names can file a reading.

The slug is a filename, a matrix value and a contract field at once. When the
workflow's own shape check and the contract disagreed, a shard downloaded its
weights, encoded nothing and died on the first write - so the check that
matters is the one the contract makes, and it is made here before any runner
time is spent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from idhazh.contracts.encoder_reading import EncoderReading, PairCounts, ReadingState

CONFIG = Path(__file__).resolve().parents[3] / "config" / "encoder-comparison.json"


def encoders() -> list[dict[str, object]]:
    return json.loads(CONFIG.read_text(encoding="utf-8"))["encoders"]


@pytest.mark.parametrize("encoder", encoders(), ids=lambda e: str(e["slug"]))
def test_every_named_encoder_can_open_a_reading(encoder: dict[str, object]) -> None:
    reading = EncoderReading(
        slug=encoder["slug"],
        model_id=encoder["model_id"],
        parameters_millions=encoder["parameters_millions"],
        prefix=encoder["prefix"],
        why=encoder["why"],
        state=ReadingState.LOADING,
        written_at="2026-10-08T00:00:00Z",
        articles_to_encode=1,
        pairs=PairCounts(same=1, different=1, ambiguous=1),
    )
    assert reading.slug == encoder["slug"]


def test_a_slug_with_a_dot_is_refused() -> None:
    """The failure this test exists for: `qwen3-embedding-0.6b`, 2026-10-08."""
    with pytest.raises(ValidationError):
        EncoderReading(
            slug="qwen3-embedding-0.6b",
            model_id="Qwen/Qwen3-Embedding-0.6B",
            parameters_millions=595,
            prefix="",
            why="a version number is not a slug",
            state=ReadingState.LOADING,
            written_at="2026-10-08T00:00:00Z",
            articles_to_encode=1,
        )


def test_a_measured_reading_encoded_everything() -> None:
    with pytest.raises(ValidationError):
        EncoderReading(
            slug="half-done",
            model_id="x/y",
            parameters_millions=1,
            why="stopped early but claims to be measured",
            state=ReadingState.MEASURED,
            written_at="2026-10-08T00:00:00Z",
            articles_to_encode=100,
            articles_done=40,
            separation=0.9,
        )


def test_an_unavailable_reading_says_why() -> None:
    with pytest.raises(ValidationError):
        EncoderReading(
            slug="silent-failure",
            model_id="x/y",
            parameters_millions=1,
            why="unavailable with no reason tells nobody anything",
            state=ReadingState.UNAVAILABLE,
            written_at="2026-10-08T00:00:00Z",
            articles_to_encode=100,
        )
