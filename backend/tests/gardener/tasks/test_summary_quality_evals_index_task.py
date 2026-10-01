"""Which days of the eval ledger's ID folder does its task take, and what does it never touch?

None, however old. The index is what a run dedupes against, and an observation
key carries no date, so an index day taken would make every measurement in it
new again. Every eval row is kept for ever, so the committed declaration keeps
every month, and a pass over an index older than any window takes nothing, dry
or live. The task's one live action is its fold, which settles each closed
month into one file and each closed day of the open month into one file;
`tests/gardener/test_closed_day_fold.py` holds what the fold itself promises.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text, seed_scores
from retention._trees import HISTORY_MONTHS, TODAY, months_back

from idhazh import day_shards, ledger
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.knobs.gardener import ForeverWindow, MonthsWindow, RetentionPolicy
from idhazh.contracts.ledger_name import LedgerName
from idhazh.evals import writer
from idhazh.gardener import closed_day_fold, retention_files

from ._oracle_tree import files_under
from ._task import context_for, declared, run_task

pytestmark = pytest.mark.contract

NAME: Final = "summary-quality-evals-index"

#: A day older than any window a gardener task has declared.
LONG_AGO: Final = "2020-03-04"


def a_measurement(day: str, number: int) -> EvalRow:
    """One eval row off the committed fixture, unique in every field the dedupe reads."""
    base = json.loads(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json"))
    seed = f"{day}-{number}"
    return EvalRow.model_validate(
        {
            **base,
            "date": day,
            "run_id": f"{day}-1",
            "item_id": f"ai-{number:04d}",
            "url_key": hashlib.sha256(seed.encode("ascii")).hexdigest(),
            "output_digest": hashlib.sha256(f"out-{seed}".encode("ascii")).hexdigest(),
            "scored_at": f"{day}T06:18:02Z",
        }
    )


def an_old_index(state: Path) -> list[EvalRow]:
    """Two measurements on the 4th of each of twenty months, and two more six years back.

    Filed through the real writer, so each day's index is written beside its rows.
    """
    days = [LONG_AGO, *(f"{month}-04" for month in months_back(TODAY, HISTORY_MONTHS))]
    rows: list[EvalRow] = []
    for number, day in enumerate(days):
        held = [a_measurement(day, number * 10 + offset) for offset in range(2)]
        assert seed_scores(state, held, run_id=f"{day}-1") == len(held)
        rows.extend(held)
    return rows


def test_the_committed_declaration_keeps_every_index_day() -> None:
    policy = declared()[NAME]
    assert isinstance(policy, RetentionPolicy)
    assert isinstance(policy.window, ForeverWindow), (
        "the ID task keeps every index day; a bounded window makes old measurements new"
    )
    assert not policy.series, "nothing summarises a month, so the task keeps no series"
    assert policy.owns == [ledger.tree_relpath(LedgerName.SUMMARY_QUALITY_EVALS_INDEX)]


@pytest.mark.parametrize("dry_run", [True, False])
def test_no_index_day_goes_however_old_and_every_measurement_stays_held(
    dry_run: bool, tmp_path: Path
) -> None:
    """Twenty-one index days, the oldest six years back, and the pass selects none of them."""
    state = tmp_path / ledger.STATE_DIRNAME
    rows = an_old_index(state)
    held = writer.recorded_observations(state)
    before = files_under(tmp_path)
    assert len(writer.index_days(state)) == HISTORY_MONTHS + 1, (
        "the fixture holds one index file a day it wrote"
    )

    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=dry_run)

    assert outcome.selected == 0
    assert (outcome.taken, outcome.written, outcome.appended) == ((), (), ())
    assert files_under(tmp_path) == before
    assert writer.recorded_observations(state) == held
    assert seed_scores(state, rows, run_id=f"{TODAY.isoformat()}-9") == 0, (
        "a measurement from an old index day was filed again as new"
    )


def test_the_committed_declaration_settles_each_closed_month_into_one_file() -> None:
    """The folder gained one file a day with no summary, so its fold settles whole months."""
    policy = declared()[NAME]
    assert isinstance(policy, RetentionPolicy)
    assert policy.fold is not None and policy.fold.settles_months, (
        "the ID task's fold settles closed months; without it the folder grows a file a day"
    )


def test_the_tasks_fold_leaves_one_file_a_closed_month_and_every_measurement_held(
    tmp_path: Path,
) -> None:
    """Twenty closed months become twenty files, and the open month's closed day folds alone.

    Called the way the runner calls it, with the committed declaration and the
    folders the runner hands this task. The dedupe reads every ID it read
    before, so not one measurement can be filed again as new.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    rows = an_old_index(state)
    held = writer.recorded_observations(state)
    policy = declared()[NAME]
    assert isinstance(policy, RetentionPolicy) and policy.fold is not None
    *closed, still_open = months_back(TODAY, HISTORY_MONTHS)

    folded = closed_day_fold.run(context_for(NAME, tmp_path, today=TODAY), policy.fold, skip=())

    assert [month.month for month in folded.months] == [LONG_AGO[:7], *closed]
    assert [day.day for day in folded.days] == [f"{still_open}-04"]
    root = ledger.tree_root(state, LedgerName.SUMMARY_QUALITY_EVALS_INDEX)
    for month in (LONG_AGO[:7], *closed):
        assert [path.relative_to(root).as_posix() for path in day_shards.one_month(root, month)] == [
            f"{month[:4]}/{month[5:7]}/{day_shards.SETTLED_NAME}"
        ]
    assert writer.recorded_observations(state) == held
    assert seed_scores(state, rows, run_id=f"{TODAY.isoformat()}-9") == 0, (
        "a measurement from a settled month was filed again as new"
    )


def test_a_window_of_months_takes_a_settled_month_whole_or_leaves_it(tmp_path: Path) -> None:
    """The only window a month's file may sit beside, apart from forever, goes a month at a time.

    The committed window keeps every month. This one keeps three, so the file of
    each settled month before them goes whole, and every file of a month it
    keeps stays where the fold put it.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    an_old_index(state)
    policy = declared()[NAME]
    assert isinstance(policy, RetentionPolicy) and policy.fold is not None
    closed_day_fold.run(context_for(NAME, tmp_path, today=TODAY), policy.fold, skip=())
    root = ledger.tree_root(state, LedgerName.SUMMARY_QUALITY_EVALS_INDEX)
    before = {path.relative_to(root).as_posix() for path in root.rglob("*.csv")}
    window = {"unit": "months", "value": 3}
    first_kept = retention_files.first_kept_month(MonthsWindow.model_validate(window), TODAY)
    assert first_kept is not None

    run_task(NAME, tmp_path, today=TODAY, dry_run=False, window=window)

    after = {path.relative_to(root).as_posix() for path in root.rglob("*.csv")}
    assert after == {kept for kept in before if kept[:4] + "-" + kept[5:7] >= first_kept}
    assert after < before, "the fixture holds no month the window would take, so this proves nothing"
