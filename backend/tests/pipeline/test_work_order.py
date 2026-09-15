"""In what order does a shard work its items, and where does its config come from?"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from conftest import CONFIG_DIR

from idhazh import config, itemrecord
from idhazh.contracts.article import Article
from idhazh.stages.work import _FetchedWorkItem, _summarize_band_sort_key

from ._builders import (
    article,
    plan,
)

pytestmark = pytest.mark.slow


def test_work_items_sort_by_summarize_band_and_keep_in_band_order() -> None:
    """Band order groups identical system prompts without changing item identity."""
    settings = config.load(CONFIG_DIR)
    items = plan().items
    base = article()

    def sized(words: int) -> Article:
        # Both counts, because the band follows the source body and the sort
        # has to agree with the prompt it is grouping.
        return base.model_copy(update={"word_count": words, "source_word_count": words})

    def quiet() -> itemrecord.ItemRecorder:
        """A recorder the sort never reads. It travels with the item, so it has to exist."""
        return itemrecord.ItemRecorder(
            run_id="r",
            flags=itemrecord.Flags(item_lines=False, stage_lines=False),
            now=lambda: "2026-09-15T00:00:00Z",
            log=logging.getLogger("test"),
        )

    candidates = [
        _FetchedWorkItem(items[0], sized(2000), "", 0, 0, 0.0, 0, quiet()),
        _FetchedWorkItem(items[1], sized(10), "", 0, 0, 0.0, 1, quiet()),
        _FetchedWorkItem(items[2], sized(800), "", 0, 0, 0.0, 2, quiet()),
        _FetchedWorkItem(items[3], sized(100), "", 0, 0, 0.0, 3, quiet()),
    ]

    ordered = sorted(candidates, key=lambda candidate: _summarize_band_sort_key(candidate, settings))

    assert [candidate.item.item_id for candidate in ordered] == ["ai-02", "ai-04", "ai-03", "ai-01"]


def test_a_fresh_clone_loads_its_committed_config() -> None:
    settings = config.load(CONFIG_DIR)
    assert settings.app.run.safety_ceiling_per_run >= 1
    assert settings.sources.feeds
    assert settings.taxonomy.verticals


def test_the_config_that_was_read_travels_with_the_run() -> None:
    """A knob edited between two runs changes every output and is otherwise invisible."""
    settings = config.load(CONFIG_DIR)
    assert {digest.path for digest in settings.digests} == {
        "config/idhazh.json",
        # Named through the pointer, never spelled here: a swap moves it, and a
        # test that spelled the incumbent's filename would then be asserting
        # that the record still names a model the run did not read.
        f"config/{settings.app.models_file}",
        "config/sources.json",
        "config/taxonomy.json",
        "config/watchlist.json",
    }
    digests = settings.digests
    assert all(len(digest.sha256) == 64 for digest in digests)


def test_a_missing_config_file_fails_at_startup(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        config.load(tmp_path)
