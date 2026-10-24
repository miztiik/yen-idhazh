"""Config builders shared by backend tests."""

from typing import Any

from idhazh import config
from idhazh.contracts.knobs.collect import CollectConfig


def collect_config(**values: Any) -> CollectConfig:
    collect = CollectConfig(**values)
    collect.bind_source_tiers(config.load().taxonomy.source_tiers)
    return collect
