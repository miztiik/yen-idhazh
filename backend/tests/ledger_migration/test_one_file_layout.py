"""Does a ledger kept in one CSV file move onto the door a day at a time, and leave only whole?

The holdout marks sat in one file, `state/content-similarity-judge/holdout-pairs.csv`,
and each row named the day it was marked in `marked_on`. The migrator reads a
named month's days out of that column, files each day's rows through the door
under that day, proves them, and deletes the file only when every month it
holds was named: the one file is every month's source at once.

Each case builds its own state root and config under `tmp_path`, and nothing
reads committed state (CLAUDE.md section 13).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Final

import pytest
from conftest import SEED_COMMIT
from gardener._historical_config import PRE_YEARLY_CONFIG

from idhazh import config, ledger
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.similarity_holdout_pair import SimilarityHoldoutPair
from idhazh.ledger import render_file
from utilities.ledger_migration import csv_files, phases, planning
from utilities.ledger_migration.inputs import MigrationInputs
from utilities.ledger_migration.refusals import NotProvenError

from ._fixtures import RUN, config_beside, file_hashes

pytestmark = pytest.mark.contract

HOLDOUT: Final = LedgerName.CONTENT_SIMILARITY_JUDGE_HOLDOUT_PAIRS

#: Two days in two months, so a run can name one month of the file and not the other.
SEPTEMBER: Final = "2026-09-19"
OCTOBER: Final = "2026-10-02"

#: The wake the copy runs on, after both days.
TODAY: Final = date(2026, 10, 8)


def a_mark(key: str, *, marked_on: str, same: bool = True) -> SimilarityHoldoutPair:
    """One mark of two articles published the day before it was made."""
    return SimilarityHoldoutPair(
        version=SimilarityHoldoutPair.schema_version(),
        left_url=f"https://left.test/{key}",
        right_url=f"https://right.test/{key}",
        left_date="2026-09-17",
        right_date="2026-09-17",
        left_title=f"Left story {key}",
        right_title=f"Right story {key}",
        same_story=same,
        marked_on=marked_on,
        note=f"a-labeller at score 0.9{len(key)}",
    )


#: Two marks of September and one of October, the way a harvest wrote them.
MARKS: Final = (
    ("first", SEPTEMBER, True),
    ("second", SEPTEMBER, False),
    ("third", OCTOBER, True),
)


def a_marks_file(state: Path, rows: Sequence[SimilarityHoldoutPair]) -> Path:
    """The one CSV file every mark sat in, in the judge's folder."""
    path = state / "content-similarity-judge" / "holdout-pairs.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_file(SimilarityHoldoutPair.csv_columns(), [row.csv_row() for row in rows]),
        encoding="utf-8",
        newline="",
    )
    return path


def the_marks() -> list[SimilarityHoldoutPair]:
    return [a_mark(key, marked_on=day, same=same) for key, day, same in MARKS]


def a_config_keeping_the_marks(state: Path) -> Path:
    """The recorded pre-expiry config beside the state tree, with a compaction for the marks.

    It keeps every month for ever, as every recorded declaration did before yearly
    expiry, so the move is held to the window the one file kept.
    """
    config_dir = config_beside(state)
    folder = "content-similarity-judge/holdout-pairs"
    declaration = json.loads(
        (PRE_YEARLY_CONFIG / "gardener" / "compact-candidate-models.json").read_text(
            encoding="utf-8"
        )
    )
    declaration.update(
        ledger=HOLDOUT.value, owns=[f"state/raw/{folder}", f"state/compact/{folder}"]
    )
    task = config.compaction_task(HOLDOUT)
    (config_dir / "gardener" / f"{task}.json").write_text(
        json.dumps(declaration, indent=2) + "\n", encoding="ascii"
    )
    settings_path = config_dir / "idhazh_gardener.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    settings["task_names"] = sorted({*settings["task_names"], task})
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="ascii")
    return config_dir


def inputs(state: Path, *months: str) -> MigrationInputs:
    return MigrationInputs(
        state_dirs=[state],
        which=[HOLDOUT],
        run_id=RUN,
        git_sha=SEED_COMMIT,
        today=TODAY,
        config_dir=a_config_keeping_the_marks(state),
        months=months,
    )


def read_back(state: Path, day: str) -> list[dict[str, str]]:
    """One day's marks as the door serves them, in a stable order."""
    rows = ledger.load_days(state, HOLDOUT, [day], model=SimilarityHoldoutPair)
    return sorted((row.csv_row() for row in rows), key=lambda cells: cells["left_url"])


def by_day(day: str) -> list[dict[str, str]]:
    """The marks of one day, as the one file held them."""
    rows = [row.csv_row() for row in the_marks() if row.marked_on == day]
    return sorted(rows, key=lambda cells: cells["left_url"])


def test_a_named_month_is_filed_day_by_day_under_the_day_its_rows_name(tmp_path: Path) -> None:
    """The copy of September files its two marks under their day, and leaves October alone.

    The file is kept: a copy writes raw files and deletes nothing.
    """
    state = tmp_path / "state"
    source = a_marks_file(state, the_marks())

    plans = planning.plan_roots(inputs(state, "2026-09"))
    (moved,) = phases.write_roots(plans, raw_only=True)

    assert list(plans[0].planned[HOLDOUT]) == [SEPTEMBER]
    assert (moved[1].csv_files, moved[1].days, moved[1].rows, moved[1].filed) == (1, 1, 2, 1)
    assert ledger.raw_days(state, HOLDOUT) == [SEPTEMBER]
    assert read_back(state, SEPTEMBER) == by_day(SEPTEMBER)
    assert source.is_file()


def test_the_one_file_is_counted_once_however_many_days_it_holds(tmp_path: Path) -> None:
    state = tmp_path / "state"
    source = a_marks_file(state, the_marks())

    (plan,) = planning.plan_roots(inputs(state, "2026-09", "2026-10"))

    assert list(plan.planned[HOLDOUT]) == [SEPTEMBER, OCTOBER]
    report = plan.reports[HOLDOUT]
    assert (report.csv_files, report.csv_bytes, report.days, report.rows) == (
        1,
        source.stat().st_size,
        2,
        3,
    )


def test_the_file_is_deleted_only_once_every_month_it_holds_is_named(tmp_path: Path) -> None:
    """A retirement naming September alone would delete October's marks, which nothing copied.

    It is refused before any file goes. Named whole, every month is proved
    again and the one file is deleted, and the door still holds every mark.
    """
    state = tmp_path / "state"
    source = a_marks_file(state, the_marks())
    phases.write_roots(planning.plan_roots(inputs(state, "2026-09")), raw_only=True)
    before = file_hashes(state)

    with pytest.raises(NotProvenError, match="also holds rows of 2026-10"):
        phases.retire_roots(inputs(state, "2026-09"))
    assert file_hashes(state) == before

    phases.write_roots(planning.plan_roots(inputs(state, "2026-09", "2026-10")), raw_only=True)
    phases.retire_roots(inputs(state, "2026-09", "2026-10"))

    assert not source.exists()
    assert csv_files.left(state, [HOLDOUT], months=["2026-09", "2026-10"]) == []
    assert read_back(state, SEPTEMBER) == by_day(SEPTEMBER)
    assert read_back(state, OCTOBER) == by_day(OCTOBER)


def test_a_mark_whose_day_is_not_a_day_is_refused_before_anything_is_written(
    tmp_path: Path,
) -> None:
    """The day comes from the cell, so a cell that is not a UTC day is refused, not guessed."""
    state = tmp_path / "state"
    source = a_marks_file(state, the_marks())
    source.write_text(
        source.read_text(encoding="utf-8").replace(OCTOBER, "2026-10-2"),
        encoding="utf-8",
        newline="",
    )

    with pytest.raises(NotProvenError, match=r"marked_on '2026-10-2' is not a UTC day"):
        planning.plan_roots(inputs(state, "2026-09"))
    assert not ledger.raw_root(state, HOLDOUT).exists()
