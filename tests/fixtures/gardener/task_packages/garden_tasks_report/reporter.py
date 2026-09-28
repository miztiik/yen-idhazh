"""Which report does a task file into the ledger its declaration appends to, under today?"""

from fixture_report import file_report

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    return file_report(context, producer=__name__, covers=context.today)
