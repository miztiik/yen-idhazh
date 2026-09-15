"""Over fifteen months, what is left standing?"""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

import pytest

from idhazh import day_partition, ledger
from idhazh.contracts.item_health import ItemStage
from idhazh.contracts.knobs.collect import CollectConfig
from idhazh.contracts.knobs.observability import ObservabilityConfig
from idhazh.contracts.knobs.retention import RetentionConfig
from idhazh.retention import month_shards
from idhazh.stages.prune_state import stage_prune_state
from idhazh.telemetry.publish import public_telemetry

from ._trees import (
    CONSOLE_MAX_WINDOW_DAYS,
    RUN_ID,
    TODAY,
    a_state_tree,
    feed_health_history,
    feed_health_months,
    health_row,
    item_health_days,
    item_health_history,
    item_health_months,
    months_back,
    totals_from_aggregate,
    totals_from_shard,
)


def test_the_oracle_fifteen_months_leave_fourteen_of_each_and_one_verified_summary(
    tmp_path: Path,
) -> None:
    """One month expires and the three stores that hold it agree about it.

    Fifteen months against a fourteen-month age is the tightest fixture that can
    fail either way: one month expires, so an off-by-one shows up as an empty
    result or as an emptied tree rather than as a shard on the wrong side.

    What the run has to leave: fourteen full-grain item-health shards, fourteen
    matching browser copies, fourteen feed-health shards, the expired item month
    present only as one aggregate whose totals equal the shard it replaced, the
    expired feed month gone, and a second run that changes no byte.
    """
    config = ObservabilityConfig()
    keep = config.item_health_full_grain_months
    months = months_back(TODAY, keep + 1)
    expired, survivors = months[0], months[1:]
    assert len(survivors) == keep == 14

    state = tmp_path / "state"
    item_health_history(state, months)
    feed_health_history(state, months)
    public = tmp_path / "frontend" / "public" / "telemetry"
    public_telemetry.publish(state_root=state, public_root=public)
    doomed_texts = [
        day.read_text(encoding="utf-8")
        for day in item_health_days(state)
        if day_partition.month_of(day) == expired
    ]

    first = stage_prune_state(
        observability=config,
        collect=CollectConfig(),
        retention_config=RetentionConfig(),
        run_id=RUN_ID,
        today=TODAY,
        state_dir=state,
        public_root=public,
    )
    assert first == 0

    assert item_health_months(state) == survivors
    assert [path.stem for path in month_shards(public)] == survivors
    assert feed_health_months(state) == survivors
    assert len(survivors) == 14

    # The expired month survives as one summary, and the summary is checked
    # against the file it replaced rather than against the code that wrote it.
    aggregate = ledger.telemetry_aggregate_path(state, expired)
    assert [path.stem for path in month_shards(state / ledger.TELEMETRY_AGGREGATE_DIRNAME)] == [
        expired
    ]
    assert totals_from_aggregate(ledger.load_telemetry_aggregate(aggregate)) == totals_from_shard(
        doomed_texts
    )
    assert not public_telemetry.shard_path(public, expired).exists()
    assert not ledger.health_path(state, f"{expired}-11").exists()

    # Every window a 366-day console read can select still names a file that is
    # there. `shards_in_window` is the reader's own helper, so this is the read
    # itself rather than a restatement of it.
    for offset in range(31):
        anchor = (TODAY - timedelta(days=offset)).isoformat()
        for stem in ledger.shards_in_window(anchor, CONSOLE_MAX_WINDOW_DAYS):
            if stem < months[0] or stem > months[-1]:
                continue
            assert public_telemetry.shard_path(public, stem).exists(), (
                f"a {CONSOLE_MAX_WINDOW_DAYS}-day read anchored on {anchor} names "
                f"{stem}, which this prune deleted"
            )

    everything = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in sorted(tmp_path.rglob("*.csv"))
    }

    assert (
        stage_prune_state(
            observability=config,
            collect=CollectConfig(),
            retention_config=RetentionConfig(),
            run_id=RUN_ID,
            today=TODAY,
            state_dir=state,
            public_root=public,
        )
        == 0
    )

    assert {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in sorted(tmp_path.rglob("*.csv"))
    } == everything, "a second run over a settled tree must move no byte"


def test_the_stage_names_every_file_a_live_run_would_remove(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The dry run's whole deliverable: the paths, not a count.

    This list is what a person reads before turning the deletion on, so it is
    the POSIX relative path of each file (`CLAUDE.md` section 2) and it says
    "would remove" rather than "removed" while nothing is being removed.
    """
    config = ObservabilityConfig()
    months = months_back(TODAY, config.item_health_full_grain_months + 1)
    state = tmp_path / "state"
    item_health_history(state, months)
    feed_health_history(state, months)
    public = tmp_path / "frontend" / "public" / "telemetry"
    public_telemetry.publish(state_root=state, public_root=public)
    expired = months[0]

    with caplog.at_level(logging.INFO):
        assert (
            stage_prune_state(
                observability=config,
                collect=CollectConfig(),
                retention_config=RetentionConfig(),
                run_id=RUN_ID,
                today=TODAY,
                state_dir=state,
                public_root=public,
                dry_run=True,
            )
            == 0
        )

    named = sorted(
        line.split("would remove ", 1)[1]
        for line in caplog.text.splitlines()
        if "prune-state would remove " in line and not line.endswith("files:")
    )
    # Every day file the fold would take, named one by one. The month has two, so
    # a list that named `<month>-01` would print a path the ledger never held and
    # miss the one it did - and the dry run's whole deliverable is that its list
    # equals what a live run removes, file for file. Feed health is the same
    # shape one store over: it files by day too, and the fixture writes the 11th.
    expired_days = [
        day.relative_to(state.parent).as_posix()
        for day in item_health_days(state)
        if day_partition.month_of(day) == expired
    ]
    assert len(expired_days) == 2, "the fixture writes two days a month"
    assert named == sorted(
        [
            *expired_days,
            ledger.health_relpath(f"{expired}-11"),
            f"frontend/public/telemetry/{expired}.csv",
        ]
    )
    assert "\\" not in caplog.text, "a path leaving the process is POSIX (section 2)"
    assert all((state.parent / relpath).exists() for relpath in expired_days)
    assert public_telemetry.shard_path(public, expired).exists()
    assert ledger.health_path(state, f"{expired}-11").exists()


def test_the_stage_says_so_when_there_is_nothing_to_remove(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Silence and "nothing expired" read the same, and only one of them is true."""
    state = tmp_path / "state"
    day = f"{TODAY:%Y-%m}-04"
    ledger.append_item_health(
        state, day, [health_row(day=day, run=1, number=1, stage=ItemStage.PUBLISH)]
    )

    with caplog.at_level(logging.INFO):
        assert (
            stage_prune_state(
                observability=ObservabilityConfig(),
                collect=CollectConfig(),
                retention_config=RetentionConfig(),
                run_id=RUN_ID,
                today=TODAY,
                state_dir=state,
            )
            == 0
        )

    assert "prune-state removes no file today" in caplog.text


def test_the_stage_reports_what_it_folded(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """What a person reads off the run: which months went, and how many rows they held."""
    state = a_state_tree(tmp_path)
    with caplog.at_level(logging.INFO):
        assert (
            stage_prune_state(
                observability=ObservabilityConfig(),
                collect=CollectConfig(),
                retention_config=RetentionConfig(),
                run_id=RUN_ID,
                today=TODAY,
                state_dir=state,
            )
            == 0
        )
    assert "telemetry fold:" in caplog.text
    assert "2025-06" in caplog.text, "the oldest month past the window has to be named"
    assert "2025-07" not in caplog.text, "the oldest month kept must not be folded"


def test_the_stage_says_so_when_every_month_is_still_at_full_grain(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    state = tmp_path / "state"
    day = f"{TODAY:%Y-%m}-04"
    ledger.append_item_health(
        state, day, [health_row(day=day, run=1, number=1, stage=ItemStage.PUBLISH)]
    )
    with caplog.at_level(logging.INFO):
        assert (
            stage_prune_state(
                observability=ObservabilityConfig(),
                collect=CollectConfig(),
                retention_config=RetentionConfig(),
                run_id=RUN_ID,
                today=TODAY,
                state_dir=state,
            )
            == 0
        )
    assert "every month is still at full grain" in caplog.text
    assert ledger.item_health_path(state, day).exists()
