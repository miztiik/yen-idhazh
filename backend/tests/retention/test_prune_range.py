"""Does a named prune take exactly the days it was asked for, and nothing else?

`idhazh telemetry prune` is the manual half of retention: the scheduled pass
deletes what a window has aged out, and this deletes what a person names. The
two properties it has to hold are both about what it did NOT do - the days
outside the range are still there, byte for byte, and a pass that fails part way
has removed only the days it had already reached.

That second property changed on 2026-09-17. Until then the prune moved a whole
range into a scratch directory and rolled every move back if one failed, so a
failed pass removed nothing at all. It deletes one day file at a time now
through `idhazh.gardener.one_at_a_time`, so a failed pass keeps what it had
deleted and the record says where the next pass resumes.

Every tree here is BUILT (CLAUDE.md section 13). The committed archive grows, so
a test that read it would cost more every month for the same answer
(Guardrail #12) - and a built tree carries the cases the archive has never
produced: a day either side of a boundary, a ledger whose month directory is
emptied exactly, and a delete that fails on the third file of four.

A ledger on the ledger door is a target too, of its own kind. Its days sit in
raw files and in daily, monthly and yearly files that hold other days as well,
so its property is about rows rather than files: no row of a day the range
names is left, every other day reads back the same rows, and every index still
loads. Those trees are built through the door and the shipped
compaction (`ledger/_every_tier.py`), and whether a ledger on the door is a
target at all is its compaction declaration's `prune_refusal`.
"""

from __future__ import annotations

import functools
import hashlib
import shutil
from collections.abc import Callable, Iterable, Mapping
from datetime import date as date_type
from datetime import timedelta
from pathlib import Path
from typing import Final

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text, seed_item_health
from gardener.tasks._marks import marks_on_disk
from ledger._every_tier import (
    CENSUS,
    FILED_DAYS,
    RAW_DAYS,
    a_census_in_every_tier,
)

from idhazh import atomic_write, config, day_partition, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.fitted_similarity_threshold import FittedSimilarityThreshold
from idhazh.contracts.item_health import ItemHealthRow, ItemStage
from idhazh.contracts.knobs.gardener import CompactionPolicy, TaskPolicy
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain
from idhazh.telemetry import door_prune, prune

from ._trees import health_row

pytestmark = pytest.mark.contract


@functools.cache
def committed_tasks() -> Mapping[str, TaskPolicy]:
    """Every committed gardener declaration, loaded and checked as `idhazh telemetry prune` loads them."""
    return config.load_gardener().tasks


def prune_range(
    state_root: Path,
    *,
    target: str,
    since: str,
    until: str,
    dry_run: bool = True,
    max_deletes: int | None = None,
    run_id: str | None = None,
    commit: str | None = None,
    tasks: Mapping[str, TaskPolicy] | None = None,
) -> prune.Outcome:
    """The verb's body, handed the declarations the command line loads unless a test names its own."""
    return prune.prune_range(
        state_root,
        target=target,
        since=since,
        until=until,
        tasks=committed_tasks() if tasks is None else tasks,
        dry_run=dry_run,
        max_deletes=max_deletes,
        run_id=run_id,
        commit=commit,
    )


#: Where one day of each ledger this prunes lands. The test below holds this
#: against `prune.TARGETS`, so a target added to the vocabulary without a ledger
#: that files by day fails here rather than by quietly selecting nothing.
#:
#: Keyed the way an operator types it - the registry prefix joined by hyphens -
#: and valued with the typed name the builder takes. That pairing is the whole of
#: what makes a nested ledger prunable, so it is the pairing this file holds.
DAY_PATHS: Final[dict[str, LedgerName]] = {
    "-".join(ledger.entry(name).prefix): name
    for name in (
        LedgerName.CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS,
        LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS,
        LedgerName.CONTENT_SIMILARITY_JUDGE_MERGE_LINE_HOLDOUT_SCORES,
        LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS,
    )
}


#: The seven days every range test is drawn on. Wide enough that a boundary off
#: by one has a day on the wrong side rather than an empty result, and it spans a
#: month end so a directory that empties has a parent that does not.
FIRST_DAY: Final = "2026-07-29"
DAYS: Final = tuple(
    (date_type.fromisoformat(FIRST_DAY) + timedelta(days=offset)).isoformat()
    for offset in range(7)
)


#: The ledger every range test below prunes: one `<DD>.csv` a day, filed by the
#: judge's own writer, and the name an operator types for it.
THRESHOLDS: Final = LedgerName.CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS
TARGET: Final = "-".join(ledger.entry(THRESHOLDS).prefix)


def a_threshold_record(state_root: Path, days: Iterable[str] = DAYS) -> Path:
    """One fitted-threshold day per day, written through the judge's own writer.

    Real rows rather than invented text: the prune walks a ledger the pipeline
    writes, and a tree assembled by hand could be a shape no run produces.
    """
    fixture = CONTRACT_FIXTURES_DIR / "fitted-similarity-threshold"
    base = FittedSimilarityThreshold.from_json(
        read_text(fixture / "the-record-is-too-small-to-fit-on.json")
    )
    for day in days:
        row = FittedSimilarityThreshold.model_validate(
            {**base.model_dump(), "date": day, "run_id": f"{day}-1"}
        )
        ledger.append_fitted_thresholds(state_root, day, [row])
    return state_root


def the_day_file(day: str) -> str:
    """The one file `a_threshold_record` leaves for a day, POSIX and relative."""
    return ledger.relpath(THRESHOLDS, day)


def a_census(state_root: Path, days: Iterable[str] = DAYS) -> Path:
    """One item-health day per day, filed through the ledger door.

    A ledger beside the one a test prunes: its days are raw files under
    `state/raw/`, which no CSV target walks, so a prune of another ledger that
    reached them would be deleting rows nobody named.
    """
    for number, day in enumerate(days):
        seed_item_health(
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


def a_day_on_disk(name: LedgerName, state_root: Path, day: str) -> Path:
    """Put one file where the registry says the day goes, and name it."""
    where = ledger.path(state_root, name, day)
    where.parent.mkdir(parents=True, exist_ok=True)
    where.write_text("version\n", encoding="utf-8", newline="\n")
    return where


def dates_on_disk(state_root: Path) -> list[str]:
    """Which days the pruned ledger still holds, through the prune's own walk."""
    return [
        day_partition.date_of(path)
        for path in day_partition.day_files(ledger.tree_root(state_root, THRESHOLDS))
    ]


# --- The range -----------------------------------------------------------------


def test_both_ends_of_the_range_are_named(tmp_path: Path) -> None:
    """`--since` and `--until` are inclusive, and the days either side stay.

    Asserted as a bijection rather than as a count: every day inside the range
    went, and every day outside it is still there. A count would pass a prune
    that removed the right NUMBER of the wrong files.
    """
    state = a_threshold_record(tmp_path / "state")
    since, until = DAYS[2], DAYS[4]

    outcome = prune_range(
        state,
        target=TARGET,
        since=since,
        until=until,
        dry_run=False,
    )

    assert [
        the_day_file(day) for day in (DAYS[2], DAYS[3], DAYS[4])
    ] == sorted(outcome.removed), (
        "the removed list is not exactly the three days the range names: "
        f"{outcome.removed}"
    )
    assert dates_on_disk(state) == [
        DAYS[0],
        DAYS[1],
        DAYS[5],
        DAYS[6],
    ], "a day outside the range went, or a day inside it stayed"
    assert outcome.kept == 4


def test_one_day_is_a_range_of_itself(tmp_path: Path) -> None:
    """`--since X --until X` removes exactly X, which is what inclusive means."""
    state = a_threshold_record(tmp_path / "state")

    outcome = prune_range(
        state,
        target=TARGET,
        since=DAYS[3],
        until=DAYS[3],
        dry_run=False,
    )

    assert outcome.removed == (the_day_file(DAYS[3]),)
    assert DAYS[3] not in dates_on_disk(state)
    assert len(dates_on_disk(state)) == len(DAYS) - 1


def test_every_sibling_outside_the_range_is_byte_identical(tmp_path: Path) -> None:
    """The files a prune did not name are the files it did not touch.

    Two ledgers, so the check also covers the one the prune was never pointed at:
    a walk that reached the wrong directory would move a file nobody named. The
    census beside it holds the same days, so a walk keyed on the day alone would
    reach it too.
    """
    state = a_threshold_record(tmp_path / "state")
    a_census(state)

    before = fingerprints(state)
    outcome = prune_range(
        state,
        target=TARGET,
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
    state = a_threshold_record(tmp_path / "state")

    with pytest.raises(ValueError, match="is after --until"):
        prune_range(
            state,
            target=TARGET,
            since=DAYS[4],
            until=DAYS[1],
            dry_run=False,
        )

    assert dates_on_disk(state) == list(DAYS)


@pytest.mark.parametrize("value", ["2026-8-4", "20260804", "yesterday", "2026-13-01"])
def test_a_day_that_is_not_a_day_is_refused(tmp_path: Path, value: str) -> None:
    """The width is checked as well as the parse.

    `date.fromisoformat` takes `20260804`, and a range compared as text - which
    is how every date comparison in this tree works - would then put that day
    outside every range it belongs in.
    """
    state = a_threshold_record(tmp_path / "state")

    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        prune_range(state, target=TARGET, since=value, until=DAYS[4], dry_run=False)

    assert dates_on_disk(state) == list(DAYS)


def test_the_month_and_year_a_prune_empties_go_with_it(tmp_path: Path) -> None:
    """A ledger that keeps its emptied directories makes its own walk cost more.

    `DAYS` crosses a month end, so a range that takes July whole leaves August
    standing - which is what says the drop is scoped to what emptied.
    """
    state = a_threshold_record(tmp_path / "state")

    prune_range(state, target=TARGET, since=DAYS[0], until=DAYS[2], dry_run=False)

    ledger_root = ledger.tree_root(state, THRESHOLDS)
    assert not (ledger_root / "2026" / "07").exists(), "an emptied month directory was left behind"
    assert (ledger_root / "2026" / "08").is_dir(), "the month that still holds days was removed"


# --- The vocabulary ------------------------------------------------------------


def test_every_target_names_a_store_that_files_by_day(tmp_path: Path) -> None:
    """The vocabulary and the ledgers are held against each other, both ways.

    A target with no day-filing ledger would select nothing for every range an
    operator ever names - a command that reports success and removes nothing.
    """
    assert set(prune.TARGETS) == set(DAY_PATHS), (
        "the prune vocabulary and the ledgers that file by day disagree: "
        f"{sorted(set(prune.TARGETS) ^ set(DAY_PATHS))}"
    )

    for target, name in DAY_PATHS.items():
        state = tmp_path / target
        path = a_day_on_disk(name, state, DAYS[3])

        outcome = prune_range(
            state, target=target, since=DAYS[3], until=DAYS[3], dry_run=False
        )

        assert outcome.removed == (
            f"{ledger.STATE_DIRNAME}/{path.relative_to(state).as_posix()}",
        ), f"{target} did not select the day file its own module files at"
        assert not path.exists(), f"{target} reported a removal that did not happen"


#: The ledgers whose rows must never be forgotten, so a range of them is refused
#: by name: they stop a repeat publication or discovery.
MUST_NOT_FORGET: Final = (
    LedgerName.PUBLISHED,
    LedgerName.SEEN,
)


@pytest.mark.parametrize("target", MUST_NOT_FORGET)
def test_the_ledgers_that_must_not_forget_are_refused(tmp_path: Path, target: str) -> None:
    """`published` and `seen` are refused by name, with the reason.

    Refused rather than left out of the vocabulary: a ledger missing from a list
    reads as an oversight, and somebody who typed one of these is holding a real
    question whose answer is why the answer is no. Both are on the ledger door,
    so each one's compaction declaration gives its reason in `prune_refusal`.
    """
    reasons = prune.door_refusals(committed_tasks())
    state = a_threshold_record(tmp_path / "state")
    before = fingerprints(state)

    with pytest.raises(ValueError) as refusal:
        prune_range(state, target=target, since=DAYS[0], until=DAYS[6], dry_run=False)

    message = str(refusal.value)
    assert target in message and "refused" in message
    assert reasons[target] in message, "the refusal did not say why"
    assert fingerprints(state) == before


@pytest.mark.parametrize(
    "target",
    [
        "state/content-similarity-judge/fitted-thresholds",
        "../content-similarity-judge-fitted-thresholds",
        "content-similarity-judge-fitted-thresholds/2026/07/29",
        "/etc/passwd",
        "traces",
        "day-metrics",
        "",
    ],
)
def test_a_target_outside_the_vocabulary_is_refused(tmp_path: Path, target: str) -> None:
    """A path is never a target, and neither is a ledger this does not name.

    The three path-shaped values are the point: a deletion primitive that
    resolved its argument against the file system is the one accident nobody can
    undo, and fetched text may never become a file path (Guardrail #11). There
    is no argument here a path can travel through, and this is what says so.
    Each names a ledger the vocabulary does take, so a refusal here is a refusal
    of the path and never of the ledger.
    """
    state = a_threshold_record(tmp_path / "state")
    before = fingerprints(state)

    with pytest.raises(ValueError) as refusal:
        prune_range(state, target=target, since=DAYS[0], until=DAYS[6], dry_run=False)

    assert "the name of a ledger" in str(refusal.value)
    assert fingerprints(state) == before


# --- Dry run, and the failure part way -----------------------------------------


def test_a_dry_run_names_every_file_and_removes_none(tmp_path: Path) -> None:
    """The default, and the list a person reads before passing `--no-dry-run`.

    The same list on both sides: what a dry run prints has to be what a live run
    removes, file for file, or reading it settles nothing.
    """
    state = a_threshold_record(tmp_path / "state")
    before = fingerprints(state)

    reported = prune_range(state, target=TARGET, since=DAYS[1], until=DAYS[3])

    assert reported.dry_run is True
    assert fingerprints(state) == before, "a dry run moved a file"

    removed = prune_range(state, target=TARGET, since=DAYS[1], until=DAYS[3], dry_run=False)
    assert removed.removed == reported.removed
    assert removed.bytes_freed == reported.bytes_freed

    lines = prune.report(reported)
    assert all(any(relpath in line for line in lines) for relpath in reported.removed)
    assert "--no-dry-run" in lines[-1]


def test_a_delete_that_fails_part_way_keeps_what_it_already_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Four files are selected and the third delete raises: two are gone, two remain.

    This is what atomic means here, and it is not what this test asserted before
    2026-09-17. Until then the prune moved a whole range into a scratch
    directory and put every file back if one move failed, so the property was
    "the tree is exactly as you found it". The owner replaced that shape with
    short atomic deletes, so the property moved with it: one `unlink` is the
    unit, it either happened or it did not, and an interruption after the second
    file leaves two files gone and no rollback to get wrong.

    The record is what makes the difference workable. An operator whose pass
    stopped reads which files went and which one to retry, where a rollback only
    ever told them to start again.
    """
    state = a_threshold_record(tmp_path / "state")
    deletes = 0
    real_delete = prune._delete

    def fail_on_the_third(day: Path) -> None:
        nonlocal deletes
        deletes += 1
        if deletes == 3:
            raise OSError("the file system said no")
        real_delete(day)

    monkeypatch.setattr(prune, "_delete", fail_on_the_third)

    with pytest.raises(prune.PruneInterruptedError) as stop:
        prune_range(
            state,
            target=TARGET,
            since=DAYS[1],
            until=DAYS[4],
            dry_run=False,
        )

    assert deletes == 3, "the prune kept deleting after a failure"
    assert stop.value.so_far.taken == (
        the_day_file(DAYS[1]),
        the_day_file(DAYS[2]),
    )
    assert stop.value.so_far.resume_from == the_day_file(DAYS[3]), (
        "the next pass has to retry the day that failed"
    )
    assert dates_on_disk(state) == [
        DAYS[0],
        DAYS[3],
        DAYS[4],
        DAYS[5],
        DAYS[6],
    ], "a day after the failure went, or a day before it came back"


def test_a_ceiling_stops_a_pass_and_names_the_day_to_resume_at(tmp_path: Path) -> None:
    """A range wider than the bite an operator wants is taken in bites.

    The point of the ceiling on a ledger's day files is the same as on a
    collection of 612 artifacts: one command, a bounded cost, and a record that
    says whether there is more.
    """
    state = a_threshold_record(tmp_path / "state")

    outcome = prune_range(
        state,
        target=TARGET,
        since=DAYS[0],
        until=DAYS[4],
        dry_run=False,
        max_deletes=2,
    )

    assert outcome.removed == (
        the_day_file(DAYS[0]),
        the_day_file(DAYS[1]),
    )
    assert outcome.more_to_do
    assert outcome.resume_from == the_day_file(DAYS[2])
    assert dates_on_disk(state) == list(DAYS[2:])
    assert any("run it again" in line for line in prune.report(outcome))


def test_the_range_an_operator_typed_is_its_own_ceiling(tmp_path: Path) -> None:
    """With no `--max-deletes`, a range of n days deletes at most n files.

    A real bound rather than a number somebody picked: the arithmetic is the
    operator's own, so the default cannot silently take less than was asked for.
    """
    state = a_threshold_record(tmp_path / "state")

    outcome = prune_range(state, target=TARGET, since=DAYS[0], until=DAYS[6], dry_run=False)

    assert len(outcome.removed) == len(DAYS)
    assert outcome.resume_from is None, "the range was taken whole, so nothing is left"
    assert dates_on_disk(state) == []


def test_nothing_is_left_under_state_for_a_commit_to_pick_up(tmp_path: Path) -> None:
    """No scratch directory, because there is no longer a phase that needs one."""
    state = a_threshold_record(tmp_path / "state")

    prune_range(state, target=TARGET, since=DAYS[0], until=DAYS[1], dry_run=False)

    assert [entry.name for entry in state.iterdir()] == [ledger.entry(THRESHOLDS).prefix[0]]
    assert not list(state.glob(".prune-*")), "a scratch directory appeared from somewhere"


def test_a_range_with_no_day_in_it_says_so(tmp_path: Path) -> None:
    """A range that names nothing is not a failure, and the report says which."""
    state = a_threshold_record(tmp_path / "state")

    outcome = prune_range(state, target=TARGET, since="2025-01-01", until="2025-01-31")

    assert outcome.removed == ()
    assert outcome.kept == len(DAYS)
    assert "no day file in that range" in prune.report(outcome)[0]


def test_a_store_that_has_never_been_written_prunes_nothing(tmp_path: Path) -> None:
    """A fresh clone has no history, which is not a fault."""
    outcome = prune_range(
        tmp_path / "state",
        target=TARGET,
        since=DAYS[0],
        until=DAYS[6],
        dry_run=False,
    )

    assert outcome.removed == ()
    assert outcome.kept == 0


# --- A ledger on the ledger door ---------------------------------------------------

#: The writer every file a live pass on the door rebuilds names, as an operator types it.
PRUNE_RUN: Final = "2026-03-21-1"
PRUNE_COMMIT: Final = "c" * 40
PRUNE_WRITER: Final = WriterIdentity(
    run_id=PRUNE_RUN,
    attempt=1,
    job=ServerJob.MIGRATE,
    shard=0,
    producer="telemetry.prune",
    git_sha=PRUNE_COMMIT,
)

#: A range that reaches every kind of file the built census sits in: the end of
#: 2025's December in its year file, the whole of January's month file, both
#: filed daily files and the first raw day. The census's first and last filed
#: days stay, in the year file and in a raw file.
SINCE: Final = "2025-12-20"
UNTIL: Final = RAW_DAYS[0]


def the_range() -> list[str]:
    """Every UTC day from `SINCE` to `UNTIL`, both named."""
    first, last = date_type.fromisoformat(SINCE), date_type.fromisoformat(UNTIL)
    return [(first + timedelta(days=step)).isoformat() for step in range((last - first).days + 1)]


@pytest.fixture(scope="module")
def every_tier(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One census in every kind of file, built once for this module and copied by each test."""
    root = tmp_path_factory.mktemp("every-tier")
    a_census_in_every_tier(root)
    return root


def a_copy(every_tier: Path, under: Path) -> Path:
    """The built census copied to a tree of its own, and that tree's state root."""
    shutil.copytree(every_tier, under)
    return under / ledger.STATE_DIRNAME


def census_by_day(state: Path) -> dict[str, list[ItemHealthRow]]:
    """Every census row the ledger serves, by the day it was filed under, read as readers read it."""
    served: dict[str, list[ItemHealthRow]] = {}
    for row in ledger.load_days(
        state, CENSUS, ledger.held_days(state, CENSUS), model=ItemHealthRow
    ):
        served.setdefault(row.date, []).append(row)
    return served


def indexes(state: Path) -> dict[Period, list[CompactEntry]]:
    """Every compact index of the census, each read whole, so one that cannot load fails here."""
    return {
        period: CompactIndex.read(ledger.compact_index_path(state, CENSUS, period)).entries
        for period in Period
    }


def compaction_of(tasks: Mapping[str, TaskPolicy], which: LedgerName) -> CompactionPolicy:
    """The one compaction declaration of a ledger."""
    (found,) = [
        policy
        for policy in tasks.values()
        if isinstance(policy, CompactionPolicy) and policy.ledger is which
    ]
    return found


def with_refusal(
    tasks: Mapping[str, TaskPolicy], which: LedgerName, sentence: str | None
) -> dict[str, TaskPolicy]:
    """These declarations with one ledger's `prune_refusal` changed, and nothing else."""
    return {
        name: (
            policy.model_copy(update={"prune_refusal": sentence})
            if isinstance(policy, CompactionPolicy) and policy.ledger is which
            else policy
        )
        for name, policy in tasks.items()
    }


def test_a_range_taken_out_of_a_ledger_on_the_door_takes_its_rows_and_no_other(
    every_tier: Path, tmp_path: Path
) -> None:
    """The oracle: no row of a day the range names is left, and every other day reads the same.

    The range reaches into a year file, a month file, two daily files and a raw
    day, so each kind of file is rebuilt or deleted, and the year file and the raw
    days each keep a day outside it. Every index still loads, no day reads as a
    hole, and no mark the indexes give moves, because nothing was compacted.
    """
    state = a_copy(every_tier, tmp_path / "checkout")
    before = census_by_day(state)
    marks = marks_on_disk(state, CENSUS)
    assert set(before) == set(FILED_DAYS), "the built census is not the one this test reads"

    outcome = prune_range(
        state,
        target=CENSUS,
        since=SINCE,
        until=UNTIL,
        dry_run=False,
        run_id=PRUNE_RUN,
        commit=PRUNE_COMMIT,
    )

    assert census_by_day(state) == {
        day: rows for day, rows in before.items() if not SINCE <= day <= UNTIL
    }
    assert set(indexes(state)) == set(Period)
    assert marks_on_disk(state, CENSUS) == marks, "a prune moved a mark"
    assert ledger.list_ledger_files(state, CENSUS).holes == ()
    assert ledger.list_raw_files(state, CENSUS, days=[RAW_DAYS[0]]) == []
    assert outcome.removed and outcome.rewritten and outcome.bytes_freed > 0


def test_a_ledger_on_the_door_with_only_raw_files_gives_up_whole_days(tmp_path: Path) -> None:
    """Until its compaction runs live, a ledger's days on the door are raw files, taken whole.

    The days are the members, so `kept` counts the days outside the range and
    nothing is rewritten, because no compact file holds a row yet.
    """
    state = a_census(tmp_path / "state")
    before = {
        day: ledger.load_days(state, CENSUS, [day], model=ItemHealthRow) for day in DAYS
    }

    outcome = prune_range(
        state,
        target=CENSUS,
        since=DAYS[2],
        until=DAYS[4],
        dry_run=False,
        run_id=PRUNE_RUN,
        commit=PRUNE_COMMIT,
    )

    for day in DAYS:
        expected = [] if DAYS[2] <= day <= DAYS[4] else before[day]
        assert ledger.load_days(state, CENSUS, [day], model=ItemHealthRow) == expected, day
    assert (len(outcome.removed), outcome.rewritten, outcome.kept) == (3, (), 4)
    assert ledger.list_raw_files(state, CENSUS, days=DAYS[2:5]) == []


def test_a_ledger_on_the_door_is_a_target_unless_its_declaration_gives_a_reason() -> None:
    """Which ledgers on the door this takes days from is worked out, never listed.

    The registry says which ledgers are on the door, and each one's compaction
    declaration says in `prune_refusal` whether their days may go: null makes it
    a target, and a sentence refuses it with that sentence. So the answer moves
    when the config does, with no list here to keep in step. A ledger on the
    door that no compaction declares is refused, because nothing then says its
    days may go. On main the census is a target.
    """
    tasks = committed_tasks()
    assert set(prune.DOOR_LEDGERS.values()) == {
        name for name in LedgerName if ledger.entry(name).grain is Grain.RAW_AND_COMPACT
    }
    for word, name in prune.DOOR_LEDGERS.items():
        sentence = compaction_of(tasks, name).prune_refusal
        if sentence is None:
            assert prune.resolve(word, tasks) == word
            continue
        with pytest.raises(ValueError) as refusal:
            prune.resolve(word, tasks)
        assert f"{word} is refused" in str(refusal.value) and sentence in str(refusal.value)
    assert prune.resolve(CENSUS, tasks) == CENSUS

    with pytest.raises(ValueError, match="a person chose to keep every census row"):
        prune.resolve(CENSUS, with_refusal(tasks, CENSUS, "a person chose to keep every census row"))
    evals = LedgerName.SUMMARY_QUALITY_EVALS
    assert prune.resolve(evals, with_refusal(tasks, evals, None)) == evals
    undeclared = {
        name: policy
        for name, policy in tasks.items()
        if not (isinstance(policy, CompactionPolicy) and policy.ledger is CENSUS)
    }
    with pytest.raises(ValueError, match="no compaction under config/gardener/ declares it"):
        prune.resolve(CENSUS, undeclared)


def test_the_eval_ledger_is_refused_with_the_sentence_its_declaration_gives(
    tmp_path: Path,
) -> None:
    """Every eval row is kept for ever, so no range of its days may be taken, and the refusal says so.

    The sentence is read off the committed declaration rather than copied here,
    so the reason a person reads is the one that sits beside the eval ledger's
    windows. Refused before anything is read, so the tree is as it was.
    """
    state = a_census(tmp_path / "state")
    before = fingerprints(state)
    sentence = compaction_of(committed_tasks(), LedgerName.SUMMARY_QUALITY_EVALS).prune_refusal
    assert sentence, "the eval ledger's declaration gives no reason, so a prune would take its days"

    with pytest.raises(ValueError) as refusal:
        prune_range(
            state,
            target=LedgerName.SUMMARY_QUALITY_EVALS,
            since=DAYS[0],
            until=DAYS[6],
            dry_run=False,
            run_id=PRUNE_RUN,
            commit=PRUNE_COMMIT,
        )

    message = str(refusal.value)
    assert f"{LedgerName.SUMMARY_QUALITY_EVALS} is refused" in message
    assert sentence in message
    assert fingerprints(state) == before


@pytest.mark.parametrize(
    ("run_id", "commit", "says"),
    [
        (None, PRUNE_COMMIT, "--run-id"),
        (PRUNE_RUN, None, "--commit"),
        ("2026-03-21", PRUNE_COMMIT, "YYYY-MM-DD-N"),
        (PRUNE_RUN, "c0ffee", "forty"),
    ],
)
def test_a_live_pass_on_the_door_is_refused_without_a_writer_it_can_name(
    tmp_path: Path, run_id: str | None, commit: str | None, says: str
) -> None:
    """A rebuilt file names the run and the commit that wrote it, so a live pass needs both.

    Refused before a file is read, so the tree is as it was. A dry run needs
    neither, and still lists what the live pass would take.
    """
    state = a_census(tmp_path / "state")
    before = fingerprints(state)

    with pytest.raises(ValueError, match=says):
        prune_range(
            state,
            target=CENSUS,
            since=DAYS[0],
            until=DAYS[6],
            dry_run=False,
            run_id=run_id,
            commit=commit,
        )

    assert fingerprints(state) == before
    assert prune_range(state, target=CENSUS, since=DAYS[0], until=DAYS[6]).removed
    assert fingerprints(state) == before, "a dry run changed a file"


def test_a_dry_run_on_the_door_names_every_change_a_live_pass_makes_and_makes_none(
    every_tier: Path, tmp_path: Path
) -> None:
    """The list a person reads before `--no-dry-run` is the list the live pass carries out.

    Both passes name the same writer, so every file the dry run builds is the
    file the live pass writes, byte count and all.
    """
    state = a_copy(every_tier, tmp_path / "checkout")
    before = fingerprints(state)

    dry = prune_range(
        state, target=CENSUS, since=SINCE, until=UNTIL, run_id=PRUNE_RUN, commit=PRUNE_COMMIT
    )

    assert dry.dry_run and not dry.changed
    assert fingerprints(state) == before, "a dry run changed a file"
    live = prune_range(
        state,
        target=CENSUS,
        since=SINCE,
        until=UNTIL,
        dry_run=False,
        run_id=PRUNE_RUN,
        commit=PRUNE_COMMIT,
    )
    assert (dry.removed, dry.rewritten, dry.bytes_freed, dry.kept) == (
        live.removed,
        live.rewritten,
        live.bytes_freed,
        live.kept,
    )
    after = fingerprints(state)
    changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
    named = {
        relpath.removeprefix(f"{ledger.STATE_DIRNAME}/")
        for relpath in (*live.removed, *live.rewritten)
    }
    assert changed == named, "the files that changed are not the files the pass named"
    lines = prune.report(dry)
    assert all(any(relpath in line for line in lines) for relpath in (*dry.removed, *dry.rewritten))
    assert "--no-dry-run" in lines[-1]


def test_a_ceiling_takes_the_oldest_days_and_the_same_command_finishes_the_range(
    every_tier: Path, tmp_path: Path
) -> None:
    """A range wider than the bite an operator wants is taken in bites, oldest day first.

    The first held day of the range is the 20th of December, so five days stop
    the pass at the 25th, and running the command again without a ceiling leaves
    exactly what one pass over the whole range leaves.
    """
    bites = a_copy(every_tier, tmp_path / "bites")
    whole = a_copy(every_tier, tmp_path / "whole")

    first = prune_range(
        bites,
        target=CENSUS,
        since=SINCE,
        until=UNTIL,
        dry_run=False,
        max_deletes=5,
        run_id=PRUNE_RUN,
        commit=PRUNE_COMMIT,
    )
    rest = prune_range(
        bites,
        target=CENSUS,
        since=SINCE,
        until=UNTIL,
        dry_run=False,
        run_id=PRUNE_RUN,
        commit=PRUNE_COMMIT,
    )
    prune_range(
        whole,
        target=CENSUS,
        since=SINCE,
        until=UNTIL,
        dry_run=False,
        run_id=PRUNE_RUN,
        commit=PRUNE_COMMIT,
    )

    assert (first.more_to_do, first.resume_from) == (True, "2025-12-25")
    assert any("run it again" in line for line in prune.report(first))
    assert rest.resume_from is None
    assert census_by_day(bites) == census_by_day(whole)
    assert indexes(bites) == indexes(whole)


def test_a_file_whose_every_row_goes_stays_as_an_empty_file_its_index_names(
    every_tier: Path, tmp_path: Path
) -> None:
    """A month and a day whose rows all go are kept as empty files, so no index has a hole.

    Their index entries count no row and weigh what the empty files weigh, and
    neither day nor month reads as missing.
    """
    state = a_copy(every_tier, tmp_path / "checkout")

    prune_range(
        state,
        target=CENSUS,
        since="2026-01-01",
        until="2026-02-28",
        dry_run=False,
        run_id=PRUNE_RUN,
        commit=PRUNE_COMMIT,
    )

    month = ledger.compact_file(state, CENSUS, Period.MONTHLY, "2026-01")
    day = ledger.compact_file(state, CENSUS, Period.DAILY, "2026-02-10")
    assert month is not None and day is not None, "an emptied period lost its file"
    assert ledger.load([month, day], model=ItemHealthRow) == []
    entries = indexes(state)
    assert CompactEntry(covers="2026-01", rows=0, bytes=month.stat().st_size) in entries[
        Period.MONTHLY
    ]
    assert CompactEntry(covers="2026-02-10", rows=0, bytes=day.stat().st_size) in entries[
        Period.DAILY
    ]
    assert ledger.list_ledger_files(state, CENSUS).holes == ()


def a_month_with_lost_days(state: Path) -> CompactIndex:
    """Row 8's sample monthly index, written over a real file for the month that names one.

    That month is packed through the door from census rows filed on two of its
    days, and its entry counts that file's rows and bytes; its state, lost days
    and set-aside count are the sample's. The daily and yearly indexes are
    written empty, because a ledger's three indexes exist together.
    """
    sample = CompactIndex.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "compact-index" / "a-month-with-lost-days.json")
    )
    entries: list[CompactEntry] = []
    for entry in sample.entries:
        if not entry.names_file:
            entries.append(entry)
            continue
        days = [f"{entry.covers}-05", f"{entry.covers}-20"]
        for number, day in enumerate(days):
            seed_item_health(
                state, day, [health_row(day=day, run=1, number=number, stage=ItemStage.PUBLISH)]
            )
        raws = ledger.list_raw_files(state, CENSUS, days=days)
        month = ledger.persist_period(
            state,
            ledger.load_stored([raw.path for raw in raws], model=ItemHealthRow),
            model=ItemHealthRow,
            ledger=CENSUS,
            period=Period.MONTHLY,
            covers=entry.covers,
            identity=raws[0].envelope.identity,
            built_from=len(raws),
        )
        for raw in raws:
            raw.path.unlink()
            day_partition.drop_empty_day_dirs(raw.path)
        entries.append(entry.model_copy(update={"rows": len(days), "bytes": month.stat().st_size}))
    planted = sample.model_copy(update={"entries": entries})
    for period in Period:
        index = (
            planted
            if period is planted.period
            else CompactIndex(
                version=CompactIndex.schema_version(), ledger=CENSUS, period=period, entries=[]
            )
        )
        path = ledger.compact_index_path(state, CENSUS, period)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(index.to_json().encode("ascii"))
    return planted


def test_a_rebuilt_entry_keeps_its_state_its_lost_days_and_what_was_set_aside(
    tmp_path: Path,
) -> None:
    """A prune that builds the rebuilt month's entry afresh fails this: it counts the rows and
    bytes left and drops the two days recorded lost and the file set aside, so the record of
    a gap is gone. The empty month beside it is carried as it was."""
    state = tmp_path / ledger.STATE_DIRNAME
    empty, packed = a_month_with_lost_days(state).entries

    prune_range(
        state,
        target=CENSUS,
        since=f"{packed.covers}-05",
        until=f"{packed.covers}-05",
        dry_run=False,
        run_id=PRUNE_RUN,
        commit=PRUNE_COMMIT,
    )

    month = ledger.compact_file(state, CENSUS, Period.MONTHLY, packed.covers)
    assert month is not None
    left = ledger.load([month], model=ItemHealthRow)
    assert [row.date for row in left] == [f"{packed.covers}-20"]
    assert indexes(state)[Period.MONTHLY] == [
        empty,
        packed.model_copy(update={"rows": len(left), "bytes": month.stat().st_size}),
    ]


def test_a_rebuilt_file_names_the_prune_as_its_writer_and_each_kept_row_keeps_its_own(
    every_tier: Path, tmp_path: Path
) -> None:
    """The envelope says who rebuilt the file; every row left still says who first filed it.

    A reader settles rows by their own identity cells, so a rebuild that stamped
    its own on them would make a later re-run of their writer lose to the prune.
    """
    state = a_copy(every_tier, tmp_path / "checkout")
    year = ledger.compact_file(state, CENSUS, Period.YEARLY, "2025")
    assert year is not None
    kept = [
        held
        for held in ledger.load_stored([year], model=ItemHealthRow)
        if held.identity.covers != "2025-12-20"
    ]

    prune_range(
        state,
        target=CENSUS,
        since="2025-12-20",
        until="2025-12-20",
        dry_run=False,
        run_id=PRUNE_RUN,
        commit=PRUNE_COMMIT,
    )

    envelope = ledger.read_envelope(year)
    assert (envelope.identity, envelope.built_from) == (PRUNE_WRITER, 1)
    assert ledger.load_stored([year], model=ItemHealthRow) == kept


def stopped_after_its_deletes(state: Path) -> None:
    """The tree a pass leaves when it stops after its deletes and before its first rewrite."""
    planned = prune_range(
        state, target=CENSUS, since=SINCE, until=UNTIL, run_id=PRUNE_RUN, commit=PRUNE_COMMIT
    )
    for relpath in planned.removed:
        (state / relpath.removeprefix(f"{ledger.STATE_DIRNAME}/")).unlink()


def stopped_after_its_first_rewrite(state: Path) -> None:
    """The same, and the first file the pass rebuilds written as the pass writes it."""
    stopped_after_its_deletes(state)
    first = next(
        held
        for held in ledger.find_holding_files(state, CENSUS, the_range())
        if held.period is not None
    )
    built = ledger.rebuild_without(state, first, first.days, identity=PRUNE_WRITER)
    atomic_write.write_atomic_bytes(built.path, built.data)


@pytest.mark.parametrize("stop", [stopped_after_its_deletes, stopped_after_its_first_rewrite])
def test_a_pass_that_stopped_part_way_is_finished_by_the_same_command(
    every_tier: Path, tmp_path: Path, stop: Callable[[Path], None]
) -> None:
    """Running the command again finishes a pass a failure stopped, and leaves what one pass leaves.

    Each tree is the one a failure leaves at a point the pass can stop at, made
    by doing that much of the pass for real and nothing more: after its deletes,
    and after its first rewrite as well.
    """
    stopped = a_copy(every_tier, tmp_path / "stopped")
    whole = a_copy(every_tier, tmp_path / "whole")
    stop(stopped)

    for state in (stopped, whole):
        prune_range(
            state,
            target=CENSUS,
            since=SINCE,
            until=UNTIL,
            dry_run=False,
            run_id=PRUNE_RUN,
            commit=PRUNE_COMMIT,
        )

    assert census_by_day(stopped) == census_by_day(whole)
    assert indexes(stopped) == indexes(whole)
    assert set(fingerprints(stopped)) == set(fingerprints(whole)), "the trees hold other files"


def test_a_pass_on_the_door_that_fails_part_way_names_what_changed_and_is_run_again(
    every_tier: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The third change raises: the two before it happened, the record names them, a re-run finishes.

    The failure is injected the way the CSV test above injects it: the real
    change runs for every file but the third, so the tree is the one a file
    system that refused one change leaves. The record names the first two
    paths of the dry run's list, and the first day of the range as the place
    the next pass starts, because no day was finished.
    """
    stopped = a_copy(every_tier, tmp_path / "stopped")
    whole = a_copy(every_tier, tmp_path / "whole")
    planned = prune_range(
        stopped, target=CENSUS, since=SINCE, until=UNTIL, run_id=PRUNE_RUN, commit=PRUNE_COMMIT
    )
    changes = 0
    real_apply = door_prune._apply

    def fail_on_the_third(change: door_prune._Change) -> None:
        nonlocal changes
        changes += 1
        if changes == 3:
            raise OSError("the file system said no")
        real_apply(change)

    monkeypatch.setattr(door_prune, "_apply", fail_on_the_third)
    with pytest.raises(prune.PruneInterruptedError) as stop:
        prune_range(
            stopped,
            target=CENSUS,
            since=SINCE,
            until=UNTIL,
            dry_run=False,
            run_id=PRUNE_RUN,
            commit=PRUNE_COMMIT,
        )
    monkeypatch.undo()

    so_far = stop.value.so_far
    first_two = (*planned.removed, *planned.rewritten)[:2]
    assert changes == 3, "the pass kept changing files after a failure"
    assert (so_far.taken, so_far.written) == (
        tuple(path for path in first_two if path in planned.removed),
        tuple(path for path in first_two if path in planned.rewritten),
    )
    assert (so_far.stopped_because, so_far.resume_from) == (StopReason.FAILED, SINCE)
    for state in (stopped, whole):
        prune_range(
            state,
            target=CENSUS,
            since=SINCE,
            until=UNTIL,
            dry_run=False,
            run_id=PRUNE_RUN,
            commit=PRUNE_COMMIT,
        )
    assert census_by_day(stopped) == census_by_day(whole)
    assert indexes(stopped) == indexes(whole)
    assert set(fingerprints(stopped)) == set(fingerprints(whole)), "the trees hold other files"
