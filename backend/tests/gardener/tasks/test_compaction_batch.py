"""Does a pass write each index once and resume after any write phase without losing rows?"""

from __future__ import annotations

import dataclasses
from collections import Counter
from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest

from idhazh import ledger
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.gardener.tasks import _compaction_periods, _daily_period, _monthly_period
from idhazh.gardener.tasks._compact_tree import CompactTree

from ._task import context_for
from .test_compaction import VISUALS, a_pass, compact, filed, state, watermark
from .test_compaction_years import index_entries

pytestmark = pytest.mark.contract


def test_a_pending_index_cannot_overwrite_a_path_the_pass_deletes(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    index_entries(root, Period.DAILY, [])
    path = ledger.compact_index_path(state(root), VISUALS, Period.DAILY)
    before = path.read_bytes()
    context = context_for("compact-visual-prunes", root, today=date(2026, 1, 8))
    tree = CompactTree.read(context.state_dir, VISUALS, context.listing)
    tree.delete(path)
    tree.mark_index(Period.DAILY)

    with pytest.raises(ValueError, match="was deleted earlier in this pass"):
        tree.finish()

    assert path.read_bytes() == before


def decide(root: Path, today: date) -> CompactTree:
    """Plan the shipped monthly and daily stages on a real ledger tree."""
    context = context_for(
        "compact-visual-prunes",
        root,
        today=today,
        dry_run=False,
        daily_keep_days=31,
        monthly_window={"unit": "forever"},
        max_periods_per_run=64,
    )
    policy = context.policy
    assert isinstance(policy, CompactionPolicy)
    tree = CompactTree.read(context.state_dir, VISUALS, context.listing)
    now = datetime.combine(today, time.min, tzinfo=UTC)
    identity = WriterIdentity(
        run_id=context.run_id,
        attempt=context.attempt,
        job=context.job,
        shard=context.shard,
        producer="gardener.tasks.compaction",
        git_sha=context.git_sha,
    )
    tree.name_raw_months(
        _compaction_periods.first_run_months(tree, policy, now=now, operator_range=None)
    )
    chosen = _compaction_periods.choose(tree, policy, now=now, operator_range=None)
    assert (
        _monthly_period.absorb(
            tree, chosen.months, stamp="2026-03-05T00:00:00Z", identity=identity
        )
        == ()
    )
    assert (
        _daily_period.compact(
            tree,
            policy,
            chosen.days,
            rerun_span=chosen.rerun_span,
            stamp="2026-03-05T00:00:00Z",
            identity=identity,
        )
        == ()
    )
    tree.finish()
    return tree


def served(root: Path) -> list[VisualPruneRow]:
    """Read sources without settlement, so duplicate rows cannot hide."""
    found = ledger.list_ledger_files(state(root), VISUALS)
    assert found.holes == ()
    return sorted(
        [
            held.row
            for source in found.sources
            for held in ledger.load_stored(source.paths, model=VisualPruneRow)
        ],
        key=lambda row: row.date,
    )


@pytest.mark.parametrize("monthly", [False, True], ids=["days", "months-and-days"])
@pytest.mark.parametrize("phase", ["data", "indexes", "some-deletes", "deletes"])
def test_indexes_are_written_once_and_an_interrupted_pass_resumes(
    tmp_path: Path,
    monthly: bool,
    phase: str,
) -> None:
    root = tmp_path / "checkout"
    filed(root, a_pass("2026-01-05"))
    if monthly:
        compact(
            root,
            date(2026, 2, 3),
            daily_keep_days=31,
            monthly_window={"unit": "forever"},
            max_periods_per_run=64,
        )
        filed(root, a_pass("2026-02-10"))
        today = date(2026, 3, 5)
    else:
        filed(root, a_pass("2026-01-06"))
        today = date(2026, 1, 8)
    before = served(root)
    tree = decide(root, today)
    indexes = {ledger.compact_index_path(state(root), VISUALS, p) for p in Period}
    marks = {ledger.watermark_path(state(root), VISUALS, p) for p in Period}
    counts = Counter(change.path for change in tree.changes if change.path in indexes | marks)
    assert counts and set(counts.values()) == {1}
    index_positions = [i for i, change in enumerate(tree.changes) if change.path in indexes]
    delete_positions = [i for i, change in enumerate(tree.changes) if change.data is None]
    assert max(index_positions) < min(delete_positions)
    cuts = {
        "data": min(index_positions),
        "indexes": max(index_positions) + 1,
        "some-deletes": min(delete_positions) + 1,
        "deletes": max(delete_positions) + 1,
    }
    dataclasses.replace(tree, changes=tree.changes[: cuts[phase]]).apply()
    assert served(root) == before

    compact(
        root,
        today,
        daily_keep_days=31,
        monthly_window={"unit": "forever"},
        max_periods_per_run=64,
    )

    assert served(root) == before
    assert watermark(root, Period.DAILY) == ("2026-03-03" if monthly else "2026-01-06")
    assert ledger.list_raw_files(state(root), VISUALS) == []
    if monthly:
        assert watermark(root, Period.MONTHLY) == "2026-01"
        assert ledger.compact_file(state(root), VISUALS, Period.DAILY, "2026-01-05") is None
