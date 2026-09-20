"""What does folding a month of telemetry keep, and what happens to the browser's copy?"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Final

import pytest
from conftest import seed_item_health

from idhazh import day_partition, ledger
from idhazh.contracts.item_health import ItemStage
from idhazh.contracts.knobs.observability import ObservabilityConfig
from idhazh.contracts.telemetry_aggregate import percentile
from idhazh.evals import archive as score_archive
from idhazh.retention import compact_month, month_shards, oldest_month_kept, prune_telemetry
from idhazh.telemetry.publish import public_telemetry

from ._trees import (
    HISTORY_MONTHS,
    NOT_MONTHS,
    TODAY,
    a_state_tree,
    health_row,
    item_health_days,
    item_health_months,
    months_back,
    totals_from_aggregate,
    totals_from_shard,
)


def test_the_fold_keeps_the_configured_window_at_full_grain(tmp_path: Path) -> None:
    """Every day inside the window is byte-identical, and every day outside is gone.

    Two-sided on the day files themselves, because that is what the prune now
    unlinks: an assertion only about months would pass on a month directory left
    behind holding rows nobody deleted.
    """
    state = a_state_tree(tmp_path)
    config = ObservabilityConfig()
    before = {day: day.read_bytes() for day in item_health_days(state)}
    assert sorted({day_partition.month_of(day) for day in before}) == months_back(
        TODAY, HISTORY_MONTHS
    )

    result = prune_telemetry(state, config, TODAY)

    kept = oldest_month_kept(TODAY, config.item_health_full_grain_months)
    assert config.item_health_full_grain_months == 14, (
        "a 366-day console read can open fourteen month shards"
    )
    assert kept == "2025-07", "fourteen months ending in August 2026 starts in July 2025"
    assert list(result.folded) == sorted(
        {month for month in months_back(TODAY, HISTORY_MONTHS) if month < kept}
    )
    assert len(result.folded) == HISTORY_MONTHS - config.item_health_full_grain_months
    expired = [day for day in before if day_partition.month_of(day) < kept]
    assert expired, "the fixture has to reach past the window or this proves nothing"
    for day, bytes_before in before.items():
        if day_partition.month_of(day) < kept:
            assert not day.exists(), f"{day.name} is past the window and must be gone"
        else:
            assert day.read_bytes() == bytes_before, f"{day.name} is inside the window"
    assert item_health_months(state) == [
        month for month in months_back(TODAY, HISTORY_MONTHS) if month >= kept
    ]
    # The emptied month and year directories go with their files. A walk that
    # kept them would cost more every year while the rows it reads are deleted.
    assert not expired[0].parent.exists()


def test_the_fold_loses_no_total(tmp_path: Path) -> None:
    """The grain changes; the answer does not. A fold that loses a total is a failed fold."""
    state = a_state_tree(tmp_path)
    config = ObservabilityConfig()
    kept = oldest_month_kept(TODAY, config.item_health_full_grain_months)
    doomed: dict[str, list[str]] = {}
    for day in item_health_days(state):
        month = day_partition.month_of(day)
        if month < kept:
            doomed.setdefault(month, []).append(day.read_text(encoding="utf-8"))
    assert doomed, "the fixture has to reach past the window or this proves nothing"

    prune_telemetry(state, config, TODAY)

    for month, texts in doomed.items():
        folded = ledger.load_telemetry_aggregate(ledger.telemetry_aggregate_path(state, month))
        assert totals_from_aggregate(folded) == totals_from_shard(texts), (
            f"{month} lost a total in the fold"
        )


def test_the_fold_keeps_a_repeated_row_rather_than_deciding_for_a_reader(
    tmp_path: Path,
) -> None:
    """The committed ledger carries repeated keys, and the fold reproduces them.

    Run `2026-08-29-3` really did leave 212 item-health rows for 168 items.
    Collapsing them at fold time would make the aggregate disagree with the file
    it replaced, and nobody could then say which of the two was right.
    """
    day = "2024-01-04"
    state = tmp_path / "state"
    rows = [health_row(day=day, run=run, number=7, stage=ItemStage.PUBLISH) for run in (1, 2)]
    seed_item_health(state, day, rows)

    folded = compact_month(ledger.load_item_health_shard(ledger.item_health_path(state, day)))

    assert [row.items for row in folded] == [2]
    assert folded[0].timed == 2
    slowest = folded[0].max_ms
    assert slowest is not None
    assert folded[0].sum_ms == 2 * slowest, "both copies of one item, added"


def test_a_group_that_timed_nothing_says_so_rather_than_saying_zero(tmp_path: Path) -> None:
    """An instrument that did not run writes an empty cell. Empty is not zero."""
    day = "2024-01-04"
    state = tmp_path / "state"
    seed_item_health(
        state, day, [health_row(day=day, run=1, number=1, stage=ItemStage.PLAN)]
    )

    folded = compact_month(ledger.load_item_health_shard(ledger.item_health_path(state, day)))

    assert [row.stage for row in folded] == [ItemStage.PLAN]
    assert folded[0].items == 1
    assert folded[0].timed == 0
    assert (folded[0].p50_ms, folded[0].p90_ms, folded[0].max_ms, folded[0].sum_ms) == (
        None,
        None,
        None,
        None,
    )
    assert folded[0].csv_row()["p50_ms"] == ""


def test_a_percentile_is_a_number_some_item_really_took(tmp_path: Path) -> None:
    """Nearest rank, never interpolation. An invented millisecond count cannot be checked."""
    assert percentile([5], 0.5) == 5
    assert percentile([5], 0.9) == 5
    assert percentile([1, 2, 3, 4], 0.5) == 2
    assert percentile([1, 2, 3, 4], 0.9) == 4
    assert percentile(list(range(1, 11)), 0.9) == 9
    with pytest.raises(ValueError):
        percentile([], 0.5)


def test_a_dry_run_changes_nothing_on_disk(tmp_path: Path) -> None:
    state = a_state_tree(tmp_path)
    before = {
        path.relative_to(state).as_posix(): path.read_bytes()
        for path in sorted(state.rglob("*.csv"))
    }

    result = prune_telemetry(state, ObservabilityConfig(), TODAY, dry_run=True)

    after = {
        path.relative_to(state).as_posix(): path.read_bytes()
        for path in sorted(state.rglob("*.csv"))
    }
    assert result.dry_run is True
    assert result.folded, "it still has to report what it would have done"
    assert result.rows_folded > 0
    assert after == before
    assert not (state / ledger.TELEMETRY_AGGREGATE_DIRNAME).exists()


def test_the_aggregate_is_kept_forever_unless_somebody_asks_for_the_bytes_back(
    tmp_path: Path,
) -> None:
    """`console.max_window_days` is 366, so a shard has to answer for a year.

    Running the fold twenty times over must never remove an aggregate while
    `item_health_aggregate_keep_months` is null, which is what ships.
    """
    state = a_state_tree(tmp_path)
    config = ObservabilityConfig()
    assert config.item_health_aggregate_keep_months is None

    first = prune_telemetry(state, config, TODAY)
    written = sorted(path.stem for path in month_shards(state / ledger.TELEMETRY_AGGREGATE_DIRNAME))
    again = prune_telemetry(state, config, TODAY)

    assert written == sorted(first.folded)
    assert again.folded == (), "the shards are gone, so a second fold has nothing to do"
    assert again.hard_deleted == ()
    assert (
        sorted(path.stem for path in month_shards(state / ledger.TELEMETRY_AGGREGATE_DIRNAME))
        == written
    )


def test_a_hard_delete_takes_the_aggregate_only_after_the_fold_has_had_it(
    tmp_path: Path,
) -> None:
    """The escape hatch, for the day the owner wants the bytes back.

    The config refuses a threshold at or below the full-grain window, so a month
    is always folded before it can be deleted - this proves the deletion happens
    at the threshold the config does allow.
    """
    state = a_state_tree(tmp_path)
    config = ObservabilityConfig(item_health_aggregate_keep_months=16)
    prune_telemetry(state, ObservabilityConfig(), TODAY)
    before = sorted(path.stem for path in month_shards(state / ledger.TELEMETRY_AGGREGATE_DIRNAME))

    result = prune_telemetry(state, config, TODAY)

    boundary = oldest_month_kept(TODAY, 16)
    assert sorted(result.hard_deleted) == [stem for stem in before if stem < boundary]
    assert result.hard_deleted, "a threshold inside the fixture has to remove something"
    left = sorted(path.stem for path in month_shards(state / ledger.TELEMETRY_AGGREGATE_DIRNAME))
    assert left == [stem for stem in before if stem >= boundary]


def test_the_window_is_counted_in_months_and_not_in_thirty_day_steps() -> None:
    """A month file is kept or dropped whole, so the arithmetic is in months."""
    assert oldest_month_kept(date(2026, 8, 30), 13) == "2025-08"
    assert oldest_month_kept(date(2026, 8, 1), 13) == "2025-08"
    assert oldest_month_kept(date(2026, 1, 15), 13) == "2025-01"
    assert oldest_month_kept(date(2026, 1, 15), 1) == "2026-01"
    assert oldest_month_kept(date(2026, 12, 31), 24) == "2025-01"
    with pytest.raises(ValueError):
        oldest_month_kept(date(2026, 8, 30), 0)


#: The rest of what turns up beside a shard: the wrong width, no date at all,
#: and a file whose real suffix is not the one being read.
OTHER_STRAYS: Final = ("notes", "2025-1", "README", "2025-01.csv")


def test_the_prune_takes_the_expired_day_and_keeps_the_day_beside_it(tmp_path: Path) -> None:
    """The row's oracle, on a tree built to hold exactly the two cases.

    One day inside `observability.item_health_full_grain_months` and one day
    outside it, `dry_run=False` passed as the argument every prune function
    already takes. The assertion is two-sided on purpose: "nothing failed", or
    "`folded` is a tuple", passes on an EMPTY tree - and an empty tree is exactly
    what `retention.month_shards` returns over a day store, because it matches a
    seven-character `YYYY-MM` stem and a day tree has none. The store would
    silently stop being pruned and nothing would fail.

    The fold is the other half: the aggregate is written and read back before a
    day file is unlinked, so the expired day's rows survive as totals rather than
    being deleted on the strength of a write nobody checked.

    `retention.dry_run` in `config/idhazh.json` never enters this - it is read by
    the CLI stage alone, so the pruner under test is not switched off.
    """
    state = tmp_path / "state"
    config = ObservabilityConfig()
    keep_from = oldest_month_kept(TODAY, config.item_health_full_grain_months)
    expired_day = f"{months_back(TODAY, config.item_health_full_grain_months + 1)[0]}-09"
    kept_day = f"{keep_from}-09"
    assert expired_day[:7] < keep_from <= kept_day[:7], "the fixture must straddle the boundary"
    for day in (expired_day, kept_day):
        seed_item_health(
            state, day, [health_row(day=day, run=1, number=1, stage=ItemStage.PUBLISH)]
        )
    expired_path = ledger.item_health_path(state, expired_day)
    kept_path = ledger.item_health_path(state, kept_day)
    expired_text = expired_path.read_text(encoding="utf-8")
    assert expired_path.exists() and kept_path.exists()

    result = prune_telemetry(state, config, TODAY, dry_run=False)

    assert not expired_path.exists(), "the expired day is still there, so nothing was pruned"
    assert kept_path.exists(), "the day inside the window was deleted"
    assert list(result.folded) == [expired_day[:7]]
    assert item_health_months(state) == [kept_day[:7]]
    folded = ledger.load_telemetry_aggregate(ledger.telemetry_aggregate_path(state, expired_day[:7]))
    assert totals_from_aggregate(folded) == totals_from_shard([expired_text])


def test_the_month_readers_all_agree_on_what_a_month_is(tmp_path: Path) -> None:
    """One rule for the two directories still filing by month. They used to carry three.

    This is the defect the row is about, stated as one assertion. A directory a
    prune deletes from names what it recognises, so two directories that
    recognise different things dispose of the same file two different ways.

    `state/scores/` and `state/score-index/` left this set on 2026-09-13 when
    they moved to `<YYYY>/<MM>/<DD>.csv` - they walk through
    `day_partition.day_files` now, which has its own refusal rule and its own
    test.
    """
    state = tmp_path / "state"
    readers: dict[str, tuple[Path, str, Callable[[], list[Path]]]] = {
        "retention.month_shards": (
            state / ledger.TELEMETRY_AGGREGATE_DIRNAME,
            ".csv",
            lambda: month_shards(state / ledger.TELEMETRY_AGGREGATE_DIRNAME),
        ),
        "evals.archive.archive_files": (
            state / score_archive.ARCHIVE_DIRNAME,
            ".json",
            lambda: score_archive.archive_files(state),
        ),
    }
    for directory, suffix, _ in readers.values():
        directory.mkdir(parents=True)
        for stem in ("2025-01", "2025-12", *NOT_MONTHS, *OTHER_STRAYS):
            (directory / f"{stem}{suffix}").write_text("header\n", encoding="utf-8")

    found = {name: [path.stem for path in read()] for name, (_, _, read) in readers.items()}

    assert found == {name: ["2025-01", "2025-12"] for name in readers}


def test_a_file_that_is_not_a_month_shard_is_never_a_candidate(tmp_path: Path) -> None:
    """A directory this deletes from names what it recognises, never the rest."""
    directory = tmp_path / "state" / ledger.TELEMETRY_AGGREGATE_DIRNAME
    directory.mkdir(parents=True)
    for stem in ("2025-01", *NOT_MONTHS, *OTHER_STRAYS):
        (directory / f"{stem}.csv").write_text("header\n", encoding="utf-8")

    assert [path.name for path in month_shards(directory)] == ["2025-01.csv"]


def test_an_empty_state_tree_folds_nothing_and_says_so(tmp_path: Path) -> None:
    """A fresh clone has no history, and no history is not an error."""
    result = prune_telemetry(tmp_path / "state", ObservabilityConfig(), TODAY)
    assert result.changed is False
    assert result.rows_folded == 0


def a_published_tree(tmp_path: Path) -> tuple[Path, Path]:
    """A state tree and the browser's copy of every month in it.

    The copy is written by the publisher rather than by this file, so what the
    prune deletes is the file the pipeline really produces.
    """
    state = a_state_tree(tmp_path)
    public = tmp_path / "frontend" / "public" / "telemetry"
    public_telemetry.publish(state_root=state, public_root=public)
    return state, public


def test_the_browser_copy_goes_with_the_month_it_copies(tmp_path: Path) -> None:
    """One boundary, two trees. A copy nobody can check is worse than no copy.

    `public_telemetry_keep_months` must equal `item_health_full_grain_months`,
    so the two sets are the same months and the assertion is that both trees end
    up holding exactly them.
    """
    state, public = a_published_tree(tmp_path)
    config = ObservabilityConfig()
    kept = oldest_month_kept(TODAY, config.item_health_full_grain_months)
    assert len(month_shards(public)) == HISTORY_MONTHS

    result = prune_telemetry(state, config, TODAY, public_root=public)

    assert sorted(result.public_deleted) == sorted(result.folded)
    assert [path.stem for path in month_shards(public)] == [
        stem for stem in months_back(TODAY, HISTORY_MONTHS) if stem >= kept
    ]
    for stem in result.public_deleted:
        assert not public_telemetry.shard_path(public, stem).exists()


def test_a_copy_whose_source_is_already_gone_is_still_taken(tmp_path: Path) -> None:
    """The case the fold loop cannot see, because there is nothing left to fold.

    A run that unlinked the shard and then lost its push - or died between the
    two - leaves a published month with no ledger behind it. It is the one copy
    a reader can still fetch and nobody can check, so the pass that takes it
    walks the published tree rather than the shards being folded.
    """
    state = tmp_path / "state"
    public = tmp_path / "telemetry"
    public.mkdir(parents=True)
    orphan = public_telemetry.shard_path(public, "2024-01")
    orphan.write_text(",".join(public_telemetry.PUBLIC_COLUMNS) + "\n", encoding="utf-8")
    live = public_telemetry.shard_path(public, TODAY.strftime("%Y-%m"))
    live.write_text(",".join(public_telemetry.PUBLIC_COLUMNS) + "\n", encoding="utf-8")

    result = prune_telemetry(state, ObservabilityConfig(), TODAY, public_root=public)

    assert result.folded == (), "there was no shard to fold"
    assert result.public_deleted == ("2024-01",)
    assert result.changed is True, "a deletion is a change even with nothing folded"
    assert not orphan.exists()
    assert live.exists()


def test_a_dry_run_names_the_copy_it_would_take_and_leaves_it(tmp_path: Path) -> None:
    """The list a dry run prints is the list a live run removes, file for file.

    That equality is the deliverable: the workflow ships in dry run so a person
    can read the list before the deletion is switched on, and a list assembled
    from what the deletion happened to reach could not be read that way.
    """
    state, public = a_published_tree(tmp_path)
    before = {path.name: path.read_bytes() for path in month_shards(public)}

    planned = prune_telemetry(state, ObservabilityConfig(), TODAY, public_root=public, dry_run=True)
    done = prune_telemetry(state, ObservabilityConfig(), TODAY, public_root=public)

    assert planned.public_deleted == done.public_deleted
    assert planned.folded == done.folded
    assert {path.name for path in month_shards(public)} == set(before) - {
        f"{stem}.csv" for stem in done.public_deleted
    }
    for name, content in before.items():
        copy = public / name
        if copy.exists():
            assert copy.read_bytes() == content, f"{name} was rewritten rather than left alone"


def test_a_state_tree_with_no_site_beside_it_deletes_no_copy(tmp_path: Path) -> None:
    """`public_root` is None by default on purpose.

    A caller that names its own state tree and forgets the published one must get
    nothing, never the committed tree. Deleting a published shard out of a test
    run is the failure the pairing exists to stop.
    """
    state, public = a_published_tree(tmp_path)
    held = {path.name: path.read_bytes() for path in month_shards(public)}

    result = prune_telemetry(state, ObservabilityConfig(), TODAY)

    assert result.public_deleted == ()
    assert {path.name: path.read_bytes() for path in month_shards(public)} == held


def test_a_fold_that_cannot_be_written_leaves_the_shard_and_its_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing is deleted on the strength of a write nobody checked.

    The aggregate is written, read back and reconciled first. A read-back that
    disagrees raises, and BOTH files that month owns stay - the private record
    and the browser's copy of it. Half a deletion is the state nothing can
    recover from.
    """
    state, public = a_published_tree(tmp_path)
    config = ObservabilityConfig()
    doomed = [
        day
        for day in item_health_days(state)
        if day_partition.month_of(day)
        < oldest_month_kept(TODAY, config.item_health_full_grain_months)
    ]
    assert doomed, "the fixture has to reach past the window or this proves nothing"
    monkeypatch.setattr(ledger, "load_telemetry_aggregate", lambda _path: [])

    with pytest.raises(ValueError, match="did not read back"):
        prune_telemetry(state, config, TODAY, public_root=public)

    assert doomed[0].exists(), "the first day file was unlinked after an unverified write"
    assert public_telemetry.shard_path(public, day_partition.month_of(doomed[0])).exists()
    assert len(month_shards(public)) == HISTORY_MONTHS
