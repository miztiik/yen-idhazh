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
from idhazh.contracts.file_envelope import Period
from utilities import build_canary_day


def test_the_fixture_ledgers_pack_from_a_state_tree_outside_the_repository_root(
    tmp_path: Path,
) -> None:
    """`tmp_path` stands for the repository and `canary/` for the tree the canary builds."""
    state = tmp_path / "canary" / ledger.STATE_DIRNAME
    state.mkdir(parents=True)

    build_canary_day.pack_fixture_ledgers(state, tmp_path)

    for which in build_canary_day.PACKED_LEDGERS:
        assert ledger.watermark_path(state, which, Period.DAILY).is_file(), which.value
