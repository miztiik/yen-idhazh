"""Is the retired index folder outside every gardener task and every day-tree rule?"""

from __future__ import annotations

from typing import Final

import pytest

from idhazh import ledger
from idhazh.contracts.ledger_name import DAY_TREES, LedgerName
from idhazh.gardener import registry, runner, tasks

from ._task import declared

pytestmark = pytest.mark.contract

NAME: Final = "summary-quality-evals-index"


def test_the_index_has_no_calendar_task() -> None:
    assert NAME not in declared(), "the observation lookup has no CSV days or months to fold"
    modules = registry.discover(tasks, declared())
    assert "summary_quality_evals_index" not in modules
    runner.preflight(declared(), modules)


def test_the_index_is_not_a_csv_segment_or_a_cleanup_target() -> None:
    which = LedgerName.SUMMARY_QUALITY_EVALS_INDEX
    assert which not in DAY_TREES
    with pytest.raises(ValueError, match="not a day tree"):
        ledger.segment_contract(which)
    tasks = declared()
    assert not any(runner.owner_of(name, tasks)(ledger.tree_relpath(which)) for name in tasks)
