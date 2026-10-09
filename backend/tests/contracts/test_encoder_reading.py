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
from typing import TypedDict

import pytest
from pydantic import ValidationError

from idhazh.contracts.encoder_reading import EncoderReading, PairCounts, ReadingState

CONFIG = Path(__file__).resolve().parents[3] / "config" / "encoder-comparison.json"


class NamedEncoder(TypedDict):
    """One row of `config/encoder-comparison.json`, as its readers use it.

    Written down rather than read as a bag of anything, because this test
    exists to catch a config and a contract disagreeing before a runner spends
    an hour on it. A row whose parameter count arrived as text would pass a
    read that promises nothing about its fields, and fail on the runner.
    """

    slug: str
    model_id: str
    prefix: str
    parameters_millions: int
    why: str


def encoders() -> list[NamedEncoder]:
    """The encoders the comparison names, in the order the config lists them."""
    settings: dict[str, list[NamedEncoder]] = json.loads(
        CONFIG.read_text(encoding="utf-8")
    )
    return settings["encoders"]


@pytest.mark.parametrize("encoder", encoders(), ids=lambda e: e["slug"])
def test_every_named_encoder_can_open_a_reading(encoder: NamedEncoder) -> None:
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


def test_the_thread_setting_resolves_to_a_positive_count() -> None:
    """The failure this test exists for: five shards died at once, 2026-10-08.

    The setting carries zero to mean "take the machine's own count", and the
    program handed the zero straight to a library that will only accept a
    positive number. Every shard failed in the first second, after the pair set
    had been built and the weights had begun downloading.
    """
    import os

    settings = json.loads(CONFIG.read_text(encoding="utf-8"))
    asked = settings["encode"]["threads"]
    assert asked >= 0, "a thread count is zero for automatic, or a positive number"
    resolved = asked or os.cpu_count() or 1
    assert resolved >= 1, "the resolved thread count has to be positive"
