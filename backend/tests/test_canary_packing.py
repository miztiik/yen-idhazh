"""Does the canary pack its fixture ledgers the way the gardener packs production?

The canary's `state/` sits in a tree of its own rather than at the repository
root, and the gardener's compaction learns what a ledger holds from a listing of
its declared `state/...` folders. So the listing is read from the tree that
holds that `state/`: read from the repository root, every path the compaction
asked about would sit outside it, and the pack would be refused before it
packed a day.
"""

from __future__ import annotations

from pathlib import Path

from idhazh import ledger
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledger_name import LedgerName
from utilities import build_canary_day


def test_the_fixture_ledgers_pack_from_a_state_tree_outside_the_repository_root(
    tmp_path: Path,
) -> None:
    """`tmp_path` stands for the repository and `canary/` for the tree the canary builds.

    Each ledger given a fixture row is packed. One with no row has nothing to
    pack, so its pass writes nothing: the real build files their rows first.
    """
    state = tmp_path / "canary" / ledger.STATE_DIRNAME
    state.mkdir(parents=True)

    filed = build_canary_day.file_published_fixture_rows(state)
    build_canary_day.pack_fixture_ledgers(state, tmp_path)
    build_canary_day.file_unpacked_fixture_day(state)

    assert filed, "the fixture files rows into some published ledgers"
    for which in build_canary_day.PACKED_LEDGERS:
        packed = which in filed
        assert (state / "compact" / which.value / "index" / "daily.json").is_file() is packed

    raw_day = state / "raw" / "item-health" / build_canary_day.UNPACKED_DATE.replace("-", "/")
    assert raw_day.is_dir()
    assert list(raw_day.glob("*.parquet"))
    assert not (
        state / "raw" / "item-health" / "index" / f"{build_canary_day.UNPACKED_DATE}.json"
    ).exists()


def test_the_canary_feed_results_reach_the_packed_days_the_voices_page_reads(
    tmp_path: Path,
) -> None:
    """The page reads feed results from packed days alone, so each canary day is packed.

    Filed by the canary's own builder and packed by the call the build makes, then
    read back day by day: every row it filed is in a packed file, and none twice.
    """
    state = tmp_path / "canary" / ledger.STATE_DIRNAME
    filed = build_canary_day.health(state)

    build_canary_day.pack_fixture_ledgers(state, tmp_path)

    days = (build_canary_day.YESTERDAY, build_canary_day.DATE)
    for day in days:
        packed = ledger.compact_path(state, LedgerName.FEED_HEALTH, Period.DAILY, day)
        assert packed.is_file(), f"{day} was not packed"
    rows = ledger.load_days(state, LedgerName.FEED_HEALTH, list(days), model=FeedHealthRow)
    assert len(rows) == filed
    assert len({(row.run_id, row.feed_id) for row in rows}) == filed
