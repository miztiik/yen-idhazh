"""Which span-rollup files does the span-rollup task take, and what does it never touch?

None yet. Its window is `forever`, because nobody has said how long a span total
is wanted, so a month of any age stays, dry or live. The task's one live action
is the fold of its closed days, which `tests/gardener/test_closed_day_fold.py`
holds. No pass of the old cleanup ever took these files, so there is no record
to hold the task to either: a window that bounds it owes a test here of what it
takes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest
from conftest import seed_host_fingerprint
from retention._trees import HISTORY_MONTHS, TODAY, months_back

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.knobs.gardener import ForeverWindow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.span_rollup import RollupSpan, SpanRollupRow

from ._oracle_tree import files_under
from ._task import declared, run_task

pytestmark = pytest.mark.contract

NAME: Final = "span-rollup"


def keeps_every_month() -> None:
    assert isinstance(declared()[NAME].window, ForeverWindow), (
        "span-rollup keeps every month; a bounded window owes a test here of what it takes"
    )


def span_rollup_history(state: Path, months: list[str]) -> None:
    """One work shard's span total on the 11th of each month, filed by the ledger's own writer."""
    for month in months:
        day = f"{month}-11"
        ledger.write_segment(
            state,
            LedgerName.SPAN_ROLLUP,
            [
                SpanRollupRow(
                    version=SpanRollupRow.schema_version(),
                    date=day,
                    run_id=f"{day}-1",
                    shard=0,
                    span_name=RollupSpan.ITEM,
                    count=1,
                    total_ms=700,
                )
            ],
            run_id=f"{day}-1",
            attempt=1,
            job=ServerJob.WORK,
            shard=0,
        )


def a_machine_in(state: Path, month: str) -> None:
    """One machine on the 11th of `month`, filed through the ledger door by its job's writer."""
    day = f"{month}-11"
    seed_host_fingerprint(
        state,
        [
            HostFingerprintRow(
                version=HostFingerprintRow.schema_version(),
                date=day,
                run_id=f"{day}-1",
                shard=0,
                cpu_model="AMD EPYC 7763 64-Core Processor",
            )
        ],
    )


@pytest.mark.parametrize("dry_run", [True, False])
def test_no_month_goes_however_old_and_no_other_ledger_is_touched(
    dry_run: bool, tmp_path: Path
) -> None:
    """Twenty months of span totals stay, and so does a machine file from the oldest of them."""
    keeps_every_month()
    state = tmp_path / ledger.STATE_DIRNAME
    months = months_back(TODAY, HISTORY_MONTHS)
    span_rollup_history(state, months)
    a_machine_in(state, months[0])
    before = files_under(tmp_path)
    assert len(before) == len(months) + 1, "the tree holds one file a month and one machine file"

    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=dry_run)

    assert (outcome.taken, outcome.written, outcome.appended) == ((), (), ())
    assert files_under(tmp_path) == before
