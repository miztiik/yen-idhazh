"""Which score-index days does the scores task take, and what does it never touch?

None, however old. The index is what a run dedupes against, and an observation
key carries no date, so an index day taken would make every measurement in it
new again. Every eval row is kept for ever, so the committed declaration keeps
every month, and a pass over an index older than any window takes nothing, dry
or live. The task's one live action is the fold of its closed days, which
`tests/gardener/test_closed_day_fold.py` holds.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text, seed_scores
from retention._trees import HISTORY_MONTHS, TODAY, months_back

from idhazh import ledger
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.knobs.gardener import ForeverWindow, RetentionPolicy
from idhazh.contracts.ledger_name import LedgerName
from idhazh.evals import writer

from ._oracle_tree import files_under
from ._task import declared, run_task

pytestmark = pytest.mark.contract

NAME: Final = "scores"

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
        "the scores task keeps every index day; a bounded window makes old measurements new"
    )
    assert not policy.series, "nothing summarises a month, so the task keeps no series"
    assert policy.owns == [ledger.tree_relpath(LedgerName.SCORE_INDEX)]


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
