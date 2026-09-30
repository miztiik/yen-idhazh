"""Which score-index days and score summaries does the scores task take, and which must it keep?

The pass under test is the gardener's `scores` task, run through the shipped
module and the committed declaration. The eval ledger's own rows are filed
through the ledger door and kept by its compaction, so this task archives no
month and deletes no row. It takes an index day once a summary covers that
day's month and the month is past the full-grain window, and it takes a
summary once the summary is past the archive's own series. `pruned` reads what
one pass took back into the words these tests ask in.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text, seed_scores
from gardener.tasks._task import declared, run_task

from idhazh import day_shards, ledger
from idhazh.contracts.eval_row import ConfidenceBand, EvalRow
from idhazh.contracts.knobs.gardener import MonthsWindow, RetentionPolicy
from idhazh.contracts.ledger_name import LedgerName
from idhazh.evals import archive as score_archive
from idhazh.evals import writer as score_writer
from idhazh.retention import oldest_month_kept

from ._trees import (
    HISTORY_MONTHS,
    NOT_MONTHS,
    TODAY,
    months_back,
)

pytestmark = pytest.mark.slow


def full_grain_months() -> int:
    window = declared()["scores"].window
    assert isinstance(window, MonthsWindow), "scores keeps its rows for a window of months"
    return window.value


@dataclass(frozen=True)
class Pruned:
    """What one pass of the scores task took and wrote."""

    written: tuple[str, ...]
    index_days_removed: tuple[str, ...]
    hard_deleted: tuple[str, ...]
    dry_run: bool
    changed: bool


def pruned(
    state: Path, *, today: date = TODAY, dry_run: bool = False, archive_months: int | None = None
) -> Pruned:
    """One pass of the shipped scores task over the checkout `state` sits in."""
    full = {"unit": "months", "value": full_grain_months()}
    archive = {"unit": "forever"} if archive_months is None else {"unit": "months", "value": archive_months}
    outcome = run_task(
        "scores",
        state.parent,
        today=today,
        dry_run=dry_run,
        window=full,
        series={"full-grain": full, "archive": archive},
    )
    under = {
        which: f"{ledger.tree_relpath(which)}/"
        for which in (LedgerName.SCORE_INDEX, LedgerName.SCORE_ARCHIVE)
    }
    return Pruned(
        written=tuple(outcome.written),
        index_days_removed=tuple(
            p for p in outcome.taken if p.startswith(under[LedgerName.SCORE_INDEX])
        ),
        hard_deleted=tuple(
            Path(p).stem for p in outcome.taken if p.startswith(under[LedgerName.SCORE_ARCHIVE])
        ),
        dry_run=outcome.dry_run,
        changed=outcome.changed,
    )


def score_row(*, day: str, run: int, number: int) -> EvalRow:
    """One eval row, built off the committed fixture so every column is real-shaped.

    `hhem` walks the deciles and `band` follows it, so a fixture month exercises
    more than one bucket and more than one band - a summary that collapsed
    either would still pass a single-value fixture.
    """
    base = json.loads(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json"))
    faithfulness = round(0.05 + (number % 10) / 10, 4)
    seed = f"{day}-{run}-{number}"
    band = (
        ConfidenceBand.HIGH
        if faithfulness >= 0.80
        else ConfidenceBand.MEDIUM
        if faithfulness >= 0.50
        else ConfidenceBand.LOW
    )
    return EvalRow.model_validate(
        {
            **base,
            "date": day,
            "run_id": f"{day}-{run}",
            "item_id": f"ai-{number:04d}",
            "url_key": hashlib.sha256(seed.encode("ascii")).hexdigest(),
            "output_digest": hashlib.sha256(f"out-{seed}".encode("ascii")).hexdigest(),
            "hhem": faithfulness,
            "hhem_full": faithfulness,
            "hhem_delta": 0.0,
            "band": band.value,
            "unsupported_numbers": number % 3,
            "hedge_dropped": number % 4 == 0,
            "extraction_suspect": number % 5 == 0,
            "source_words_before_cap": 1320,
            "source_words": 1320 - (number % 2) * 40,
            "score_ms": 1000 + number,
            "scored_at": f"{day}T06:18:02Z",
        }
    )


def score_history(state_dir: Path, months: list[str]) -> None:
    """Two real score days a month, filed through the real writer, index and all."""
    for index, month in enumerate(months):
        for day_of_month in (4, 17):
            day = f"{month}-{day_of_month:02d}"
            seed_scores(
                state_dir,
                [score_row(day=day, run=1, number=index * 100 + offset) for offset in range(6)],
                run_id=f"{day}-1",
            )


def archive_history(state: Path, months: Iterable[str], *, scratch: Path) -> None:
    """A committed month summary for each month, built by the archive module itself.

    Nothing in the pipeline builds one any more, so the test builds each the
    way a committed one was built: the month's rows, read back through the
    ledger door and written out as the CSV the summariser reads, under `scratch`
    and outside the state tree.
    """
    scratch.mkdir(parents=True, exist_ok=True)
    columns = EvalRow.csv_columns()
    for month in months:
        shard = scratch / f"{month}.csv"
        rows = ledger.load_days(state, LedgerName.SCORES, ledger.month_days(month), model=EvalRow)
        with shard.open("w", encoding="utf-8", newline="") as handle:
            out = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
            out.writeheader()
            out.writerows(row.csv_row() for row in rows)
        built = score_archive.summarise(
            [shard], month=month, observation_key=score_writer.OBSERVATION_KEY
        )
        score_archive.write(score_archive.archive_path(state, month), built)


@pytest.fixture(scope="module")
def built_tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Twenty months of scores, with a summary for every month past the full-grain window.

    Built once for the module, because filing twenty months through the writer
    is the slow part of every case here, and copied by `a_score_tree` so that
    each case changes a tree of its own.
    """
    root = tmp_path_factory.mktemp("score-tree")
    state = root / "state"
    months = months_back(TODAY, HISTORY_MONTHS)
    score_history(state, months)
    boundary = oldest_month_kept(TODAY, full_grain_months())
    archive_history(
        state, [month for month in months if month < boundary], scratch=root / "scratch"
    )
    return state


def a_score_tree(tmp_path: Path, built: Path) -> Path:
    """This case's own copy of the built tree."""
    state = tmp_path / "state"
    shutil.copytree(built, state)
    return state


def index_months(state: Path) -> list[str]:
    """The months the score index still holds a day of, oldest first."""
    return sorted({day_shards.date_of(shard)[:7] for shard in score_writer.index_days(state)})


def everything(state: Path) -> dict[str, bytes]:
    """Every file under the state tree, by its path below it, with its bytes."""
    return {
        path.relative_to(state).as_posix(): path.read_bytes()
        for path in sorted(state.rglob("*"))
        if path.is_file()
    }


def test_a_score_month_inside_the_window_is_untouched(tmp_path: Path) -> None:
    """The window guards an index day, not only the summary beside it.

    Every month here has a summary, so what keeps each index day is the
    full-grain window alone.
    """
    state = tmp_path / "state"
    months = months_back(TODAY, 3)
    score_history(state, months)
    archive_history(state, months, scratch=tmp_path / "scratch")
    held = everything(state)

    result = pruned(state)

    assert result.changed is False
    assert result.index_days_removed == ()
    assert result.hard_deleted == ()
    assert everything(state) == held


def test_a_score_dry_run_names_what_it_would_take_and_changes_nothing(
    tmp_path: Path, built_tree: Path
) -> None:
    """A dry run's deliverable is the list, so it names both kinds of file and moves no byte.

    A finite archive age, so a summary is past its series and the dry run has
    one of each to name.
    """
    state = a_score_tree(tmp_path, built_tree)
    held = everything(state)

    result = pruned(state, dry_run=True, archive_months=15)

    assert result.dry_run is True
    assert result.index_days_removed, "a dry run that names no index day is not a deliverable"
    assert result.hard_deleted, "a dry run that names no summary is not a deliverable"
    assert result.written == ()
    assert everything(state) == held


def test_a_second_score_run_over_a_settled_tree_moves_no_byte(
    tmp_path: Path, built_tree: Path
) -> None:
    state = a_score_tree(tmp_path, built_tree)
    pruned(state)
    settled = everything(state)

    again = pruned(state)

    assert again.changed is False
    assert everything(state) == settled


def test_a_score_file_the_reader_cannot_place_stops_the_prune(
    tmp_path: Path, built_tree: Path
) -> None:
    """A stray is refused, where a reader that skipped it would walk past it.

    `day_shards.shard_files` refuses a name it cannot place, so an index holding
    one is unreadable rather than partly readable - and the prune it stops is
    the one that deletes. It is the stronger of the two behaviours: a file the
    reader skips is a day it might decide about without.
    """
    state = a_score_tree(tmp_path, built_tree)
    stray = ledger.tree_root(state, LedgerName.SCORE_INDEX) / "notes.csv"
    stray.write_text("nothing the contract knows\n", encoding="utf-8")
    before = everything(state)

    with pytest.raises(ValueError, match=re.escape("notes.csv")):
        pruned(state)

    assert everything(state) == before, "the refused pass deleted something anyway"


def test_a_month_shaped_name_in_the_archive_folder_is_never_taken_as_a_summary(
    tmp_path: Path, built_tree: Path
) -> None:
    """The defect this test exists for, on the one path here that deletes by month name.

    A summary past the archive's own series is deleted by its `<YYYY-MM>` stem.
    A reader that accepted any seven characters of the right shape would take
    `2025-13.json` for a month older than the series and delete it. Nothing in
    this repository writes that name, so nothing could say afterwards what was
    in it, and the gardener's history job force-pushes `main`. The archive
    folder is read by the strict month rule, so a name that is not a month is
    never a summary and never goes.
    """
    state = a_score_tree(tmp_path, built_tree)
    strays = {
        ledger.tree_root(state, LedgerName.SCORE_ARCHIVE) / f"{stem}.json": (
            f"{stem} was never written\n"
        )
        for stem in NOT_MONTHS
    }
    for path, text in strays.items():
        path.write_text(text, encoding="utf-8")

    result = pruned(state, archive_months=15)

    assert result.hard_deleted, "a finite archive age took no summary, so this proves nothing"
    assert not set(result.hard_deleted) & set(NOT_MONTHS)
    assert {path: path.read_text(encoding="utf-8") for path in strays} == strays


def test_the_archive_is_kept_forever_unless_somebody_asks_for_the_bytes_back(
    tmp_path: Path, built_tree: Path
) -> None:
    state = a_score_tree(tmp_path, built_tree)
    policy = declared()["scores"]
    assert isinstance(policy, RetentionPolicy) and policy.series is not None
    assert policy.series["archive"].unit == "forever"
    before = score_archive.archived_months(state)
    assert before, "the fixture holds no summary, so this proves nothing"

    result = pruned(state)

    assert result.hard_deleted == ()
    assert score_archive.archived_months(state) == before


def test_a_finite_archive_age_takes_the_summaries_past_it_and_keeps_the_rest(
    tmp_path: Path, built_tree: Path
) -> None:
    """A summary goes once it is past the archive's own series, and no other does.

    A finite age must sit above the full-grain window, and here it does: fifteen
    against fourteen, so every summary it takes is of a month whose index days
    were already past the window.
    """
    state = a_score_tree(tmp_path, built_tree)
    before = score_archive.archived_months(state)
    assert len(before) > 1

    result = pruned(state, archive_months=15)

    assert result.hard_deleted == tuple(
        month for month in before if month < oldest_month_kept(TODAY, 15)
    )
    assert result.hard_deleted, "the fixture has to reach past both ages"
    assert score_archive.archived_months(state) == [
        month for month in before if month not in result.hard_deleted
    ]


def test_an_archived_month_whose_index_went_is_still_refused_as_a_repeat(
    tmp_path: Path, built_tree: Path
) -> None:
    """After the pass takes a month's index, every measurement in it is still held.

    The index is what a run dedupes against, and the task takes a month's index
    days only because a summary carries the same digests. Without that, the day
    the index went every row of the month would be scoreable again as if it
    were new.
    """
    state = a_score_tree(tmp_path, built_tree)
    boundary = oldest_month_kept(TODAY, full_grain_months())
    month = next(name for name in index_months(state) if name < boundary)
    replayed = ledger.load_days(state, LedgerName.SCORES, ledger.month_days(month), model=EvalRow)
    assert replayed, "the month holds no row, so this proves nothing"

    pruned(state)

    assert month not in index_months(state), "the pass kept the month's index, so this proves nothing"
    assert seed_scores(state, replayed, run_id=f"{month}-28-9") == 0, (
        "a month whose index went made its measurements new again"
    )
    assert month not in index_months(state), "the replay wrote an index day the summary replaced"


def test_an_index_day_goes_once_an_archive_covers_its_month(
    tmp_path: Path, built_tree: Path
) -> None:
    """An index day past the window goes once a summary carries its digests, and not before.

    The summary carries those digests, so nothing here removes the last record
    of a measurement - which is why the drop is guarded on the summary being on
    disk rather than on the month's age alone.
    """
    state = a_score_tree(tmp_path, built_tree)
    boundary = oldest_month_kept(TODAY, full_grain_months())
    before = index_months(state)
    assert any(month < boundary for month in before), "the fixture never reaches past the window"
    taken = [
        f"{ledger.STATE_DIRNAME}/{shard.relative_to(state).as_posix()}"
        for shard in score_writer.index_days(state)
        if day_shards.date_of(shard)[:7] < boundary
    ]
    held = score_writer.recorded_observations(state)

    dry = pruned(state, dry_run=True)
    assert dry.index_days_removed, "a dry run that names no index file is not a deliverable"
    assert index_months(state) == before, "a dry run deleted the index"

    live = pruned(state)
    assert live.index_days_removed == dry.index_days_removed, (
        "the index files a live run removed are not the ones a dry run named"
    )
    assert list(live.index_days_removed) == taken
    assert index_months(state) == [month for month in before if month >= boundary]
    # Every measurement the deleted index held is still refused, because the
    # summary beside it carries the same digests.
    assert score_writer.recorded_observations(state) == held


def test_an_index_day_no_archive_covers_is_left_alone(tmp_path: Path, built_tree: Path) -> None:
    """The guard on the drop, asked from the side that would lose a record.

    A month nobody summarised - and nothing in the pipeline builds a summary
    now - leaves the index as the only thing that remembers its measurements,
    because a run dedupes against the index and never reads a row. Dropping it
    there would silently make every one of them new again, so the drop is
    guarded on a summary being on disk rather than on the month's age.
    """
    state = a_score_tree(tmp_path, built_tree)
    orphan = "2020-03-04"
    unsummarised = score_row(day=orphan, run=1, number=1)
    assert seed_scores(state, [unsummarised], run_id=f"{orphan}-1") == 1
    assert day_shards.one_day(ledger.tree_root(state, LedgerName.SCORE_INDEX), orphan), (
        "the index for the orphaned day was never written, so this proves nothing"
    )

    pruned(state)

    assert day_shards.one_day(ledger.tree_root(state, LedgerName.SCORE_INDEX), orphan), (
        "the last record of those measurements went, and no archive carries them"
    )
    assert score_writer.observation_digest(
        unsummarised.model_dump(mode="json")
    ) in score_writer.recorded_observations(state)
