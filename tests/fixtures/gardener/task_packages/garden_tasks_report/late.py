"""Which report does a task file under a day that is not the wake's?

A real defect, written down: the ledger is the one the declaration appends to,
and the day is yesterday, which is a day an earlier wake already reported on.
"""

from datetime import timedelta

from fixture_report import file_report

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    return file_report(context, producer=__name__, covers=context.today - timedelta(days=1))
