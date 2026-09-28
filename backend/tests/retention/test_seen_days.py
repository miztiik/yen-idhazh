"""Which seen and counterfactual day files does the planner still read, and which go?"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, timedelta
from pathlib import Path

import pytest

from idhazh import day_partition, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.counterfactual_score import CounterfactualScoreRow
from idhazh.contracts.knobs.collect import CollectConfig
from idhazh.contracts.knobs.observability import ObservabilityConfig
from idhazh.contracts.knobs.placement import LensWeightsConfig
from idhazh.contracts.knobs.retention import RetentionConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.seen import SeenRow
from idhazh.retention import prune_counterfactual_scores
from idhazh.stages.prune_state import stage_prune_state

from ._trees import (
    RUN_ID,
    TODAY,
)


def _seen_day(state: Path, day: str, rows: int = 1) -> Path:
    """One day of the seen ledger, written by the real appender."""
    ledger.append_seen(
        state,
        day,
        [
            SeenRow(
                version=SeenRow.schema_version(),
                url_key=hashlib.sha256(f"{day}-{n}".encode()).hexdigest(),
                first_seen_at=f"{day}T06:00:00Z",
                first_seen_run=f"{day}-1",
            )
            for n in range(rows)
        ],
    )
    return ledger.path(state, LedgerName.SEEN, day)


def _counterfactual_day(state: Path, day: str, rows: int = 1) -> Path:
    """One day of the counterfactual ledger, written by the real producer.

    The day directory comes back, because that is what the ledger files now: one
    file per writer inside it, and the prune deletes the files.
    """
    ledger.write_segment(
        state,
        LedgerName.COUNTERFACTUAL_SCORES,
        [
            CounterfactualScoreRow(
                version=CounterfactualScoreRow.schema_version(),
                date=day,
                run_id=f"{day}-1",
                vertical="ai",
                url_key=hashlib.sha256(f"{day}-{n}".encode()).hexdigest(),
                taken=n == 0,
                lens_id="chips",
                lens_bonus=0.3,
                lens_multiplier=1.25,
                score_committed=1.2,
                score_counterfactual=1.275,
            )
            for n in range(rows)
        ],
        run_id=f"{day}-1",
        attempt=1,
        job=ServerJob.PLAN,
        shard=0,
    )
    return ledger.path(state, LedgerName.COUNTERFACTUAL_SCORES, day)


def _counterfactual_file(day: str) -> str:
    """What the writer above named its file, spelled by the producer's own helper."""
    return ledger.day_shard_relpath(
        LedgerName.COUNTERFACTUAL_SCORES,
        date=day,
        run_id=f"{day}-1",
        attempt=1,
        job=ServerJob.PLAN,
        shard=0,
    )


def test_a_counterfactual_day_outside_the_window_goes_and_says_what_it_weighed(
    tmp_path: Path,
) -> None:
    """The ledger is appended to on every run, so without this it has no ceiling.

    `2024-01-15` is far outside any window this config can name. The day inside
    the window stays, and the empty year directory goes with the last day in it
    - a walk that kept them would cost more every year while reading the same
    rows.
    """
    state = tmp_path / "state"
    window = LensWeightsConfig().window_days
    today = TODAY.isoformat()
    stale = _counterfactual_day(state, "2024-01-15", rows=3)
    weight = sum(path.stat().st_size for path in stale.iterdir())
    kept = _counterfactual_day(state, today)

    result = prune_counterfactual_scores(state, today=today, within_days=window)

    assert result.deleted == (_counterfactual_file("2024-01-15"),)
    assert result.kept == (_counterfactual_file(today),)
    assert result.bytes_freed == weight
    assert not stale.exists()
    assert kept.exists()
    assert not (ledger.tree_root(state, LedgerName.COUNTERFACTUAL_SCORES) / "2024").exists()


def test_a_counterfactual_dry_run_names_the_day_file_and_leaves_it(tmp_path: Path) -> None:
    state = tmp_path / "state"
    stale = _counterfactual_day(state, "2024-01-15")

    result = prune_counterfactual_scores(
        state, today=TODAY.isoformat(), within_days=LensWeightsConfig().window_days, dry_run=True
    )

    assert result.deleted == (_counterfactual_file("2024-01-15"),)
    assert result.dry_run
    assert stale.exists()


def test_a_counterfactual_day_the_window_still_names_is_never_deleted(tmp_path: Path) -> None:
    """The boundary is the window's OLDEST day, not the window's edges.

    A run can be handed a date in the past, and deleting everything outside the
    window would then take the live day with it. The anchor here is a month
    before the day on disk, so the day on disk is newer than every date the
    window names - and it still has to survive.
    """
    state = tmp_path / "state"
    on = TODAY.isoformat()
    day = _counterfactual_day(state, on)
    past = (TODAY - timedelta(days=30)).isoformat()

    result = prune_counterfactual_scores(state, today=past, within_days=7)

    assert result.deleted == ()
    assert day.exists()


def test_the_stage_deletes_the_counterfactual_days_nobody_reads(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The wiring, asserted through the step an operator actually runs.

    A prune nothing calls is a prune that does not happen, and the ledger it
    would have bounded is the one that grows on every run.
    """
    state = tmp_path / "state"
    stale = _counterfactual_day(state, "2024-01-15")

    with caplog.at_level(logging.INFO):
        assert (
            stage_prune_state(
                observability=ObservabilityConfig(),
                collect=CollectConfig(),
                retention_config=RetentionConfig(),
                commit_sha="a" * 40,
                lens_weights=LensWeightsConfig(),
                run_id=RUN_ID,
                today=TODAY,
                state_dir=state,
            )
            == 0
        )

    assert not stale.exists()
    assert f"removed {_counterfactual_file('2024-01-15')}" in caplog.text


def test_the_stage_says_so_when_every_seen_day_is_inside_the_window(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A prune that deleted nothing has to say which window it measured against.

    Without the number, "nothing was deleted" reads the same whether the window
    is 90 days or the config went missing.
    """
    state = tmp_path / "state"
    _seen_day(state, TODAY.isoformat())

    with caplog.at_level(logging.INFO):
        assert (
            stage_prune_state(
                observability=ObservabilityConfig(),
                collect=CollectConfig(),
                retention_config=RetentionConfig(),
                commit_sha="a" * 40,
                run_id=RUN_ID,
                today=TODAY,
                state_dir=state,
            )
            == 0
        )

    assert "seen prune: every day file is inside the" in caplog.text
    assert str(CollectConfig().seen_window_days) in caplog.text


def test_the_stage_names_every_seen_day_it_removed_and_counts_what_it_kept(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The day grain moved what this line may say, and this is that difference.

    `kept` was at most four month stems and the line named every one. The window
    is 90 days, so it is now up to 91 paths - a line that joined them would be a
    wall nobody reads. The count and the oldest kept go in the line; the paths
    themselves are what `_report_removals` prints, one to a line, and that list
    is the deliverable of a dry run.
    """
    state = tmp_path / "state"
    _seen_day(state, "2024-01-15")
    _seen_day(state, TODAY.isoformat())

    with caplog.at_level(logging.INFO):
        assert (
            stage_prune_state(
                observability=ObservabilityConfig(),
                collect=CollectConfig(),
                retention_config=RetentionConfig(),
                commit_sha="a" * 40,
                run_id=RUN_ID,
                today=TODAY,
                state_dir=state,
                dry_run=True,
            )
            == 0
        )

    assert "seen prune (dry run): deleted 1 day files" in caplog.text
    assert f"kept 1 back to {ledger.relpath(LedgerName.SEEN, TODAY.isoformat())}" in caplog.text
    assert "would remove state/seen/2024/01/15.csv" in caplog.text


def test_what_is_kept_is_exactly_what_the_planner_reads() -> None:
    """The margin, in days, over every anchor date a year can offer.

    At month grain the two were only comparable in days: the prune kept whole
    month files and the reader asked for a span of days, so what survived ran 90
    to 120 days against a 90-day window. At day grain they are the same unit and
    the margin is zero on every date - which is a stronger property than the one
    it replaces, and the reason the grain moved.

    Arithmetic over 366 built anchor dates, so it opens no file and reads nothing
    the archive holds.
    """
    window = CollectConfig().seen_window_days
    for offset in range(366):
        anchor = date(2026, 1, 1) + timedelta(days=offset)
        oldest_kept = min(day_partition.days_in_window(anchor.isoformat(), window))
        retained_days = (anchor - date.fromisoformat(oldest_kept)).days
        assert retained_days == window, (
            f"on {anchor} the prune keeps back to {oldest_kept}, which is "
            f"{retained_days} days - the planner reads {window}"
        )
