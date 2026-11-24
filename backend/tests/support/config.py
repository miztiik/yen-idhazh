"""Config builders shared by backend tests."""

from typing import Any

from idhazh import config
from idhazh.contracts.knobs.collect import CollectConfig
from idhazh.contracts.knobs.content_similarity_canaries import ContentSimilarityCanaryConfig


def collect_config(**values: Any) -> CollectConfig:
    values.setdefault("vertical_feed_floors", {"ai": 1})
    collect = CollectConfig(**values)
    collect.bind_source_tiers(config.load().taxonomy.source_tiers)
    return collect


def canary_config() -> ContentSimilarityCanaryConfig:
    """Five independent examples exercise all verdicts and wrap around four runners."""
    examples = [
        ("same-1", "same", "YES", "A footbridge opened Monday.", "On Monday, a footbridge opened."),
        ("same-2", "same", "YES", "The library reopened Tuesday.", "The library is open again as of Tuesday."),
        ("different-1", "different", "NO", "A train derailed.", "A team won the cup."),
        ("different-2", "different", "NO", "The mayor resigned.", "A comet was discovered."),
        ("unclear-1", "unclear", "UNCLEAR", "A road was closed.", "Flooding closed Main Street."),
    ]
    return ContentSimilarityCanaryConfig.model_validate({
        "version": "2026-11-18",
        "pairs": [
            {
                "id": identifier,
                "kind": kind,
                "expected": expected,
                "left": {"summary": left},
                "right": {"summary": right},
            }
            for identifier, kind, expected, left, right in examples
        ],
    })
