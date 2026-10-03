"""What does the telemetry-aggregate task keep of a folded month, and of the browser's copy?

The pass under test is the shipped task, run through its module and the
committed declaration. `pruned` reads what one pass took and wrote back into
the words these tests ask in: which months it folded, which browser copies and
which summaries it deleted.

The census rows themselves are not this task's: they sit under the ledger door,
and the `item-health` compaction's monthly window is what deletes them. So a
pass here reads the census and never touches a file of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

import pytest
from conftest import seed_item_health
from retention._trees import (
    HISTORY_MONTHS,
    NOT_MONTHS,
    TODAY,
    a_state_tree,
    census_of,
    health_row,
    item_health_months,
    months_back,
    totals_from_aggregate,
    totals_from_shard,
)

from idhazh import config, ledger
from idhazh.contracts.item_health import ItemHealthRow, ItemStage
from idhazh.contracts.item_health_summary import percentile
from idhazh.contracts.knobs.gardener import MonthsWindow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.retention import compact_month, month_shards, oldest_month_kept
from idhazh.telemetry.publish import public_telemetry

from ._task import declared, run_task

NAME: Final = "telemetry-aggregate"


def full_grain_months() -> int:
    window = declared()[NAME].window
    assert isinstance(window, MonthsWindow), "the census keeps its rows for a window of months"
    return window.value


@dataclass(frozen=True)
class Folded:
    """What one pass of the task folded, took and wrote."""

    folded: tuple[str, ...]
    public_deleted: tuple[str, ...]
    hard_deleted: tuple[str, ...]
    dry_run: bool
    changed: bool


def pruned(
    state: Path, *, today: date = TODAY, dry_run: bool = False, aggregate_months: int | None = None
) -> Folded:
    """One pass of the shipped task over the checkout `state` sits in."""
    full = {"unit": "months", "value": full_grain_months()}
    aggregate = (
        {"unit": "forever"}
        if aggregate_months is None
        else {"unit": "months", "value": aggregate_months}
    )
    outcome = run_task(
        NAME,
        state.parent,
        today=today,
        dry_run=dry_run,
        window=full,
        series={"full-grain": full, "public-copy": full, "aggregate": aggregate},
    )
    copies = f"{public_telemetry.DEFAULT_PUBLIC_ROOT.relative_to(config.REPO_ROOT).as_posix()}/"
    summaries = f"{ledger.tree_relpath(LedgerName.ITEM_HEALTH_SUMMARY)}/"
    return Folded(
        folded=tuple(Path(path).stem for path in outcome.written),
        public_deleted=tuple(Path(p).stem for p in outcome.taken if p.startswith(copies)),
        hard_deleted=tuple(Path(p).stem for p in outcome.taken if p.startswith(summaries)),
        dry_run=outcome.dry_run,
        changed=outcome.changed,
    )


def summary_stems(state: Path) -> list[str]:
    return sorted(
        path.stem for path in month_shards(ledger.tree_root(state, LedgerName.ITEM_HEALTH_SUMMARY))
    )


def census_files(state: Path) -> dict[str, bytes]:
    """Every file the census holds under the ledger door, by path, with its bytes."""
    root = ledger.raw_root(state, LedgerName.ITEM_HEALTH)
    return {
        path.relative_to(state).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def census_text(state: Path, month: str) -> str:
    """One month of the census as CSV text, read through the ledger door the way the task reads it.

    `totals_from_shard` recomputes its totals from text rather than from
    `compact_month`, so the oracle cannot pass by agreeing with the code it
    checks.
    """
    rows = ledger.load_days(
        state, LedgerName.ITEM_HEALTH, ledger.month_days(month), model=ItemHealthRow
    )
    return ledger.render_file(ItemHealthRow.csv_columns(), [row.csv_row() for row in rows])


def test_the_fold_keeps_the_configured_window_at_full_grain(tmp_path: Path) -> None:
    """Every month past the window is summarised, and no census file is touched.

    A month inside the window keeps its full grain and gets no summary. The
    months past it are summarised and their rows stay where they were: deleting
    them is the compaction's, whose monthly window reaches further back.
    """
    state = a_state_tree(tmp_path)
    before = census_files(state)
    assert item_health_months(state) == months_back(TODAY, HISTORY_MONTHS)

    result = pruned(state)

    kept = oldest_month_kept(TODAY, full_grain_months())
    assert full_grain_months() == 14, "a 366-day console read can open fourteen month shards"
    assert kept == "2025-07", "fourteen months ending in August 2026 starts in July 2025"
    assert list(result.folded) == [
        month for month in months_back(TODAY, HISTORY_MONTHS) if month < kept
    ]
    assert len(result.folded) == HISTORY_MONTHS - full_grain_months()
    assert summary_stems(state) == list(result.folded), "a month inside the window was summarised"
    assert census_files(state) == before, "the pass deleted or rewrote a census file"
    assert item_health_months(state) == months_back(TODAY, HISTORY_MONTHS)


def test_the_fold_loses_no_total(tmp_path: Path) -> None:
    """The grain changes; the answer does not."""
    state = a_state_tree(tmp_path)
    kept = oldest_month_kept(TODAY, full_grain_months())
    doomed = {
        month: census_text(state, month) for month in item_health_months(state) if month < kept
    }
    assert doomed, "the fixture has to reach past the window or this proves nothing"

    pruned(state)

    for month, text in doomed.items():
        target = ledger.path(state, LedgerName.ITEM_HEALTH_SUMMARY, month)
        assert totals_from_aggregate(ledger.load_item_health_summary(target)) == (
            totals_from_shard([text])
        ), f"{month} lost a total in the fold"


def test_the_fold_keeps_a_repeated_row_rather_than_deciding_for_a_reader(tmp_path: Path) -> None:
    """The committed ledger carries repeated keys, and the fold reproduces them."""
    day = "2024-01-04"
    state = tmp_path / "state"
    rows = [health_row(day=day, run=run, number=7, stage=ItemStage.PUBLISH) for run in (1, 2)]
    seed_item_health(state, day, rows)

    folded = compact_month(census_of(state, day))

    assert [row.items for row in folded] == [2]
    assert folded[0].timed == 2
    slowest = folded[0].max_ms
    assert slowest is not None
    assert folded[0].sum_ms == 2 * slowest, "both copies of one item, added"


def test_a_group_that_timed_nothing_says_so_rather_than_saying_zero(tmp_path: Path) -> None:
    """An instrument that did not run writes an empty cell. Empty is not zero."""
    day = "2024-01-04"
    state = tmp_path / "state"
    seed_item_health(state, day, [health_row(day=day, run=1, number=1, stage=ItemStage.PLAN)])

    folded = compact_month(census_of(state, day))

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


def test_a_percentile_is_a_number_some_item_really_took() -> None:
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
        for path in sorted(state.rglob("*"))
        if path.is_file()
    }

    result = pruned(state, dry_run=True)

    after = {
        path.relative_to(state).as_posix(): path.read_bytes()
        for path in sorted(state.rglob("*"))
        if path.is_file()
    }
    assert result.dry_run is True
    assert result.folded, "it still has to report what it would have done"
    assert after == before
    assert not (ledger.tree_root(state, LedgerName.ITEM_HEALTH_SUMMARY)).exists()


def test_the_aggregate_is_kept_forever_unless_somebody_asks_for_the_bytes_back(
    tmp_path: Path,
) -> None:
    """Running the fold again must never remove a summary while the aggregate series is forever."""
    state = a_state_tree(tmp_path)

    first = pruned(state)
    written = summary_stems(state)
    again = pruned(state)

    assert written, "the first pass has to summarise a month or the rest proves nothing"
    assert written == sorted(first.folded)
    assert again.folded == (), "a month already summarised is not folded again"
    assert again.hard_deleted == ()
    assert summary_stems(state) == written


def test_a_hard_delete_takes_the_aggregate_only_after_the_fold_has_had_it(tmp_path: Path) -> None:
    """The escape hatch, for the day the owner wants the bytes back."""
    state = a_state_tree(tmp_path)
    pruned(state)
    before = summary_stems(state)

    result = pruned(state, aggregate_months=16)

    boundary = oldest_month_kept(TODAY, 16)
    assert sorted(result.hard_deleted) == [stem for stem in before if stem < boundary]
    assert result.hard_deleted, "a threshold inside the fixture has to remove something"
    assert summary_stems(state) == [stem for stem in before if stem >= boundary]


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


def test_the_task_summarises_the_expired_month_and_not_the_month_beside_it(
    tmp_path: Path,
) -> None:
    """Two-sided on purpose: one day past the window, one day inside it.

    The month past the window is summarised and the summary is read back; the
    month inside keeps its full grain and gets none. Neither loses a census row,
    because the rows are the compaction's to delete.
    """
    state = tmp_path / "state"
    keep_from = oldest_month_kept(TODAY, full_grain_months())
    expired_day = f"{months_back(TODAY, full_grain_months() + 1)[0]}-09"
    kept_day = f"{keep_from}-09"
    assert expired_day[:7] < keep_from <= kept_day[:7], "the fixture must straddle the boundary"
    for day in (expired_day, kept_day):
        seed_item_health(state, day, [health_row(day=day, run=1, number=1, stage=ItemStage.PUBLISH)])
    expired_text = census_text(state, expired_day[:7])
    before = census_files(state)

    result = pruned(state)

    assert list(result.folded) == [expired_day[:7]]
    assert summary_stems(state) == [expired_day[:7]], "the month inside the window was summarised"
    assert census_files(state) == before, "the pass deleted or rewrote a census file"
    assert item_health_months(state) == [expired_day[:7], kept_day[:7]]
    target = ledger.path(state, LedgerName.ITEM_HEALTH_SUMMARY, expired_day[:7])
    assert totals_from_aggregate(ledger.load_item_health_summary(target)) == (
        totals_from_shard([expired_text])
    )


def test_a_file_that_is_not_a_month_shard_is_never_a_candidate(tmp_path: Path) -> None:
    directory = ledger.tree_root(tmp_path / "state", LedgerName.ITEM_HEALTH_SUMMARY)
    directory.mkdir(parents=True)
    for stem in ("2025-01", *NOT_MONTHS, *OTHER_STRAYS):
        (directory / f"{stem}.csv").write_text("header\n", encoding="utf-8")

    assert [path.name for path in month_shards(directory)] == ["2025-01.csv"]


def test_an_empty_state_tree_folds_nothing_and_says_so(tmp_path: Path) -> None:
    result = pruned(tmp_path / "state")
    assert (result.changed, result.folded) == (False, ())


def a_published_tree(tmp_path: Path) -> tuple[Path, Path]:
    """A state tree and the browser's copy of every month in it, written by the publisher."""
    state = a_state_tree(tmp_path)
    public = tmp_path / "frontend" / "public" / "telemetry"
    public_telemetry.publish(
        state_root=state,
        public_root=public,
        months=set(item_health_months(state)),
    )
    return state, public


def test_the_browser_copy_goes_with_the_month_it_copies(tmp_path: Path) -> None:
    """One boundary, two trees. A copy nobody can check is worse than no copy."""
    state, public = a_published_tree(tmp_path)
    kept = oldest_month_kept(TODAY, full_grain_months())
    assert len(month_shards(public)) == HISTORY_MONTHS

    result = pruned(state)

    assert sorted(result.public_deleted) == sorted(result.folded)
    assert [path.stem for path in month_shards(public)] == [
        stem for stem in months_back(TODAY, HISTORY_MONTHS) if stem >= kept
    ]
    for stem in result.public_deleted:
        assert not public_telemetry.shard_path(public, stem).exists()


def test_a_copy_whose_source_is_already_gone_is_still_taken(tmp_path: Path) -> None:
    """A published month with no ledger behind it is the one copy nobody can check."""
    state = tmp_path / "state"
    public = tmp_path / "frontend" / "public" / "telemetry"
    public.mkdir(parents=True)
    orphan = public_telemetry.shard_path(public, "2024-01")
    orphan.write_text(",".join(public_telemetry.PUBLIC_COLUMNS) + "\n", encoding="utf-8")
    live = public_telemetry.shard_path(public, TODAY.strftime("%Y-%m"))
    live.write_text(",".join(public_telemetry.PUBLIC_COLUMNS) + "\n", encoding="utf-8")

    result = pruned(state)

    assert result.folded == (), "there was no shard to fold"
    assert result.public_deleted == ("2024-01",)
    assert result.changed is True, "a deletion is a change even with nothing folded"
    assert not orphan.exists()
    assert live.exists()


def test_a_dry_run_names_the_copy_it_would_take_and_leaves_it(tmp_path: Path) -> None:
    """The list a dry run prints is the list a live run removes, file for file."""
    state, public = a_published_tree(tmp_path)
    before = {path.name: path.read_bytes() for path in month_shards(public)}

    planned = pruned(state, dry_run=True)
    done = pruned(state)

    assert planned.public_deleted == done.public_deleted
    assert planned.folded == done.folded
    assert {path.name for path in month_shards(public)} == set(before) - {
        f"{stem}.csv" for stem in done.public_deleted
    }
    for name, content in before.items():
        copy = public / name
        if copy.exists():
            assert copy.read_bytes() == content, f"{name} was rewritten rather than left alone"


def test_a_checkout_with_no_published_copies_takes_no_copy(tmp_path: Path) -> None:
    """The runner hands the task only the folders the checkout holds, and this one has no site."""
    state = a_state_tree(tmp_path)

    result = pruned(state)

    assert result.folded
    assert result.public_deleted == ()


def test_a_checkout_that_holds_no_summary_yet_still_writes_its_first(tmp_path: Path) -> None:
    """The first summary is what makes the summary folder, so the fold cannot wait for it.

    The runner hands a task only the folders the commit holds, and a checkout
    that has never summarised a month holds no `state/item-health-summary/`. A
    fold that waited for that folder would never write its first summary, and
    the compaction would later delete the month's rows with nothing kept of them.
    """
    state = a_state_tree(tmp_path)
    assert not ledger.tree_root(state, LedgerName.ITEM_HEALTH_SUMMARY).exists()

    result = pruned(state)

    assert result.folded, "no month was summarised"
    assert summary_stems(state) == sorted(result.folded)


def test_a_fold_that_cannot_be_read_back_leaves_the_browser_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing is deleted on the strength of a write nobody checked, not even a copy.

    Every summary is written and read back before the pass lists a single file
    to delete, so a summary that does not read back stops the pass before its
    first deletion - which the runner records as a pass that reached no member.
    """
    state, public = a_published_tree(tmp_path)
    doomed = [
        month
        for month in item_health_months(state)
        if month < oldest_month_kept(TODAY, full_grain_months())
    ]
    assert doomed, "the fixture has to reach past the window or this proves nothing"
    monkeypatch.setattr(ledger, "load_item_health_summary", lambda _path: [])

    with pytest.raises(ValueError, match="did not read back"):
        pruned(state)

    assert public_telemetry.shard_path(public, doomed[0]).exists()
    assert len(month_shards(public)) == HISTORY_MONTHS


def test_a_census_the_declaration_does_not_read_is_refused_and_never_read_as_empty(
    tmp_path: Path,
) -> None:
    """The census sits in folders another task owns, so the task names them under `reads`.

    Without them its listing does not cover the census, and asking about it is
    refused. A task that saw no month due would report success over a census it
    never saw, and the compaction would later delete rows with nothing kept.
    """
    state = a_state_tree(tmp_path)
    assert declared()[NAME].reads, "the shipped task reads the census, or this proves nothing"

    with pytest.raises(ValueError, match="owns or reads"):
        run_task(NAME, state.parent, reads=[])
