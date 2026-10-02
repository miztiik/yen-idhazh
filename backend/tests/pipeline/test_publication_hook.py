"""Is the `Check.ledger` hook live, or only declared?

Integration tier (CLAUDE.md section 13). No check shipped today declares a
ledger, so the branch that files a check's rows has no production consumer -
and a branch nothing exercises is a branch that stops working without anyone
noticing. This is its one named consumer.

**The write path is real, not seamed.** `write_segment`, the day shard it
lands in, and `settled_rows` reading it back all run for real; the only thing
replaced is `discover`, so the run sees one probe check instead of the four on
disk. That is a seam on what is under test, not a mock of the thing under test
(Guardrail #7): nothing here stands in for a value production would compute.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from idhazh import day_shards, ledger
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.ledger_name import LedgerName
from idhazh.publication_checks import PublicationCheckError, registry, runner
from utilities import build_canary_day

DAY = "2026-09-20"
RUN_ID = "2026-09-20-1"


def a_row() -> FeedHealthRow:
    """One real feed response filed through the publication hook."""
    return FeedHealthRow(
        version=FeedHealthRow.schema_version(),
        date=DAY,
        run_id=RUN_ID,
        feed_id="example-feed",
        checked_at=f"{DAY}T06:00:00Z",
        outcome=FetchOutcome.OK,
        status=200,
        items=3,
    )


def a_probe(row: FeedHealthRow, name: str = "probe") -> registry.Check:
    """A check that measures nothing and files one row into a real ledger."""
    return registry.Check(
        name=name,
        scope=registry.CheckScope.DAY,
        run=lambda _ctx: registry.CheckResult(rows=(row,)),
        ledger=LedgerName.FEED_HEALTH,
    )


def a_committed_day(tmp_path: Path) -> Path:
    """One quiet day under a published tree, written by the canary builder."""
    digest_root = tmp_path / "public" / "digest"
    build_canary_day.quiet_day(digest_root, DAY)
    return digest_root


def test_a_declared_ledger_row_is_written_and_read_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hook is live: a row goes in through `write_segment` and comes back equal."""
    row = a_row()
    monkeypatch.setattr(runner, "discover", lambda: (a_probe(row),))
    state_dir = tmp_path / "state"

    assert (
        runner.run_publication_checks(
            a_committed_day(tmp_path), [DAY], state_dir=state_dir, run_id=RUN_ID
        )
        == 0
    )

    read = [
        FeedHealthRow.from_csv_row(cells)
        for cells in day_shards.settled_rows(
            ledger.tree_root(state_dir, LedgerName.FEED_HEALTH),
            ledger.FEED_HEALTH_KEY,
            FeedHealthRow,
            days=UNBOUNDED_WINDOW,
        )
    ]
    assert read == [row]


def test_a_sweep_over_the_whole_archive_files_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gate re-reads every frozen day on a contract change, and must not re-file.

    A sweep is a re-reading of days already measured. Filing its rows would add
    a row per day per contract change, so the same run that finds nothing wrong
    would grow the ledger it writes into (Guardrail #12).
    """
    monkeypatch.setattr(runner, "discover", lambda: (a_probe(a_row()),))
    state_dir = tmp_path / "state"

    assert (
        runner.run_publication_checks(
            a_committed_day(tmp_path), state_dir=state_dir, run_id=RUN_ID
        )
        == 0
    )

    assert not ledger.tree_root(state_dir, LedgerName.FEED_HEALTH).exists()


def test_a_run_with_no_run_id_refuses_rather_than_filing_an_unattributable_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A row nothing can attribute is worse than no row.

    The verb takes `--run-id` optionally because no check on disk needs one.
    The day one does, a caller that forgot the flag has to hear about it - the
    alternative is a ledger quietly missing the rows it was built for.
    """
    monkeypatch.setattr(runner, "discover", lambda: (a_probe(a_row()),))

    with pytest.raises(PublicationCheckError, match="--run-id"):
        runner.run_publication_checks(
            a_committed_day(tmp_path), [DAY], state_dir=tmp_path / "state"
        )


def test_a_check_with_no_ledger_may_not_emit_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rows with nowhere to go are dropped silently unless somebody refuses them."""
    stray = registry.Check(
        name="stray",
        scope=registry.CheckScope.DAY,
        run=lambda _ctx: registry.CheckResult(rows=(a_row(),)),
    )
    monkeypatch.setattr(runner, "discover", lambda: (stray,))

    with pytest.raises(PublicationCheckError, match="nowhere to file"):
        runner.run_publication_checks(
            a_committed_day(tmp_path), [DAY], state_dir=tmp_path / "state", run_id=RUN_ID
        )
