"""Does the published day come out the same whatever order its blocks land in?"""

from __future__ import annotations

import itertools
import shutil
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, read_text

from idhazh import assemble, config
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.digest_run_fragment import DigestRunFragment

from ._builders import digest_item

pytestmark = pytest.mark.contract

#: Three blocks of one date, two of them finishing in the same second. The tie is
#: the point: a clock alone cannot order them, so the run id is what decides, and
#: a sort that read the clock alone would answer differently on every run.
FRAGMENTS_DIR = FIXTURES_DIR / "digest-fragments"
DATE = "2026-08-21"


FRAGMENT_NAMES = (
    "2026-08-21-1000000001.json",
    "2026-08-21-1000000002.json",
    "2026-08-21-1000000003.json",
)


def _blocks() -> list[Path]:
    return [FRAGMENTS_DIR / name for name in FRAGMENT_NAMES]


def _day_from(order: tuple[Path, ...], root: Path) -> DigestDay:
    """Land the blocks in one order and assemble the day out of what is there."""
    folder = assemble.fragment_dir(root, DATE)
    folder.mkdir(parents=True, exist_ok=True)
    for path in order:
        shutil.copyfile(path, folder / path.name)
    return assemble.assemble_day(
        assemble.read_fragments(root, DATE),
        taxonomy=config.load(CONFIG_DIR).taxonomy,
        retention_window_months=-1,
    )


def test_the_day_is_the_same_bytes_whatever_order_the_blocks_landed_in(tmp_path: Path) -> None:
    """The oracle. Arrival order is a property of the runners, not of the day.

    Two of the three blocks finish in the same second, so a clock alone leaves
    the order undecided - and an undecided order means two assemblies of one set
    of blocks write different bytes into the one file a reader opens, which is
    an add/add conflict on every republish.
    """
    orders = list(itertools.permutations(_blocks()))
    assert len(orders) == 6, "three blocks land in six orders"
    written = {
        _day_from(order, tmp_path / f"landing-{n}").to_json() for n, order in enumerate(orders)
    }
    assert len(written) == 1, "the day depends on which blocks exist, never on when they arrived"


def test_a_block_keeps_the_position_it_landed_in(tmp_path: Path) -> None:
    """A reader part-way down the page finds what they left where they left it."""
    base = DigestRunFragment.read(_blocks()[0])
    blocks = [
        base.model_copy(update={
            "run_id": f"{DATE}-90", "completed_at": f"{DATE}T06:00:00Z",
            "items": [digest_item(1), digest_item(2)], "items_planned": 2,
            "failed_item_ids": [],
        }),
        base.model_copy(update={
            "run_id": f"{DATE}-10", "completed_at": f"{DATE}T12:00:00Z",
            "items": [digest_item(3)], "items_planned": 1, "failed_item_ids": [],
        }),
        base.model_copy(update={
            "run_id": f"{DATE}-20", "completed_at": f"{DATE}T12:00:00Z",
            "items": [digest_item(4)], "items_planned": 1, "failed_item_ids": [],
        }),
    ]
    folder = assemble.fragment_dir(tmp_path, DATE)
    folder.mkdir(parents=True)
    for block in reversed(blocks):
        (folder / f"{block.run_id}.json").write_text(block.to_json(), encoding="utf-8")
    read_back = assemble.read_fragments(tmp_path, DATE)
    assert [block.run_id for block in read_back] == [block.run_id for block in blocks]
    day = assemble.assemble_day(
        read_back[::-1],
        taxonomy=config.load(CONFIG_DIR).taxonomy,
        retention_window_months=-1,
    )
    assert [run.n for run in day.runs] == list(range(1, len(blocks) + 1))
    assert [run.run_id for run in day.runs] == [block.run_id for block in blocks]
    assert {item.item_id: item.introduced_by_run for item in day.items} == {
        item.item_id: n for n, block in enumerate(blocks, start=1) for item in block.items
    }
    assert [item.introduced_by_run for item in day.items] == [
        n for n, block in enumerate(blocks, start=1) for _ in block.items
    ]


def test_a_story_that_failed_early_and_landed_later_is_not_a_failure(tmp_path: Path) -> None:
    """Failure is a fact about a run; the reader is asking about the day.

    The first block records a story as unfinished and the second block publishes
    it. Summing the blocks would print `partial` beside the story the reader can
    already see - and beside a failure count that had counted it too.
    """
    recovered = digest_item(7)
    unresolved = digest_item(8)
    base = DigestRunFragment.read(_blocks()[0])
    blocks = [
        base.model_copy(update={
            "run_id": f"{DATE}-40", "completed_at": f"{DATE}T06:00:00Z",
            "items": [], "items_planned": 2,
            "failed_item_ids": [recovered.item_id, unresolved.item_id],
        }),
        base.model_copy(update={
            "run_id": f"{DATE}-50", "completed_at": f"{DATE}T12:00:00Z",
            "items": [recovered], "items_planned": 1, "failed_item_ids": [],
        }),
    ]
    folder = assemble.fragment_dir(tmp_path, DATE)
    folder.mkdir(parents=True)
    for block in blocks:
        (folder / f"{block.run_id}.json").write_text(block.to_json(), encoding="utf-8")
    day = assemble.assemble_day(
        assemble.read_fragments(tmp_path, DATE),
        taxonomy=config.load(CONFIG_DIR).taxonomy,
        retention_window_months=-1,
    )
    assert [item.item_id for item in day.items] == [recovered.item_id]
    assert day.items_failed == 1
    assert day.partial is True
    assert len(day.items) + (day.items_failed or 0) <= day.items_planned


def test_the_stamp_is_the_newest_block_and_never_the_assembling_clock(tmp_path: Path) -> None:
    """A wall clock here is what makes two assemblies of one day disagree."""
    day = _day_from(tuple(_blocks()), tmp_path)
    newest = max(DigestRunFragment.read(path).completed_at for path in _blocks())
    assert day.generated_at == newest
    assert day.generated_at != assemble.utc_now()


def test_fewer_blocks_give_a_prefix_the_rest_is_appended_to(tmp_path: Path) -> None:
    """An assembly that cannot see every block is not wrong, only early.

    It inherits each block's position rather than computing one, so the blocks
    it did see keep the numbers they already had when the rest arrive.
    """
    blocks = _blocks()
    early = _day_from(tuple(blocks[:2]), tmp_path / "early")
    whole = _day_from(tuple(blocks), tmp_path / "whole")
    assert [item.item_id for item in whole.items[: len(early.items)]] == [
        item.item_id for item in early.items
    ]
    assert [run.run_id for run in whole.runs[: len(early.runs)]] == [
        run.run_id for run in early.runs
    ]


def test_a_day_written_before_blocks_existed_is_left_alone() -> None:
    """The whole read-side migration, and it retires itself.

    A day published before runs filed their own blocks records runs that no
    block can reproduce. Assembling that date would publish only what the blocks
    hold and delete every story the reader has already been shown, so the day
    that is there stands.
    """
    older = DigestDay.from_json(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    assert [run.run_id for run in older.runs] == [None, None]
    assert assemble.predates_fragments(older) is True


def test_a_day_whose_runs_all_name_themselves_is_assembled(tmp_path: Path) -> None:
    day = _day_from(tuple(_blocks()), tmp_path)
    assert assemble.predates_fragments(day) is False
