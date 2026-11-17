"""In what order does a shard work its items, and where does its config come from?"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from support.paths import CONFIG_DIR

from idhazh import config
from idhazh.contracts.article import Article
from idhazh.stages.work import _FetchedWorkItem, _work_order
from idhazh.telemetry.record import Flags, ItemRecorder

from ._builders import (
    article,
    plan,
)


def test_a_shard_works_its_shortest_sources_first_and_fetch_order_settles_a_tie() -> None:
    """When the shard's clock runs out, the items left unworked are the longest ones."""
    items = plan().items
    base = article()

    def sized(words: int, *, before_the_cut: int | None = None) -> Article:
        return base.model_copy(
            update={"word_count": words, "source_word_count": before_the_cut or words}
        )

    def quiet() -> ItemRecorder:
        """A recorder the sort never reads. It travels with the item, so it has to exist."""
        return ItemRecorder(
            run_id="r",
            flags=Flags(item_lines=False, stage_lines=False),
            now=lambda: "2026-09-15T00:00:00Z",
            log=logging.getLogger("test"),
        )

    candidates = [
        _FetchedWorkItem(items[0], sized(2000), "", 0, 0, 0.0, 0, quiet()),
        _FetchedWorkItem(items[1], sized(10), "", 0, 0, 0.0, 1, quiet()),
        _FetchedWorkItem(items[2], sized(800), "", 0, 0, 0.0, 2, quiet()),
        _FetchedWorkItem(items[3], sized(800), "", 0, 0, 0.0, 3, quiet()),
        # The extractor kept 1,000 words of a 9,000-word source: it is a long item.
        _FetchedWorkItem(items[4], sized(1000, before_the_cut=9000), "", 0, 0, 0.0, 4, quiet()),
    ]

    arrival = candidates[::-1]
    ordered = sorted(arrival, key=_work_order)

    assert [candidate.item.item_id for candidate in ordered] == [
        candidates[index].item.item_id for index in (1, 2, 3, 0, 4)
    ]


def test_the_config_that_was_read_travels_with_the_run() -> None:
    """A knob edited between two runs changes every output and is otherwise invisible."""
    settings = config.load(CONFIG_DIR)
    assert {digest.path for digest in settings.digests} == {
        "config/idhazh.json",
        "config/ledgers.json",
        "config/llm_council.json",
        *(f"config/judges/{name}.json" for name in settings.council.judge_names),
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
