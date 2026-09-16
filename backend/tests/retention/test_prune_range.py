"""Does a named prune take exactly the days it was asked for, and nothing else?

`idhazh telemetry prune` is the manual half of retention: the scheduled pass
deletes what a window has aged out, and this deletes what a person names. The
two properties it has to hold are both about what it did NOT do - the days
outside the range are still there, byte for byte, and a run that fails part way
has removed nothing at all.

Every tree here is BUILT (CLAUDE.md section 13). The committed archive grows, so
a test that read it would cost more every month for the same answer
(Guardrail #12) - and a built tree carries the cases the archive has never
produced: a day either side of a boundary, a store whose month directory is
emptied exactly, and a move that fails on the third file of four.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from datetime import date as date_type
from datetime import timedelta
from pathlib import Path
from typing import Final

import pytest

from idhazh import day_partition, ledger
from idhazh.contracts.item_health import ItemStage
from idhazh.evals import writer as score_writer
from idhazh.telemetry import prune

from ._trees import feed_health_history, health_row

pytestmark = pytest.mark.contract


#: Where one day of each store this prunes lands, asked of the module that owns
#: the store. The test below holds this against `prune.TARGETS`, so a target
#: added to the vocabulary without a store that files by day fails here rather
#: than by quietly selecting nothing.
DAY_PATHS: Final[dict[str, Callable[[Path, str], Path]]] = {
    ledger.COUNTERFACTUAL_SCORES_DIRNAME: ledger.counterfactual_scores_path,
    ledger.HEALTH_DIRNAME: ledger.health_path,
    ledger.ITEM_HEALTH_DIRNAME: ledger.item_health_path,
    ledger.VISUAL_PRUNES_DIRNAME: ledger.visual_prunes_path,
    score_writer.INDEX_DIRNAME: score_writer.index_path,
    score_writer.LEDGER_DIRNAME: score_writer.ledger_path,
}


#: The seven days every range test is drawn on. Wide enough that a boundary off
#: by one has a day on the wrong side rather than an empty result, and it spans a
#: month end so a directory that empties has a parent that does not.
FIRST_DAY: Final = "2026-07-29"
DAYS: Final = tuple(
    (date_type.fromisoformat(FIRST_DAY) + timedelta(days=offset)).isoformat()
    for offset in range(7)
)


def a_census(state_root: Path, days: Iterable[str] = DAYS) -> Path:
    """One item-health day file per day, written through the real appender.

    Real rows rather than invented text: the prune walks a store the pipeline
    writes, and a tree assembled by hand could be a shape no run produces.
    """
    for number, day in enumerate(days):
        ledger.append_item_health(
            state_root,
            day,
            [health_row(day=day, run=1, number=number, stage=ItemStage.PUBLISH)],
        )
    return state_root


def fingerprints(root: Path) -> dict[str, str]:
    """Every file under `root`, by relative path, with the SHA-256 of its bytes.

    A byte hash rather than a size or a modification time, because "the sibling
    survived" and "the sibling is the same file" are different claims and only
    the second one is worth making.
    """
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def dates_on_disk(state_root: Path, target: str) -> list[str]:
    """Which days the store still holds, through the pipeline's own walk."""
    return [
        day_partition.date_of(day)
        for day in day_partition.day_files(state_root / target)
    ]


# --- The range -----------------------------------------------------------------


def test_both_ends_of_the_range_are_named(tmp_path: Path) -> None:
    """`--since` and `--until` are inclusive, and the days either side stay.

    Asserted as a bijection rather than as a count: every day inside the range
    went, and every day outside it is still there. A count would pass a prune
    that removed the right NUMBER of the wrong files.
    """
    state = a_census(tmp_path / "state")
    since, until = DAYS[2], DAYS[4]

    outcome = prune.prune_range(
        state,
        target=ledger.ITEM_HEALTH_DIRNAME,
        since=since,
        until=until,
        dry_run=False,
    )

    assert [
        ledger.item_health_relpath(day) for day in (DAYS[2], DAYS[3], DAYS[4])
    ] == sorted(outcome.removed), (
        "the removed list is not exactly the three days the range names: "
        f"{outcome.removed}"
    )
    assert dates_on_disk(state, ledger.ITEM_HEALTH_DIRNAME) == [
        DAYS[0],
        DAYS[1],
        DAYS[5],
        DAYS[6],
    ], "a day outside the range went, or a day inside it stayed"
    assert outcome.kept == 4


def test_one_day_is_a_range_of_itself(tmp_path: Path) -> None:
    """`--since X --until X` removes exactly X, which is what inclusive means."""
    state = a_census(tmp_path / "state")

    outcome = prune.prune_range(
        state,
        target=ledger.ITEM_HEALTH_DIRNAME,
        since=DAYS[3],
        until=DAYS[3],
        dry_run=False,
    )

    assert outcome.removed == (ledger.item_health_relpath(DAYS[3]),)
    assert DAYS[3] not in dates_on_disk(state, ledger.ITEM_HEALTH_DIRNAME)
    assert len(dates_on_disk(state, ledger.ITEM_HEALTH_DIRNAME)) == len(DAYS) - 1


def test_every_sibling_outside_the_range_is_byte_identical(tmp_path: Path) -> None:
    """The files a prune did not name are the files it did not touch.

    Two stores, so the check also covers the one the prune was never pointed at:
    a walk that reached the wrong directory would move a file nobody named.
    """
    state = a_census(tmp_path / "state")
    feed_health_history(state, ["2026-07", "2026-08"])

    before = fingerprints(state)
    outcome = prune.prune_range(
        state,
        target=ledger.ITEM_HEALTH_DIRNAME,
        since=DAYS[1],
        until=DAYS[2],
        dry_run=False,
    )

    after = fingerprints(state)
    gone = {relpath.removeprefix(f"{ledger.STATE_DIRNAME}/") for relpath in outcome.removed}
    assert set(before) - set(after) == gone, "the files that left are not the files it named"
    for relpath, digest in after.items():
        assert before[relpath] == digest, f"{relpath} survived the prune with different bytes"


def test_a_backwards_range_names_no_day(tmp_path: Path) -> None:
    """An operator who swapped the two ends is told, rather than deleting nothing."""
    state = a_census(tmp_path / "state")

    with pytest.raises(ValueError, match="is after --until"):
        prune.prune_range(
            state,
            target=ledger.ITEM_HEALTH_DIRNAME,
            since=DAYS[4],
            until=DAYS[1],
            dry_run=False,
        )

    assert dates_on_disk(state, ledger.ITEM_HEALTH_DIRNAME) == list(DAYS)


@pytest.mark.parametrize("value", ["2026-8-4", "20260804", "yesterday", "2026-13-01"])
def test_a_day_that_is_not_a_day_is_refused(tmp_path: Path, value: str) -> None:
    """The width is checked as well as the parse.

    `date.fromisoformat` takes `20260804`, and a range compared as text - which
    is how every date comparison in this tree works - would then put that day
    outside every range it belongs in.
    """
    state = a_census(tmp_path / "state")

    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        prune.prune_range(
            state, target=ledger.ITEM_HEALTH_DIRNAME, since=value, until=DAYS[4], dry_run=False
        )

    assert dates_on_disk(state, ledger.ITEM_HEALTH_DIRNAME) == list(DAYS)


def test_the_month_and_year_a_prune_empties_go_with_it(tmp_path: Path) -> None:
    """A store that keeps its emptied directories makes its own walk cost more.

    `DAYS` crosses a month end, so a range that takes July whole leaves August
    standing - which is what says the drop is scoped to what emptied.
    """
    state = a_census(tmp_path / "state")

    prune.prune_range(
        state, target=ledger.ITEM_HEALTH_DIRNAME, since=DAYS[0], until=DAYS[2], dry_run=False
    )

    store = state / ledger.ITEM_HEALTH_DIRNAME
    assert not (store / "2026" / "07").exists(), "an emptied month directory was left behind"
    assert (store / "2026" / "08").is_dir(), "the month that still holds days was removed"


# --- The vocabulary ------------------------------------------------------------


def test_every_target_names_a_store_that_files_by_day(tmp_path: Path) -> None:
    """The vocabulary and the stores are held against each other, both ways.

    A target with no day-filing store would select nothing for every range an
    operator ever names - a command that reports success and removes nothing.
    """
    assert set(prune.TARGETS) == set(DAY_PATHS), (
        "the prune vocabulary and the stores that file by day disagree: "
        f"{sorted(set(prune.TARGETS) ^ set(DAY_PATHS))}"
    )

    for target, day_path in DAY_PATHS.items():
        state = tmp_path / target
        path = day_path(state, DAYS[3])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("version\n", encoding="utf-8", newline="\n")

        outcome = prune.prune_range(
            state, target=target, since=DAYS[3], until=DAYS[3], dry_run=False
        )

        assert outcome.removed == (
            f"{ledger.STATE_DIRNAME}/{path.relative_to(state).as_posix()}",
        ), f"{target} did not select the day file its own module files at"
        assert not path.exists(), f"{target} reported a removal that did not happen"


@pytest.mark.parametrize("target", sorted(prune.REFUSED))
def test_the_two_stores_that_must_not_forget_are_refused(tmp_path: Path, target: str) -> None:
    """`published` and `seen` are refused by name, with the reason attached.

    Refused rather than left out of the vocabulary: a store missing from a list
    reads as an oversight, and somebody who typed one of these is holding a real
    question whose answer is why the answer is no.
    """
    state = a_census(tmp_path / "state")
    before = fingerprints(state)

    with pytest.raises(ValueError) as refusal:
        prune.prune_range(state, target=target, since=DAYS[0], until=DAYS[6], dry_run=False)

    message = str(refusal.value)
    assert target in message and "refused" in message
    assert prune.REFUSED[target] in message, "the refusal did not say why"
    assert fingerprints(state) == before


@pytest.mark.parametrize(
    "target",
    [
        "state/item-health",
        "../item-health",
        "item-health/2026/07/29.csv",
        "/etc/passwd",
        "traces",
        "day-metrics",
        "",
    ],
)
def test_a_target_outside_the_vocabulary_is_refused(tmp_path: Path, target: str) -> None:
    """A path is never a target, and neither is a store this does not name.

    The three path-shaped values are the point: a deletion primitive that
    resolved its argument against the file system is the one accident nobody can
    undo, and fetched text may never become a file path (Guardrail #11). There
    is no argument here a path can travel through, and this is what says so.
    """
    state = a_census(tmp_path / "state")
    before = fingerprints(state)

    with pytest.raises(ValueError) as refusal:
        prune.prune_range(state, target=target, since=DAYS[0], until=DAYS[6], dry_run=False)

    assert "the name of a store" in str(refusal.value)
    assert fingerprints(state) == before


# --- Dry run, and the failure part way -----------------------------------------


def test_a_dry_run_names_every_file_and_removes_none(tmp_path: Path) -> None:
    """The default, and the list a person reads before passing `--no-dry-run`.

    The same list on both sides: what a dry run prints has to be what a live run
    removes, file for file, or reading it settles nothing.
    """
    state = a_census(tmp_path / "state")
    before = fingerprints(state)

    reported = prune.prune_range(
        state, target=ledger.ITEM_HEALTH_DIRNAME, since=DAYS[1], until=DAYS[3]
    )

    assert reported.dry_run is True
    assert fingerprints(state) == before, "a dry run moved a file"

    removed = prune.prune_range(
        state, target=ledger.ITEM_HEALTH_DIRNAME, since=DAYS[1], until=DAYS[3], dry_run=False
    )
    assert removed.removed == reported.removed
    assert removed.bytes_freed == reported.bytes_freed

    lines = prune.report(reported)
    assert all(any(relpath in line for line in lines) for relpath in reported.removed)
    assert "--no-dry-run" in lines[-1]


def test_a_move_that_fails_part_way_leaves_the_tree_as_it_was(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point of the staging directory, driven by a real mid-way failure.

    Four files are selected and the third move raises. A prune that unlinked as
    it went would leave two of the four gone and an archive nobody can reason
    about; this one puts back what it had moved and re-raises, so the tree is
    byte-identical to the one it was handed.
    """
    state = a_census(tmp_path / "state")
    before = fingerprints(state)
    moves = 0

    def fail_on_the_third(day: Path, parked: Path) -> None:
        nonlocal moves
        moves += 1
        if moves == 3:
            raise OSError("the file system said no")
        day.rename(parked)

    monkeypatch.setattr(prune, "_park", fail_on_the_third)

    with pytest.raises(OSError, match="said no"):
        prune.prune_range(
            state,
            target=ledger.ITEM_HEALTH_DIRNAME,
            since=DAYS[1],
            until=DAYS[4],
            dry_run=False,
        )

    assert moves == 3, "the prune kept moving after a failure"
    assert fingerprints(state) == before, "a failed prune left the tree changed"
    assert dates_on_disk(state, ledger.ITEM_HEALTH_DIRNAME) == list(DAYS)
    assert not list(state.glob(".prune-*")), "the staging directory outlived the failure"


def test_the_staging_directory_does_not_outlive_a_prune(tmp_path: Path) -> None:
    """Nothing is left under `state/` for a commit to pick up."""
    state = a_census(tmp_path / "state")

    prune.prune_range(
        state, target=ledger.ITEM_HEALTH_DIRNAME, since=DAYS[0], until=DAYS[1], dry_run=False
    )

    assert [entry.name for entry in state.iterdir()] == [ledger.ITEM_HEALTH_DIRNAME]


def test_a_range_with_no_day_in_it_says_so(tmp_path: Path) -> None:
    """A range that names nothing is not a failure, and the report says which."""
    state = a_census(tmp_path / "state")

    outcome = prune.prune_range(
        state, target=ledger.ITEM_HEALTH_DIRNAME, since="2025-01-01", until="2025-01-31"
    )

    assert outcome.removed == ()
    assert outcome.kept == len(DAYS)
    assert "no day file in that range" in prune.report(outcome)[0]


def test_a_store_that_has_never_been_written_prunes_nothing(tmp_path: Path) -> None:
    """A fresh clone has no history, which is not a fault."""
    outcome = prune.prune_range(
        tmp_path / "state",
        target=ledger.ITEM_HEALTH_DIRNAME,
        since=DAYS[0],
        until=DAYS[6],
        dry_run=False,
    )

    assert outcome.removed == ()
    assert outcome.kept == 0
