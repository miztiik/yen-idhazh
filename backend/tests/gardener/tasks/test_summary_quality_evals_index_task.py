"""Does gardener retirement leave historical candidate membership untouched?"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Final

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text, seed_scores
from retention._trees import HISTORY_MONTHS, TODAY, months_back

from idhazh import ledger
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.knobs.gardener import DEFAULT_CLOSED_AFTER_DAYS
from idhazh.contracts.ledger_name import DAY_TREES, LedgerName
from idhazh.evals import writer
from idhazh.gardener import closed_day_fold, registry, runner

from ._oracle_tree import files_under
from ._task import declared

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

    Filed through the real writer, so the production batch path builds the lookup.
    """
    days = [LONG_AGO, *(f"{month}-04" for month in months_back(TODAY, HISTORY_MONTHS))]
    rows: list[EvalRow] = []
    for number, day in enumerate(days):
        held = [a_measurement(day, number * 10 + offset) for offset in range(2)]
        assert seed_scores(state, held, run_id=f"{day}-1") == len(held)
        rows.extend(held)
    return rows


def test_the_index_has_no_calendar_task() -> None:
    assert NAME not in declared(), "the observation lookup has no CSV days or months to fold"
    modules = registry.discover()
    assert "summary_quality_evals_index" not in modules
    runner.preflight(declared(), modules)


def test_the_index_is_not_a_csv_segment_or_a_cleanup_target() -> None:
    which = LedgerName.SUMMARY_QUALITY_EVALS_INDEX
    assert which not in DAY_TREES
    with pytest.raises(ValueError, match="not a day tree"):
        ledger.segment_contract(which)
    tasks = declared()
    assert not any(runner.owner_of(name, tasks)(ledger.tree_relpath(which)) for name in tasks)


@pytest.mark.parametrize("dry_run", [True, False])
def test_folding_leaves_every_historical_candidate_and_every_lookup_file_unchanged(
    dry_run: bool, tmp_path: Path
) -> None:
    state = tmp_path / ledger.STATE_DIRNAME
    rows = an_old_index(state)
    candidates = {writer.observation_digest(row.model_dump(mode="json")) for row in rows}
    assert writer.recorded_observations(state, candidates) == candidates
    before = files_under(tmp_path)

    folded = closed_day_fold.fold(
        state,
        DAY_TREES,
        now=datetime.combine(TODAY, time.min, tzinfo=UTC),
        after_days=DEFAULT_CLOSED_AFTER_DAYS,
        dry_run=dry_run,
        settles_months=True,
    )

    assert (folded.days, folded.months) == ((), ())
    assert files_under(tmp_path) == before
    assert writer.recorded_observations(state, candidates) == candidates
    assert seed_scores(state, rows, run_id=f"{TODAY.isoformat()}-9") == 0
