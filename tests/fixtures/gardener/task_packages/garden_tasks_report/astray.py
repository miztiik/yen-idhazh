"""Which report does a task file into a ledger its declaration never names?

A real defect, written down: the report is a well-formed file of a real ledger
under today, and the declaration appends to nothing, which is what the runner's
append check exists to stop before anything is staged.
"""

from fixture_report import file_report

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    return file_report(context, producer=__name__, covers=context.today)
