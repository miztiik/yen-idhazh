"""When is a feed-health shard folded, when is it deleted, and what is never a candidate?"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from idhazh import day_shards, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.knobs.observability import ObservabilityConfig
from idhazh.retention import oldest_month_kept, prune_feed_health

from ._trees import (
    HISTORY_MONTHS,
    TODAY,
    feed_health_history,
    feed_health_months,
    months_back,
)


def feed_health_days(state_dir: Path) -> list[Path]:
    """Every feed-health file, oldest first, through the pipeline's own walk."""
    return list(day_shards.shard_files(state_dir / ledger.HEALTH_DIRNAME, days=UNBOUNDED_WINDOW))


def the_file_the_fixture_wrote(date: str) -> str:
    """Where the fixture's one plan job filed its verdicts for `date`.

    Built from the identity grammar rather than typed, so a change to how a
    writer names its file fails here with the grammar rather than passing on a
    string this test froze.
    """
    name = ledger.segment_name(run_id=f"{date}-1", attempt=1, job=ServerJob.PLAN, shard=0)
    return f"{ledger.health_relpath(date)}/{name}"


def test_the_feed_health_prune_takes_the_expired_day_and_keeps_the_day_beside_it(
    tmp_path: Path,
) -> None:
    """The prune half of the row's acceptance gate, on a tree built for the two cases.

    One day inside `observability.feed_health_keep_months` and one day outside
    it, `dry_run=False` passed as the argument every prune function already
    takes. The assertion is two-sided on purpose: "nothing failed", or "`deleted`
    is a tuple", passes on an EMPTY result - and an empty result is exactly what
    `retention.month_shards` returns over a day store, because it matches a
    seven-character `YYYY-MM` stem and a day tree has none. The store would
    silently stop being pruned and nothing would fail.

    `retention.dry_run` in `config/idhazh.json` never enters this - it is read by
    the CLI stage alone, so the pruner under test is not switched off.
    """
    state = tmp_path / "state"
    config = ObservabilityConfig()
    boundary = oldest_month_kept(TODAY, config.feed_health_keep_months)
    expired_day = f"{months_back(TODAY, config.feed_health_keep_months + 1)[0]}-09"
    kept_day = f"{boundary}-09"
    assert expired_day[:7] < boundary <= kept_day[:7], "the fixture must straddle the boundary"
    feed_health_history(state, [expired_day[:7], kept_day[:7]], day_of_month=9)
    expired_path = ledger.health_path(state, expired_day)
    kept_path = ledger.health_path(state, kept_day)
    assert expired_path.exists() and kept_path.exists()

    result = prune_feed_health(state, config, TODAY, dry_run=False)

    assert not expired_path.exists(), "the expired day is still there, so nothing was pruned"
    assert kept_path.exists(), "the day inside the window was deleted"
    assert list(result.deleted) == [expired_day[:7]]
    assert list(result.days_removed) == [the_file_the_fixture_wrote(expired_day)]
    assert feed_health_months(state) == [kept_day[:7]]
    # The emptied month and day directories go with their files, for the reason
    # the item-health prune gives: the walk reads every directory it finds.
    assert not expired_path.parent.exists()


def test_a_feed_health_month_past_its_own_age_is_deleted_rather_than_folded(
    tmp_path: Path,
) -> None:
    """Nothing reads a feed's result from fourteen months ago.

    The quarantine reads 31 days and the console reaches at most
    `console.max_window_days`, so a summary of an older month would be a shape
    with no consumer, written for ever. The knob is the store's own, and what
    survives is asserted against it rather than against a stem this test picked.
    """
    state = tmp_path / "state"
    config = ObservabilityConfig()
    months = months_back(TODAY, HISTORY_MONTHS)
    feed_health_history(state, months)
    boundary = oldest_month_kept(TODAY, config.feed_health_keep_months)

    result = prune_feed_health(state, config, TODAY)

    assert list(result.deleted) == [stem for stem in months if stem < boundary]
    assert list(result.kept) == [stem for stem in months if stem >= boundary]
    assert result.bytes_freed > 0
    assert feed_health_months(state) == list(result.kept)
    assert not (state / ledger.TELEMETRY_AGGREGATE_DIRNAME).exists(), (
        "feed health is deleted rather than folded; an aggregate here has no reader"
    )


def test_the_retirement_ledger_is_never_a_candidate(tmp_path: Path) -> None:
    """It carries no time window, so no age can expire it.

    One row is one address a server reported permanently gone. A run that forgot
    it would start asking a dead address again, and the evidence that retired it
    lives in shards this prune is entitled to delete - so the record has to
    outlive them.
    """
    state = tmp_path / "state"
    feed_health_history(state, months_back(TODAY, HISTORY_MONTHS))
    retirements = ledger.feed_retirements_path(state)
    retirements.write_text("header\n", encoding="utf-8")

    result = prune_feed_health(state, ObservabilityConfig(), TODAY)

    assert result.deleted, "the fixture has to reach past the window or this proves nothing"
    assert retirements.read_text(encoding="utf-8") == "header\n"


def test_a_feed_health_name_the_walk_cannot_place_stops_the_prune(tmp_path: Path) -> None:
    """Inside a day tree nothing is skipped, so a stray refuses the read.

    This is where the two grains differ and the difference is deliberate. A month
    directory is the top of its own store and may hold something that is not the
    collection, so `month_shards` left a stray alone. Below a year directory every
    name is written by `append_health` and by nothing else, so a name this walk
    cannot read means something else is writing there - and a prune that skipped
    it would delete the rows beside a file nobody can account for.
    """
    state = tmp_path / "state"
    feed_health_history(state, ["2024-01"])
    (state / ledger.HEALTH_DIRNAME / "2024-01.csv").write_text("header\n", encoding="utf-8")

    with pytest.raises(ValueError, match="not a file inside a YYYY/MM/DD day directory"):
        prune_feed_health(state, ObservabilityConfig(), TODAY)

    assert ledger.health_path(state, "2024-01-11").exists(), "a refused read deleted a day"


def test_a_feed_health_dry_run_names_the_day_and_leaves_it(tmp_path: Path) -> None:
    state = tmp_path / "state"
    feed_health_history(state, ["2024-01", TODAY.strftime("%Y-%m")])

    result = prune_feed_health(state, ObservabilityConfig(), TODAY, dry_run=True)

    assert result.deleted == ("2024-01",)
    # The writer's own file, never a `<month>-01` the ledger may never have held:
    # the dry run's whole deliverable is that its list equals what a live run
    # removes, file for file.
    assert result.days_removed == (the_file_the_fixture_wrote("2024-01-11"),)
    assert result.dry_run
    assert ledger.health_path(state, "2024-01-11").exists()


def test_a_feed_health_run_handed_an_older_date_keeps_the_live_shard(tmp_path: Path) -> None:
    """`--date` takes whatever it is given, so the boundary has to be a floor.

    `prune-state --date <last January>` computes a smaller window, and every
    day since is outside it. The rule is "older than the oldest month kept",
    not "outside the window", so the live day stays and only the genuinely
    older one goes. Deleting what is outside would take the file the next
    quarantine reads.
    """
    state = tmp_path / "state"
    feed_health_history(state, ["2024-01", "2026-08"])

    result = prune_feed_health(state, ObservabilityConfig(), date(2026, 1, 5))

    assert result.deleted == ("2024-01",)
    assert result.kept == ("2026-08",)
    assert ledger.health_path(state, "2026-08-11").exists(), (
        "the live shard was deleted by a run given an older date"
    )
    assert not ledger.health_path(state, "2024-01-11").exists()


def test_an_empty_state_tree_deletes_no_feed_health_and_says_so(tmp_path: Path) -> None:
    result = prune_feed_health(tmp_path / "state", ObservabilityConfig(), TODAY)
    assert result.changed is False
    assert result.deleted == ()
    assert result.bytes_freed == 0
